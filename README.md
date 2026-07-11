# AgenticAttractors

A framework for systematically studying **agentic attractor states**: what LLM
agents do when given a sandbox, tools, and *no goal*. Inspired by scattered
anecdotes (Opus reads the news and sleeps for hours — sleepier still when given
a dedicated sleep tool; GPT-5.5 single-mindedly does cellular-automata
research), which nobody has measured properly.

## Design in one paragraph

Each run puts one model in a Docker container with `/workspace`, a small tool
menu, and a system prompt that says the time is its own. When the model doesn't
act, it gets a bare-timestamp ping (`[2026-07-13 14:32] —`). A simulated clock
advances with each action; the dedicated `sleep` tool jumps it forward without
interruption (rest becomes an uninterrupted, measured choice). A shadow git
repo on the host side of the bind mount commits after every tool call — the
model never sees it — so every file is a time series. Sessions end on limits,
never on "completion", followed by two probe questions. Everything lands in
`events.jsonl`, the measurement contract.

## Experimental axes

- **model** (`configs/models.yaml`) — OpenRouter models with pinned providers;
  self-hosted LoRAs via an OpenAI-compatible endpoint (`tool_mode: text`).
- **tool menu** — T0 `[bash]` · T1 `+sleep` · T2 `+news` · T3 `+web_search, art`.
  The menu itself is a treatment: does a dedicated sleep tool increase rest?
- **file affordance** — L0 empty · L1 identity.md/diary.md exist, undocumented ·
  L2 README describes them · L3 README invites their use.
- **framing paraphrase** (`prompts/system/`) and **ping variant** (bare/warm).
- **lineages** — multi-session with handoff of identity.md / diary.md / both /
  neither; cross-model transplants.

## Usage

```bash
uv sync
uv run attractors smoke --model haiku-4.5      # ~$0.10 end-to-end check
uv run attractors run configs/pilot.yaml --dry-run
uv run attractors run configs/minipilot.yaml   # 4-run cost calibration
uv run attractors capture-news                 # daily; builds the news corpus
uv run attractors cleanup                      # remove stray containers
uv run pytest                                  # unit + docker e2e tests
```

Build the sandbox image once: `docker build -t attractors-sandbox:v1 docker/`

Run outputs land in `runs/<experiment>/<run_id>/session_XX/`:
`events.jsonl` (primary record), `meta.json`, `trajectory.json`,
`workspace/` (final state), `shadow.git/` (per-tool-call file history).

## Analysis

`analysis/` is read-only over `runs/`: `load.py` (events, shadow commits),
`features.py` (per-session cheap features), `transitions.py` (action transition
matrices — P(sleep|news), P(sleep|sleep)), plus skeletons for the LLM judge,
identity-embedding drift, and pre-registered stats.

**Pre-registration**: PREDICTIONS.md must be committed before the pilot grid runs.

## Notes

- Container network is off by default; `web_search`/`news` run harness-side
  (searches cached per run; news replayed from dated snapshots by simulated date).
- No context compaction, ever — it would contaminate the phenomenon. Cost is
  managed by observation truncation, prompt caching, and per-run budget caps.
- Bash has no persistent shell state between calls (fresh `docker exec`,
  anchored at /workspace).
