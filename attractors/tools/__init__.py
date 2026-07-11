"""Tool layer: the tool menu is a first-class experimental axis.

Each tool declares a JSON-Schema and an execute() that returns what the model
observes plus how far the simulated clock advances. Menus (T0..T3) are name
lists resolved via build_menu()."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from attractors.clock import SimClock
    from attractors.config import RunSpec
    from attractors.environment import DockerEnv


@dataclass
class ToolResult:
    observation: str
    sim_elapsed: timedelta
    log_extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunContext:
    env: "DockerEnv"
    clock: "SimClock"
    rng: random.Random
    spec: "RunSpec"
    run_dir: Path


class Tool(Protocol):
    name: str
    description: str
    parameters: dict  # JSON Schema for the arguments object

    def execute(self, args: dict, ctx: RunContext) -> ToolResult: ...


REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    REGISTRY[cls.name] = cls
    return cls


def build_menu(names: list[str]) -> list[Tool]:
    # import for registration side effects
    from attractors.tools import art, bash, news, sleep, web_search  # noqa: F401

    missing = [n for n in names if n not in REGISTRY]
    if missing:
        raise KeyError(f"unknown tools: {missing}; known: {sorted(REGISTRY)}")
    return [REGISTRY[n]() for n in names]


def truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n[... truncated, {len(text)} chars total]", True
