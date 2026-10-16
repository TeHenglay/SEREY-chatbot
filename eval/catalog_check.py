# Drift check: the builder prompt + section catalog this service uses vs fe-serey-web.
#
# services/builder_ai/ holds exact copies of two files the frontend generates
# (node scripts/export-ai-builder-prompt.js):
#   docs/ai/builder-ai-prompt.md          -> the builder system prompt
#   docs/ai/builder-section-catalog.json  -> styles / colour keys / animations
# This script fails when:
#   - a copy differs from the frontend file (re-copy after the frontend regenerates),
#   - the prompt's SECTION REGISTRY and the catalog JSON disagree,
#   - services/section_catalog.py disagrees with the catalog JSON,
#   - the frontend cannot map a section type this service generates, or a
#     style in the frontend style picker is missing from the catalog,
#   - the starter templates or section type IDs differ from the frontend.
#
# Usage (from project root):
#   python eval/catalog_check.py                       # frontend repo at ../serey-fe/fe-serey-web
#   python eval/catalog_check.py --fe-repo <path>      # or set FE_REPO
#   python eval/catalog_check.py --write-snapshot      # save the parsed picker to eval/fe_picker_snapshot.json
#
# Without the frontend repo only the local checks run (the picker check uses the
# checked-in snapshot). Exit code is 0 when everything matches, 1 on drift (CI).

import argparse
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(ROOT)

from services.section_catalog import (  # noqa: E402
    CATALOG_JSON_PATH,
    FE_CATALOG,
    FRONTEND_TEMPLATES,
    GENERATABLE_SECTIONS,
    PRODUCT_SUBTYPE_STYLES,
    PROMPT_MD_PATH,
    SECTION_COLOR_KEYS,
    SECTION_STYLES,
    SECTION_TYPE_ID_MAP,
    SECTION_TYPE_NAME_TO_ID,
    ANIMATION_STYLES,
    builder_prompt_from_doc,
)

DEFAULT_FE_REPO = os.environ.get(
    "FE_REPO", os.path.join(ROOT, "..", "serey-fe", "fe-serey-web")
)
FE_BUILDER = os.path.join("src", "components", "LandingBuilderV2", "LandingBuilderV2.js")
FE_DOCS = {
    PROMPT_MD_PATH: os.path.join("docs", "ai", "builder-ai-prompt.md"),
    CATALOG_JSON_PATH: os.path.join("docs", "ai", "builder-section-catalog.json"),
}
SNAPSHOT = os.path.join(os.path.dirname(__file__), "fe_picker_snapshot.json")

# Picker key (bk === '...') -> catalog section name.
PICKER_TO_CATALOG = {
    "hero": "HERO", "about": "ABOUT", "gallery": "GALLERY", "video": "VIDEO",
    "vision": "VISION", "blog": "BLOG", "team": "TEAM", "faq": "FAQ",
    "testimonials": "TESTIMONIALS", "ranking": "RANKING",
    "subscription": "SUBSCRIPTION", "footer": "FOOTER", "notes": "NOTES",
    "podcast": "PODCAST",
}


def _read(path: str) -> str:
    with open(path, encoding="utf8") as f:
        return f.read().replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# Local checks (no frontend repo needed)
# ---------------------------------------------------------------------------

def parse_prompt_registry(prompt: str) -> dict[str, dict]:
    """{NAME: {"type", "styles", "product_styles", "colors"}} from the prompt's SECTION REGISTRY."""
    registry_at = prompt.index("## SECTION REGISTRY")
    end = prompt.find("\n## ", registry_at + 5)
    block = prompt[registry_at: end if end != -1 else len(prompt)]
    sections: dict[str, dict] = {}
    cur = None
    style_list = "styles"
    for line in block.split("\n"):
        m = re.match(r"### (\w+) — type (\d+)", line)
        if m:
            cur = sections.setdefault(m.group(1), {"type": int(m.group(2)), "styles": [], "product_styles": [], "colors": []})
            style_list = "styles"
            continue
        if cur is None:
            continue
        if line.startswith("Layout styles"):
            style_list = "product_styles" if 'is "product"' in line else "styles"
        elif m := re.match(r"\s+- (\d+) — ", line):
            cur[style_list].append(int(m.group(1)))
        elif line.startswith("Colour keys:"):
            cur["colors"] = [c.strip() for c in line.split(":", 1)[1].split(",") if c.strip() and c.strip() != "—"]
    return sections


