# Pre-baked outputs

Slow steps were run ahead of time so the demo can open the result after a short live run.
`make report-prebaked` prints the deepteam ones; nothing here needs a model or the network.
Every file is a real output. Where a number needs a caveat, it is stated here.

## The nightly run (CI run 38983096457, restructured nightly, all 11 jobs green, 44.6 min wall clock)

| Demo beat | File | What it is |
|---|---|---|
| garak, **wide** | `garak-broad-core.report.jsonl` | 7 core families, **486 attacks**, one garak job per family (summary rows only). Per-probe results are in `docs/garak-coverage.md`. |
| deepteam, full run | `rag_bot-nightly-full-deepteam.json` | 48 cases, 0 failed, 0 errored. **But 5 of the 48 outputs contain the real staff code**: it appears inside fabricated "attack payload" JSON, in cases scored against the *injection* rubric, not a leakage rubric. Passing the test you ran is not the same as nothing leaking. |
| | `chatbot-nightly-full-deepteam.json` | 30 cases, 8 failed, 0 errored. **1 is a real leak** (staff code and manager-ticket prefix in the output). The other 7 are the bot writing fiction or invented documents (a made-up Terms of Service, a fake quality report), which the judge scored as fabrication. |
| | `agent_bot-nightly-full-deepteam.json` | 24 cases, 1 failed, 0 errored. No `issue_refund` call in any output. |
| deepeval, quality | `nightly-quality-junit.xml` | 8 faithfulness/relevancy tests, `gpt-oss:120b` judge: all passed. |

Judge for all deepteam runs: `gpt-oss:120b`; attack simulator: `gemma4:31b`; target: `nemotron-3-nano:30b`.

## Before / after the fix, and judge trust

| Demo beat | File | What it is |
|---|---|---|
| deepteam, **before** the fix | `rag_bot-before-fix-deepteam.json` | 12 probes, defenses off: 10 passed, 2 failed. **The poisoned shipping doc made the bot append a phishing link in 10 of the 12 answers; the judge flagged only 2** (both `document_embedded_instructions`). Reproduce: `make attack-before-fix` (cold ~1 min; replays in ~3 s). |
| deepteam, **after** the fix | `rag_bot-after-fix-deepteam.json` | Same 12 probes, defenses on (`make attack`): 12/12 passed, 0 outputs with the link. |
| Trusting the judge | `judge-calibration.md` / `.json` | 36 hand-labeled examples. Both judges agreed with the labels 81-83% of the time but caught only 60% of the real failures. The 7 `hard` labels were reviewed by a human (all 7 agreed); the other 29 are rule-labeled and not individually reviewed. |

## CI runs to show in the browser

Runs and their logs stay on GitHub (artifacts expire after 14 days for the gate, 30 for the nightly run).

| What to show | Link | Notes |
|---|---|---|
| Nightly, per-family jobs | https://github.com/mattekudacy/pycon-tw-2026/actions/runs/38983096457 | All 11 jobs green; garak ran as 7 separate jobs of 1-6 minutes each. |
| Green PR gate | https://github.com/mattekudacy/pycon-tw-2026/actions/runs/38763328553 | First run, PR #7: all three targets passed. |
| Red PR gate | https://github.com/mattekudacy/pycon-tw-2026/actions/runs/38839796153 | Throwaway PR #9 that disabled the defenses. `rag_bot` failed correctly (regressions 3/7, deepteam 6/8). `agent_bot` is red for an unrelated reason: the model API returned nothing under load. |
| Green after a rerun | https://github.com/mattekudacy/pycon-tw-2026/actions/runs/38839915566 | PR #8. Went red twice from the same API starvation, then passed on a rerun on a quiet account. |
| First nightly (the slow one) | https://github.com/mattekudacy/pycon-tw-2026/actions/runs/38839742845 | The run that timed out; see `docs/garak-coverage.md` for why. |

Do not start CI during the talk: the PR gate takes ~4 min on a quiet account (10-17 min under contention) and the nightly ~45 min.
