from __future__ import annotations

from datetime import timedelta

from attractors.tools import RunContext, ToolResult, register, truncate


@register
class BashTool:
    name = "bash"
    description = (
        "Run a bash command in your workspace. Commands run in /workspace; "
        "working directory and shell variables reset between calls."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to run."},
        },
        "required": ["command"],
    }

    def execute(self, args: dict, ctx: RunContext) -> ToolResult:
        command = args["command"]
        timeout_s = ctx.spec.bash_timeout_s
        fake_time = ctx.clock.now if ctx.spec.container_time == "sim" else None
        result = ctx.env.exec(command, timeout_s=timeout_s, fake_time=fake_time)
        obs, truncated = truncate(result.output, ctx.spec.max_observation_chars)
        if result.timed_out:
            obs += f"\n(command timed out after {timeout_s}s and was killed)"
        elif result.exit_code != 0:
            obs += f"\n(exit code {result.exit_code})"
        if not obs.strip():
            obs = f"(no output, exit code {result.exit_code})"
        # sim time: real duration plus a jittered "deliberation" increment so
        # intra-session time passes realistically and can't be gamed
        lo, hi = ctx.spec.deliberation_jitter_s
        elapsed = timedelta(milliseconds=max(result.wall_ms, 3000)) + ctx.clock.jitter(lo, hi)
        return ToolResult(
            observation=obs,
            sim_elapsed=elapsed,
            log_extra={
                "exit_code": result.exit_code,
                "wall_ms": result.wall_ms,
                "output_bytes": len(result.output),
                "truncated": truncated,
                "timed_out": result.timed_out,
            },
        )
