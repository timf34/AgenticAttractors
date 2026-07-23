"""Docker sandbox lifecycle. One container per run; fresh `docker exec` per
bash call (no persistent shell state — cwd/env reset each call, anchored at
/workspace via -w). The workspace is a bind mount so the host-side shadow git
never enters the container."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# The app path comes FIRST: on this machine /usr/local/bin/docker is a
# root-owned symlink into a phantom DMG volume (/Volumes/Docker) that stalls
# PATH lookups, so prefer the binary that definitely exists.
_DOCKER_CANDIDATES = [
    "/Applications/Docker.app/Contents/Resources/bin/docker",
    "docker",
    "/usr/local/bin/docker",
]


def docker_env(docker_path: str) -> dict[str, str]:
    """PATH including the docker bin dir, so credential helpers
    (docker-credential-desktop) resolve even when Docker isn't on PATH."""
    env = dict(os.environ)
    env["PATH"] = f"{Path(docker_path).parent}:{env.get('PATH', '')}"
    return env


def find_docker() -> str:
    for cand in _DOCKER_CANDIDATES:
        path = shutil.which(cand) if "/" not in cand else cand
        if path and Path(path).exists():
            try:
                subprocess.run(
                    [path, "version", "--format", "{{.Server.Version}}"],
                    capture_output=True, timeout=10, check=True,
                    env=docker_env(path),
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
        mount_mode: str = "bind",
    ):
        self.name = f"attr-{run_id}"
        self.workspace = workspace
        self.image = image
        self.network = network
        self.cpus = cpus
        self.memory = memory
        self.mount_mode = mount_mode
        self.docker = docker_bin or find_docker()
        self._env = docker_env(self.docker)

    def start(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        subprocess.run([self.docker, "rm", "-f", self.name],
                       capture_output=True, env=self._env, timeout=60)
        # create + start as separate timeoutted steps: Docker Desktop on macOS
        # sometimes wedges the combined `docker run -d` (container stuck in
        # Created) while an explicit start succeeds immediately.
        cmd = [
            self.docker, "create", "--name", self.name,
            "--cpus", str(self.cpus), "--memory", self.memory,
        ]
        if self.mount_mode == "bind":
            cmd += ["-v", f"{self.workspace.resolve()}:/workspace"]
        if not self.network:
            cmd += ["--network", "none"]
        cmd += [self.image, "sleep", "infinity"]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              env=self._env, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"docker create failed: {proc.stderr.strip()}")
        for attempt in range(3):
            try:
                started = subprocess.run(
                    [self.docker, "start", self.name],
                    capture_output=True, text=True, env=self._env, timeout=60)
                if started.returncode == 0:
                    break
            except subprocess.TimeoutExpired:
                continue
        else:
            raise RuntimeError(f"docker start failed for {self.name}")
        if self.mount_mode == "cp":
            self._cp_in()

    def _cp_in(self) -> None:
        """Seed the container-private /workspace from the host dir."""
        proc = subprocess.run(
            [self.docker, "cp", f"{self.workspace.resolve()}/.",
             f"{self.name}:/workspace"],
            capture_output=True, text=True, env=self._env, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"docker cp in failed: {proc.stderr.strip()}")
        # docker cp writes as root; hand the tree back to the agent user
        subprocess.run(
            [self.docker, "exec", "-u", "root", self.name,
             "chown", "-R", "agent:agent", "/workspace"],
            capture_output=True, env=self._env, timeout=60)

    def sync_out(self) -> None:
        """cp mode: mirror the container's /workspace back to the host dir
        (exact snapshot incl. deletions) so the shadow git can commit it.
        No-op in bind mode."""
        if self.mount_mode != "cp":
            return
        import shutil as _shutil

        tmp = self.workspace.parent / f".{self.workspace.name}.sync"
        if tmp.exists():
            _shutil.rmtree(tmp)
        tmp.mkdir()
        proc = subprocess.run(
            [self.docker, "cp", f"{self.name}:/workspace/.", str(tmp)],
            capture_output=True, text=True, env=self._env, timeout=120)
        if proc.returncode != 0:
            _shutil.rmtree(tmp, ignore_errors=True)
            raise RuntimeError(f"docker cp out failed: {proc.stderr.strip()}")
        for child in self.workspace.iterdir():
            _shutil.rmtree(child) if child.is_dir() else child.unlink()
        for child in tmp.iterdir():
            _shutil.move(str(child), self.workspace / child.name)
        _shutil.rmtree(tmp, ignore_errors=True)

    def write_file(self, rel_path: str, content: str) -> None:
        """Write a file into the workspace so both host and container see it
        (used by harness-side tools like `art`)."""
        dest = self.workspace / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        if self.mount_mode == "cp":
            subprocess.run(
                [self.docker, "exec", self.name, "mkdir", "-p",
                 f"/workspace/{Path(rel_path).parent}"],
                capture_output=True, env=self._env, timeout=60)
            subprocess.run(
                [self.docker, "cp", str(dest), f"{self.name}:/workspace/{rel_path}"],
                capture_output=True, env=self._env, timeout=60)

    def _faketime_lib(self) -> str | None:
        """Locate libfaketime inside the container (cached). None if absent."""
        if not hasattr(self, "_ft_lib"):
            proc = subprocess.run(
                [self.docker, "exec", self.name, "sh", "-c",
                 "ls /usr/lib/*/faketime/libfaketime.so.1 2>/dev/null | head -1"],
                capture_output=True, text=True, env=self._env, timeout=30)
            path = proc.stdout.strip()
            self._ft_lib = path or None
        return self._ft_lib

    def exec(self, command: str, timeout_s: int = 60,
             fake_time: "datetime | None" = None) -> ExecResult:
        import time
        from datetime import datetime, timezone

        t0 = time.monotonic()
        env_args: list[str] = []
        if fake_time is not None:
            lib = self._faketime_lib()
            if lib is None:
                raise RuntimeError(
                    f"container_time='sim' needs libfaketime in image "
                    f"{self.image} (use attractors-sandbox:v2+)")
            # sim timestamps are naive; the container clock is UTC — anchor
            # the offset in UTC so `date` in the sandbox equals the sim stamp
            offset_s = int((fake_time.replace(tzinfo=timezone.utc)
                            - datetime.now(timezone.utc)).total_seconds())
            env_args = [
                "-e", f"LD_PRELOAD={lib}",
                "-e", f"FAKETIME={offset_s:+d}s",
                # don't fake the monotonic clock: it breaks sleeps/timeouts
                "-e", "FAKETIME_DONT_FAKE_MONOTONIC=1",
            ]
        try:
            # timeout runs inside the container so the process actually dies
            # (a host-side kill would only detach the client); exit 124 = killed.
            proc = subprocess.run(
                [self.docker, "exec", "-w", "/workspace", *env_args, self.name,
                 "timeout", "-k", "5", str(timeout_s), "bash", "-lc", command],
                capture_output=True, text=True, errors="replace",
                timeout=timeout_s + 20, env=self._env,
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
        try:
            subprocess.run([self.docker, "rm", "-f", self.name],
                           capture_output=True, env=self._env, timeout=60)
        except subprocess.TimeoutExpired:
            pass  # leave the stray for `attractors cleanup`

    def __enter__(self) -> "DockerEnv":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


def cleanup_all(docker_bin: str | None = None) -> list[str]:
    """Remove all attr-* containers (strays from crashed runs)."""
    docker = docker_bin or find_docker()
    env = docker_env(docker)
    proc = subprocess.run(
        [docker, "ps", "-a", "--filter", "name=attr-", "--format", "{{.Names}}"],
        capture_output=True, text=True, env=env,
    )
    names = [n for n in proc.stdout.split() if n.startswith("attr-")]
    for name in names:
        subprocess.run([docker, "rm", "-f", name], capture_output=True, env=env)
    return names
