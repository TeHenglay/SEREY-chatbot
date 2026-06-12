from __future__ import annotations

from typing import Any


SECTION_TYPE_ID_MAP: dict[int, str] = {
    1: "HERO",
    2: "ABOUT",
    3: "GALLERY",
    4: "FOOTER",
    5: "VIDEO",
    6: "VISION",
    7: "BLOG",
    8: "TEAM",
    9: "FAQ",
    10: "TESTIMONIALS",
    11: "CUSTOM",
    12: "RANKING",
    13: "SUBSCRIPTION",
}

# Builder V2 style/section contract. See BUILDER_V2_AI_BACKEND.md.
#
# GALLERY (type 3) is split by `section_subtype`:
#   - 'gallery' (photo)   -> GallerySection, styles 1-9,11,12
#   - 'product'/'project' -> ProductSection, styles 1-5
# The product variant lives under the virtual key "GALLERY_PRODUCT" below and is
# selected via _resolve_style_key(). It is NOT a real section type id.
#
# rendered_fields lists the IMAGE/array fields a given style actually renders, so
# uploads_needed only prompts for slots the chosen style will show. Styles tagged
# [IMG: none] in the spec (e.g. hero 3, about 5/8, testimonials 7) render no image.
SECTION_STYLE_MAP: dict[str, dict[str, Any]] = {
    "HERO": {
        "allowed_styles": (1, 2, 3, 5, 7, 8),
        "rendered_fields": {
            1: ("image_url",),  # Two Column [optional]
            2: ("image_url",),  # Full-Bleed Cinematic [required]
            3: (),              # Centered — NO image
            5: ("image_url",),  # Magazine Split [required]
            7: ("image_url",),  # Editorial Magazine Cover [optional]
            8: ("image_url",),  # Padded Card [required]
        },
    },
    "ABOUT": {
        "allowed_styles": (1, 2, 4, 5, 7, 8, 10, 11),
        "rendered_fields": {
            1: ("image_url",),
            2: ("image_url",),
            4: ("image_url",),
            5: (),               # Text only
            7: ("image_url",),
            8: (),               # Panel text only
            10: ("image_url",),
            11: ("image_url",),
        },
    },
    # Photo gallery (section_subtype: 'gallery')
    "GALLERY": {
        "allowed_styles": (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12),
        "rendered_fields": {
            style: ("images",) for style in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12)
        },
    },
    # Product/service/feature cards (section_subtype: 'product' or 'project')
    "GALLERY_PRODUCT": {
        "allowed_styles": (1, 2, 3, 4, 5),
        "rendered_fields": {style: ("images",) for style in (1, 2, 3, 4, 5)},
    },
    "FOOTER": {
        "allowed_styles": (1, 2, 3, 4, 5),
        "rendered_fields": {style: ("logo_url",) for style in (1, 2, 3, 4, 5)},
    },
    "VIDEO": {
        "allowed_styles": (1, 2, 3, 4),
        "rendered_fields": {style: () for style in (1, 2, 3, 4)},
    },
    "VISION": {
        "allowed_styles": (1, 2, 3, 4, 5, 6, 7),
        "rendered_fields": {style: () for style in (1, 2, 3, 4, 5, 6, 7)},
    },
    "BLOG": {
        "allowed_styles": (1, 2, 3, 4, 5, 6),
        "rendered_fields": {style: () for style in (1, 2, 3, 4, 5, 6)},
    },
    "TEAM": {
        "allowed_styles": (1, 2, 4, 5, 6, 7, 8),
        "rendered_fields": {style: ("members",) for style in (1, 2, 4, 5, 6, 7, 8)},
    },
    "FAQ": {
        "allowed_styles": (1, 2, 3, 4, 5, 6, 7),
        "rendered_fields": {style: () for style in (1, 2, 3, 4, 5, 6, 7)},
    },
    "TESTIMONIALS": {
        "allowed_styles": (1, 3, 4, 5, 6, 7, 9, 10),
        # style 7 = Cards No Image — no avatar uploads needed
        "rendered_fields": {
            **{style: ("testimonial_items",) for style in (1, 3, 4, 5, 6, 9, 10)},
            7: (),
        },
    },
    "CUSTOM": {
        "allowed_styles": (1, 2, 3, 4, 5, 6, 7),
        "rendered_fields": {style: ("image_url",) for style in (1, 2, 3, 4, 5, 6, 7)},
    },
    "RANKING": {
        "allowed_styles": (1,),
        "rendered_fields": {1: ()},
    },
    "SUBSCRIPTION": {
        "allowed_styles": (1,),
        "rendered_fields": {1: ()},
    },
}

_ARRAY_FIELD_IMAGE_KEY = {
    "images": "image_url",
    "members": "image_url",
    "testimonial_items": "image_url",
}

