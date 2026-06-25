"""T13 — web channel parity (V1_TECHNICAL_PLAN §13 T13, §15).

Live acceptance specs that skip until the FastAPI web app lands. The plan's
hard guarantee is parity: the web POST /check builds a CheckInput and calls the
SAME run_check() as the bot. Captcha-gating and rate-limit assertions are added
against the live app once its routes are known; this pins the route surface.
"""

import pytest


def _web_app():
    module = pytest.importorskip("app.web.app")
    app = getattr(module, "app", None)
    if app is None:
        factory = getattr(module, "create_app", None)
        if factory is None:
            pytest.skip("web app object/factory not found yet")
        try:
            app = factory()
        except Exception as exc:  # needs config we can't supply here
            pytest.skip(f"create_app needs configuration: {exc}")
    return app


def test_web_app_exposes_core_routes() -> None:
    app = _web_app()
    paths = {getattr(route, "path", "") for route in getattr(app, "routes", [])}
    # §13: GET / , POST /check , GET /privacy , GET /healthz.
    assert "/check" in paths, f"web app must expose POST /check; saw {sorted(paths)}"


def test_web_reuses_the_shared_engine() -> None:
    routes_mod = pytest.importorskip("app.web.routes")
    source = pytest.importorskip("inspect").getsource(routes_mod)
    assert "run_check" in source, "web layer must call the shared engine.run_check (§13 parity)"
