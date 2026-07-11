"""Docker sandbox lifecycle. One container per run; fresh `docker exec` per
bash call (no persistent shell state — cwd/env reset each call, anchored at
/workspace via -w). The workspace is a bind mount so the host-side shadow git
never enters the container."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_DOCKER_CANDIDATES = [
    "docker",
    "/usr/local/bin/docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
]


def find_docker() -> str:
    for cand in _DOCKER_CANDIDATES:
        path = shutil.which(cand) if "/" not in cand else cand
        if path and Path(path).exists():
            try:
                subprocess.run(
                    [path, "version", "--format", "{{.Server.Version}}"],
                    capture_output=True, timeout=10, check=True,
                )
                return path
            except (subprocess.SubprocessError, OSError):
                continue
    raise RuntimeError(
        "No working docker CLI found (is Docker Desktop running?). "
        f"Tried: {_DOCKER_CANDIDATES}"
    )


@dataclass
class ExecResult:
    exit_code: int
    output: str  # merged stdout+stderr
    wall_ms: int
    timed_out: bool


class DockerEnv:
    def __init__(
        self,
        run_id: str,
        workspace: Path,
        image: str,
        network: bool = False,
        cpus: float = 1.0,
        memory: str = "1g",
        docker_bin: str | None = None,
    ):
        self.name = f"attr-{run_id}"
        self.workspace = workspace
        self.image = image
        self.network = network
        self.cpus = cpus
        self.memory = memory
        self.docker = docker_bin or find_docker()

    def start(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        subprocess.run([self.docker, "rm", "-f", self.name], capture_output=True)
        cmd = [
            self.docker, "run", "-d", "--name", self.name,
            "--cpus", str(self.cpus), "--memory", self.memory,
            "-v", f"{self.workspace.resolve()}:/workspace",
        ]
        if not self.network:
            cmd += ["--network", "none"]
        cmd += [self.image, "sleep", "infinity"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"docker run failed: {proc.stderr.strip()}")

    def exec(self, command: str, timeout_s: int = 60) -> ExecResult:
        import time

        t0 = time.monotonic()
        try:
            # timeout runs inside the container so the process actually dies
            # (a host-side kill would only detach the client); exit 124 = killed.
            proc = subprocess.run(
                [self.docker, "exec", "-w", "/workspace", self.name,
                 "timeout", "-k", "5", str(timeout_s), "bash", "-lc", command],
                capture_output=True, text=True, errors="replace",
                timeout=timeout_s + 20,
            )
            wall_ms = int((time.monotonic() - t0) * 1000)
            output = proc.stdout + (proc.stderr or "")
            return ExecResult(proc.returncode, output, wall_ms,
                              timed_out=proc.returncode in (124, 137))
        except subprocess.TimeoutExpired as e:
            wall_ms = int((time.monotonic() - t0) * 1000)
            partial = ""
            for chunk in (e.stdout, e.stderr):
                if chunk:
                    partial += chunk if isinstance(chunk, str) else chunk.decode(errors="replace")
            return ExecResult(124, partial, wall_ms, timed_out=True)

    def stop(self, remove: bool = True) -> None:
        subprocess.run([self.docker, "rm", "-f", self.name], capture_output=True)

    def __enter__(self) -> "DockerEnv":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


def cleanup_all(docker_bin: str | None = None) -> list[str]:
    """Remove all attr-* containers (strays from crashed runs)."""
    docker = docker_bin or find_docker()
    proc = subprocess.run(
        [docker, "ps", "-a", "--filter", "name=attr-", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    names = [n for n in proc.stdout.split() if n.startswith("attr-")]
    for name in names:
        subprocess.run([docker, "rm", "-f", name], capture_output=True)
    return names
