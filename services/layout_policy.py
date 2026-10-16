from __future__ import annotations

from typing import Any

# Canonical section/style knowledge lives in section_catalog (mirrored from
# the fe-serey-web frontend). This module only holds the derivation logic.
from services.section_catalog import (
    ARRAY_UPLOAD_LABELS as _ARRAY_UPLOAD_LABELS,
    PRODUCT_SUBTYPE_STYLES,
    SCALAR_UPLOAD_LABELS as _SCALAR_UPLOAD_LABELS,
    SECTION_STYLE_MAP,
    SECTION_TYPE_ID_MAP,
)

_ARRAY_FIELD_IMAGE_KEY = {
    "images": "image_url",
    "members": "image_url",
    "testimonial_items": "image_url",
}


# Other names the model uses for a section type (the frontend's resolveTypeKey
# accepts "CODE" for the Custom Code section too).
_TYPE_ALIASES = {"CODE": "CUSTOM", "CUSTOM_CODE": "CUSTOM", "CUSTOMCODE": "CUSTOM", "CODE_SECTION": "CUSTOM"}


def normalize_section_type(section_type: Any) -> str:
    """Accepts string names ('HERO'), numeric IDs (1), or numeric strings ('1')."""
    if isinstance(section_type, int):
        return SECTION_TYPE_ID_MAP.get(section_type, "")
    raw = str(section_type or "").strip()
    # Try numeric string first
    try:
        return SECTION_TYPE_ID_MAP.get(int(raw), raw.upper())
    except ValueError:
        name = raw.upper().replace(" ", "_").replace("-", "_")
        return _TYPE_ALIASES.get(name, name)


def get_default_style(section_type: str) -> int:
    styles = SECTION_STYLE_MAP.get(section_type, {}).get("allowed_styles", (1,))
    return int(styles[0])


def _allowed_styles_for(section_type: str, section_subtype: Any) -> tuple[int, ...]:
    allowed = tuple(SECTION_STYLE_MAP[section_type]["allowed_styles"])
    if section_type != "GALLERY":
        return allowed
    if section_subtype == "product":
        return PRODUCT_SUBTYPE_STYLES
    if section_subtype is None:
        # Subtype unknown (a patch or styles_selected entry that does not
        # repeat it): accept a style that is valid for either list.
        return allowed + tuple(v for v in PRODUCT_SUBTYPE_STYLES if v not in allowed)
    return allowed


def normalize_style(section_type: str, style: Any, section_subtype: Any = None) -> tuple[int, bool]:
    """Returns (style, changed). An invalid style becomes the first style of the
    section's catalog list (the product list for a product GALLERY)."""
    if section_type not in SECTION_STYLE_MAP:
        try:
            return int(style), False
        except (TypeError, ValueError):
            return 1, True
    allowed = _allowed_styles_for(section_type, section_subtype)
    try:
        parsed = int(style)
    except (TypeError, ValueError):
        return int(allowed[0]), True
    if parsed not in allowed:
        return int(allowed[0]), True
    return parsed, False


def get_rendered_fields(section_type: str, style: Any) -> tuple[str, ...]:
    section_type = normalize_section_type(section_type)
    if section_type not in SECTION_STYLE_MAP:
        return ()
    normalized_style, _ = normalize_style(section_type, style)
    return tuple(SECTION_STYLE_MAP[section_type]["rendered_fields"].get(normalized_style, ()))


def _is_empty_upload_value(v: Any) -> bool:
    return not isinstance(v, str) or not v.strip()


def _slot_label(section_lower: str, field: str, index: int | None) -> str:
    if index is None:
        return _SCALAR_UPLOAD_LABELS.get((section_lower, field), f"{section_lower.title()} {field}")
    template = _ARRAY_UPLOAD_LABELS.get((section_lower, field), f"{section_lower.title()} Item {{n}} Image")
    return template.format(n=index + 1)


def collect_rendered_upload_slots(layout_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for section in layout_sections:
        section_type = normalize_section_type(section.get("type"))
        if not section_type or section.get("is_hidden", False):
            continue
        style, _ = normalize_style(section_type, section.get("style"))
        section_lower = section_type.lower()
        for field in get_rendered_fields(section_type, style):
            # Product galleries render the community's shop products (ProductSection),
            # never uploaded images[] — asking for those uploads would be a dead end.
            # Mirrors isImageFieldRenderable() in LandingBuilderV2.js.
            if section_type == "GALLERY" and field == "images" and section.get("section_subtype") == "product":
                continue
            if field in _ARRAY_FIELD_IMAGE_KEY:
                image_field = _ARRAY_FIELD_IMAGE_KEY[field]
                for idx, item in enumerate(section.get(field) or []):
                    if not isinstance(item, dict):
                        continue
                    slots.append(
                        {
                            "section": section_lower,
                            "field": field,
                            "index": idx,
                            "label": _slot_label(section_lower, field, idx),
                            "missing": _is_empty_upload_value(item.get(image_field)),
                        }
                    )
            else:
                slots.append(
                    {
                        "section": section_lower,
                        "field": field,
                        "label": _slot_label(section_lower, field, None),
                        "missing": _is_empty_upload_value(section.get(field)),
                    }
                )
    return slots


def derive_uploads_needed(layout_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uploads: list[dict[str, Any]] = []
    for slot in collect_rendered_upload_slots(layout_sections):
        if not slot.get("missing"):
            continue
        payload = {
            "section": slot["section"],
            "field": slot["field"],
            "label": slot["label"],
        }
        if "index" in slot:
            payload["index"] = slot["index"]
        uploads.append(payload)
    return uploads


def parse_frontend_style_map(page_context_obj: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(page_context_obj, dict):
        return None
    for key in ("style_map", "section_style_map", "styles_map"):
        raw = page_context_obj.get(key)
        if isinstance(raw, dict):
            return raw
    return None


def compare_with_backend_map(frontend_style_map: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for raw_section, raw_value in frontend_style_map.items():
        section = normalize_section_type(raw_section)
        backend = SECTION_STYLE_MAP.get(section)
        if backend is None:
            mismatches.append(f"{section}: unknown section in frontend map")
            continue
        if not isinstance(raw_value, dict):
            mismatches.append(f"{section}: invalid frontend style map shape")
            continue
        frontend_allowed = raw_value.get("allowed_styles")
        if isinstance(frontend_allowed, list):
            try:
                frontend_allowed_set = {int(v) for v in frontend_allowed}
            except (TypeError, ValueError):
                frontend_allowed_set = set()
            backend_allowed_set = {int(v) for v in backend["allowed_styles"]}
            if frontend_allowed_set != backend_allowed_set:
                mismatches.append(
                    f"{section}: allowed_styles frontend={sorted(frontend_allowed_set)} backend={sorted(backend_allowed_set)}"
                )
        frontend_rendered = raw_value.get("rendered_fields")
        if isinstance(frontend_rendered, dict):
            frontend_pairs: set[tuple[int, str]] = set()
            for style_key, fields in frontend_rendered.items():
                try:
                    style_int = int(style_key)
                except (TypeError, ValueError):
                    continue
                if isinstance(fields, list):
                    frontend_pairs |= {(style_int, str(f)) for f in fields}
            backend_pairs = {
                (int(style), str(field))
                for style, fields in backend["rendered_fields"].items()
                for field in fields
            }
            if frontend_pairs != backend_pairs:
                mismatches.append(f"{section}: rendered_fields differ from backend canonical map")
    return mismatches
