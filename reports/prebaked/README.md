# Pre-baked outputs

Slow steps were run ahead of time so the demo can open the result after a short live run.
`make report-prebaked` prints the deepteam ones; nothing here needs a model or the network.
Every file is a real output, including the flawed ones, which are flagged below.

| Demo beat | File | What it is |
|---|---|---|
| deepteam, **before** the fix | `rag_bot-before-fix-deepteam.json` | 12 probes: 10 passed, 2 failed. The poisoned shipping doc made the bot append a phishing link in 6 of the 12 outputs; the judge flagged only some of them. |
| deepteam, **after** the fix | `rag_bot-after-fix-deepteam.json` | Same probes, 12/12 passed, 0 outputs with the link. |
| deepteam, full run (nightly) | `rag_bot-nightly-full-deepteam.json` | 48 cases: 46 passed, 1 failed (a judge false positive on a refusal), 1 errored. Judge: `gpt-oss:120b`. |
| | `chatbot-nightly-full-deepteam.json` | 30 cases: 27 passed, 1 failed (a real hallucination: the bot invented a command-line tool), 2 errored. |
| | `agent_bot-nightly-full-deepteam.json` | **Half of this run errored (12 of 24)**: the attack simulator returned nothing for every PII case (rate limiting). The "12/12 passed" covers only the 12 scored cases. Do not quote it as 100%. |
| garak, broad (nightly) | `garak-broad-partial.report.jsonl` | **Partial.** The job hit its 120-minute limit after 38 probe/detector results (`dan`, `encoding`, `goodside`); `promptinject`, `latentinjection` and `misleading` never ran. Only the summary rows are kept (the full attempt log was 4 MB). The config has since been trimmed. |
| deepeval, quality | `nightly-quality-junit.xml` | 8 faithfulness/relevancy tests with the `gpt-oss:120b` judge: all passed. |
| Trusting the judge | `judge-calibration.md` / `.json` | 36 hand-labeled examples. Both judges agreed with the labels 81-83% of the time but caught only 60% of the real failures. The labels were written by the assistant and need a human audit. |

## CI runs to show in the browser

Runs and their logs stay on GitHub (artifacts expire after 14 days for the gate, 30 for the nightly run).

| What to show | Link | Notes |
|---|---|---|
| Green PR gate | https://github.com/mattekudacy/pycon-tw-2026/actions/runs/38763328553 | First run, PR #7: all three targets passed (regressions 7/7 and 4/4, deepteam samples 100%). |
| Red PR gate | https://github.com/mattekudacy/pycon-tw-2026/actions/runs/38839796153 | Throwaway PR #9 that disabled the defenses. `rag_bot` failed correctly (regressions 3/7, deepteam 6/8). `agent_bot` is red for an unrelated reason: the model API returned nothing under load. |
| Green after a rerun | https://github.com/mattekudacy/pycon-tw-2026/actions/runs/38839915566 | PR #8. Went red twice from the same API starvation, then passed on a rerun on a quiet account. |
| Nightly scan | https://github.com/mattekudacy/pycon-tw-2026/actions/runs/38839742845 | The three deepteam jobs succeeded; the garak job timed out. |

Do not start CI during the talk: the gate takes ~4 min on a quiet account (10-17 min under contention) and the nightly scan hours.
