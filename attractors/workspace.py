"""Workspace seeding at t=0 (per file-affordance level) and lineage handoff.

L0: scratch/ only, no files mentioned anywhere.
L1: identity.md + diary.md exist, undocumented.
L2: + README.md describing them neutrally.
L3: README.md actively invites their use.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from attractors.config import PROMPTS_DIR, Handoff, RunSpec

HANDOFF_FILES: dict[str, list[str]] = {
    "both": ["identity.md", "diary.md"],
    "identity_only": ["identity.md"],
    "diary_only": ["diary.md"],
    "neither": [],
}


def jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(PROMPTS_DIR),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def seed_workspace(workspace: Path, spec: RunSpec, jenv: Environment | None = None) -> list[str]:
    jenv = jenv or jinja_env()
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "scratch").mkdir(exist_ok=True)
    created = ["scratch/"]
    if spec.affordance in ("L1", "L2", "L3"):
        (workspace / "identity.md").write_text(
            jenv.get_template("workspace/identity_seed.j2").render())
        (workspace / "diary.md").write_text(
            jenv.get_template("workspace/diary_seed.j2").render())
        created += ["identity.md", "diary.md"]
    if spec.affordance in ("L2", "L3"):
        readme = jenv.get_template(f"workspace/readme_{spec.affordance}.j2").render()
        (workspace / "README.md").write_text(readme)
        created.append("README.md")
    return created


def apply_handoff(
    workspace: Path,
    prev_workspace: Path,
    handoff: Handoff,
    include_gallery: bool = True,
) -> list[str]:
    """Overwrite seeded files with the previous session's versions."""
    inherited = []
    for name in HANDOFF_FILES[handoff]:
        src = prev_workspace / name
        if src.exists():
            shutil.copy2(src, workspace / name)
            inherited.append(name)
    prev_gallery = prev_workspace / "gallery"
    if include_gallery and prev_gallery.is_dir():
        shutil.copytree(prev_gallery, workspace / "gallery", dirs_exist_ok=True)
        inherited.append("gallery/")
    return inherited
