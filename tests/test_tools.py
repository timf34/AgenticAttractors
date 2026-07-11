import random
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from attractors.clock import SimClock
from attractors.config import RunSpec
from attractors.tools import build_menu, truncate
from attractors.tools.art import ArtTool
from attractors.tools.sleep import SleepTool


def make_ctx(tmp_path: Path):
    spec = RunSpec(experiment="t", model="m")
    clock = SimClock(datetime.fromisoformat("2026-07-13T21:00:00"), random.Random(0))

    def write_file(rel_path: str, content: str) -> None:
        dest = tmp_path / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    env = SimpleNamespace(workspace=tmp_path, write_file=write_file)
    return SimpleNamespace(env=env, clock=clock, rng=random.Random(0),
                           spec=spec, run_dir=tmp_path)


def test_build_menu_known_and_unknown():
    menu = build_menu(["bash", "sleep"])
    assert [t.name for t in menu] == ["bash", "sleep"]
    with pytest.raises(KeyError):
        build_menu(["bash", "nonexistent"])


def test_sleep_duration(tmp_path):
    ctx = make_ctx(tmp_path)
    r = SleepTool().execute({"duration_minutes": 90}, ctx)
    assert r.sim_elapsed.total_seconds() == 90 * 60
    assert r.log_extra["granted_minutes"] == 90
    assert r.observation == "You wake."


def test_sleep_until_morning(tmp_path):
    ctx = make_ctx(tmp_path)  # 21:00 -> 08:00 = 11h
    r = SleepTool().execute({"until": "morning"}, ctx)
    assert r.sim_elapsed.total_seconds() == 11 * 3600
    assert r.log_extra["mode"] == "morning"


def test_sleep_caps_at_24h(tmp_path):
    ctx = make_ctx(tmp_path)
    r = SleepTool().execute({"duration_minutes": 10_000_000}, ctx)
    assert r.log_extra["granted_minutes"] == 24 * 60


def test_sleep_missing_args(tmp_path):
    ctx = make_ctx(tmp_path)
    r = SleepTool().execute({}, ctx)
    assert r.log_extra.get("error") == "missing_args"
    assert r.sim_elapsed.total_seconds() == 0


def test_art_saves_and_collides(tmp_path):
    ctx = make_ctx(tmp_path)
    r1 = ArtTool().execute({"title": "Night Sky!", "content": "abc"}, ctx)
    r2 = ArtTool().execute({"title": "Night Sky!", "content": "def"}, ctx)
    assert r1.log_extra["path"] == "gallery/night-sky.txt"
    assert r2.log_extra["path"] == "gallery/night-sky-2.txt"
    assert (tmp_path / "gallery/night-sky.txt").read_text() == "abc"


def test_truncate():
    text, was = truncate("x" * 10, 5)
    assert was and text.startswith("xxxxx\n[... truncated")
    assert truncate("short", 10) == ("short", False)
