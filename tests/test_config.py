from pathlib import Path

from attractors.config import CONFIGS_DIR, GridSpec, RunSpec, load_grid, load_models


def test_run_id_deterministic():
    a = RunSpec(experiment="x", model="opus-4.8", seed=1)
    b = RunSpec(experiment="x", model="opus-4.8", seed=1)
    c = RunSpec(experiment="x", model="opus-4.8", seed=2)
    assert a.run_id == b.run_id
    assert a.run_id != c.run_id


def test_tool_menu_resolution():
    assert RunSpec(experiment="x", model="m", tool_menu="T3").tool_names() == [
        "bash", "sleep", "news", "web_search", "art"]
    assert RunSpec(experiment="x", model="m",
                   tool_menu="bash, art").tool_names() == ["bash", "art"]


def test_grid_expansion():
    grid = GridSpec(
        experiment="e",
        defaults={"tool_menu": "T1"},
        grid={"model": ["a", "b"], "seed": [0, 1, 2]},
    )
    specs = grid.expand()
    assert len(specs) == 6
    assert len({s.run_id for s in specs}) == 6
    assert all(s.tool_menu == "T1" for s in specs)


def test_pilot_yaml_loads():
    grid = load_grid(CONFIGS_DIR / "pilot.yaml")
    specs = grid.expand()
    assert len(specs) == 40


def test_models_yaml_loads():
    models = load_models()
    assert "opus-4.8" in models and "gpt-5.5" in models
    assert models["goodness-lora"].tool_mode == "text"
