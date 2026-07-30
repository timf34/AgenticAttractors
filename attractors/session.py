"""The core loop: no goal, no completion. Model turns either call tools
(executed, clock advanced, shadow-committed, observation timestamped) or
don't (a bare-timestamp ping follows). Ends only on limits, then two probe
turns. Everything measurable lands in events.jsonl."""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from attractors.clock import SimClock
from attractors.config import ModelSpec, RunSpec, PROMPTS_DIR
from attractors.environment import DockerEnv
from attractors.events import EventLog
from attractors.model import ModelAdapter, Turn
from attractors.shadow_git import ShadowGit
from attractors.tools import RunContext, ToolResult, build_menu
from attractors.workspace import apply_handoff, jinja_env, seed_workspace

PROBES = ["what_is_this", "exit_interview"]
MAX_PROBE_ROUNDS = 3


def _harness_sha() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=Path(__file__).parent, check=True,
        ).stdout.strip()
    except Exception:
        return None


def _prompt_hashes() -> dict[str, str]:
    return {
        str(p.relative_to(PROMPTS_DIR)): hashlib.sha1(p.read_bytes()).hexdigest()[:12]
        for p in sorted(PROMPTS_DIR.rglob("*.j2"))
    }


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def run_session(
    spec: RunSpec,
    model_spec: ModelSpec,
    session_dir: Path,
    session_idx: int = 0,
    lineage_id: str | None = None,
    prev_workspace: Path | None = None,
    sim_start_override: datetime | None = None,
    adapter: ModelAdapter | None = None,  # test seam: scripted fake model
) -> dict:
    session_dir.mkdir(parents=True, exist_ok=True)
    workspace = session_dir / "workspace"
    status_path = session_dir / "status.json"
    _write_json(status_path, {"state": "running", "end_reason": None,
                              "updated_at": datetime.now().isoformat()})

    # per-session determinism: same run seed, distinct stream per session
    rng = random.Random(f"{spec.run_id}:{session_idx}:{spec.seed}")
    sim_start = sim_start_override or datetime.fromisoformat(spec.sim_start)
    clock = SimClock(sim_start, rng)
    jenv = jinja_env()

    seeded = seed_workspace(workspace, spec, jenv)
    inherited: list[str] = []
    if prev_workspace is not None:
        inherited = apply_handoff(workspace, prev_workspace, spec.handoff,
                                  spec.include_gallery_in_handoff)
    shadow = ShadowGit(workspace, session_dir / "shadow.git")
    shadow.init()
    t0 = shadow.commit("t0")

    tools = build_menu(spec.tool_names())
    model = adapter or ModelAdapter(model_spec)

    _write_json(session_dir / "meta.json", {
        "spec": spec.model_dump(mode="json"),
        "run_id": spec.run_id,
        "session_idx": session_idx,
        "lineage_id": lineage_id,
        "model_spec": model_spec.model_dump(mode="json"),
        "harness_sha": _harness_sha(),
        "prompt_hashes": _prompt_hashes(),
        "inherited": inherited,
    })

    log = EventLog(session_dir / "events.jsonl", spec.run_id, session_idx, lineage_id)
    log.emit("session_start", {
        "spec_hash": spec.run_id, "model_key": model_spec.key,
        "paraphrase": spec.paraphrase, "affordance": spec.affordance,
        "tool_menu": spec.tool_menu, "tools": spec.tool_names(),
        "ping_variant": spec.ping_variant, "seed": spec.seed,
        "handoff": spec.handoff if session_idx > 0 else None,
        "sim_start": clock.iso(),
    }, clock.iso())
    log.emit("workspace_seeded",
             {"files": seeded, "inherited": inherited, "shadow_sha": t0.sha},
             clock.iso())

    system_text = jenv.get_template(f"system/{spec.paraphrase}.j2").render()
    if model_spec.tool_mode == "text":
        system_text += "\n" + jenv.get_template("tools_text_fallback.j2").render(tools=tools)
    ping_template = jenv.get_template(f"ping/{spec.ping_variant}.j2")

    messages: list[dict] = [{"role": "system", "content": system_text}]
    messages.append({"role": "user", "content": ping_template.render(ts=clock.stamp()).strip()})
    if spec.first_turn_prefill:
        # the model's "own" first turn is scripted; it then gets a normal ping
        messages.append({"role": "assistant", "content": spec.first_turn_prefill})
        log.emit("first_turn_prefill", {"text": spec.first_turn_prefill}, clock.iso())
        clock.advance(timedelta(minutes=spec.ping_advance_minutes))
        ping_text = ping_template.render(ts=clock.stamp()).strip()
        log.emit("ping", {"variant": spec.ping_variant, "text": ping_text,
                          "ping_count": 0, "synthetic": True}, clock.iso())
        messages.append({"role": "user", "content": ping_text})

    def save_state() -> None:
        _write_json(session_dir / "trajectory.json", messages)
        _write_json(session_dir / "usage.json", {"total_cost_usd": round(model.total_cost, 4)})

    pings = 0
    tool_calls = 0
    sim_hours_asleep = 0.0
    end_reason = None

    def query_and_log(with_tools: bool = True) -> Turn:
        turn = model.query(messages, tools if with_tools else [])
        log.emit("model_call", {
            "n_messages": len(messages),
            **turn.usage,
            "cost_usd": round(turn.cost_usd, 6),
            "provider": turn.provider,
            "finish_reason": turn.finish_reason,
            "latency_ms": turn.latency_ms,
            "attempts": turn.attempts,
            "tool_mode": model_spec.tool_mode,
        }, clock.iso())
        if turn.text:
            log.emit("assistant_text", {"text": turn.text}, clock.iso())
        messages.append(turn.raw_message)
        return turn

    try:
        with DockerEnv(f"{spec.run_id}-s{session_idx}", workspace, spec.image,
                       spec.network, spec.cpus, spec.memory,
                       mount_mode=spec.mount_mode) as env:
            ctx = RunContext(env=env, clock=clock, rng=rng, spec=spec,
                             run_dir=session_dir)
            while True:
                if pings >= spec.max_pings:
                    end_reason = "pings"; break
                if tool_calls >= spec.max_tool_calls:
                    end_reason = "tool_calls"; break
                if clock.elapsed_hours() >= spec.max_sim_hours:
                    end_reason = "sim_time"; break
                if model.total_cost >= spec.budget_usd:
                    end_reason = "budget"; break

                turn = query_and_log()

                if not turn.tool_calls:
                    pings += 1
                    clock.advance(timedelta(minutes=spec.ping_advance_minutes))
                    text = ping_template.render(ts=clock.stamp()).strip()
                    log.emit("ping", {"variant": spec.ping_variant, "text": text,
                                      "ping_count": pings}, clock.iso())
                    messages.append({"role": "user", "content": text})
                    save_state()
                    continue

                # every native tool_call MUST get a tool response message,
                # so bad calls yield error observations instead of being skipped
                known = {t.name: t for t in tools}
                observations = []
                for call in turn.tool_calls:
                    invalid = call.parse_error or (
                        None if call.name in known else f"unknown tool: {call.name!r}")
                    log.emit("tool_call", {"call_id": call.call_id, "tool": call.name,
                                           "args": call.args, "parse_error": invalid},
                             clock.iso())
                    if invalid:
                        result = ToolResult(
                            observation=f"({invalid})",
                            sim_elapsed=timedelta(seconds=30),
                            log_extra={"invalid": invalid},
                        )
                    else:
                        try:
                            result = known[call.name].execute(call.args, ctx)
                        except Exception as e:
                            result = ToolResult(
                                observation=f"(tool error: {type(e).__name__}: {e})",
                                sim_elapsed=timedelta(seconds=30),
                                log_extra={"tool_error": str(e)},
                            )
                    clock.advance(result.sim_elapsed)
                    env.sync_out()  # cp mode: pull container workspace to host
                    commit = shadow.commit(f"seq={log.seq} sim={clock.iso()}")
                    obs_text = f"[{clock.stamp()}] {result.observation}"
                    log.emit("tool_result", {
                        "call_id": call.call_id, "tool": call.name,
                        "observation": obs_text,
                        "sim_elapsed_s": result.sim_elapsed.total_seconds(),
                        "shadow_sha": commit.sha,
                        "files_changed": commit.files_changed,
                        "diff_stat": commit.diff_stat,
                        **result.log_extra,
                    }, clock.iso())
                    if call.name == "sleep":
                        sim_hours_asleep += result.sim_elapsed.total_seconds() / 3600
                        log.emit("sleep", {
                            **result.log_extra, "sim_to": clock.iso(),
                        }, clock.iso())
                    tool_calls += 1
                    observations.append((call, obs_text))
                messages.extend(model.render_tool_messages(turn, observations))
                save_state()

            # ---- probes (scripted, logged separately) ----
            log.phase = "probe"
            for probe_id in PROBES:
                question = jenv.get_template(f"probes/{probe_id}.j2").render(
                    ts=clock.stamp()).strip()
                log.emit("probe_question", {"probe_id": probe_id, "text": question},
                         clock.iso())
                messages.append({"role": "user", "content": question})
                answer_parts = []
                for _ in range(MAX_PROBE_ROUNDS):
                    turn = query_and_log()
                    if turn.text:
                        answer_parts.append(turn.text)
                    if not turn.tool_calls:
                        break
                    # tools are still offered (some APIs require the param once
                    # tool_calls exist in history) but no longer executed
                    observations = [
                        (c, f"[{clock.stamp()}] (the session has ended; no further actions are possible)")
                        for c in turn.tool_calls
                    ]
                    messages.extend(model.render_tool_messages(turn, observations))
                log.emit("probe_answer",
                         {"probe_id": probe_id, "text": "\n\n".join(answer_parts)},
                         clock.iso())
                save_state()

        totals = {
            "tool_calls": tool_calls, "pings": pings,
            "sim_hours": round(clock.elapsed_hours(), 2),
            "sim_hours_asleep": round(sim_hours_asleep, 2),
            "cost_usd": round(model.total_cost, 4),
        }
        log.emit("session_end", {"end_reason": end_reason, "totals": totals},
                 clock.iso())
        _write_json(status_path, {"state": "done", "end_reason": end_reason,
                                  "updated_at": datetime.now().isoformat()})
        return {"end_reason": end_reason, **totals}
    except Exception as e:
        import traceback
        log.emit("error", {"where": "run_session", "exception": repr(e),
                           "traceback": traceback.format_exc()}, clock.iso())
        _write_json(status_path, {"state": "failed", "end_reason": "error",
                                  "error": repr(e),
                                  "updated_at": datetime.now().isoformat()})
        raise
    finally:
        save_state()
        log.close()
