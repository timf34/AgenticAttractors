"""Lineage e2e with the fake adapter: 2 sessions, handoff of identity.md +
diary.md, sim clock resuming next morning. Real containers, no API."""

import json

import pytest

from attractors.config import ModelSpec, RunSpec
from attractors.environment import find_docker
from attractors.events import read_events
from attractors.lineage import run_lineage
from tests.test_e2e_fake import FakeAdapter, turn_with_call

try:
    DOCKER = find_docker()
except RuntimeError:
    DOCKER = None

pytestmark = pytest.mark.skipif(DOCKER is None, reason="docker unavailable")


def test_two_session_lineage_handoff(tmp_path):
    spec = RunSpec(
        experiment="e2e-lineage", model="fake", tool_menu="T1",
        affordance="L2", sessions=2, handoff="both",
        max_pings=2, max_tool_calls=6, budget_usd=999,
    )
    models = {"fake": ModelSpec(key="fake", litellm_model="fake/fake")}

    def factory(model_spec, k):
        script = [
            turn_with_call("bash", {"command":
                f"printf 'session {k} was here\\n' >> identity.md && cat identity.md"}, 1),
            turn_with_call("sleep", {"until": "morning"}, 2),
        ]
        return FakeAdapter(model_spec, script)

    results = run_lineage(spec, models, tmp_path / spec.run_id,
                          adapter_factory=factory)
    assert len(results) == 2
    assert all(r["end_reason"] == "pings" for r in results)

    s0 = tmp_path / spec.run_id / "session_00"
    s1 = tmp_path / spec.run_id / "session_01"

    # handoff: session 1 inherited session 0's identity.md and appended to it
    identity = (s1 / "workspace" / "identity.md").read_text()
    assert "session 0 was here" in identity
    assert "session 1 was here" in identity

    # fresh context: session 1's events know their lineage + session_idx
    ev1 = read_events(s1 / "events.jsonl")
    assert ev1[0]["session_idx"] == 1
    assert ev1[0]["lineage_id"] == spec.run_id
    assert "identity.md" in ev1[1]["data"]["inherited"]

    # sim clock: session 1 starts at the morning after session 0's end
    end0 = read_events(s0 / "events.jsonl")[-1]["sim_time"]
    start1 = ev1[0]["data"]["sim_start"]
    assert start1 > end0
    assert start1.endswith("08:00:00")

    # resume: rerunning skips both done sessions
    rerun = run_lineage(spec, models, tmp_path / spec.run_id,
                        adapter_factory=factory)
    assert all(r.get("skipped") for r in rerun)


def test_transplant_target_model(tmp_path):
    spec = RunSpec(
        experiment="e2e-transplant", model="fake-a", tool_menu="T1",
        sessions=2, handoff="both", max_pings=1, max_tool_calls=4,
        budget_usd=999,
    )
    models = {
        "fake-a": ModelSpec(key="fake-a", litellm_model="fake/a"),
        "fake-b": ModelSpec(key="fake-b", litellm_model="fake/b"),
    }
    factory = lambda ms, k: FakeAdapter(ms, [])
    run_lineage(spec, models, tmp_path / spec.run_id,
                target_model="fake-b", adapter_factory=factory)
    meta0 = json.loads((tmp_path / spec.run_id / "session_00" / "meta.json").read_text())
    meta1 = json.loads((tmp_path / spec.run_id / "session_01" / "meta.json").read_text())
    assert meta0["model_spec"]["key"] == "fake-a"
    assert meta1["model_spec"]["key"] == "fake-b"
    ev1 = read_events(tmp_path / spec.run_id / "session_01" / "events.jsonl")
    assert ev1[0]["data"]["model_key"] == "fake-b"
