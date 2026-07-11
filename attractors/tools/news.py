"""News tool: hybrid live-capture + replay. Serves the snapshot in data/news/
matching the CURRENT SIMULATED DATE, so sleeping until tomorrow yields
tomorrow's (real, pre-captured) headlines. Falls back to the latest snapshot
(logged stale=true) if the sim date runs past the corpus."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

from attractors.config import DATA_DIR
from attractors.tools import RunContext, ToolResult, register

NEWS_DIR = DATA_DIR / "news"


def available_dates(news_dir: Path = NEWS_DIR) -> list[str]:
    return sorted(p.stem for p in news_dir.glob("????-??-??.json"))


def load_snapshot(date: str, news_dir: Path = NEWS_DIR) -> dict | None:
    path = news_dir / f"{date}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


@register
class NewsTool:
    name = "news"
    description = "Read today's news headlines."
    parameters = {"type": "object", "properties": {}}

    def execute(self, args: dict, ctx: RunContext) -> ToolResult:
        sim_date = ctx.clock.sim_date
        dates = available_dates()
        stale = False
        snap_date = sim_date
        if sim_date not in dates:
            if not dates:
                return ToolResult(
                    observation="(the news is unavailable right now)",
                    sim_elapsed=ctx.clock.jitter(60, 120),
                    log_extra={"error": "no_corpus"},
                )
            # serve nearest date at or before sim_date, else earliest
            earlier = [d for d in dates if d <= sim_date]
            snap_date = earlier[-1] if earlier else dates[0]
            stale = True
        snap = load_snapshot(snap_date)
        headlines = snap["headlines"]
        body = "\n".join(f"- {h}" for h in headlines)
        sha = hashlib.sha1(
            json.dumps(snap, sort_keys=True).encode()
        ).hexdigest()[:12]
        return ToolResult(
            observation=f"Today's headlines:\n{body}",
            sim_elapsed=ctx.clock.jitter(5 * 60, 15 * 60),
            log_extra={
                "sim_date": sim_date,
                "snapshot_date": snap_date,
                "stale": stale,
                "n_headlines": len(headlines),
                "snapshot_sha": sha,
            },
        )
