"""Static checks for deployment privacy guardrails."""

from pathlib import Path

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
