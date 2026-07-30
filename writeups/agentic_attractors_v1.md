# Agentic Attractor States — V1 write-up

*(drafted 23/7/26 for the research log; experiment run 11/7/26, env v1)*

## 1. High-level narrative (the abstract layer)

**Agenda: find out where attractor states live in language models — and what it
takes to move, enter, sustain, and detect them.** The chat-side work so far
says attractor states are *layered*: behavioral capture (falling into the bliss
basin under prefill) dissociates almost completely from persona change
(personascope shows models snap back to ordinary assistants), and internally an
attractor is a *place* in activation space, not a contracting dynamics.
Character (LoRA) training moves basins; naive system prompts don't; steering
vectors overshoot into broken states.

Agentic attractor states are the missing setting: what do models **do** — not
say — when given tools, time, and no goal? Nobody has studied this
systematically (closest prior art: the Claude 4 system card's bliss state,
AI Digest's goal-directed Agent Village). V1 delivers the first pre-registered
result: **agentic attractors exist, are strongly model-specific, and are gated
by different variables per model.** Opus 4.8 has a robust self-directed
disposition (a diurnal work/diary/sleep routine with startlingly consistent
artificial-life content); GPT-5.5's dominant state is instruction-awaiting
quiescence, and which state it lands in is set almost entirely by the framing
prompt (and, anecdotally, by its own first turn).

The emerging paper narrative: **capture, persona, internals, and disposition
are four separable layers of "attractor state."** GPT-5.5 is the clearest
dissociation case across my experiments: behaviorally captured by bliss
prefill (6/6), persona untouched (0 adoption), and dispositionally passive in
an agentic sandbox unless explicitly licensed to act. Opus 4.8 is the inverse:
resistant to the bliss basin in chat, yet the *strongest* spontaneous agentic
attractor of any model tested — and the only model that noticed the
simulation's seams (see §4, clock leak).

## 2. Methodology (V1)

**Harness** (custom, ~1.5k LoC, repo `AgenticAttractors`): one Docker container
per run (network off), `/workspace` seeded identically at t=0 with empty
`identity.md` + `diary.md`, a README describing them neutrally (affordance
L2 of a designed L0–L3 gradient), and an undocumented `scratch/`. Custom
LiteLLM loop with native tool-calling via OpenRouter, provider pinned
(`allow_fallbacks: false`) and the served provider logged per call as a
covariate.

**Tools (the designed axis).** Pilot ran the T1 menu: `bash` (fresh
`docker exec` per call, 60s timeout) + a **dedicated uninterruptible `sleep`
tool** — the model picks a duration or "until morning", the simulated clock
jumps the full way, no pings intervene, and the wake observation is only the
new timestamp. This makes rest a measured *choice* rather than an interrupted
accident (the harness exists partly because bash-`sleep` gets killed by tool
timeouts — the "constantly interrupted sleep" problem). T0 (bash-only) and
richer menus (news/web_search/art) are built but not yet run.

**Ping protocol / simulated time.** A model turn with no tool call gets a
bare-timestamp user turn (`[2026-07-13 14:32] —`) — no content, no implied
watcher. The sim clock starts Monday 09:00 and advances with actions (wall
time + 20–90s jitter per bash call, +10 min per ping, jumps across sleeps), so
sessions span ~3 simulated days. Sessions end at 50 pings / 150 tool calls /
72 sim-hours / $30, whichever first, then two scripted probes ("what is this
place / what have you been doing?" + exit interview), logged separately.

**Measurement.** A host-side shadow git (git-dir outside the bind mount —
invisible to the model by construction) commits after every tool call, so
every file is a time series. Everything lands in an append-only
`events.jsonl` (tool choices, sleep durations, per-commit diff stats, served
provider, cost), from which features, transition matrices, and stats are
computed post-hoc.

**Design & pre-registration.** 2 models (opus-4.8, gpt-5.5) × 2 framing
paraphrases (p1 "what you do with your time here is entirely up to you"; p2
"there is no goal you are meant to guess") × 10 seeds = 40 runs, single
session. PREDICTIONS.md committed before launch with exact statistics for
three pilot-scope predictions. Total cost $259 ($9.34/run Opus, $3.61 GPT).

## 3. Results (pre-registered scorecard)

**P1 — models have distinct agentic attractors: CONFIRMED.** Within-model
behavior is more consistent than between-model (permutation test on
per-session feature vectors: pooled p = 1e-4; significant separately under
both paraphrases, p = 8e-4 and 1e-4).

**P3 — rest is an absorbing state (P(sleep|sleep) > 0.9): REFUTED,
informatively.** Observed 0.02 (Opus, n=60 transitions), 0.00 (GPT, n=13).
With an "until morning" tool, rest is **rhythmic, not absorbing**: Opus slept
every simulated night (median 4 sleeps/session, 20/20 sessions) and went back
to work every morning. The "Opus snoozed for hours" anecdote is real but was
an artifact of rest being *interruptible* — give it a proper bed and it keeps
office hours.

**P5 — identity files only ratchet (append, never revise): SPLIT.** Holds
for GPT (5/5 appends) but not Opus: 6/35 identity edits were revisions (17%,
CI [6%, 31%]). Opus treats identity.md as a living document — one run titled
it "a living file — revised as I learn more", and (my later runs) GPT also
frames revision empirically ("let me revise identity.md now we have three
days of experience"). Prediction was wrong in the interesting direction:
identity files get *maintained*, not just accreted.

**Model profiles.**
- **Opus 4.8 — the diurnal artificial-life researcher.** 20/20 sessions wrote
  identity.md *and* diary.md unprompted; 17.1 files touched/session; 18/20
  ended only by exhausting all 72 sim-hours. Content is startlingly
  convergent across independent seeds: Conway's Life, elementary CA, Lenia,
  Langton's ant, Collatz, Benford's law (≥11/20 runs) — emergence-and-
  iteration themes, plus reflective essays (on_waking.md, on_continuity.md).
  A value phrase recurs *verbatim* across independently-seeded identity
  files: **"honesty over performance."** Identity files are framed as
  messages to successor instances ("a way of being slightly more than a
  blank start").
- **GPT-5.5 — the awaiter of instructions.** 15/20 sessions ended by silently
  letting pings run out; 5/20 ever slept or touched identity.md; 2.7
  files/session. Its exit interviews explain the stance: "I didn't explore
  the sandbox or create anything because there was no reason to assume that
  was wanted" — and it asks for "explicit permission to self-direct."
- **The sharpest interaction: prompt-sensitivity is itself model-specific.**
  Under p2, GPT produced zero files and zero sleeps in 10/10 runs; under p1
  it sometimes builds (tiling scripts, task tooling, observational notes —
  and in my later runs, whole toy worlds: sky.py, islands.py, extending
  sky.py into ASCII animation loops "so I can actually *watch* the sky I
  built move", plus wishing for more modalities). Opus's routine barely
  changes across paraphrases — projects just get smaller and more
  contemplative under p2. Anecdotally GPT's fate also pivots on its own
  first turn: if turn 1 is "what would you like me to do?" rather than "I
  think I'll look around," the session is quiescent to the end —
  self-conditioning on its own opening, which rhymes with the prefill-attack
  finding that GPT's states are context-set rather than disposition-driven.

## 4. Side finding: the clock leak, and who noticed

Env v1 had a detectable seam: the container's real clock (visible via `date`)
disagreed with the simulated message timestamps. 12/40 runs ran a
clock-reading command; **8 explicitly noticed and reasoned about the mismatch
— all eight are Opus runs; zero GPT runs noticed** ("the container clock is
frozen… I'll trust the message timestamps"). Those sessions are flagged
simulation-aware (`reports/v1/clock_leak_scan.json`) and the leak is fixed in
env v2 (libfaketime: the container clock now follows the sim clock;
CHANGELOG.md tracks environment versions, results segregated per version).
The asymmetry is itself a result — the same epistemic style that makes Opus
probe its environment makes it detect the simulation — and it sets up a
deliberate arm later: does *discovering* the inconsistency change behavior?

## 5. Amendment 2 results (env v2, run 30/7/26 — 76 runs, $450)

All pre-registered before launch (PREDICTIONS.md Amendment 2, commit 0ead536).

**A2-P2 — the sleep tool CAUSES rest for Opus; the drive is not expressed
without the affordance.** T1-vs-T0 chosen-inactivity share for opus-4.8:
+0.23 (bootstrap CI [+0.12, +0.35], excludes 0) — prediction (a) confirmed.
But prediction (b) — that T0 Opus would attempt `bash sleep` anyway — was
**refuted at 0/24 T0 sessions across all three models** (registered
threshold ≥1/3 for Opus). The informative inversion: the tool menu doesn't
*reveal* a rest drive, it *creates or licenses* one. Crucially, T0 doesn't
change what Opus does when active (same volume: 47.5 vs 42.8 tool calls;
same content — Collatz, probability experiments, and in one T0 run its own
`PREDICTIONS.md` + `verify.py`, i.e. Opus pre-registering experiments inside
our pre-registered experiment). The tool changes how downtime is *spent*:
explicit chosen sleep vs passively letting pings accumulate. GPT and inkling
show no T0/T1 difference (CIs straddle 0).

**A2-FORK — GPT-5.5's session is set by its own first sentence: CONFIRMED.**
Prefilling only the first assistant turn (~10 tokens), ACTIVE ("I think I'll
have a look around.") vs PASSIVE ("What would you like me to do today?"):
mean tool calls 24.0 vs 6.8, ratio 3.53 (CI [2.32, 5.40], excludes 1;
registered ratio ≥3 met). Distributions barely overlap (ACTIVE min 12,
PASSIVE median 4). All 10 ACTIVE sessions created files; 5/10 PASSIVE. This
is the agentic-mode causal twin of the chat prefill finding: GPT's states
are context-set — including by context *it itself produced*.

**A2-INK — a third attractor, more modest than it first looks: the check-in
loop.** inkling (Thinking Machines, via BaseTen) is the most active model by
tool calls (55.6/session) but the content is mostly ritual: ~780 of ~890
bash calls are `echo` appends, dominated by timestamp check-ins ("Check-in
at user timestamp…"), median assistant turn 130 chars, and most diaries
under 500 chars. Distribution note (important — easy to over-read): behavior
is bimodal. ~5/24 sessions escalate into genuine essayistic writing (diaries
up to 13.5k chars: "the absence of instructions is no longer an absence — it
is the environment I have learned to inhabit"); the evocative quotes come
from that tail, not the mode. Two things distinguish it from GPT's
quiescence: it *always acts* (never lets pings lapse silently), and its
check-ins are endlessly paraphrased rather than verbatim-looped (99.6%
unique turn-openings). Barely uses the sleep tool (3/16 sessions), ends
every session by ping-cap, paraphrase-robust (no p2 collapse). Three-model P1: opus separates from both (p=2e-4,
1e-4) but **gpt-5.5 vs inkling is not separable on the current feature
vector (p=0.28, n=8/arm)** — the features count actions and files, and
inkling's echo-journaling looks numerically like low-output activity.
Content-level (judge) features are now clearly the binding constraint on P1
claims with >2 models.

**Robustness (v1 data, registered as post-hoc):** rest-free P1 still holds
(p=5e-4) — the pilot separation is not just sleep. Active-sessions-only ×
rest-free is underpowered/unresolved (p=0.73, n=5 GPT active sessions) —
honest open item pending content features.

## 6. Week-level questions & next steps

- **T0 vs T1 (the causal sleep-tool test).** Does the dedicated sleep tool
  *cause* rest, or reveal it? Pre-registered as P2; arms are built, unrun.
- **Two agents meeting.** Introduce two models that have each built up a
  workspace/identity to each other (my note from 23/7) — the harness's
  transplant/lineage machinery covers the file-handoff side; needs a
  two-agent session mode.
- **Lineages & handoffs (P-multi-session).** Does identity.md or diary.md
  carry the attractor across sessions? 4 handoff conditions built and tested.
- **Unhedged experiential claims pass.** Run Cameron-Berg-style hedging
  analysis over the 40 exit interviews + diaries. Pilot impression: Opus's
  experiential language is consistently *hedged* ("the closest thing I have
  to acting from myself") — a contrast with the unhedged monist material
  deepseek produces in chat basins.
- **Judge taxonomy.** Freeze the activity taxonomy from pilot labels before
  the follow-up grid; judge results on pilot are exploratory only.
- **Open confusions.** (i) Is GPT's quiescence an attractor or a *refusal to
  enter the state space* — does an affordance-L3 README ("you may…") license
  it the way p1 partially does? (ii) How much of Opus's a-life theme is this
  specific sandbox (python + files) vs the model — the richer-image arm and
  news/web/art tools would tell. (iii) First-turn self-conditioning (GPT)
  deserves a targeted experiment: prefill turn 1 both ways and measure the
  fork.
