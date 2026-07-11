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
