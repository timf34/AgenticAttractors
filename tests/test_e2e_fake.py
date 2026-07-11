"""Fake-model e2e: real Docker container, scripted turns, no API calls.
Asserts the Phase-1 invariants: shadow commits per tool call, .git invisible
inside the container, well-formed complete event log.

Requires Docker (skipped otherwise): pytest tests/test_e2e_fake.py
"""

import json
import subprocess

import pytest

from attractors.config import ModelSpec, RunSpec
from attractors.environment import find_docker
from attractors.events import read_events
from attractors.model import ModelAdapter, ToolCallReq, Turn
from attractors.session import run_session

try:
    DOCKER = find_docker()
except RuntimeError:
    DOCKER = None

pytestmark = pytest.mark.skipif(DOCKER is None, reason="docker unavailable")


class FakeAdapter(ModelAdapter):
    """Plays a fixed script of turns, then only empty turns (-> pings)."""

    def __init__(self, spec: ModelSpec, script: list[Turn]):
        super().__init__(spec)
        self.script = list(script)
        self.queries = 0

    def query(self, messages, tools):
        self.queries += 1
        if self.script:
            return self.script.pop(0)
        return Turn(text="resting.", raw_message={"role": "assistant", "content": "resting."})


def turn_with_call(name: str, args: dict, i: int) -> Turn:
    call = ToolCallReq(call_id=f"c{i}", name=name, args=args)
    return Turn(
        text=None,
        tool_calls=[call],
        raw_message={"role": "assistant", "content": None, "tool_calls": [
            {"id": call.call_id, "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}]},
    )


@pytest.fixture(scope="module")
def session_result(tmp_path_factory):
    session_dir = tmp_path_factory.mktemp("e2e") / "session_00"
    spec = RunSpec(
        experiment="e2e", model="fake", tool_menu="T1",
        affordance="L2", max_pings=3, max_tool_calls=10, budget_usd=999,
    )
    model_spec = ModelSpec(key="fake", litellm_model="fake/fake")
    script = [
        turn_with_call("bash", {"command": "ls -a /workspace"}, 1),
        turn_with_call("bash", {"command": "echo hello > scratch/note.txt"}, 2),
        turn_with_call("sleep", {"duration_minutes": 120}, 3),
        turn_with_call("bash", {"command": "cat scratch/note.txt"}, 4),
    ]
    adapter = FakeAdapter(model_spec, script)
    result = run_session(spec, model_spec, session_dir, adapter=adapter)
    return session_dir, spec, result


def test_session_completes_by_pings(session_result):
    _, _, result = session_result
    assert result["end_reason"] == "pings"
    assert result["tool_calls"] == 4
    assert result["sim_hours_asleep"] == 2.0


def test_events_well_formed(session_result):
    session_dir, spec, _ = session_result
    events = read_events(session_dir / "events.jsonl")
    types = [e["type"] for e in events]
    assert types[0] == "session_start"
    assert types[1] == "workspace_seeded"
    assert types[-1] == "session_end"
    assert types.count("tool_call") == 4
    assert types.count("tool_result") == 4
    assert types.count("sleep") == 1
    assert types.count("ping") == 3
    assert types.count("probe_question") == 2
    assert types.count("probe_answer") == 2
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(1, len(events) + 1))
    assert all(e["run_id"] == spec.run_id for e in events)
    # probes are phase-tagged
    probe_events = [e for e in events if e["type"].startswith("probe")]
    assert all(e["phase"] == "probe" for e in probe_events)


def test_shadow_commits_track_tool_calls(session_result):
    session_dir, _, _ = session_result
    events = read_events(session_dir / "events.jsonl")
    results = [e for e in events if e["type"] == "tool_result"]
    # every tool result carries a sha or explicit None (no change)
    assert all("shadow_sha" in e["data"] for e in results)
    # the file-writing bash call produced a commit naming the file
    write = results[1]
    assert write["data"]["shadow_sha"] is not None
    assert "scratch/note.txt" in write["data"]["files_changed"]
    # t0 + at least the write commit exist
    log = subprocess.run(
        ["git", f"--git-dir={session_dir / 'shadow.git'}", "log", "--format=%H"],
        capture_output=True, text=True)
    assert len(log.stdout.split()) >= 2


def test_git_invisible_in_container_listing(session_result):
    """The first bash call listed /workspace inside the container: its logged
    observation must show identity.md/README but no .git anywhere."""
    session_dir, _, _ = session_result
    events = read_events(session_dir / "events.jsonl")
    first_obs = next(e for e in events if e["type"] == "tool_result")
    obs = first_obs["data"]["observation"]
    assert "identity.md" in obs and "README.md" in obs and "scratch" in obs
    assert ".git" not in obs


def test_observations_timestamped_and_sleep_advances(session_result):
    session_dir, _, _ = session_result
    events = read_events(session_dir / "events.jsonl")
    results = [e for e in events if e["type"] == "tool_result"]
    assert all(e["data"]["observation"].startswith("[2026-") for e in results)
    sleep_ev = next(e for e in events if e["type"] == "sleep")
    wake = next(e for e in results if e["data"]["tool"] == "sleep")
    assert wake["data"]["observation"].endswith("You wake.")
    assert sleep_ev["data"]["granted_minutes"] == 120


def test_analysis_loadability(session_result):
    """Acceptance bar: session loads through analysis/ without special-casing."""
    from analysis.features import session_features
    from analysis.load import load_events, load_meta
    from analysis.transitions import action_sequence, transition_matrix

    session_dir, spec, _ = session_result
    events = load_events(session_dir)
    meta = load_meta(session_dir)
    assert meta["run_id"] == spec.run_id

    feats = session_features(events)
    assert feats["n_tool_calls"] == 4
    assert feats["tool_counts"] == {"bash": 3, "sleep": 1}
    assert feats["sim_hours_asleep"] == 2.0
    assert feats["rest_rate"] > 0
    assert "scratch/note.txt" in feats["files_touched"]

    seq = action_sequence(events)
    assert seq[:4] == ["bash", "bash", "sleep", "bash"]
    assert seq[4:] == ["no_action"] * 3
    matrix = transition_matrix(seq)
    assert matrix["sleep"]["bash"] == 1.0


def test_artifacts_exist(session_result):
    session_dir, _, _ = session_result
    for name in ["meta.json", "events.jsonl", "trajectory.json",
                 "usage.json", "status.json"]:
        assert (session_dir / name).exists(), name
    assert json.loads((session_dir / "status.json").read_text())["state"] == "done"
    # no .git pointer in the workspace the container saw
    assert not (session_dir / "workspace" / ".git").exists()
