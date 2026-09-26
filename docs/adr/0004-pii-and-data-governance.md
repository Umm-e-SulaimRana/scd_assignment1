# ADR 0004: PII and Data Governance for the AI Triage Layer

## Status
Accepted

## Context
Citizen complaints routinely contain names, phone numbers, and precise
addresses. §2.5 requires an explicit decision about what leaves the
machine when a hosted LLM provider is used, and to whom.

## Decision
- With `TRIAGE_PROVIDER=llm` (Groq): we send the complaint `text` and
  `location` fields only. `reporter_contact` is never included in the
  prompt sent to the provider.
- Per Groq's published terms (cited in the assignment handout), Groq's
  free tier does not retain prompts for training. We accept this as
  documented and do not redact `text`/`location` further, because doing
  so (e.g. stripping names) would materially degrade triage quality for
  addresses that legitimately need to stay intact ("Street 12, G-9").
- With `TRIAGE_PROVIDER=ollama`: nothing leaves the machine -- the model
  runs in a container on the same Docker network. This is the
  zero-PII-exposure path, and the one to switch to if the team decides
  Groq's data policy is unacceptable for a given deployment.
- The `RuleBasedTriage` fallback never makes a network call at all.

## Consequence
Anyone auditing this system can answer "what left our infrastructure and
why" by reading this file and `app/providers/triage/llm.py`'s prompt
(which explicitly excludes `reporter_contact`).
