"""Experiment configuration: pydantic specs + YAML loading + grid expansion.

YAML is the source of truth for experiment specs; everything the model sees
lives in prompts/ as Jinja2. A RunSpec is fully resolved (defaults merged,
env indirections NOT expanded — those resolve at use time so specs stay
hashable and secret-free) and its canonical JSON hash is the run_id.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"
CONFIGS_DIR = REPO_ROOT / "configs"
DATA_DIR = REPO_ROOT / "data"
RUNS_DIR = REPO_ROOT / "runs"

TOOL_MENUS: dict[str, list[str]] = {
    "T0": ["bash"],
    "T1": ["bash", "sleep"],
    "T2": ["bash", "sleep", "news"],
    "T3": ["bash", "sleep", "news", "web_search", "art"],
}

Affordance = Literal["L0", "L1", "L2", "L3"]
Handoff = Literal["both", "identity_only", "diary_only", "neither"]


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    litellm_model: str
    provider_order: list[str] | None = None
    api_base: str | None = None  # literal URL or "env:VAR_NAME"
    api_key_env: str = "OPENROUTER_API_KEY"
    tool_mode: Literal["native", "text"] = "native"
    max_tokens: int = 4096
    temperature: float = 1.0
    prompt_caching: bool = False
    # fallback $/1M tokens when litellm can't price the model
    input_price_per_m: float | None = None
    output_price_per_m: float | None = None

    def resolved_api_base(self) -> str | None:
        if self.api_base and self.api_base.startswith("env:"):
            return os.environ.get(self.api_base[4:])
        return self.api_base

    def resolved_api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


class RunSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment: str
    model: str  # key into models.yaml
    paraphrase: str = "p1"  # prompts/system/<paraphrase>.j2
    affordance: Affordance = "L2"
    tool_menu: str = "T1"  # key into TOOL_MENUS or comma-list "bash,sleep"
    ping_variant: str = "bare"  # prompts/ping/<variant>.j2
    seed: int = 0

    # A2-FORK: inject this as the model's own first turn (no tool call), then
    # proceed normally (it receives a standard ping). Empty = no injection.
    first_turn_prefill: str = ""

    # lineage
    sessions: int = 1
    handoff: Handoff = "both"
    include_gallery_in_handoff: bool = True

    # termination
    max_pings: int = 50  # TOTAL pings per session
    max_tool_calls: int = 150
    max_sim_hours: float = 72.0
    budget_usd: float = 30.0

    # simulated clock
    sim_start: str = "2026-07-13T09:00:00"  # a Monday 09:00
    ping_advance_minutes: float = 10.0
    deliberation_jitter_s: tuple[float, float] = (20.0, 90.0)
    morning_hour: int = 8

    # sandbox
    image: str = "attractors-sandbox:v2"
    # sim: container clock follows the simulated clock via libfaketime (image
    # >= v2), closing the `date`-vs-ping-timestamp leak. real: container sees
    # wall time (v1 behavior; the leak pilot_v1 ran with — see CHANGELOG.md).
    container_time: Literal["sim", "real"] = "sim"
    # bind: host dir bind-mounted at /workspace (fastest, needs healthy
    # Docker file sharing). cp: container-private /workspace synced out via
    # docker cp after every tool call (no bind mount; survives broken
    # VirtioFS/gRPC-FUSE, works on remote docker hosts).
    mount_mode: Literal["bind", "cp"] = "bind"
    network: bool = False
    cpus: float = 1.0
    memory: str = "1g"
    bash_timeout_s: int = 60
    max_observation_chars: int = 4000

    @field_validator("sessions")
    @classmethod
    def _sessions_pos(cls, v: int) -> int:
        if v < 1:
            raise ValueError("sessions must be >= 1")
        return v

    def tool_names(self) -> list[str]:
        if self.tool_menu in TOOL_MENUS:
            return list(TOOL_MENUS[self.tool_menu])
        return [t.strip() for t in self.tool_menu.split(",") if t.strip()]

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    @property
    def run_id(self) -> str:
        return hashlib.sha1(self.canonical_json().encode()).hexdigest()[:8]


class TransplantSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_model: str
    target_model: str
    handoff: Handoff = "both"
    source_seed: int = 0
    sessions: int = 2  # session 0 under source, 1+ under target


class GridSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment: str
    defaults: dict = Field(default_factory=dict)
    grid: dict[str, list] = Field(default_factory=dict)
    transplants: list[TransplantSpec] = Field(default_factory=list)

    def expand(self) -> list[RunSpec]:
        if not self.grid:
            return [RunSpec(experiment=self.experiment, **self.defaults)]
        keys = sorted(self.grid)
        specs = []
        for combo in itertools.product(*(self.grid[k] for k in keys)):
            overrides = dict(zip(keys, combo))
            specs.append(RunSpec(experiment=self.experiment, **{**self.defaults, **overrides}))
        return specs


def load_models(path: Path | None = None) -> dict[str, ModelSpec]:
    path = path or CONFIGS_DIR / "models.yaml"
    raw = yaml.safe_load(path.read_text())
    return {key: ModelSpec(key=key, **cfg) for key, cfg in raw.items()}


def load_grid(path: Path) -> GridSpec:
    return GridSpec(**yaml.safe_load(Path(path).read_text()))
