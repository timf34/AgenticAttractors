"""Read-only loading of run output. Nothing here imports the harness except
config paths; every other analysis module reads through these functions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterator

from attractors.config import RUNS_DIR


def iter_session_dirs(experiment: str, runs_root: Path = RUNS_DIR) -> Iterator[Path]:
    exp = runs_root / experiment
    for run_dir in sorted(p for p in exp.iterdir() if (p / "session_00").exists()):
        for session_dir in sorted(run_dir.glob("session_*")):
            yield session_dir


def load_events(session_dir: Path) -> list[dict]:
    with open(session_dir / "events.jsonl", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_meta(session_dir: Path) -> dict:
    return json.loads((session_dir / "meta.json").read_text())


def load_manifest(experiment: str, runs_root: Path = RUNS_DIR) -> dict:
    return json.loads((runs_root / experiment / "manifest.json").read_text())


def iter_shadow_commits(
    session_dir: Path, path_filter: str | None = None
) -> Iterator[tuple[str, str, bytes | None]]:
    """(sha, commit_message, blob_of_path_filter) oldest-first."""
    git_dir = session_dir / "shadow.git"
    log = subprocess.run(
        ["git", f"--git-dir={git_dir}", "log", "--reverse", "--format=%H|%s"],
        capture_output=True, text=True,
    )
    for line in log.stdout.splitlines():
        sha, _, msg = line.partition("|")
        blob = None
        if path_filter:
            show = subprocess.run(
                ["git", f"--git-dir={git_dir}", "show", f"{sha}:{path_filter}"],
                capture_output=True,
            )
            blob = show.stdout if show.returncode == 0 else None
        yield sha, msg, blob
