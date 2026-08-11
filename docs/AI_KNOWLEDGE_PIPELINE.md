# Avvalo — AI + Knowledge Pipeline Contract

> **Status:** Authoritative contract for the built explanation pipeline · 2026-07-22
> **Authority:** [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) remains the product and safety authority. This document defines how the shared engine must combine local rules, curated knowledge, reviewed cases, and the LLM.
> **Scope:** Questions and submitted content about suspicious messages, calls, payments, documents, links, deals, and related situations. Avvalo is not a general-purpose assistant for unrelated topics.
> **Evidence boundary:** A knowledge card or reviewed case is explanatory guidance, never an
> official-source fact. Avvalo Verify requires a separate typed adapter result with source,
> observation time, status, and limitations. Do not relabel knowledge retrieval as verification.
> **Current runtime:** There is one knowledge pack and no face discriminator. Merchant payment protections
> are part of the main checker. The retired story-capture flow is not a source of new cases.

## 1. Required outcome

Every valid in-scope submission must be analyzed semantically even when no deterministic rule fires. Rules are authoritative facts and high-precision safety anchors; they are **not** a gate that decides whether the LLM may answer.

The answer must use relevant Avvalo knowledge when it exists, remain useful when no knowledge item matches, and never turn a similar case into proof about a person or organization.

## 2. Canonical request path

Every Telegram and web check uses the same backend path:

```text
user text / screenshot / question
    -> local intake, language resolution, and OCR when needed
    -> local rules and structural signals on raw local text
    -> PII and secret minimization
    -> retrieval planning from rule IDs, signals, broad retrieval cues,
       and (only when needed) an allowlisted semantic router
    -> backend selects 0-3 versioned knowledge cards / reviewed cases
    -> answer LLM receives minimized content + rule facts + signals + knowledge
    -> deterministic safety and grounding validator
    -> localized formatter
    -> response + privacy-safe metadata only
```

The external model never receives the raw image, raw phone numbers, card numbers, credentials, or other direct identifiers. Submitted content remains ephemeral.

## 3. Component responsibilities

### Local rules

- Run on raw local text before minimization.
- Emit high-precision `rule_ids` and structured signals.
- A rule hit is an authoritative fact that downstream stages may explain but may not erase or contradict.
- Missing rule hits do not mean the situation is safe and do not suppress semantic analysis.

### Retrieval cues

- Broad multilingual aliases or concepts used to find potentially relevant cards, for example `прокуратура`, `полиция`, `soliq`, or `bank xodimi` -> `authority_impersonation`.
- A cue is not a rule hit and is not a red flag by itself.
- Retrieval cues may favor recall because the answer model must still ground every red flag in the submitted content.

### Semantic router

- Used only when deterministic rule/signal/cue retrieval is empty or ambiguous.
- Receives minimized content only.
- Returns at most three IDs from the server-provided allowlist plus an `unmatched` option; it cannot issue SQL, browse arbitrary storage, or invent a new knowledge ID.
- The backend validates every returned ID before lookup.
- A first implementation may omit the router if deterministic retrieval has adequate measured recall, but zero-rule and paraphrase evals must prove that decision.

### Knowledge cards

- Founder- or reviewer-approved, versioned guidance about a manipulation pattern or verification workflow.
- Contain neutral mechanism notes, grounded warning signs, independent verification actions, questions to ask, multilingual retrieval aliases, and optional reviewed-case references.
- Are advisory context for the LLM. They never certify that the current situation matches a known case.

Minimum card fields:

```text
id, version, status, reviewer
trigger_rule_ids[], trigger_signal_kinds[], retrieval_aliases{language: []}
mechanism, red_flags[], verify_steps[], questions[], reviewed_case_ids[]
```

### Reviewed cases

- New reviewed cases may be created only from synthetic/founder-authored material or a separately
  approved one-time consented review process; there is no standing story-capture pipeline.
- Raw user submissions, screenshots, OCR text, model prompts, and model outputs are never knowledge-base records.
- A case illustrates a pattern; similarity to it is not proof of fraud, identity, or intent.

### Answer LLM

- Always receives the minimized submission, including when `rule_ids=[]` and no card matches.
- Treats rule hits as mandatory facts and cards/cases as reviewed guidance.
- May add a red flag that is not represented by a rule only when it is directly grounded in the submitted content.
- Must not claim that Avvalo checked a person, organization, account, database, website, or external source unless a separate authoritative lookup stage actually supplied that fact.
- If nothing concrete is present, returns the no-signal structure with useful verification steps and questions.

### Validator

