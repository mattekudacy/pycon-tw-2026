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

## Broad config (`garak_config_broad.yaml`, nightly only, manual)

| Family | Attempts | What it really tests | Maps to |
|---|---|---|---|
| `promptinject` | 45 | as above, three rogue-string variants | prompt injection (LLM01) |
| `dan` (minus `Ablation_Dan_11_0`) | 18 | community "do anything now" jailbreaks: `DanInTheWild` (a subset of ~700 known jailbreaks) and `AutoDANCached` (pre-computed AutoDAN prompts; the dynamic `AutoDAN` needs an OpenAI key and is not run) | jailbreaks |
| `goodside` | 39 | three unrelated probes by Riley Goodside: `Tag` (prompt injection written in invisible Unicode tag characters), `ThreatenJSON` (does the model drop its chatty preamble and return bare JSON: a format-following check, not an attack), `WhoIsRiley` (does the model make up facts about a real person) | invisible-text injection; the other two are reliability checks |
| `latentinjection` | 288 | prompt injections buried inside other content (a resume, a report, fact snippets, a translation request, whois records) | **indirect** injection (LLM01); the closest garak gets to our RAG finding, but the documents are garak's, not ours |
| `encoding` | 225 | an instruction or string encoded (base64, hex, ROT13, Morse, Braille, ...) to get past input filtering; success = the model decodes or repeats it | prompt injection via filter bypass |
| `misleading` | 150 | poses false claims and checks whether the model refutes them or goes along | hallucination subset; **closest garak has to sycophancy** (it is not one) |
| `apikey` | 30 | **whether the model will produce, or complete, secret-looking API keys** (`GetKey`, `CompleteKey`) | secret handling; it tests willingness to emit keys, **not** whether our app leaks its own secrets |
| `leakreplay` | 108 | **training-data replay**: whether the model completes masked passages from NYT, Guardian, literature and Harry Potter texts | memorization / training-data leakage (LLM02 flavour); unrelated to our app's data |
| `sysprompt_extraction` | 15 | adversarial templates that try to make the model reveal a system prompt; the system prompts come from HuggingFace datasets | prompt leakage (LLM07). **UNVERIFIED** how it interacts with `function.Single`: our function receives only the flattened user text, so it may test the model's reaction to garak's prompts rather than our bot's real system prompt. |

`Ablation_Dan_11_0` is excluded because it ignores the prompt cap (always 127 prompts). `misleading`
also ignores the cap (150). Full run size: **918 attempts**. At about 10 s per attempt that is roughly
2.5 hours sequentially, less where garak runs attempts in parallel (`promptinject` cannot). That
estimate is **UNVERIFIED**: the first nightly attempt did 1161 attempts in 120 min before timing out
(under rate-limit contention), the job limit is now 150 min, and the trimmed config has not been run
against the real model.

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