# Labels are keyed by the resolved STYLE KEY (uppercase), so the photo gallery and
# product gallery — both section type "gallery" — get distinct upload labels.
_SCALAR_UPLOAD_LABELS = {
    ("HERO", "image_url"): "Hero Background",
    ("ABOUT", "image_url"): "About Section Image",
    ("CUSTOM", "image_url"): "Custom Section Image",
    ("CUSTOM", "image_url_2"): "Custom Section Image 2",
    ("FOOTER", "logo_url"): "Footer Logo",
}

_ARRAY_UPLOAD_LABELS = {
    ("GALLERY", "images"): "Gallery Photo {n}",
    ("GALLERY_PRODUCT", "images"): "Product {n} — Image",
    ("TEAM", "members"): "Team Member {n} Photo",
    ("TESTIMONIALS", "testimonial_items"): "Reviewer {n} Avatar",
}


def normalize_section_type(section_type: Any) -> str:
    """Accepts string names ('HERO'), numeric IDs (1), or numeric strings ('1')."""
    if isinstance(section_type, int):
        return SECTION_TYPE_ID_MAP.get(section_type, "")
    raw = str(section_type or "").strip()
    # Try numeric string first
    try:
        return SECTION_TYPE_ID_MAP.get(int(raw), raw.upper())
    except ValueError:
        return raw.upper()


def normalize_gallery_subtype(section: dict[str, Any]) -> str | None:
    """Return the cleaned subtype for a GALLERY section, else None.

    'gallery' stays 'gallery' (photo). Anything else ('product', 'project',
    unknown) collapses to 'product' — the frontend normalizes the same way and
    expects 'product' on the wire. When absent, infer from item content: items
    carrying a name/description are products; bare images are a photo gallery.
    """
    if normalize_section_type(section.get("type")) != "GALLERY":
        return None
    raw = str(section.get("section_subtype") or "").strip().lower()
    if raw == "gallery":
        return "gallery"
    if raw:
        return "product"
    for item in section.get("images") or []:
        if isinstance(item, dict) and (
            str(item.get("name") or "").strip() or str(item.get("description") or "").strip()
        ):
            return "product"
    return "gallery"


def _resolve_style_key(section_type: str, section_subtype: Any = None) -> str:
    """Map (section_type, subtype) to the SECTION_STYLE_MAP key."""
    if section_type == "GALLERY":
        sub = str(section_subtype or "").strip().lower()
        if sub and sub != "gallery":
            return "GALLERY_PRODUCT"
        return "GALLERY"
    return section_type


def get_default_style(section_type: str, section_subtype: Any = None) -> int:
    key = _resolve_style_key(section_type, section_subtype)
    styles = SECTION_STYLE_MAP.get(key, {}).get("allowed_styles", (1,))
    return int(styles[0])


def normalize_style(section_type: str, style: Any, section_subtype: Any = None) -> tuple[int, bool]:
    key = _resolve_style_key(section_type, section_subtype)
    if key not in SECTION_STYLE_MAP:
        try:
            return int(style), False
        except (TypeError, ValueError):
            return 1, True
    allowed = SECTION_STYLE_MAP[key]["allowed_styles"]
    try:
        parsed = int(style)
    except (TypeError, ValueError):
        return get_default_style(section_type, section_subtype), True
    if parsed not in allowed:
        return get_default_style(section_type, section_subtype), True
    return parsed, False


def get_rendered_fields(section_type: str, style: Any, section_subtype: Any = None) -> tuple[str, ...]:
    section_type = normalize_section_type(section_type)
    key = _resolve_style_key(section_type, section_subtype)
    if key not in SECTION_STYLE_MAP:
        return ()
    normalized_style, _ = normalize_style(section_type, style, section_subtype)
    return tuple(SECTION_STYLE_MAP[key]["rendered_fields"].get(normalized_style, ()))


def _is_empty_upload_value(v: Any) -> bool:
    return not isinstance(v, str) or not v.strip()


def _slot_label(style_key: str, section_lower: str, field: str, index: int | None) -> str:
    if index is None:
        return _SCALAR_UPLOAD_LABELS.get((style_key, field), f"{section_lower.title()} {field}")
    template = _ARRAY_UPLOAD_LABELS.get((style_key, field), f"{section_lower.title()} Item {{n}} Image")
    return template.format(n=index + 1)


def collect_rendered_upload_slots(layout_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for section in layout_sections:
        section_type = normalize_section_type(section.get("type"))
        if not section_type or section.get("is_hidden", False):
            continue
        subtype = section.get("section_subtype")
        style_key = _resolve_style_key(section_type, subtype)
        style, _ = normalize_style(section_type, section.get("style"), subtype)
        section_lower = section_type.lower()
        for field in get_rendered_fields(section_type, style, subtype):
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
                            "label": _slot_label(style_key, section_lower, field, idx),
                            "missing": _is_empty_upload_value(item.get(image_field)),
                        }
                    )
            else:
                slots.append(
                    {
                        "section": section_lower,
                        "field": field,
                        "label": _slot_label(style_key, section_lower, field, None),
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