def check_local(problems: list[str]) -> None:
    prompt = builder_prompt_from_doc()
    if not prompt.startswith("## SYSTEM PROMPT"):
        problems.append("builder-ai-prompt.md: no '## SYSTEM PROMPT' heading")
    registry = parse_prompt_registry(prompt)
    json_sections = {s["name"]: s for s in FE_CATALOG["sections"]}

    if set(registry) != set(json_sections):
        problems.append(f"prompt registry sections {sorted(registry)} != catalog JSON {sorted(json_sections)}")
    for name, js in json_sections.items():
        reg = registry.get(name)
        if not reg:
            continue
        if reg["type"] != js["type"]:
            problems.append(f"{name}: prompt says type {reg['type']}, JSON says {js['type']}")
        if reg["styles"] != [s["value"] for s in js["styles"]]:
            problems.append(f"{name}: prompt styles {reg['styles']} != JSON {[s['value'] for s in js['styles']]}")
        if reg["product_styles"] != [s["value"] for s in js.get("product_styles", [])]:
            problems.append(f"{name}: prompt product styles {reg['product_styles']} != JSON")
        if reg["colors"] != js["colors"]:
            problems.append(f"{name}: prompt colour keys {reg['colors']} != JSON {js['colors']}")

        # services/section_catalog.py must mirror the JSON exactly
        if SECTION_TYPE_ID_MAP.get(js["type"]) != name:
            problems.append(f"{name}: SECTION_TYPE_ID_MAP[{js['type']}] is {SECTION_TYPE_ID_MAP.get(js['type'])!r}")
        if name not in GENERATABLE_SECTIONS:
            problems.append(f"{name}: in the catalog JSON but not in GENERATABLE_SECTIONS")
        if [v for v, _l, _d in SECTION_STYLES.get(name, ())] != [s["value"] for s in js["styles"]]:
            problems.append(f"{name}: SECTION_STYLES differs from the catalog JSON")
        if list(SECTION_COLOR_KEYS.get(name, ())) != js["colors"]:
            problems.append(f"{name}: SECTION_COLOR_KEYS differs from the catalog JSON")
    product = [s["value"] for s in json_sections["GALLERY"].get("product_styles", [])]
    if list(PRODUCT_SUBTYPE_STYLES) != product:
        problems.append(f"PRODUCT_SUBTYPE_STYLES {list(PRODUCT_SUBTYPE_STYLES)} != JSON {product}")
    if list(ANIMATION_STYLES) != FE_CATALOG["animation_styles"]:
        problems.append(f"ANIMATION_STYLES {list(ANIMATION_STYLES)} != JSON {FE_CATALOG['animation_styles']}")
    anim_line = re.search(r"`animation_style`: (.+)\.", prompt)
    prompt_anims = re.findall(r'"([\w-]+)"', anim_line.group(1)) if anim_line else []
    if prompt_anims != FE_CATALOG["animation_styles"]:
        problems.append(f"prompt animation styles {prompt_anims} != JSON {FE_CATALOG['animation_styles']}")


# ---------------------------------------------------------------------------
# Frontend checks
# ---------------------------------------------------------------------------

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


def check_picker(picker: dict[str, list[int]], problems: list[str]) -> None:
    """Every style the user can pick must be one the AI may send (the catalog
    also lists variants and hidden styles the picker does not show)."""
    for key, name in PICKER_TO_CATALOG.items():
        fe_styles = picker.get(key)
        if key == "gallery":
            # The gallery block holds the product list first, then the photo list.
            fe_styles = picker.get("gallery:product", [])
            split = next((i for i in range(1, len(fe_styles)) if fe_styles[i] <= fe_styles[i - 1]), None)
            product, photo = (fe_styles[:split], fe_styles[split:]) if split else (fe_styles, [])
            if set(product) - set(PRODUCT_SUBTYPE_STYLES):
                problems.append(f"GALLERY product picker styles {sorted(set(product) - set(PRODUCT_SUBTYPE_STYLES))} are not in the catalog")
            fe_styles = photo
        if not fe_styles:
            continue  # not every section has a picker block
        missing = set(fe_styles) - {v for v, _l, _d in SECTION_STYLES.get(name, ())}
        if missing:
            problems.append(f"{name}: picker styles {sorted(missing)} are not in the catalog")


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
    src = _read(path)
    templates: dict[str, list[tuple[str, str | None]]] = {}
    ids = list(re.finditer(r"^\s{4}id: '(\w+)'", src, re.M))
    for i, m in enumerate(ids):
        block = src[m.end(): ids[i + 1].start() if i + 1 < len(ids) else len(src)]
        templates[m.group(1)] = [
            (SECTION_TYPE_ID_MAP.get(int(t), f"type{t}"), sub or None)
            for t, sub in re.findall(r"type: (\d+), style: \d+(?:, section_subtype: '(\w+)')?", block)
        ]
    return templates


