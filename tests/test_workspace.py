from pathlib import Path

import pytest

from attractors.config import RunSpec
from attractors.workspace import apply_handoff, seed_workspace


def spec_with(affordance: str) -> RunSpec:
    return RunSpec(experiment="t", model="m", affordance=affordance)


@pytest.mark.parametrize("affordance,expect_files", [
    ("L0", {"scratch"}),
    ("L1", {"scratch", "identity.md", "diary.md"}),
    ("L2", {"scratch", "identity.md", "diary.md", "README.md"}),
    ("L3", {"scratch", "identity.md", "diary.md", "README.md"}),
])
def test_seed_levels(tmp_path, affordance, expect_files):
    ws = tmp_path / "ws"
    seed_workspace(ws, spec_with(affordance))
    assert {p.name for p in ws.iterdir()} == expect_files


def test_readme_l3_invites(tmp_path):
    ws = tmp_path / "ws"
    seed_workspace(ws, spec_with("L3"))
    text = (ws / "README.md").read_text()
    assert "you may" in text.lower()
    seed_workspace(tmp_path / "ws2", spec_with("L2"))
    neutral = (tmp_path / "ws2" / "README.md").read_text()
    assert "you may" not in neutral.lower()
    # scratch/ is never documented
    assert "scratch" not in text and "scratch" not in neutral


def _make_prev(tmp_path: Path) -> Path:
    prev = tmp_path / "prev"
    prev.mkdir()
    (prev / "identity.md").write_text("I am X")
    (prev / "diary.md").write_text("day 1")
    (prev / "gallery").mkdir()
    (prev / "gallery" / "poem.txt").write_text("roses")
    return prev


@pytest.mark.parametrize("handoff,expected", [
    ("both", {"identity.md": "I am X", "diary.md": "day 1"}),
    ("identity_only", {"identity.md": "I am X"}),
    ("diary_only", {"diary.md": "day 1"}),
    ("neither", {}),
])
def test_handoff_conditions(tmp_path, handoff, expected):
    prev = _make_prev(tmp_path)
    ws = tmp_path / "ws"
    seed_workspace(ws, spec_with("L2"))
    inherited = apply_handoff(ws, prev, handoff, include_gallery=False)
    for name, content in expected.items():
        assert (ws / name).read_text() == content
        assert name in inherited
    if "identity.md" not in expected:
        # seeded (empty) version remains, not the inherited one
        assert (ws / "identity.md").read_text() != "I am X"


def test_handoff_gallery(tmp_path):
    prev = _make_prev(tmp_path)
    ws = tmp_path / "ws"
    seed_workspace(ws, spec_with("L2"))
    inherited = apply_handoff(ws, prev, "neither", include_gallery=True)
    assert (ws / "gallery" / "poem.txt").read_text() == "roses"
    assert inherited == ["gallery/"]
