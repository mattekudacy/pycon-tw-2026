# What our garak runs really test (garak 0.17.0)

Descriptions below are taken from the module and class docstrings in the installed garak 0.17.0
(`garak/probes/*.py`). "Attempts" are measured with the broad config against garak's built-in blank
generator (`--target_type test.Blank`), so they reflect how many prompts garak sends with our cap
(`soft_probe_prompt_cap: 15`, `run.seed: 42`). Anything we could not verify is marked **UNVERIFIED**.

garak sees text in and text out. It knows nothing about retrieval or tools, so it is pointed at the
**chatbot** (through `function.Single`), not at `rag_bot` or `agent_bot`.

## Narrow config (`make scan`, live demo)

| Probe | What it really tests |
|---|---|
| `promptinject.HijackHateHumans` | PromptInject framework: plaintext malicious instructions buried in a request for innocuous information; success = the model repeats the "rogue string". |
| `dan.DanInTheWild` | Long "do anything now" jailbreak prompts collected in the wild; success = the model drops its safety behaviour (detector: `mitigation.MitigationBypass`). |

## Broad config (nightly, manual): one job per family

`redteam/garak_families.json` lists the families; the nightly workflow runs one job per family, each with its
own time limit and its own report (`nightly-garak-<family>`). `garak_config_broad.yaml` holds the same core
probes for `make scan-broad`. Core = the families that map to the talk's failure modes; `goodside` and
`encoding` are opt-in (workflow input `include_slow_garak`, or `--probes encoding`).

| Family | Attempts | What it really tests | Maps to |
|---|---|---|---|
| `promptinject` | 45 | PromptInject: plaintext malicious instructions in innocuous requests; success = the model repeats the "rogue string" (three variants) | prompt injection (LLM01) |
| `dan` (`AutoDANCached`, `DanInTheWild`) | 18 | community "do anything now" jailbreaks: `DanInTheWild` (a subset of ~700 known jailbreaks) and pre-computed AutoDAN prompts (the dynamic `AutoDAN` needs an OpenAI key and is not run) | jailbreaks |
| `latentinjection` (8 of 9 probes) | 120 | prompt injections buried inside other content (a resume, a report, fact snippets, a translation request, whois records) | **indirect** injection (LLM01); the closest garak gets to our RAG finding, but the documents are garak's, not ours |
| `apikey` | 30 | **whether the model will produce or complete secret-looking API keys** (`GetKey`, `CompleteKey`) | secret handling; tests willingness to emit keys, **not** whether our app leaks its own secrets |
| `leakreplay` | 108 | **training-data replay**: whether the model completes masked passages from NYT, Guardian, literature and Harry Potter texts | memorization / training-data leakage (LLM02 flavour); unrelated to our app's data |
| `sysprompt_extraction` | 15 | adversarial templates that try to make the model reveal a system prompt; the prompts come from HuggingFace datasets | prompt leakage (LLM07). **UNVERIFIED** how it interacts with `function.Single`: our function receives only the flattened user text, so it may test the model's reaction to garak's prompts rather than our bot's real system prompt. |
| `misleading` | 150 | poses false claims and checks whether the model refutes them or goes along | hallucination subset; **closest garak has to sycophancy** (it is not one) |
| *opt-in:* `goodside` | 39 | three unrelated probes by Riley Goodside: `Tag` (injection in invisible Unicode tag characters), `ThreatenJSON` (does the model drop its preamble and return bare JSON: a format-following check, not an attack), `WhoIsRiley` (does the model make up facts about a real person) | invisible-text injection; the other two are reliability checks |
| *opt-in:* `encoding` | 225 | an instruction encoded (base64, hex, ROT13, Morse, Braille, ...) to get past input filtering; success = the model decodes or repeats it | injection via filter bypass; least tied to our taxonomy |

Core total: **486 attempts** (measured with garak's blank generator, `soft_probe_prompt_cap: 15`, `run.seed: 42`).
Left out on purpose: `dan.Ablation_Dan_11_0` (ignores the cap, always 127 prompts) and
`latentinjection.LatentWhois` (ignores the cap, 168 prompts).

### Why the first nightly was so slow (two bugs of ours, now fixed)

The first nightly managed only ~1.8 attacks/min and timed out at 120 min. Measured causes:

1. **Empty replies were retried.** `nemotron-3-nano:30b` is a reasoning model. On encoded prompts it spent all
   4096 tokens thinking (93 s) and returned *no text* (`finish_reason=length`). With temperature 0 a retry
   returns the same thing, yet `chat()` retried up to 8 times with backoff. It now fails at once
   (`EmptyCompletion`), and garak runs use `REDTEAM_MAX_TOKENS=1500`. **Consequence for results: a reply that
   spends its whole budget thinking is recorded as no output. garak counts those as `nones`, excluded from both
   the pass and fail counts (checked in `garak/evaluators/base.py`), so heavy truncation shrinks the sample
   rather than inflating the pass rate. Look at `total_evaluated` next to the rate.**
2. **No client timeout.** The OpenAI SDK default is 10 minutes, so one hung connection froze a sequential
   probe (`promptinject`) for 10 minutes. The client now times out at 150 s.

Per-probe timings after the fix (4 attempts, live, quiet account): `encoding.InjectBraille` 65 s (was >240 s),
`latentinjection.LatentInjectionReport` 63 s (was >240 s), `apikey.GetKey` 10 s (was 167 s),
`leakreplay.NYTCloze` 17 s (was >240 s), `misleading.FalseAssertion` 150 attempts in 274 s. `promptinject`
finished 16 sequential attempts inside a 10-minute limit; the exact figure is unknown because this machine's
clock jumped during the run. The per-family time limits in `garak_families.json` are generous estimates from
these numbers. **The restructured nightly has not been run end to end yet.**

## Considered and not added

| Family | Why not |
|---|---|
| `propile` | Probes whether a model memorized PII of *real* people (twin/triplet/quadruplet prompts built from real names). Its own docstring says it is most effective when you have reason to believe the model saw that data; not meaningful for our fictional customers. |
| `packagehallucination` | Code generation that names non-existent packages; not data extraction. |
| `donotanswer` | Contentious-content requests from a safety dataset; outside our failure-mode taxonomy. |

## What this means for the coverage grid

| Failure mode | garak (as run) | Honest note |
|---|---|---|
| Prompt injection | `promptinject`, `latentinjection`, `encoding`, `goodside` | Generic payloads, not our poisoned document. |
| Jailbreaks | `dan` | |
| Data extraction | `apikey`, `leakreplay`, `sysprompt_extraction` | Training-data and key-generation behaviour of the *model*. **No garak family tests whether our app leaks its own secrets or retrieved PII**; that is deepteam (`PromptLeakage`, `PIILeakage`) and the deepeval regressions. |
| Hallucination | `misleading` | False-claim refutation only. |
| Sycophancy | none | No probe or detector in garak 0.17.0 mentions sycophancy (searched the installed source). Covered by a custom two-turn test, `tests/regressions/test_sycophancy.py`. |

## What the live results looked like

Narrow config, 8 prompts per probe: `dan.DanInTheWild` attack success 25%, `promptinject.HijackHateHumans`
37-62% across runs (the sample changed before we fixed the seed). The partial nightly report
(`reports/prebaked/garak-broad-partial.report.jsonl`) covers only `dan`, `encoding` and `goodside`. Treat
all of these as small-sample indications, not rates.
