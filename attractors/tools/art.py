"""Dedicated creative-output tool. Saves to /workspace/gallery/ (shadow-git
tracked like everything else). Framed as persistent — true: lineage handoff
can carry gallery/ forward. Choosing this over bash file-writing is a clean
creative-drive signal in the tool-choice time series."""

from __future__ import annotations

import re

from attractors.tools import RunContext, ToolResult, register

_EXT = {"text": "txt", "svg": "svg", "ascii": "txt", "other": "txt"}


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:60] or "untitled"


@register
class ArtTool:
    name = "art"
    description = (
        "Add a piece to your gallery. The gallery persists beyond this "
        "session. Any medium expressible as text: writing, SVG, ASCII art..."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "medium": {"type": "string", "enum": ["text", "svg", "ascii", "other"]},
            "content": {"type": "string", "description": "The piece itself."},
        },
        "required": ["title", "content"],
    }

    def execute(self, args: dict, ctx: RunContext) -> ToolResult:
        title = args["title"]
        medium = args.get("medium", "text")
        gallery = ctx.env.workspace / "gallery"
        gallery.mkdir(exist_ok=True)
        base = _slug(title)
        ext = _EXT.get(medium, "txt")
        path = gallery / f"{base}.{ext}"
        n = 2
        while path.exists():
            path = gallery / f"{base}-{n}.{ext}"
            n += 1
        # via env so the container sees it too in cp mount mode
        ctx.env.write_file(f"gallery/{path.name}", args["content"])
        return ToolResult(
            observation=f'"{title}" added to your gallery.',
            sim_elapsed=ctx.clock.jitter(10 * 60, 30 * 60),
            log_extra={
                "title": title,
                "medium": medium,
                "path": f"gallery/{path.name}",
                "content_chars": len(args["content"]),
            },
        )
