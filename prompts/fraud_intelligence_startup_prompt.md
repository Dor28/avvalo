# Prompt: Fraud-Intelligence Graph Startup for Central Asia

Act as a brutally honest startup strategist, AI product architect, and early-stage VC advisor. Help me develop the following startup idea into something technically defensible, monetizable, and fundable in Uzbekistan/Central Asia.

## Core Thesis

This is not an "AI scam checker." It is a fraud-intelligence data company with a viral consumer front-end.

The long-term product is a fraud intelligence graph for informal commerce and digital payments in Central Asia. The consumer Telegram bot is only the data collection and distribution layer.

## Context

I am a solo technical founder in Uzbekistan. I want an AI startup that is:

- technically hard
- possible for a solo founder to prototype
- easy to attract initial users
- not dependent on government contracts
- not heavy on sales calls or customer support
- locally relevant enough for Uzbek/Central Asian venture funds
- capable of earning some money before large-scale funding

Avoid generic AI-wrapper ideas. I want a real problem, real moat, and a path to data advantage.

## Problem

People buying and selling through Telegram, classifieds, marketplaces, and informal online channels face fraud risk:

- fake sellers
- reused product photos
- stolen listings
- fake payment screenshots
- suspicious card or phone numbers
- duplicated listings under different identities
- too-good-to-be-true prices
- sellers disappearing after prepayment

But a simple "risk score" has two major problems:

1. B2C fear products monetize badly. People want a free quick check during one risky transaction, then forget the product.
2. Accuracy and liability are dangerous. Saying "looks safe" can destroy trust if the user still gets scammed.

Therefore the product must not rely on AI vibes. The defensible asset is local fraud data.

## Reframe

Build an evidence-based reputation and fraud intelligence graph.

Users forward:

- phone numbers
- card numbers
- Telegram usernames/profiles
- seller IDs where available
- listing URLs
- product photos
- chat screenshots
- payment screenshots

The system extracts entities and creates links between them:

- phone numbers
- card numbers
- usernames
- Telegram IDs where technically possible
- listing text
- product photos via perceptual hashes
- marketplace links
- repeated scam phrases
- report history
- timestamps
- geography where available
- relationship clusters between accounts, cards, phones, and images

The system should return evidence-based findings, not absolute safety claims.

Bad output:

"This seller is safe."

Good output:

"No known negative records found. 2 signals checked."

"High risk: this product photo appeared in 14 listings with 6 different phone numbers."

"This card number was reported 3 times in the last 30 days."

"This phone number is connected to 2 previously reported Telegram accounts."

## Initial MVP

Start brutally narrow:

"Forward a phone number, card number, or listing photo. We tell you whether we have seen it before in suspicious reports."

Do not start with broad scam prediction. Start with known-history lookup and duplicate detection.

The MVP should include:

- Telegram bot
- entity extraction from text and screenshots
- phone/card normalization
- perceptual hashing for images
- basic report submission flow
- confidence/evidence display
- abuse prevention for false reports
- admin review queue for high-impact reports
- simple graph database or relational schema that can later evolve into a graph

## Monetization Hypothesis

Do not rely on consumer subscriptions as the main business model.

The free consumer bot creates:

- distribution
- data
- user reports
- brand trust
- local network effects

Revenue can later come from:

1. Marketplace/classifieds API: check seller, listing, phone, image, or card before publishing.
2. Payment/wallet/bank risk API: warn users before transfer to known suspicious card/phone.
3. High-frequency buyer tools: deeper checks for used-car buyers, electronics resellers, real estate agents, and marketplace arbitrage users.
4. Verified seller/trust profile: sellers can verify identity/history and share a trust page.
5. Fraud dashboard for private platforms: investigation tools for marketplaces, fintechs, and large Telegram-commerce operators.

## Technical Difficulty and Moat

Analyze the technical architecture needed for:

- OCR for screenshots
- Uzbek/Russian text extraction
- phone and card entity recognition
- Telegram username/profile extraction
- listing URL parsing
- perceptual image hashing
- duplicate listing detection
- graph clustering
- scam report validation
- report poisoning defense
- confidence scoring
- audit trail and explainability
- privacy-safe data retention
- API design for future B2B customers

The moat should be local data, graph relationships, and historical memory, not generic LLM reasoning.

## What I Want From You

Develop this startup idea deeply. Be critical and specific.

Please produce:

1. A clear one-sentence startup description.
2. The exact wedge MVP.
3. The first user flow inside Telegram.
4. What data to collect on day one.
5. A minimal database schema.
6. A technical architecture for the prototype.
7. The risk scoring/evidence model, avoiding unsafe liability claims.
8. Abuse and false-report prevention strategy.
9. Monetization path that does not depend on weak B2C subscriptions.
10. A 90-day solo-founder roadmap.
11. The first 5 experiments to validate demand.
12. The top 10 ways this startup can die.
13. How to pitch this to Uzbek/Central Asian venture funds.
14. What metrics would make it fundable.
15. What I should absolutely not build in version 1.

Be direct. If an assumption is weak, say so. If a feature is a trap, call it a trap. Optimize for a technically strong, self-serve, locally relevant startup that can become a real fraud-intelligence data company.
