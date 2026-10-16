"""Google Maps links → an embeddable map for a Custom Code section.

A link a user copies from Google Maps (maps.app.goo.gl/…, google.com/maps/place/…)
cannot be shown in an iframe — Google blocks it. It has to be rewritten into
Google's keyless embed form (maps.google.com/maps?q=…&output=embed), or for a
Google My Maps link (many pins) into /maps/d/embed?mid=…. The server builds
the section itself so Bob never writes (or breaks) the map code.
"""

from __future__ import annotations

import html
import logging
import re
from urllib.parse import parse_qs, quote, unquote_plus, urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

# Any Google Maps link in a chat message, including the short forms.
_MAP_LINK_RE = re.compile(
    r"https?://(?:"
    r"maps\.app\.goo\.gl/[^\s\"'<>)]+"
    r"|goo\.gl/maps/[^\s\"'<>)]+"
    r"|(?:www\.)?google\.[a-z.]{2,6}/maps[^\s\"'<>)]*"
    r"|maps\.google\.[a-z.]{2,6}[^\s\"'<>)]*"
    r")",
    re.IGNORECASE,
)
_SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl"}
_GOOGLE_HOST_RE = re.compile(r"^(?:[a-z0-9-]+\.)*google\.[a-z.]{2,6}$|^(?:maps\.app\.)?goo\.gl$", re.IGNORECASE)
_AT_COORDS_RE = re.compile(r"@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)(?:,(\d{1,2}(?:\.\d+)?)z)?")
_LATLNG_RE = re.compile(r"^\s*-?\d{1,3}(?:\.\d+)?\s*,\s*-?\d{1,3}(?:\.\d+)?\s*$")
_MAX_REDIRECTS = 6
_TIMEOUT_S = 6.0

MAP_HEIGHT_PX = 450


def find_map_links(text: str | None) -> list[str]:
    """Google Maps links in the user's message, in order, without duplicates."""
    seen: list[str] = []
    for match in _MAP_LINK_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;:!?")
        if url not in seen:
            seen.append(url)
    return seen


def _is_google(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return bool(_GOOGLE_HOST_RE.match(host))


async def _expand_short_link(url: str) -> str | None:
    """Follow a maps.app.goo.gl / goo.gl/maps redirect chain to the full Maps URL.
    Only Google hosts are followed, and no page body is read."""
    current = url
    async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=False,
                                 headers={"User-Agent": "Mozilla/5.0 (SereyBuilder map link)"}) as client:
        for _ in range(_MAX_REDIRECTS):
            if not _is_google(current):
                logger.warning("Map link redirected outside Google: %.120s", current)
                return None
            host = (urlparse(current).hostname or "").lower()
            if host not in _SHORT_HOSTS and "consent." not in host:
                return current
            if "consent." in host:
                # EU cookie wall: the real Maps URL is in ?continue=
                cont = parse_qs(urlparse(current).query).get("continue", [None])[0]
                if not cont:
                    return None
                current = cont
                continue
            try:
                resp = await client.head(current)
                if resp.status_code in (405, 404) or not resp.headers.get("location"):
                    async with client.stream("GET", current) as streamed:
                        resp = streamed
            except httpx.HTTPError as e:
                logger.warning("Could not expand map link %.120s: %s", current, e)
                return None
            location = resp.headers.get("location")
            if not location:
                return None
            current = urljoin(current, location)
    return None


def embed_url_from_maps_url(url: str) -> str | None:
    """The keyless embed URL for a full Google Maps URL, or None (directions,
    or nothing to locate)."""
    if not _is_google(url):
        return None
    parsed = urlparse(url)
    path = unquote_plus(parsed.path or "")
    query = parse_qs(parsed.query)

    # Google My Maps (a custom map with many pins): has its own embed page.
    if "/maps/d/" in path:
        mid = (query.get("mid") or [None])[0]
        return f"https://www.google.com/maps/d/embed?mid={quote(mid, safe='')}" if mid else None
    # Already an embed link (from Google's "Share → Embed a map").
    if path.startswith("/maps/embed"):
        pb = (query.get("pb") or [None])[0]
        return f"https://www.google.com/maps/embed?pb={quote(pb, safe='!:.-_*')}" if pb else None
    if "/maps/dir" in path or query.get("saddr") or query.get("daddr") or (query.get("api") and "/dir" in path):
        return None  # a route needs an API key to embed

    zoom = None
    at = _AT_COORDS_RE.search(parsed.path or "")
    if at and at.group(3):
        zoom = int(float(at.group(3)))

    place = None
    for key in ("q", "query", "destination"):
        if query.get(key) and query[key][0].strip():
            place = query[key][0].strip()
            break
    if not place:
        for marker in ("/maps/place/", "/maps/search/"):
            if marker in path:
                seg = path.split(marker, 1)[1].split("/", 1)[0].strip()
                if seg and not seg.startswith("@"):
                    place = seg
                break
    if not place and query.get("ll"):
        place = query["ll"][0]
    if not place and at:
        place = f"{at.group(1)},{at.group(2)}"
    if not place:
        return None

    if zoom is None:
        zoom = 15 if _LATLNG_RE.match(place) else 14
    zoom = max(3, min(zoom, 20))
    return f"https://maps.google.com/maps?q={quote(place, safe=',')}&z={zoom}&output=embed"


async def to_embed_url(link: str) -> str | None:
    """Embed URL for any Google Maps link a user pastes (short links included)."""
    url = link.strip()
    host = (urlparse(url).hostname or "").lower()
    if host in _SHORT_HOSTS:
        url = await _expand_short_link(url) or ""
        if not url:
            return None
    embed = embed_url_from_maps_url(url)
    logger.info("Map link %.80s → %s", link, embed or "not embeddable")
    return embed


def map_section_html(embed_url: str) -> str:
    """The Custom Code html for a map: full width, rounded, fixed height (no vh —
    the code iframe sizes itself to its content)."""
    src = html.escape(embed_url, quote=True)
    return (
        "<style>.serey-map{max-width:1100px;margin:0 auto;padding:48px 20px}"
        f".serey-map iframe{{display:block;width:100%;height:{MAP_HEIGHT_PX}px;border:0;border-radius:14px}}"
        "@media (max-width:640px){.serey-map{padding:32px 16px}.serey-map iframe{height:340px}}</style>"
        f'<div class="serey-map"><iframe src="{src}" title="Map" allowfullscreen '
        'referrerpolicy="no-referrer-when-downgrade"></iframe></div>'
    )


def is_map_html(value: object) -> bool:
    """True for html that embeds a Google map (the model's own attempt at one)."""
    return isinstance(value, str) and "<iframe" in value.lower() and bool(
        re.search(r"google\.[a-z.]+/maps|maps\.google\.", value, re.IGNORECASE)
    )
