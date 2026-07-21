"""Shared helpers for provider fakes."""

import re

_RULE_ID_RE = re.compile(r"(?m)^- ([a-z][a-z0-9_.-]+) \|")


def addressed_rule_ids(user_prompt: object) -> list[str]:
    """Mirror a compliant model declaring every supplied rule fact."""

    return _RULE_ID_RE.findall(str(user_prompt))
