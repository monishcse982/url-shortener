"""Supported policy variants shared by the Locust scenarios."""

LINK_TYPES = ("public", "password_protected", "ip_restricted")
VISIT_LIMIT = 10
LIMIT_PROFILES = (
    # TTL is required by the API; maximum TTL approximates visit-only links.
    ("visit-limited", 60 * 60 * 24 * 30, VISIT_LIMIT),
    ("time-limited", 60 * 60 * 24, None),
    ("time-and-visit-limited", 60 * 60, VISIT_LIMIT),
)
LINK_CASES = tuple(
    (link_type, profile_name, ttl_seconds, max_visits)
    for link_type in LINK_TYPES
    for profile_name, ttl_seconds, max_visits in LIMIT_PROFILES
)


def policy_for(link_type: str) -> dict[str, object]:
    if link_type == "public":
        return {"type": "public"}
    if link_type == "password_protected":
        return {"type": "password_protected", "password": "load-test-password"}
    if link_type == "ip_restricted":
        # Accept any runner address; access control is checked in unit tests.
        return {"type": "ip_restricted", "ip_list": ["0.0.0.0/0", "::/0"]}
    raise ValueError(f"Unsupported link type: {link_type}")


def visit_headers_for(link_type: str) -> dict[str, str]:
    if link_type == "password_protected":
        return {"password": "load-test-password"}
    return {}
