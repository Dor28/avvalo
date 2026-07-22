"""Static checks for deployment privacy guardrails."""

import asyncio
import re
from pathlib import Path

import yaml

from app.engine.faces import FACES
from app.engine.knowledge import FileKnowledgeStore
from app.main import _run_service_runners

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_offsite_backups_require_gpg_encryption() -> None:
    script = (REPO_ROOT / "deploy" / "backup.sh").read_text(encoding="utf-8")

    guard = '[[ -n "${STORAGE_BOX:-}" && -z "${GPG_RECIPIENT:-}" ]]'
    assert guard in script
    assert script.index(guard) < script.index("rsync -az")


def test_web_access_logs_are_disabled_for_privacy() -> None:
    main = (REPO_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    nginx = (REPO_ROOT / "deploy" / "nginx" / "templates" / "avvalo.conf.template").read_text(
        encoding="utf-8"
    )

    assert "access_log=False" in main
    assert "access_log off;" in nginx


def test_nginx_rejects_unknown_hosts_and_throttles_check_posts() -> None:
    nginx = (REPO_ROOT / "deploy" / "nginx" / "templates" / "avvalo.conf.template").read_text(
        encoding="utf-8"
    )

    assert "listen 80 default_server;" in nginx
    assert "if ($host != ${AVVALO_DOMAIN})" in nginx
    assert "return 301 https://${AVVALO_DOMAIN}$request_uri;" in nginx
    assert "proxy_set_header Host ${AVVALO_DOMAIN};" in nginx
    assert "limit_req_zone $check_limit_key" in nginx
    assert "location = /check" in nginx
    assert "limit_req zone=web_check_posts" in nginx
    assert "client_body_timeout 15s;" in nginx


def test_nginx_timeout_exceeds_full_pipeline_budget() -> None:
    nginx = (REPO_ROOT / "deploy" / "nginx" / "templates" / "avvalo.conf.template").read_text(
        encoding="utf-8"
    )

    proxy_timeout = re.search(r"proxy_read_timeout (\d+)s;", nginx)
    assert proxy_timeout is not None
    assert int(proxy_timeout.group(1)) > 30 + 10 + (2 * 2 * 30)


def test_nginx_csp_does_not_allow_inline_scripts() -> None:
    nginx = (REPO_ROOT / "deploy" / "nginx" / "templates" / "avvalo.conf.template").read_text(
        encoding="utf-8"
    )

    assert "script-src 'self' https://challenges.cloudflare.com" in nginx
    assert "script-src 'self' 'unsafe-inline'" not in nginx


def test_production_app_container_is_least_privilege_and_immutable() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = yaml.safe_load(
        (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    )
    app = compose["services"]["app"]

    assert re.search(r"^FROM python:\S+@sha256:[0-9a-f]{64}$", dockerfile, re.MULTILINE)
    assert "USER avvalo" in dockerfile
    assert app["image"].endswith("${IMAGE_TAG:?set IMAGE_TAG in .env}")
    assert app["read_only"] is True
    assert app["cap_drop"] == ["ALL"]
    assert any(str(item).startswith("/tmp:") for item in app["tmpfs"])


def test_third_party_container_images_are_digest_pinned() -> None:
    dev = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    prod = yaml.safe_load(
        (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    )
    images = [
        dev["services"]["db"]["image"],
        dev["services"]["ollama"]["image"],
        prod["services"]["db"]["image"],
        prod["services"]["nginx"]["image"],
        prod["services"]["certbot"]["image"],
    ]

    assert all(re.search(r"@sha256:[0-9a-f]{64}$", image) for image in images)


def test_ci_uses_hash_locked_dependencies_and_pinned_actions() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )
    action_refs = re.findall(r"^\s*uses:\s*[^@\s]+@([^\s#]+)", workflow, re.MULTILINE)

    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)
    assert "pip install --require-hashes -r requirements-dev.lock" in workflow
    assert "continue-on-error: true" not in workflow
    assert "ruff check app --select S" in workflow


def test_deploy_uses_a_pretrusted_ssh_host_key() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )

    assert "DEPLOY_HOST_KEY" in workflow
    assert "ssh-keyscan" not in workflow
    assert "printf '%s\\n' \"$SSH_HOST_KEY\" > ~/.ssh/known_hosts" in workflow


def test_production_jobs_are_gated_to_main() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )

    main_gate = "github.ref == 'refs/heads/main'"
    assert workflow.count(f"if: github.event_name != 'pull_request' && {main_gate}") == 2
    assert "group: deploy-production" not in workflow
    assert "format('ci-{0}', github.ref)" in workflow


def test_remote_update_waits_for_service_health() -> None:
    script = (REPO_ROOT / "deploy" / "remote-update.sh").read_text(encoding="utf-8")

    assert "$COMPOSE up -d --wait --wait-timeout 180" in script
    assert script.index("--wait --wait-timeout") < script.index(">> Deploy complete.")

    compose = (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "http://localhost:8000/readyz" in compose


def test_restore_stops_writers_and_fails_atomically() -> None:
    script = (REPO_ROOT / "deploy" / "restore.sh").read_text(encoding="utf-8")

    assert 'stop app' in script
    assert "ON_ERROR_STOP=1" in script
    assert "--single-transaction" in script
    assert script.index("stop app") < script.index("psql -X")
    assert "up -d --wait --wait-timeout 180 app" in script


async def test_service_runner_exit_cancels_peer() -> None:
    peer_started = asyncio.Event()
    peer_stopped = asyncio.Event()

    async def peer() -> None:
        peer_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            peer_stopped.set()

    async def owner() -> None:
        await peer_started.wait()

    await _run_service_runners([peer(), owner()])

    assert peer_stopped.is_set()


def test_web_process_assigns_signal_ownership_to_uvicorn() -> None:
    main = (REPO_ROOT / "app" / "main.py").read_text(encoding="utf-8")

    assert "handle_signals=not settings.web_enabled" in main


def test_dependabot_tracks_all_supply_chain_inputs() -> None:
    config = yaml.safe_load(
        (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    ecosystems = {entry["package-ecosystem"] for entry in config["updates"]}

    assert ecosystems == {"pip", "docker", "github-actions"}


def test_runtime_dependency_lock_contains_hashes() -> None:
    runtime_lock = (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8")
    dev_lock = (REPO_ROOT / "requirements-dev.lock").read_text(encoding="utf-8")

    assert "--hash=sha256:" in runtime_lock
    assert "--hash=sha256:" in dev_lock


def test_every_engine_runtime_asset_directory_is_copied_into_image() -> None:
    """A newly configured fourth disk asset fails until Docker copies it."""

    engine_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPO_ROOT / "app" / "engine").rglob("*.py")
    )
    configured_assets = {
        Path(face.prompt_template).parts[0]
        for face in FACES.values()
    } | {
        Path(face.rule_pack_dir).parts[0]
        for face in FACES.values()
    }
    configured_assets.update(
        re.findall(r'_REPO_ROOT\s*/\s*["\']([^/"\']+)["\']', engine_source)
    )
    configured_assets.add(
        FileKnowledgeStore().root.relative_to(REPO_ROOT).parts[0]
    )

    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    copied_roots = {
        Path(match).parts[0]
        for match in re.findall(r"^COPY\s+([^\s]+)\s+", dockerfile, re.MULTILINE)
    }
    assert configured_assets == {"prompts", "rules", "knowledge"}
    assert configured_assets <= copied_roots
