# Superseded: ML Capabilities Research

> **Status:** Historical research pointer only
> **Superseded for priority:** 2026-07-22 by [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md)

The earlier report explored classifiers, similarity search, user-donated stories, voice analysis,
URL reputation, and image techniques. It is not an implementation plan.

Current rules:

- do not train on or retain submitted content;
- do not build pattern similarity or a classifier as a current product feature;
- do not claim screenshot, document, or deepfake authenticity;
- keep any already-built URL-reputation stage local, hash-based, source-attributed, and disabled
  until production verification permits rollout;
- implement no new ML capability unless the active roadmap explicitly authorizes it.

Research history remains available in git history if it is needed for a future evidence-backed
decision.
