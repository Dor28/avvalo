"""Static checks for deployment privacy guardrails."""

import re
from pathlib import Path

import yaml

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

    assert re.search(r"^FROM python:[^\\s]+@sha256:[0-9a-f]{64}$", dockerfile, re.MULTILINE)
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
