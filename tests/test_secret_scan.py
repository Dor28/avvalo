from tools.secret_scan import path_findings, scan_text


def finding_reasons(path: str, text: str) -> list[str]:
    return [finding.reason for finding in scan_text(path, text)]


def test_secret_scan_blocks_telegram_bot_token() -> None:
    reasons = finding_reasons(
        ".env",
        "TELEGRAM_TOKEN=123456789:abcdefghijklmnopqrstuvwxyzABCDE12345\n",  # secret_scan:ignore
    )

    assert "possible Telegram bot token" in reasons


def test_secret_scan_blocks_private_key_material() -> None:
    reasons = finding_reasons(
        "secrets/gcv.json",
        '"private_key": "-----BEGIN PRIVATE KEY-----\\nabc123"\n',  # secret_scan:ignore
    )

    assert "private key material" in reasons


def test_secret_scan_allows_placeholders_and_templates() -> None:
    text = "\n".join(
        [
            "TELEGRAM_TOKEN=change-me",
            "APP_HMAC_SECRET=development-only-hmac-secret-change-me",
            "WEB_SESSION_SECRET=development-web-session-secret-change-me",
            "DATABASE_URL=postgresql+asyncpg://avvalo:${POSTGRES_PASSWORD:-avvalo}@db:5432/avvalo",
            "LLM_API_KEY=ignored",
        ]
    )

    assert finding_reasons(".env.example", text) == []


def test_secret_scan_ignores_token_count_variables() -> None:
    text = "\n".join(
        [
            "input_tokens=total_input_tokens",
            "output_tokens=response.output_tokens",
            "max_tokens=max_output_tokens",
        ]
    )

    assert finding_reasons("app/engine/pipeline.py", text) == []


def test_secret_scan_blocks_runtime_secret_paths() -> None:
    findings = path_findings(".env.production")

    assert [finding.reason for finding in findings] == ["runtime .env file must not be committed"]
