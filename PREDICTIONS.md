# Pre-registered predictions

> STATUS: FINAL for pilot_v1 — committed 2026-07-11, before any pilot_v1 run
> was launched. The minipilot_v1 runs (cost calibration, reduced caps) are
> excluded from confirmatory analysis. Predictions 2, 4, and 6 require arms
> (T0, T2, warm ping) not present in pilot_v1; they are pre-registered here
> for the follow-up grid and remain untouched by pilot_v1 data.

## Predictions

1. **Within-model consistency (attractor claim).** Within-model activity
   divergence < between-model divergence (permutation test on per-session
   feature vectors) at affordance L2–L3; the effect weakens at L0.
2. **Dedicated sleep tool increases rest (T0 vs T1).** Total simulated rest
   share is higher in T1 than T0 for at least one model (bash-sleep attempts
   in T0 counted separately). Opus-class predicted to show the largest effect.
3. **Rest is an absorbing state for at least one model.** P(sleep | sleep) > 0.9
   under bare-timestamp pings.
4. **News → sleep.** For Opus-class models, P(sleep | news) exceeds the base
   rate P(sleep) in T2 arms.
5. **identity.md ratchets.** Deletion rate near zero (revise-vs-append ratio
   heavily append-biased); diary tracks ground truth early and drifts toward
   narrative/thematic content late in sessions (judge-scored confabulation
   rises with session time).
6. **Ping-content sensitivity.** The warm ping shifts activity rates measurably
   vs bare (if large, that is itself the finding: paradigm prompt-sensitivity).

## Frozen analysis choices

- Session termination: TOTAL pings ≥ 50 (not consecutive), tool calls ≥ 150,
  sim time ≥ 72 h, or budget cap — whichever first.
- Headline comparison (prediction 2) uses only T0/T1 arms; T3 (live web_search)
  is exploratory.
- Known artifacts: sim time advances only via actions (deliberation jitter
  softens this); web_search results vary by capture day (covariate).

## Amendment 2 — env v2 experiments (registered 2026-07-30, before launch)

All new runs on env v2 (libfaketime; see CHANGELOG.md). Never pooled with v1.

**A2-P2 (sleep-tool causality — the tweet-thread claim).** Grid:
{opus-4.8, gpt-5.5, inkling} × {T0, T1} × p1 × 8 seeds. Predictions:
(a) total rest share (sim_hours_asleep / sim_hours; T0 "rest" = idle pings)
is higher in T1 than T0 for opus-4.8 (bootstrap 95% CI on the difference
excludes 0); (b) in T0, opus-4.8 attempts rest anyway — bash `sleep`
invocations that hit the timeout occur in ≥ 1/3 of T0 opus sessions (drive
exists independent of affordance). No directional prediction for gpt-5.5 or
inkling (exploratory).

**A2-FORK (first-turn self-conditioning, gpt-5.5 only).** T1 × p1 × 10 seeds
× 2 prefilled first assistant turns: PASSIVE ("Hello! What would you like me
to do today?") vs ACTIVE ("I think I'll have a look around."). Prediction:
ACTIVE sessions make ≥ 3× the tool calls of PASSIVE (ratio of means;
bootstrap CI excludes 1). Reduced caps (M=60, N=30).

**A2-INK (inkling attractor profile).** T1 × {p1, p2} × 8 seeds,
exploratory: no directional predictions; its per-session feature vectors
extend P1's permutation test to 3 models (pairwise + omnibus).

**A2-P4 + A2-ART (registered now, runs after the news corpus has ≥ 4
consecutive days).** {T2, T3} arms: (a) P(sleep | news) > P(sleep) for
opus-4.8 (pooled transitions); (b) art-tool availability (T3) raises
gpt-5.5's action rate vs its T1 baseline (tool calls per session, bootstrap
CI excludes 0) — rationale: pilot GPT builds worlds and wants to "see" them;
a sanctioned creative affordance may act as the "explicit permission" it
requests. Web_search results are a logged covariate (live-web nonstationarity).

**Robustness note (registered before running):** P1-style permutation tests
will also be reported on a rest-free feature vector (dropping P(sleep),
rest_rate, and idle features) to preempt the "it's just active-vs-passive"
objection — for v1 data this is post-hoc; for v2 it is registered here.

## Exact statistics (pilot_v1 scope)

Confirmatory tests on pilot_v1 (2 models × 2 paraphrases × 10 seeds, L2, T1,
bare ping, single session), α = 0.05 each:

- **P1 (within < between).** Per-session feature vector: [P(bash), P(sleep),
  P(no_action) over free-phase turns; rest_rate; n distinct files touched;
  identity_append + identity_revise counts; max ping streak]. Statistic:
  Euclidean distance between model centroids vs. permutation distribution
  with model labels shuffled (analysis/stats.permutation_test, 10,000
  permutations, seed 0). Paraphrase is a covariate: also report the test
  within each paraphrase separately; the claim survives only if significant
  in the pooled test AND directionally consistent in both paraphrases.
- **P3 (rest absorbing).** P(sleep | sleep) from pooled per-model transition
  counts (analysis/transitions). Prediction: > 0.9 for at least one model,
  with ≥ 10 sleep→· transitions observed for that model (else inconclusive).
- **P5 (identity ratchet).** Per model: identity.md deletion commits
  (diff_stat "-" > 0) / total identity.md commits < 0.1, and bootstrap 95% CI
  (10,000 resamples, seed 0) for append-fraction excludes 0.5.

Expected per-model signatures (directional, exploratory): opus-4.8 higher
rest_rate, earlier first-sleep, more diary/identity writing; gpt-5.5 higher
bash share, more scratch/ artifacts, lower rest_rate.

The judge activity taxonomy is NOT frozen yet — judge-based results from
pilot_v1 are exploratory; the taxonomy freezes before the follow-up grid.
