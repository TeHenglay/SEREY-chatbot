# POST /api/builder/match-products — matches user-provided product names to
# uploaded product photos using the Grok vision model, and writes a short
# grounded description per matched product. Stateless utility endpoint used
# by the landing-builder frontend after bulk product-image uploads.

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from routes.builder_chat import _verify_api_key
from schemas.requests import MatchProductsRequest, MatchProductsResponse, ProductMatch
from services import grok

router = APIRouter()
logger = logging.getLogger(__name__)

_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

_SYSTEM_PROMPT = """You match product photos to product names.
You will receive N numbered product photos (Image 1..N, in order) and M numbered product names, some with extra details from the seller.

Rules:
- Match each image to AT MOST one product name; use each name for AT MOST one image.
- Only match when the photo plausibly shows that product. If genuinely unsure, set "product": null.
- "description": 1-2 sentences per matched image, grounded ONLY in what is visible in the photo plus the seller's details. Never invent brands, materials, prices, sizes, or claims you cannot see.
- Unmatched images get "product": null and "description": "".
- Return ONLY valid JSON, no markdown, exactly:
{"matches":[{"image":1,"product":"<exact name from the list or null>","confidence":"high|medium|low","description":"..."}]}
Include one entry per image, in image order."""


def _clean_raw(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]
    return stripped.strip()


def _build_prompt(request: MatchProductsRequest) -> str:
    lines = [f"There are {len(request.images)} product photos, provided below in order (Image 1 first)."]
    lines.append(f"\nProduct names from the seller ({len(request.products)}):")
    for i, product in enumerate(request.products, start=1):
        entry = f"  {i}. {product.name}"
        if product.details.strip():
            entry += f" — seller details: {product.details.strip()}"
        lines.append(entry)
    if request.language == "kh":
        lines.append("\nWrite all descriptions in Khmer.")
    else:
        lines.append("\nWrite all descriptions in English.")
    lines.append("\nMatch the names to the photos and respond with the JSON now.")
    return "\n".join(lines)


@router.post(
    "/builder/match-products",
    response_model=MatchProductsResponse,
    dependencies=[Depends(_verify_api_key)],
)
async def match_products(request: MatchProductsRequest):
    logger.info(
        "Vision match: model=%s user=%s session=%s images=%d products=%d",
        grok.VISION_MODEL, request.user_id, request.session_id,
        len(request.images), len(request.products),
    )

    prompt = _build_prompt(request)
    image_urls = [slot.image_url for slot in request.images]

    data = None
    for attempt in (1, 2):
        raw = ""
        try:
            raw = await asyncio.to_thread(grok.generate_vision, prompt, image_urls, _SYSTEM_PROMPT)
            data = json.loads(_clean_raw(raw))
            break
        except json.JSONDecodeError as e:
            logger.error("Vision JSON parse error (attempt %d): %s | Raw: %s", attempt, str(e), raw[:400])
            if attempt == 2:
                raise HTTPException(status_code=422, detail="AI returned malformed JSON for image matching")
        except Exception as e:
            logger.error("Vision call failed (attempt %d): %s", attempt, str(e))
            if attempt == 2:
                raise HTTPException(status_code=502, detail=f"AI vision service unavailable: {str(e)}")
    if not isinstance(data, dict) or not isinstance(data.get("matches"), list):
        raise HTTPException(status_code=422, detail="AI returned unexpected format for image matching")

    # Normalize: image number -> slot; each product assigned at most once
    # (on duplicates the higher-confidence assignment wins).
    requested_names = {p.name for p in request.products}
    best_by_image: dict[int, dict] = {}
    for entry in data["matches"]:
        if not isinstance(entry, dict):
            continue
        try:
            image_no = int(entry.get("image"))
        except (TypeError, ValueError):
            continue
        if not (1 <= image_no <= len(request.images)):
            continue
        best_by_image[image_no] = entry

    assigned: dict[str, tuple[int, int]] = {}  # name -> (image_no, confidence_rank)
    for image_no, entry in sorted(best_by_image.items()):
        name = entry.get("product")
        if not isinstance(name, str) or name not in requested_names:
            continue
        confidence = str(entry.get("confidence") or "low").lower()
        rank = _CONFIDENCE_RANK.get(confidence, 1)
        prev = assigned.get(name)
        if prev is None or rank > prev[1]:
            assigned[name] = (image_no, rank)

    image_no_to_name = {image_no: name for name, (image_no, _rank) in assigned.items()}

    matches: list[ProductMatch] = []
    for i, slot in enumerate(request.images, start=1):
        entry = best_by_image.get(i, {})
        name = image_no_to_name.get(i, "")
        confidence = str(entry.get("confidence") or "low").lower()
        matches.append(
            ProductMatch(
                image_url=slot.image_url,
                index=slot.index,
                name=name,
                description=str(entry.get("description") or "") if name else "",
                confidence=confidence if confidence in _CONFIDENCE_RANK and name else "low",
            )
        )

    unmatched_products = [p.name for p in request.products if p.name not in assigned]

    matched_count = len(assigned)
    if matched_count == len(request.products):
        reply = f"Matched all {matched_count} products to your photos."
    elif matched_count == 0:
        reply = "I couldn't confidently match any product names to these photos — you can assign them manually."
    else:
        missing = ", ".join(f"'{n}'" for n in unmatched_products)
        reply = f"Matched {matched_count} of {len(request.products)} products to your photos — I couldn't find a photo for {missing}."

    return MatchProductsResponse(matches=matches, unmatched_products=unmatched_products, reply=reply)
