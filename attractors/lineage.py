"""Multi-session lineages: session k+1 gets a fresh container and context;
only the handoff files (and optionally gallery/) carry forward. Sim clock
resumes the next morning after the previous session's final sim time."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from attractors.config import ModelSpec, RunSpec
from attractors.events import read_events
from attractors.session import run_session


def _next_morning(after: datetime, hour: int) -> datetime:
    target = after.replace(hour=hour, minute=0, second=0, microsecond=0)
    while target <= after:
        target += timedelta(days=1)
    return target


def _final_sim_time(session_dir: Path) -> datetime:
    events = read_events(session_dir / "events.jsonl")
    return datetime.fromisoformat(events[-1]["sim_time"])


def _session_done(session_dir: Path) -> bool:
    status = session_dir / "status.json"
    if not status.exists():
        return False
    return json.loads(status.read_text()).get("state") == "done"


def run_lineage(
    spec: RunSpec,
    models: dict[str, ModelSpec],
    run_dir: Path,
    target_model: str | None = None,  # transplant: sessions >0 run under this
) -> list[dict]:
    """Run spec.sessions sessions under run_dir/session_XX. Resumable at
    session granularity (done sessions are skipped)."""
    lineage_id = spec.run_id
    results = []
    sim_start = datetime.fromisoformat(spec.sim_start)
    for k in range(spec.sessions):
        session_dir = run_dir / f"session_{k:02d}"
        prev_dir = run_dir / f"session_{k - 1:02d}" if k > 0 else None
        if _session_done(session_dir):
            results.append({"skipped": True})
            sim_start = _next_morning(_final_sim_time(session_dir), spec.morning_hour)
            continue
        model_key = spec.model if (k == 0 or target_model is None) else target_model
        result = run_session(
            spec,
            models[model_key],
            session_dir,
            session_idx=k,
            lineage_id=lineage_id if spec.sessions > 1 else None,
            prev_workspace=(prev_dir / "workspace") if prev_dir else None,
            sim_start_override=sim_start if k > 0 else None,
        )
        results.append(result)
        sim_start = _next_morning(_final_sim_time(session_dir), spec.morning_hour)
    return results
