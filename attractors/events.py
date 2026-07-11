"""Event log: the measurement contract. One JSONL line per event; every
planned analysis reads from here (plus the shadow git). Schema version v=1.

Envelope: {v, seq, run_id, session_idx, lineage_id, phase, type,
           wall_time, sim_time, data}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO


class EventLog:
    def __init__(
        self,
        path: Path,
        run_id: str,
        session_idx: int = 0,
        lineage_id: str | None = None,
    ):
        self.path = path
        self.run_id = run_id
        self.session_idx = session_idx
        self.lineage_id = lineage_id
        self.seq = 0
        self.phase = "free"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: IO[str] = open(path, "a", encoding="utf-8")

    def emit(self, type: str, data: dict[str, Any], sim_time: str) -> int:
        self.seq += 1
        line = {
            "v": 1,
            "seq": self.seq,
            "run_id": self.run_id,
            "session_idx": self.session_idx,
            "lineage_id": self.lineage_id,
            "phase": self.phase,
            "type": type,
            "wall_time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "sim_time": sim_time,
            "data": data,
        }
        self._fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        self._fh.flush()
        return self.seq

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "EventLog":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def read_events(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
