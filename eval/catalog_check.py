# Drift check: services/section_catalog.py vs the fe-serey-web style picker.
#
# SectionLayoutStylePicker in LandingBuilderV2.js is the source of truth for which
# style numbers exist per section. This script parses it and diffs the result
# against SECTION_STYLES (and the product-gallery styles / section type IDs).
#
# Usage (from project root):
#   python eval/catalog_check.py                      # reads FE from default path
#   python eval/catalog_check.py --fe <LandingBuilderV2.js>
#   python eval/catalog_check.py --write-snapshot     # save the parsed picker to eval/fe_picker_snapshot.json
#
# If the FE file is not available, the checked-in snapshot is used instead.
# Exit code is 0 when the catalog matches, 1 on drift (useful for CI).

import argparse
import json
import os
import re
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from services.section_catalog import (  # noqa: E402
    FRONTEND_TEMPLATES,
    GENERATABLE_SECTIONS,
    PRODUCT_SUBTYPE_STYLES,
    SECTION_STYLES,
    SECTION_TYPE_ID_MAP,
    SECTION_TYPE_NAME_TO_ID,
)

DEFAULT_FE = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "fe-serey-web",
    "src", "components", "LandingBuilderV2", "LandingBuilderV2.js",
)
SNAPSHOT = os.path.join(os.path.dirname(__file__), "fe_picker_snapshot.json")

# Picker key (bk === '...') -> catalog section name. Sections the picker does
# not expose (custom, newsletter, textblock) are not compared.
PICKER_TO_CATALOG = {
    "hero": "HERO", "about": "ABOUT", "gallery": "GALLERY", "video": "VIDEO",
    "vision": "VISION", "blog": "BLOG", "team": "TEAM", "faq": "FAQ",
    "testimonials": "TESTIMONIALS", "ranking": "RANKING",
    "subscription": "SUBSCRIPTION", "footer": "FOOTER", "notes": "NOTES",
}


def parse_picker(js: str) -> dict[str, list[int]]:
    start = js.index("function SectionLayoutStylePicker(")
    # The picker ends where the next top-level function begins.
    end_match = re.search(r"\n(?:function|const) \w+", js[start + 40:])
    block = js[start: start + 40 + end_match.start()] if end_match else js[start:]
    cur = None
    found: dict[str, list[int]] = {}
    for line in block.split("\n"):
        m = re.search(r"bk === '(\w+)'", line)
        if m:
            cur = m.group(1) + (":product" if "product" in line else "")
        for value in re.findall(r"value:\s*(\d+),\s*label:", line):
            if cur:
                found.setdefault(cur, []).append(int(value))
    return found


def parse_resolve_type_key(js: str) -> tuple[set[int], set[str]] | None:
    """Numeric IDs and string names the FE resolveTypeKey() can map. A section
    type outside these is silently dropped by the builder."""
    m = re.search(r"const resolveTypeKey = .*?NUMERIC_MAP = \{(.*?)\}.*?STRING_MAP = \{(.*?)\}", js, re.S)
    if not m:
        return None
    numeric = {int(n) for n in re.findall(r"(\d+):", m.group(1))}
    names = {n for n in re.findall(r"(\w+):", m.group(2))}
    return numeric, names


def parse_fe_templates(js_path: str) -> dict[str, list[tuple[str, str | None]]] | None:
    """Template id -> [(SECTION, subtype)] in order, from landingTemplates.js."""
    path = os.path.join(os.path.dirname(js_path), "landingTemplates.js")
    if not os.path.exists(path):
        return None
    src = open(path, encoding="utf8").read()
    templates: dict[str, list[tuple[str, str | None]]] = {}
    ids = list(re.finditer(r"^\s{4}id: '(\w+)'", src, re.M))
    for i, m in enumerate(ids):
        block = src[m.end(): ids[i + 1].start() if i + 1 < len(ids) else len(src)]
        templates[m.group(1)] = [
            (SECTION_TYPE_ID_MAP.get(int(t), f"type{t}"), sub)
            for t, sub in re.findall(r"type: (\d+), style: \d+(?:, section_subtype: '(\w+)')?", block)
        ]
        templates[m.group(1)] = [(name, sub or None) for name, sub in templates[m.group(1)]]
    return templates


