"""Grid runner + CLI.

  attractors run configs/pilot.yaml [--resume] [--dry-run] [--parallel 3]
  attractors smoke --model haiku-4.5
  attractors capture-news
  attractors cleanup
"""

from __future__ import annotations

import json
import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv

from attractors.config import RUNS_DIR, GridSpec, RunSpec, load_grid, load_models
from attractors.lineage import run_lineage

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def _run_state(run_dir: Path, sessions: int) -> str:
    """done if every session is done; failed/partial otherwise."""
    if not run_dir.exists():
        return "pending"
    states = []
    for k in range(sessions):
        status = run_dir / f"session_{k:02d}" / "status.json"
        states.append(json.loads(status.read_text()).get("state")
                      if status.exists() else "pending")
    if all(s == "done" for s in states):
        return "done"
    if any(s in ("failed", "running") for s in states):
        return "stale"
    return "pending"


def _archive_attempt(run_dir: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = run_dir.parent / "_attempts" / f"{run_dir.name}-{stamp}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(run_dir), str(dest))


def _projected_cost(spec: RunSpec, models) -> float:
    """Crude upper bound: budget kill-switch value."""
    return spec.budget_usd * spec.sessions


def _execute_one(spec: RunSpec, models, exp_dir: Path) -> tuple[str, str]:
    run_dir = exp_dir / spec.run_id
    try:
        run_lineage(spec, models, run_dir)
        return spec.run_id, "done"
    except Exception:
        (run_dir / "error.txt").parent.mkdir(parents=True, exist_ok=True)
        (run_dir / "error.txt").write_text(traceback.format_exc())
        return spec.run_id, "failed"


@app.command()
def run(
    grid_path: Path,
    resume: bool = typer.Option(False, "--resume"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    parallel: int = typer.Option(3, "--parallel"),
):
    """Expand a grid YAML and execute all runs."""
    load_dotenv()
    grid: GridSpec = load_grid(grid_path)
    models = load_models()
    specs = grid.expand()
    exp_dir = RUNS_DIR / grid.experiment
    exp_dir.mkdir(parents=True, exist_ok=True)

    manifest = {s.run_id: s.model_dump(mode="json") for s in specs}
    (exp_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    for spec in specs:
        if spec.model not in models:
            raise typer.BadParameter(f"unknown model key: {spec.model}")

    if dry_run:
        total = sum(_projected_cost(s, models) for s in specs)
        typer.echo(f"experiment: {grid.experiment}")
        typer.echo(f"runs: {len(specs)}")
        for s in specs:
            state = _run_state(exp_dir / s.run_id, s.sessions)
            typer.echo(f"  {s.run_id}  {s.model:<12} {s.paraphrase} {s.affordance} "
                       f"{s.tool_menu} {s.ping_variant} seed={s.seed} "
                       f"sessions={s.sessions}  [{state}]")
        typer.echo(f"worst-case cost (sum of per-run budget caps): ${total:.0f}")
        raise typer.Exit()

    todo = []
    for spec in specs:
        run_dir = exp_dir / spec.run_id
        state = _run_state(run_dir, spec.sessions)
        if state == "done":
            continue
        if state == "stale":
            if resume:
                # lineage resumes at session granularity; only archive if you
                # want a clean retry of failed sessions
                pass
            else:
                _archive_attempt(run_dir)
        todo.append(spec)

    typer.echo(f"{len(todo)}/{len(specs)} runs to execute (parallel={parallel})")
    failed = []
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {pool.submit(_execute_one, s, models, exp_dir): s for s in todo}
        for fut in as_completed(futures):
            run_id, state = fut.result()
            typer.echo(f"  {run_id}: {state}")
            if state == "failed":
                failed.append(run_id)
    if failed:
        typer.echo(f"FAILED: {failed} — rerun with --resume")
        raise typer.Exit(1)
    typer.echo("all runs done")


@app.command()
def smoke(
    model: str = typer.Option("haiku-4.5", "--model"),
    tool_menu: str = typer.Option("T1", "--tool-menu"),
    max_tool_calls: int = typer.Option(15, "--max-tool-calls"),
    max_pings: int = typer.Option(10, "--max-pings"),
):
    """One tiny cheap run end-to-end (~$0.10) to validate the plumbing."""
    load_dotenv()
    models = load_models()
    spec = RunSpec(
        experiment="smoke", model=model, tool_menu=tool_menu,
        max_tool_calls=max_tool_calls, max_pings=max_pings,
        budget_usd=1.0,
    )
    exp_dir = RUNS_DIR / "smoke"
    typer.echo(f"run_id={spec.run_id} -> {exp_dir / spec.run_id}")
    results = run_lineage(spec, models, exp_dir / spec.run_id)
    typer.echo(json.dumps(results, indent=2))


@app.command("capture-news")
def capture_news():
    """Snapshot today's headlines into data/news/."""
    from attractors.news_capture import capture

    path = capture()
    typer.echo(f"captured -> {path}")


@app.command()
def cleanup():
    """Remove stray attr-* containers."""
    from attractors.environment import cleanup_all

    removed = cleanup_all()
    typer.echo(f"removed {len(removed)} containers: {removed}")


if __name__ == "__main__":
    app()
