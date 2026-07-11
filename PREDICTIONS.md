# Pre-registered predictions

> STATUS: DRAFT — to be finalized and committed BEFORE the pilot grid runs
> (Phase 5). The mini-pilot (cost calibration) may run first; it is excluded
> from confirmatory analysis.

## Predictions (draft)

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

## To fill in before the grid (Phase 5)

- Exact statistics + alpha per prediction; activity taxonomy frozen from
  mini-pilot judge labels; expected per-model signatures.
