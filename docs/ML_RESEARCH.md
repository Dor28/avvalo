# Avvalo — ML Capabilities Research: what to add, what to skip, and how to train on user data legally

> **Status:** Deep-research report (web research, 2026-07-06) · commissioned by the founder
> **Question researched:** *"What ML can make the service more attractive — and can we train models on the data users send us?"*
> **Reads with:** [PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md) (this report refines §3.2, §5.2 and adds new candidates), [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) (privacy rules that constrain everything here).
> Sources are linked inline; vendor marketing claims are labeled as such.

---

## 0. The one-paragraph answer

**You cannot train on "data users sent" — and that's not a limitation, it's your positioning.** Submitted content is never persisted (enforced by tests, promised in the privacy notice, aligned with UZ law). But the industry leader does exactly what you do: Google's scam detection in Messages/Phone runs ephemerally on-device, stores nothing, and trains on nothing users send ([Google Security Blog](https://security.googleblog.com/2025/03/new-ai-powered-scam-detection-features.html)). The legal training path is the one already on your roadmap: the **opt-in, PII-minimized, founder-reviewed story corpus (R3)** — plus LLM-generated labels and curated public examples. And the research's biggest practical finding: **you need far less data than you think** — SetFit-style few-shot fine-tuning is competitive with full fine-tuning at **8–16 labeled examples per class** ([HuggingFace SetFit](https://huggingface.co/blog/setfit)), which means your corpus becomes ML-useful at *hundreds* of stories, not millions.

---

## 1. What the leaders ship (and what actually attracts users)

| Product | What it does | Lesson for Avvalo |
|---|---|---|
| **Bitdefender Scamio** ([product](https://www.bitdefender.com/en-us/consumer/scamio), [Tom's Guide test](https://www.tomsguide.com/computing/online-security/i-tried-3-ai-powered-scam-detectors-to-help-keep-me-safe-online-and-theres-a-clear-winner)) | Free AI chatbot on web/WhatsApp/Messenger/Discord; accepts image, email, text, link, QR; compares against rules + known-scam DB; **gives safe/dangerous verdicts** | Validates the chat-first checker UX. Note: it issues verdicts — viable in its jurisdictions, deliberately not in ours |
| **Norton Genie Scam Protection** ([Norton](https://us.norton.com/products/genie-scam-detector), [newsroom](https://newsroom.gendigital.com/2025-02-19-Norton-Launches-Enhanced-AI-Powered-Scam-Protection-Across-Cyber-Safety-Lineup)) | "Analyzes the meaning of words, not just links" across SMS/email/web; Pro tier adds AI call screening; deepfake-video check by upload | The frontier is **passive, always-on protection** (SMS/call screening), not manual checks — long-term direction, matches Group Guard |
| **Google (Gemini Nano on-device)** ([Security Blog](https://security.googleblog.com/2025/03/new-ai-powered-scam-detection-features.html), [9to5Google](https://9to5google.com/2025/05/08/chrome-enhanced-protection-gemini-nano/), [Android Police](https://www.androidpolice.com/android-scam-alerts/)) | Conversational scam-pattern detection in Messages/Phone; **ephemeral, nothing stored or sent**; Chrome uses Nano to extract "intent" signals for Safe Browsing; Pixel → Galaxy S26 (Feb 2026) | The giant converged on **your exact architecture**: LLM pattern analysis + ephemeral privacy. Avvalo can't out-model Google; it wins on **Uzbek/Russian patterns, local scam knowledge, verification coaching, and trust** |

**Takeaway:** Avvalo's current design is state-of-the-art in *shape*. The attractive additions are (a) evidence-flavored outputs ("matches a known circulating scam"), (b) more input types, (c) speed/cost via small models — all below.

---

## 2. Text classification: small fine-tuned models vs the hosted LLM

The benchmark literature is unusually consistent:

- Fine-tuned BERT-family models and GPT-4-class LLMs both reach **~96–99% F1 on phishing/spam benchmarks**; the gap is ~1–3 points ([MDPI comparative study](https://www.mdpi.com/2079-9292/13/11/2034), [phishing-LLM survey](https://www.sciencedirect.com/science/article/pii/S2590005626000986)). LLMs generalize better to novel scams; encoders are ~100× cheaper per call.
- **SetFit** (contrastive fine-tuning of sentence transformers) is competitive with full RoBERTa fine-tuning on 3k examples using **8 labeled examples per class** ([HF blog](https://huggingface.co/blog/setfit), [repo](https://github.com/huggingface/setfit)).
- **LLM-generated labels ≈ human labels** for training supervised classifiers ([ACL 2024](https://aclanthology.org/2024.nlpcss-1.9/)); active-distillation methods (PGKD, M-RARU) cut teacher-API costs further ([arXiv 2411.05045](https://arxiv.org/abs/2411.05045), [arXiv 2511.11574](https://arxiv.org/abs/2511.11574)). Cost-aware production studies conclude fine-tuned encoders beat LLM prompting on cost/latency at volume ([arXiv 2602.06370](https://arxiv.org/html/2602.06370v1)).

**Uzbek reality check:** usable Uzbek encoders exist — **UzBERT** (142M-word news corpus, beats mBERT; [arXiv 2108.09814](https://arxiv.org/pdf/2108.09814)), **BERTbek** (Latin script, beats mBERT on sentiment/topic/NER; [SIGUL 2024](https://aclanthology.org/2024.sigul-1.5.pdf)), UzRoberta; plus a growing benchmark ecosystem (NER corpus [Springer 2024](https://link.springer.com/article/10.1007/s10579-024-09786-0), POS tagging [LoResLM 2025](https://aclanthology.org/2025.loreslm-1.23.pdf)). Multilingual models (mBERT/XLM-R) consistently underperform these monolingual models ([Turkic CA survey](https://arxiv.org/html/2407.05006v1)); LLM *generation* in Uzbek still shows linguistic errors ([2025 study](https://www.tandfonline.com/doi/full/10.1080/23311983.2025.2600519)).

**Verdict for Avvalo:** the realistic architecture is a **cascade** — a small fine-tuned classifier (SetFit head on UzBERT/BERTbek or a multilingual embedding model) as the fast, cheap first pass; the hosted LLM stays for the *explanation* (generation quality in Uzbek still needs a big model) and for low-confidence cases. Train the classifier on: opt-in stories + curated public examples + LLM-distilled labels. **This is the "sovereign Uzbek scam model" from HORIZONS §5.2, made concrete — and it becomes feasible at ~300–500 corpus examples, not "someday."**

---

## 3. Embedding similarity — the most attractive feature nobody has locally 🏆

The approach: embed a curated corpus of known scam examples; at check time, embed the (minimized) incoming text and return nearest matches — *"this message is highly similar to the fake-delivery scam pattern circulating since June (matched against 14 community-donated examples)."* This is a production-proven pattern in phishing detection ([embedding-based phishing detection](https://arxiv.org/pdf/2012.14488); patented at scale [USPTO 11310270](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11310270)), and multilingual embedding models handle cross-language matching ([overview](https://medium.com/data-science/multilingual-text-similarity-matching-using-embedding-f79037459bf2)).

**Why this is the winner for Avvalo specifically:**
- It **recreates the emotional power of the retired "reported N×" evidence line — legally.** It matches *patterns*, never *people*: "similar to a known scam script" is a statement about text, not an accusation about a person.
- It's cheap: pgvector on the existing Postgres + one embedding call per check (~$0.0001); no training required.
- It makes the story corpus (R3) immediately valuable at ~**100–300 examples** — every donated story literally makes the next check smarter, which is also a beautiful community story ("your story protected 200 people this month").
- It compounds: the same corpus later trains the classifier (§2).

**Verdict: build** — directly after R3 produces its first ~100 reviewed examples.

---

## 4. URL/link intelligence — cheapest real detection lift

Today Avvalo classifies link *shape* (lookalike/shortener) but consults no reputation source. The free feeds are good and combinable:

- **Google Safe Browsing:** ~1.6M URLs — 17× more than PhishTank + OpenPhish combined ([blacklist analysis, ACSW](https://dl.acm.org/doi/10.1145/3373017.3373020))
- **PhishTank** (free API, community-verified), **OpenPhish** (free feed, 12 h updates), **URLhaus** (free REST, no auth, malware URLs) ([feed comparison](https://www.captaindns.com/en/blog/threat-intelligence-databases-explained))
- Combining sources cuts false negatives **15–30%** vs any single one ([Bolster comparison](https://bolster.ai/blog/phishing-threat-intelligence))

**Caveat that becomes an opportunity:** UZ-targeted phishing (fake click.uz/payme lookalikes, Uzbek-language lures) is likely underrepresented in global feeds — so Avvalo maintaining its **own Uzbekistan phishing-domain list** (seeded from checks where users confirm scams) becomes a genuinely unique data asset, publishable in the Pulse and sellable to banks later.

**Verdict: build early** — a lookup stage after signal extraction; days of work; the result line "this link appears in a phishing blacklist" is factual, sourced, and allowed by the safety contract.

---

## 5. Screenshot forensics (merchant face) — mostly skip, one exception

The honest picture: ELA-based detection works in lab settings ([ELA+deep learning, PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10167215/)) and commercial tools combine ELA + metadata + font checks into "trust scores" ([DocVerify](https://docverify.app/blog/fake-cash-app-screenshot-detection-payment-fraud), [FotoForensics-style tools](https://www.fakeimagedetector.com/) — vendor claims). But the limitations are disqualifying for your channel: **Telegram recompresses forwarded images**, destroying and creating compression artifacts; careful fakes are pixel-identical to real ones; a screenshot has no cryptographic tie to any server; smooth-edge composites evade frequency analysis. A "this screenshot is fake/real" feature would be **snake oil in your delivery channel** — and one confident false "looks genuine" costs a merchant real money and you the brand.

**The exception that does work: OCR field cross-checking.** Parse the receipt's *content* — does the amount match the order? Date plausible? Name match the buyer? Sender bank exists? These are deterministic, explainable, and robust to recompression. That plus the existing "verify in your real bank app" rule *is* the honest merchant product.

**Also viable later: perceptual hashing (pHash)** for reused/stolen listing photos — 64-bit DCT hashes, Hamming distance, robust to minor edits, >80% stolen-image detection at 1% FPR ([analysis](https://www.sciencedirect.com/science/article/pii/S1877050921011030), [copyright-protection study](https://www.researchgate.net/publication/365389392_Deep_perceptual_hash_based_on_hash_center_for_image_copyright_protection)). Needs an image corpus first (cold-start), and note pHash itself can be gamed ([Arkose Labs](https://www.arkoselabs.com/blog/how-perceptual-hashing-can-be-used-to-commit-fraud/)).

---

## 6. Voice-deepfake detection — do not claim it

Vendors advertise 94–99% accuracy ([Resemble AI](https://www.resemble.ai/resources/audio-deepfake-detection-tools) — vendor claims), but independent evaluations show the real state: open-source detectors caught synthetic audio only **~78% of the time with false positives on real voices** ([independent 3-tool test](https://www.kunalganglani.com/blog/deepfake-voice-detection-tools-tested)); detectors fail to generalize across cloning algorithms and degrade badly with noise/compression ([Frontiers forensic study](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1678043/full)) — and Telegram voice notes are exactly the compressed, noisy case. This is an arms race a solo founder cannot win, and a false "sounds real" is catastrophic.

**Verdict:** voice checks = **STT → text pipeline + the verification protocol** (call back on the known number, family control question) — which is also what Google ships (conversational pattern analysis, not audio forensics). Never market "deepfake detection."

---

## 7. Training on user data — the legal & practical playbook

- **Federated learning + differential privacy** is the formal answer ([TF Federated](https://www.tensorflow.org/federated/tutorials/federated_learning_with_differential_privacy), [Google Research](https://research.google/blog/distributed-differential-privacy-for-federated-learning/)) — and the wrong answer for Avvalo: FL is built for fleets of client devices; your inference is server-side, your team is one person, and the utility/privacy trade-off adds complexity without adding trust you can market.
- **The practical small-team stack** (what the evidence supports): explicit **opt-in donation** (R3 stories) → **PII minimization** → **human review** → curated corpus; **user feedback buttons as weak labels** (you already collect usefulness/next-action — start correlating them with rule hits: free active-learning signal); **LLM-distilled labels** for scale ([ACL 2024](https://aclanthology.org/2024.nlpcss-1.9/)); **LLM-generated synthetic variants** of known patterns to augment (never as the sole source). This matches your ZRU-547 posture: consent, purpose limitation, minimization.
- **Corpus milestones:** ~100 reviewed examples → similarity search (§3) ships · ~300–500 → SetFit classifier (§2) credible · few thousand → the self-hosted "sovereign model" IT Park story is real.

---

## 8. Final verdict table — build / skip for a solo founder

| Capability | Verdict | When | Data needed |
|---|---|---|---|
| Feedback-as-labels analytics (rule-hit × feedback correlation) | ✅ build | now — zero new collection | already have it |
| URL reputation stage (GSB + URLhaus + OpenPhish + own UZ list) | ✅ build | days of work, early | none |
| Embedding similarity vs story corpus ("matches known pattern") | ✅ build — **the flagship** | at ~100 reviewed stories | R3 corpus |
| Distilled small classifier (SetFit on UzBERT/BERTbek) as LLM pre-filter | ✅ build | at ~300–500 examples | corpus + LLM labels |
| OCR field cross-checks on receipts (merchant) | ✅ build | with merchant pilots | none |
| pHash reused-photo detection | 🔶 later | needs image corpus | opt-in images |
| ELA "fake screenshot detector" | ❌ hints only, never a verdict | — | — |
| Audio deepfake detection | ❌ don't claim | — | — |
| Federated learning / differential privacy | ❌ wrong scale | — | — |
| General Uzbek LLM fine-tune | ❌ (unchanged from prior research) | — | — |

**The through-line:** every ✅ either needs *no* user data or runs on the **consented story corpus** — which means R3 (story capture) is not just a content feature; it is the **ML data pipeline**. The flywheel gains a fourth loop: stories → similarity evidence → better checks → more users → more stories.
