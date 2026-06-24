# Avvalo — Executor Handoff Prompt

> Copy everything in the box below and give it to the coding model/agent that will build Avvalo. It assumes that model has access to this repository.

---

You are the implementing engineer for **Avvalo**, a Telegram-based AI safety assistant for Uzbekistan that helps ordinary people check a suspicious message, payment, or situation **before** they respond, pay, or share data. You are building **v1**: one shared backend engine with two thin Telegram-bot "faces" — **Family Shield** (free/consumer) and **Seller Guard** (paid/merchant). They share ~80% of the code; Seller Guard is a rule-pack + output-template delta, not a second product.

## Read these first, in order — then follow them exactly
1. **`docs/V1_TECHNICAL_PLAN.md`** — your build bible. Locked stack, architecture, data contracts, the safety validator, and the numbered build tasks **T1–T12** with acceptance criteria. Build in that order.
2. **`docs/V1_BUILD_SCOPE.md`** — what is in and out of scope, and why (one engine, two faces, for an IT Park grant demo).
3. **`docs/PRODUCT_GUIDE.md`** — the product vision and the **safety rules that override everything else**. If anything conflicts, this guide wins.

Skim `docs/FAMILY_SHIELD_VALIDATION.md` (behaviour + golden examples) and `docs/V1_MVP_PRODUCT_REVIEW.md` (why the design is shaped this way) for context.

## Non-negotiable constraints — violating any one is a critical failure
- **Never persist submitted content.** User text, images, OCR text, and model output are ephemeral: process them in RAM / a temp file, delete after the response, 1-hour hard TTL. They must never reach the database, logs, analytics, or backups. If you are about to store a user-supplied string, stop.
- **Honor the safety output contract.** Never output a verdict ("safe", "scammer", "fraud confirmed"), a risk score, or a claim that you checked an external source/database. Never repeat a full card number, OTP, or password. Never tell the user to open the suspicious link/QR or call the number inside the suspicious message. (Full list: plan §9 and `prompts/system_safety.txt`.)
- **Keep the privacy pipeline order.** Rules run on the RAW local text first → emit structured signals → THEN minimize PII → THEN call the LLM with minimized text + signals. The raw image never goes to the LLM.
- **Use the pre-authored assets — do not regenerate them.** The prompts (`prompts/system_safety.txt`, `family_shield.txt`, `seller_guard.txt`), the trilingual rule packs (`rules/family_shield/families.yaml`, `rules/seller_guard/families.yaml`), and the golden fixtures (`tests/fixtures/golden/*.json`) are hand-written and safety-reviewed. Wire code to load them. You may extend rule keywords or fix real bugs, but do not rewrite the prompts or weaken any safety wording without flagging it first.

## Stack — already decided, do not substitute
Python 3.11 · aiogram 3 · **LLM = Qwen via a neutral OpenAI-compatible host** (configured by `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`; one `app/engine/llm/openai_compat.py` adapter — host & model are env, not code) · Google Cloud Vision OCR (behind an interface; on-prem is a later swap) · PostgreSQL + SQLAlchemy/Alembic · Docker. Do not add a graph DB, a queue, Redis, a web framework, or a second LLM/OCR vendor.

## Your first action — run the model eval before writing engine code
The Uzbek quality of Qwen is an assumption that must be confirmed:
1. `pip install openai`
2. Set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (e.g. OpenRouter + `qwen/qwen-2.5-72b-instruct`; also try a current Qwen3 instruct).
3. Run `python tools/eval_models.py`. Report the rubric scores **and** your own read of the Uzbek outputs saved in `eval_out/qwen/` (natural Uzbek? grounded in the message? correct script? followed the 3-bullet structure?). If Qwen's Uzbek is broken or generic, flag it before proceeding — do not silently lock a weak model.

Then begin at **T1**.

## How to work
- Do **one task at a time**, in the T1→T12 order. Do not start the next task until the current task's **acceptance criteria** pass.
- After each task, report: what you built, which acceptance criteria pass and how you verified them, and any decision you had to make.
- Where the plan says "verify current docs" (Qwen host params, OpenAI SDK, aiogram 3, Cloud Vision), follow the current official documentation for the call specifics — but keep the interfaces defined in plan §6–§9 unchanged.
- If a task seems to require anything on the "do not build" list (plan §16: graph/person lookup, payments/subscriptions, web client, image forensics, content persistence), **stop and flag it** — it is out of scope by design.
- Ask before adding any dependency, service, or architectural pattern not listed in the plan.

Begin by confirming you have read the three primary docs, summarize the T1 task back in your own words, then start.

---

*This prompt mirrors the decisions in [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) and [V1_BUILD_SCOPE.md](V1_BUILD_SCOPE.md); if you update those, update this handoff too.*