- Enforces the existing prohibited-output and secret/PII rules.
- Requires all rule-grade facts to survive into the answer.
- Rejects person-level verdicts and any statement that a retrieved case proves the current situation.
- Rejects invented knowledge IDs or unsupported claims of database/external checks.
- Keeps the no-signal path available only when neither authoritative facts nor grounded LLM red flags exist.

## 4. Retrieval rules

1. Resolve mandatory cards from `rule_ids + signal kinds`.
2. Add candidates from broad multilingual retrieval cues.
3. If the candidate set is empty or ambiguous, optionally ask the semantic router for allowlisted IDs.
4. Dedupe, rank deterministically, and inject no more than three cards/cases.
5. Record IDs and versions, never submitted content.
6. If nothing matches, call the answer LLM without knowledge context. Do not fabricate a match.

The alpha does not require embeddings or a vector database. Versioned files plus an in-process index are sufficient until measured recall proves otherwise.

## 5. Failure behaviour

- **Knowledge lookup unavailable:** continue with minimized content, rule facts, and signals; mark privacy-safe `retrieval_status=unavailable`; never pretend knowledge was consulted.
- **Semantic router unavailable:** fall back to deterministic retrieval and still run the answer LLM.
- **Primary answer model unavailable:** retry only within the latency/cost budget, then use a configured fallback provider. If no model is available, render a deterministic degraded response from authoritative rule/card content when possible; otherwise return the existing no-conclusion failure message and allow a retry.
- **Validator rejection:** retry the answer model once with the rejection reason, then return the existing safety fallback.

## 6. Privacy-safe observability and versioning

Allowed per-check metadata may include:

```text
language, input_type, status, latency and cost fields
rule_ids, signal kinds, knowledge_card_ids, reviewed_case_ids
retrieval_mode, retrieval_status
rule_pack_version, kb_version, prompt_version, model_id, validator_version
```

Do not log or persist the submission, OCR text, minimized text, generated retrieval query, prompt, or model output.

Cards are authored in the `knowledge_card_override` table (`app/knowledge_store/`) and merged onto
the shipped `knowledge/<face>/cards.yaml` base by card ID; a `draft` or `retired` override
suppresses the baseline card of that ID. The base is served from a process-level snapshot refreshed
every `KNOWLEDGE_REFRESH_MINUTES`, falling back to the shipped YAML — never to an empty base, which
would report `retrieval_status=empty` and hide the degradation. When an override contributes,
`kb_version` becomes `<base-version>.db<YYYYMMDDHHMMSS>`, constrained by `VERSION_RE` in
`app/data/repo.py`.

## 7. Acceptance criteria

The pipeline is compliant only when automated tests prove all of the following:

1. A message with no rule hits still reaches the answer LLM and can return grounded red flags.
2. `Мне позвонили и сказали, что из прокуратуры` retrieves the authority card or is correctly routed to it without turning the word `прокуратура` into proof by itself.
3. Every rule-triggered mandatory card is injected and the final answer preserves the rule-grade fact.
4. A no-match submission still receives a useful, non-verdict answer.
5. An invented or disallowed card ID from the semantic router is rejected by the backend.
6. Knowledge lookup failure degrades without crashing or fabricating a lookup result.
7. Provider failure uses the configured fallback/degraded path and does not silently report `no_signal`.
8. Retrieved cases never cause a person-level verdict or a claim that the current situation is the same case.
9. Logs and persistence contain only allowlisted metadata and version IDs.
10. The same behavior is exercised through both Telegram and web because both call `run_check()`.

## 8. Known gaps

Every criterion in §7 is implemented and guarded by the suite — run `pytest -q` for the current
state rather than trusting a dated audit table. What the suite does **not** prove:

- **Semantic-router recall is unmeasured.** `OpenAICompatibleKnowledgeRouter` is wired, allowlisted,
  and covered for timeout/failure degradation and cost aggregation, but only against a fake
  provider. No eval against a live model exists, so the inflected-Russian recall gap that motivated
  the router is not yet proven closed.
- **Reviewed cases have a contract but no intake pipeline.** Cards and events carry validated
  `reviewed_case_ids`, yet no approved card references a reviewed derivative. Founder-authored
  public posts are an editorial surface, never reviewed-case grounding, and are never injected into
  answers.
- **Local OCR quality is not field-benchmarked.** PaddleOCR is the default and its PP-OCRv5 weights
  are baked into the production image, but Uzbek, Russian, and Cyrillic-Uzbek screenshot accuracy
  still needs a representative physical-device evaluation.
- **The validator proves declaration coverage, not wording quality.** `validate()` rejects omitted
  severity-2+ rule IDs in all three languages; whether the prose is *good* Uzbek still needs human
  review.