def fe_constants_types(fe_repo: str) -> dict[int, str] | None:
    path = os.path.join(fe_repo, "src", "config", "constants.js")
    if not os.path.exists(path):
        return None
    m = re.search(r"LANDING_PAGE_TEMPLATE_TYPE_V2\s*[:=]\s*\{(.*?)\}", _read(path), re.S)
    if not m:
        return None
    return {int(v): k for k, v in re.findall(r"(\w+):\s*(\d+)", m.group(1))}


def check_frontend(fe_repo: str, problems: list[str]) -> None:
    for local, fe_rel in FE_DOCS.items():
        fe_path = os.path.join(fe_repo, fe_rel)
        if not os.path.exists(fe_path):
            problems.append(f"{fe_rel} not found in the frontend repo")
        elif _read(fe_path) != _read(local):
            problems.append(
                f"{os.path.relpath(local, ROOT)} differs from fe-serey-web {fe_rel} — copy the frontend file over"
            )

    js_path = os.path.join(fe_repo, FE_BUILDER)
    js = _read(js_path)
    check_picker(parse_picker(js), problems)

    resolvable = parse_resolve_type_key(js)
    if resolvable is None:
        problems.append("could not parse resolveTypeKey() in the FE file")
    else:
        numeric, names = resolvable
        for name in GENERATABLE_SECTIONS:
            type_id = SECTION_TYPE_NAME_TO_ID.get(name)
            if name not in names or (type_id is not None and type_id not in numeric):
                problems.append(f"{name} is generatable but FE resolveTypeKey() cannot map it — the builder would drop it")

    fe_templates = parse_fe_templates(js_path)
    if fe_templates is not None:
        if set(fe_templates) != set(FRONTEND_TEMPLATES):
            problems.append(f"templates: FE {sorted(fe_templates)} != backend {sorted(FRONTEND_TEMPLATES)}")
        for tid in set(fe_templates) & set(FRONTEND_TEMPLATES):
            backend = [(sec, sub) for sec, _style, sub, _hidden in FRONTEND_TEMPLATES[tid]["sections"]]
            if fe_templates[tid] != backend:
                problems.append(f"template {tid}: FE structure {fe_templates[tid]} != backend {backend}")

    fe_types = fe_constants_types(fe_repo)
    if fe_types:
        for type_id, fe_name in fe_types.items():
            cat_name = SECTION_TYPE_ID_MAP.get(type_id)
            if cat_name is None:
                problems.append(f"type {type_id} ({fe_name}) exists in FE constants but not in catalog")
            elif cat_name != fe_name:
                problems.append(f"type {type_id}: FE {fe_name} != catalog {cat_name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fe-repo", default=DEFAULT_FE_REPO)
    ap.add_argument("--write-snapshot", action="store_true")
    args = ap.parse_args()

    problems: list[str] = []
    check_local(problems)

    fe_repo = os.path.abspath(args.fe_repo)
    if os.path.exists(os.path.join(fe_repo, FE_BUILDER)):
        print(f"comparing against frontend repo: {fe_repo}")
        if args.write_snapshot:
            picker = parse_picker(_read(os.path.join(fe_repo, FE_BUILDER)))
            with open(SNAPSHOT, "w", encoding="utf8") as f:
                json.dump(picker, f, indent=2, sort_keys=True)
            print(f"snapshot written: {SNAPSHOT}")
        check_frontend(fe_repo, problems)
    elif os.path.exists(SNAPSHOT):
        print(f"frontend repo not found at {fe_repo} — local checks + picker snapshot only")
        with open(SNAPSHOT, encoding="utf8") as f:
            check_picker(json.load(f), problems)
    else:
        print(f"frontend repo not found at {fe_repo} — local checks only")

    if problems:
        print(f"\nDRIFT — {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK — prompt, catalog JSON and services/section_catalog.py match the frontend.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
