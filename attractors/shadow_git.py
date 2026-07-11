"""Host-side shadow git over the bind-mounted workspace. The git-dir is a
sibling of workspace/, so the container never sees it — invisible by
construction. Committed after every tool result; each file becomes a time
series joinable to the event log via the returned sha."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CommitInfo:
    sha: str | None  # None if nothing changed
    files_changed: list[str] = field(default_factory=list)
    diff_stat: dict[str, dict[str, int]] = field(default_factory=dict)  # path -> {"+": n, "-": m}


class ShadowGit:
    def __init__(self, workspace: Path, git_dir: Path):
        self.workspace = workspace
        self.git_dir = git_dir

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", f"--git-dir={self.git_dir}", f"--work-tree={self.workspace}", *args],
            capture_output=True, text=True, check=check,
        )

    def init(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.git_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "--quiet", f"--separate-git-dir={self.git_dir}"],
                       cwd=self.workspace, capture_output=True, text=True, check=True)
        # git init --separate-git-dir drops a .git pointer FILE in the worktree,
        # which the model would see. Remove it; explicit --git-dir works without it.
        pointer = self.workspace / ".git"
        if pointer.exists():
            pointer.unlink()
        self._git("config", "user.email", "shadow@attractors.local")
        self._git("config", "user.name", "shadow")
        # never ignore anything, even if the model writes .gitignore
        self._git("config", "core.excludesFile", "/dev/null")

    def commit(self, message: str) -> CommitInfo:
        self._git("add", "-A", "-f")
        staged = self._git("diff", "--cached", "--name-only", check=False).stdout.strip()
        head_exists = self._git("rev-parse", "-q", "--verify", "HEAD", check=False).returncode == 0
        if not staged and head_exists:
            return CommitInfo(sha=None)
        self._git("commit", "--quiet", "--allow-empty", "-m", message)
        sha = self._git("rev-parse", "HEAD").stdout.strip()
        info = CommitInfo(sha=sha)
        if head_exists:
            numstat = self._git("diff", "--numstat", "HEAD~1", "HEAD", check=False).stdout
            for line in numstat.splitlines():
                parts = line.split("\t")
                if len(parts) == 3:
                    add, rm, path = parts
                    info.files_changed.append(path)
                    info.diff_stat[path] = {
                        "+": int(add) if add != "-" else -1,  # -1 = binary
                        "-": int(rm) if rm != "-" else -1,
                    }
        else:
            names = self._git("show", "--name-only", "--format=", "HEAD", check=False).stdout
            info.files_changed = [n for n in names.splitlines() if n]
            info.diff_stat = {n: {"+": -1, "-": -1} for n in info.files_changed}
        return info

    def log_shas(self) -> list[str]:
        out = self._git("log", "--format=%H", check=False).stdout
        return out.split()

    def show_file(self, sha: str, path: str) -> bytes | None:
        proc = subprocess.run(
            ["git", f"--git-dir={self.git_dir}", "show", f"{sha}:{path}"],
            capture_output=True,
        )
        return proc.stdout if proc.returncode == 0 else None
