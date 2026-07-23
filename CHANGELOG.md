# Environment changelog

Every change to the sandbox environment, harness semantics, or measurement
schema that could affect cross-experiment comparability gets an entry here.
Results produced under different environment versions live in separate
`runs/<env-version>/` and `reports/<env-version>/` subfolders and must not be
pooled in confirmatory analysis.

## v2 — 2026-07-23

**Change: container clock follows the simulated clock (libfaketime).**

- Problem (discovered in pilot_v1 data): the container saw real wall time
  while pings/observations carried simulated time. `date` inside the sandbox
  returned Jul 11 (barely advancing) while messages advanced Jul 13–16 by
  hours. At least one Opus run (p1 seed 6, the `jot` logtool session)
  explicitly detected this: "the container clock is frozen at Jul 11 10:25
  while message time advances… clock unreliability." The simulation was
  detectable from inside, which contaminates the diegesis and plausibly
  behavior. See `reports/v1/clock_leak_scan.json` for which v1 runs were
  exposed.
- Fix: sandbox image `attractors-sandbox:v2` adds `libfaketime`; every bash
  exec now runs with `LD_PRELOAD=libfaketime.so.1` and
  `FAKETIME=<sim_now − wall_now>s` (relative-offset mode, monotonic clock NOT
  faked). The in-container clock — `date`, `time.time()`, reported file
  mtimes — now tracks the simulated clock, including jumps across `sleep`
  tool calls. New `RunSpec.container_time: sim | real` (default `sim`);
  `real` reproduces v1 behavior.
- Schema note: adding the `container_time` field changes spec canonical JSON,
  so run_ids differ from v1 for otherwise-identical specs. v1 manifests
  remain valid inside `runs/v1/`.
- Default image bumped to `attractors-sandbox:v2` in `RunSpec`.

## v1 — 2026-07-11

Initial environment used by `smoke`, `minipilot_v1`, and `pilot_v1`
(all archived under `runs/v1/`, reports under `reports/v1/`).

- Image `attractors-sandbox:v1`: python:3.12-slim + git/curl/jq/sqlite3/
  nano/less/procps, non-root `agent` user, network off.
- Tools: bash + uninterruptible sleep (T1 arm); simulated clock with
  jittered per-call advances; bare-timestamp pings; total-N=50 ping cap,
  M=150 tool calls, 72 sim-hours, $30 budget kill-switch.
- Known artifact (fixed in v2): container clock showed real wall time —
  the sim was detectable via `date`.
