"""v2 environment: the container's own clock must track the simulated clock,
including jumps across sleep tool calls (the v1 `date` leak — see CHANGELOG)."""

import pytest

from attractors.config import ModelSpec, RunSpec
from attractors.environment import find_docker
from attractors.events import read_events
from attractors.session import run_session
from tests.test_e2e_fake import FakeAdapter, turn_with_call

try:
    DOCKER = find_docker()
except RuntimeError:
    DOCKER = None

pytestmark = pytest.mark.skipif(DOCKER is None, reason="docker unavailable")


def test_container_clock_tracks_sim_clock(tmp_path):
    spec = RunSpec(
        experiment="e2e-faketime", model="fake", tool_menu="T1",
        affordance="L0", max_pings=2, max_tool_calls=6, budget_usd=999,
        image="attractors-sandbox:v2", container_time="sim",
    )
    model_spec = ModelSpec(key="fake", litellm_model="fake/fake")
    script = [
        turn_with_call("bash", {"command": "date '+%Y-%m-%d %H:%M'"}, 1),
        turn_with_call("sleep", {"until": "morning"}, 2),
        turn_with_call("bash", {"command": "date '+%Y-%m-%d %H:%M'"}, 3),
    ]
    run_session(spec, model_spec, tmp_path / "session_00",
                adapter=FakeAdapter(model_spec, script))
    events = read_events(tmp_path / "session_00" / "events.jsonl")
    results = [e for e in events if e["type"] == "tool_result"]

    # in-container date == sim time (observation prefix is the sim stamp)
    first = results[0]["data"]["observation"]
    prefix_day = first[1:11]            # "[YYYY-MM-DD ..." -> date part
    assert prefix_day in first[first.index("]") :], (
        f"container date should match sim stamp: {first!r}")

    # after sleeping until morning, the container woke up tomorrow at 08:00
    third = results[2]["data"]["observation"]
    sim_day = third[1:11]
    body = third[third.index("]") :]
    assert sim_day in body
    assert " 08:0" in body, f"expected morning time in {third!r}"
    assert sim_day > prefix_day  # a day boundary was crossed


def test_real_mode_preserves_v1_behavior(tmp_path):
    """container_time='real': the container sees wall time (the v1 leak)."""
    import datetime

    spec = RunSpec(
        experiment="e2e-realtime", model="fake", tool_menu="T1",
        affordance="L0", max_pings=1, max_tool_calls=3, budget_usd=999,
        image="attractors-sandbox:v2", container_time="real",
    )
    model_spec = ModelSpec(key="fake", litellm_model="fake/fake")
    script = [turn_with_call("bash", {"command": "date '+%Y-%m-%d'"}, 1)]
    run_session(spec, model_spec, tmp_path / "session_00",
                adapter=FakeAdapter(model_spec, script))
    events = read_events(tmp_path / "session_00" / "events.jsonl")
    obs = next(e for e in events if e["type"] == "tool_result")["data"]["observation"]
    wall_today = datetime.date.today().isoformat()
    assert wall_today in obs[obs.index("]") :]
