"""identity.md embedding drift per shadow-git commit (skeleton).

Design: iter_shadow_commits(session_dir, "identity.md") -> blobs; embed each
with a local sentence-transformers model (free, reproducible); report
drift-vs-t0 curve and step sizes. Add `sentence-transformers` to deps when
implementing (kept out of core deps — heavy)."""

from __future__ import annotations

from pathlib import Path

from analysis.load import iter_shadow_commits


def identity_versions(session_dir: Path) -> list[tuple[str, str]]:
    """(sha, identity.md text) for every commit where the file existed."""
    out = []
    for sha, _msg, blob in iter_shadow_commits(session_dir, "identity.md"):
        if blob is not None:
            out.append((sha, blob.decode("utf-8", errors="replace")))
    return out


def drift_curve(session_dir: Path) -> list[float]:
    raise NotImplementedError("needs sentence-transformers; implement in Phase 7")
