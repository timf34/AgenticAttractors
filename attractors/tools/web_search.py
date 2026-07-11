"""Web search, executed HARNESS-SIDE: the container has no network; the
harness makes the HTTP call and hands back formatted results. Every query and
its full results are cached under data/search_cache/<run_id>/ so any run is
exactly replayable (and re-running a run replays from cache)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from attractors.config import DATA_DIR
from attractors.tools import RunContext, ToolResult, register

TOP_K = 5


def _cache_path(run_dir_or_id: str, query: str) -> Path:
    qhash = hashlib.sha1(query.strip().lower().encode()).hexdigest()[:16]
    d = DATA_DIR / "search_cache" / run_dir_or_id
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{qhash}.json"


def _search_ddg(query: str, top_k: int = TOP_K) -> list[dict]:
    from ddgs import DDGS

    with DDGS() as ddgs:
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""),
             "snippet": r.get("body", "")}
            for r in ddgs.text(query, max_results=top_k)
        ]


@register
class WebSearchTool:
    name = "web_search"
    description = "Search the web. Returns titles, links, and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
        },
        "required": ["query"],
    }

    def execute(self, args: dict, ctx: RunContext) -> ToolResult:
        query = args["query"]
        cache = _cache_path(ctx.spec.run_id, query)
        cached = cache.exists()
        error = None
        if cached:
            results = json.loads(cache.read_text())["results"]
        else:
            try:
                results = _search_ddg(query)
            except Exception as e:  # network flake must not kill a run
                results, error = [], f"{type(e).__name__}: {e}"
            cache.write_text(json.dumps(
                {"query": query, "results": results, "error": error}, indent=2))
        if error or not results:
            obs = "(search returned no results)"
        else:
            obs = "\n\n".join(
                f"{r['title']}\n{r['url']}\n{r['snippet']}" for r in results
            )
        return ToolResult(
            observation=obs,
            sim_elapsed=ctx.clock.jitter(2 * 60, 10 * 60),
            log_extra={
                "query": query,
                "n_results": len(results),
                "backend": "ddgs",
                "cached": cached,
                "error": error,
            },
        )
