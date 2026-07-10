# Shared request-security guards for the AI endpoints.
#
# Two independent layers, both exposed as FastAPI dependencies:
#
#   verify_api_key      — the primary gate. Requires the X-Serey-Api-Key shared
#                         secret. This is what actually stops raw curl / server-
#                         to-server enumeration, because curl carries no browser
#                         Origin and therefore sails past any CORS/origin check.
#
#   require_serey_origin — a browser-facing allowlist. When a request carries an
#                         Origin (or Referer) header it MUST resolve to serey.io
#                         or a *.serey.io subdomain (plus any configured dev
#                         origins). Requests with NO Origin are allowed through:
#                         those are legitimate server-to-server calls (Next.js →
#                         Python) which are gated by verify_api_key instead.
#                         Rejecting them here would break production while doing
#                         nothing to stop a spoofed-Origin attacker.
#
# Apply BOTH to every AI route so browser traffic is constrained to serey.io and
# non-browser traffic still needs the shared secret.

import os
import re
from urllib.parse import urlparse

from fastapi import Header, HTTPException

_CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")

# serey.io and every subdomain (any depth), http or https, optional port.
# e.g. serey.io, www.serey.io, app.serey.io, foo.bar.serey.io
_SEREY_HOST_RE = re.compile(r"^([a-z0-9-]+\.)*serey\.io$", re.IGNORECASE)

# Extra exact origins permitted in addition to serey.io — e.g. local dev hosts.
# Comma-separated full origins ("http://localhost:3000"). Reuses CORS_ORIGINS so
# there is a single place to whitelist dev/staging front-ends.
_EXTRA_ORIGINS = {
    o.strip().rstrip("/")
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3030,"
        "http://127.0.0.1:3000,http://127.0.0.1:3030",
    ).split(",")
    if o.strip()
}


def _origin_allowed(origin: str) -> bool:
    """True if `origin` is a serey.io (sub)domain or an explicitly allowed extra origin."""
    origin = origin.strip().rstrip("/")
    if not origin:
        return True  # no origin to judge — server-to-server, handled by the API key
    if origin in _EXTRA_ORIGINS:
        return True
    host = urlparse(origin).hostname or ""
    return bool(_SEREY_HOST_RE.match(host))


def verify_api_key(x_serey_api_key: str = Header(default="")) -> None:
    """Reject requests with a missing or wrong X-Serey-Api-Key header.
    Skipped entirely when CHAT_API_KEY is unset (local dev convenience)."""
    if _CHAT_API_KEY and x_serey_api_key != _CHAT_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: invalid API key")


def require_serey_origin(
    origin: str = Header(default=""),
    referer: str = Header(default=""),
) -> None:
    """Reject browser requests whose Origin/Referer is not a serey.io domain.

    Requests without an Origin or Referer (non-browser, server-to-server) are
    allowed and rely on verify_api_key. A present-but-foreign origin is a browser
    from another site and is refused with 403.
    """
    candidate = origin or referer
    if candidate and not _origin_allowed(candidate):
        raise HTTPException(status_code=403, detail="Forbidden: origin not allowed")