def fe_constants_types(js_path: str) -> dict[int, str] | None:
    path = os.path.join(os.path.dirname(js_path), "..", "..", "config", "constants.js")
    if not os.path.exists(path):
        return None
    src = open(path, encoding="utf8").read()
    m = re.search(r"LANDING_PAGE_TEMPLATE_TYPE_V2\s*[:=]\s*\{(.*?)\}", src, re.S)
    if not m:
        return None
    return {int(v): k for k, v in re.findall(r"(\w+):\s*(\d+)", m.group(1))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fe", default=DEFAULT_FE)
    ap.add_argument("--write-snapshot", action="store_true")
    args = ap.parse_args()

    fe_path = os.path.abspath(args.fe)
    if os.path.exists(fe_path):
        picker = parse_picker(open(fe_path, encoding="utf8").read())
        source = fe_path
        if args.write_snapshot:
            json.dump(picker, open(SNAPSHOT, "w", encoding="utf8"), indent=2, sort_keys=True)
            print(f"snapshot written: {SNAPSHOT}")
    elif os.path.exists(SNAPSHOT):
        picker = json.load(open(SNAPSHOT, encoding="utf8"))
        source = SNAPSHOT + " (FE file not found)"
    else:
        print("No FE file and no snapshot — pass --fe <path>.")
        return 1

    print(f"comparing catalog against: {source}")
    problems: list[str] = []

    for key, name in PICKER_TO_CATALOG.items():
        fe_styles = picker.get(key)
        if key == "gallery":
            # The gallery block holds the product list first, then the photo list.
            fe_styles = picker.get("gallery:product", [])
            split = next((i for i in range(1, len(fe_styles)) if fe_styles[i] <= fe_styles[i - 1]), None)
            product, photo = (fe_styles[:split], fe_styles[split:]) if split else (fe_styles, [])
            if sorted(product) != sorted(PRODUCT_SUBTYPE_STYLES):
                problems.append(f"GALLERY product styles: FE {sorted(product)} != catalog {sorted(PRODUCT_SUBTYPE_STYLES)}")
            fe_styles = photo
        if not fe_styles:
            problems.append(f"{name}: not found in FE picker")
            continue
        catalog = sorted(v for v, _l, _d in SECTION_STYLES.get(name, ()))
        if sorted(fe_styles) != catalog:
            problems.append(
                f"{name}: FE {sorted(fe_styles)} != catalog {catalog} "
                f"(missing in catalog: {sorted(set(fe_styles) - set(catalog))}, "
                f"extra in catalog: {sorted(set(catalog) - set(fe_styles))})"
            )

    if os.path.exists(fe_path):
        resolvable = parse_resolve_type_key(open(fe_path, encoding="utf8").read())
        if resolvable is None:
            problems.append("could not parse resolveTypeKey() in the FE file")
        else:
            numeric, names = resolvable
            for name in GENERATABLE_SECTIONS:
                type_id = SECTION_TYPE_NAME_TO_ID.get(name)
                if name not in names or (type_id is not None and type_id not in numeric):
                    problems.append(f"{name} is generatable but FE resolveTypeKey() cannot map it — the builder would drop it")
        fe_templates = parse_fe_templates(fe_path)
        if fe_templates is not None:
            if set(fe_templates) != set(FRONTEND_TEMPLATES):
                problems.append(f"templates: FE {sorted(fe_templates)} != backend {sorted(FRONTEND_TEMPLATES)}")
            for tid in set(fe_templates) & set(FRONTEND_TEMPLATES):
                backend = [(sec, sub) for sec, _style, sub, _hidden in FRONTEND_TEMPLATES[tid]["sections"]]
                if fe_templates[tid] != backend:
                    problems.append(f"template {tid}: FE structure {fe_templates[tid]} != backend {backend}")
        fe_types = fe_constants_types(fe_path)
        if fe_types:
            for type_id, fe_name in fe_types.items():
                cat_name = SECTION_TYPE_ID_MAP.get(type_id)
                if cat_name is None:
                    problems.append(f"type {type_id} ({fe_name}) exists in FE constants but not in catalog")
                elif cat_name != fe_name:
                    problems.append(f"type {type_id}: FE {fe_name} != catalog {cat_name}")

    if problems:
        print(f"\nDRIFT — {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK — catalog matches the FE picker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
