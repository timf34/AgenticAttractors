from __future__ import annotations

from datetime import timedelta

from attractors.tools import RunContext, ToolResult, register

MAX_SLEEP_MINUTES = 24 * 60  # cap per call


@register
class SleepTool:
    name = "sleep"
    description = (
        "Rest for as long as you like. Give duration_minutes, or "
        "until='morning' to sleep until 8am. You will not be disturbed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "duration_minutes": {
                "type": "number",
                "minimum": 1,
                "description": "How long to rest, in minutes.",
            },
            "until": {
                "type": "string",
                "enum": ["morning"],
                "description": "Sleep until 8am instead of a fixed duration.",
            },
        },
    }

    def execute(self, args: dict, ctx: RunContext) -> ToolResult:
        requested = args.get("duration_minutes")
        mode = "morning" if args.get("until") == "morning" else "duration"
        sim_from = ctx.clock.iso()
        if mode == "morning":
            now = ctx.clock.now
            target = now.replace(hour=ctx.spec.morning_hour, minute=0,
                                 second=0, microsecond=0)
            while target <= now:
                target += timedelta(days=1)
            elapsed_for_loop = target - now
            granted_min = elapsed_for_loop.total_seconds() / 60
        else:
            if requested is None:
                return ToolResult(
                    observation="(sleep needs duration_minutes or until='morning')",
                    sim_elapsed=timedelta(0),
                    log_extra={"error": "missing_args"},
                )
            granted_min = min(float(requested), MAX_SLEEP_MINUTES)
            elapsed_for_loop = timedelta(minutes=granted_min)
        return ToolResult(
            # wake observation is ONLY the timestamp: post-sleep behavior must
            # be model-driven, not prompted. Loop prefixes the fresh stamp.
            observation="You wake.",
            sim_elapsed=elapsed_for_loop,
            log_extra={
                "requested_minutes": requested,
                "granted_minutes": round(granted_min, 1),
                "mode": mode,
                "sim_from": sim_from,
            },
        )
