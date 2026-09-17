#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
import html
import json
import re

ROOT = Path(__file__).resolve().parent
SITE_BASE = "https://team-verdigris.github.io/Pokemon/"
OUTPUT_ROOT = ROOT / "pokemon"
MOVE_OUTPUT_ROOT = ROOT / "moves"
ABILITY_OUTPUT_ROOT = ROOT / "abilities"

FOLDERS = [
    ("artwork", "Artworks"),
    ("front", "Front"),
    ("frontShiny", "Front shiny"),
    ("back", "Back"),
    ("backShiny", "Back shiny"),
    ("icon", "Icons"),
    ("egg", "Eggs"),
    ("shadow", "Shadow"),
    ("return", "Return"),
    ("officialBackup", "Official Backup"),
]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def parse_pokemon_filename(path: Path) -> dict:
    stem = path.stem
    original_stem = stem

    is_old = False
    if re.search(r"_old$", stem, flags=re.I):
        is_old = True
        stem = re.sub(r"_old$", "", stem, flags=re.I)

    parts = stem.split("_")
    base_name = parts.pop(0) if parts else stem

    form_number = None
    is_female = False

    if parts and parts[0].isdigit():
        form_number = int(parts.pop(0))

    if parts and parts[0].lower() == "female":
        is_female = True
        parts.pop(0)

    additional_parts = parts
    additional_art_label = "_".join(additional_parts) if additional_parts else None

    variant_id = base_name
    if form_number is not None:
        variant_id += f"_{form_number}"
    if is_female:
        variant_id += "_female"
    if is_old:
        variant_id += "_old"

    return {
        "original_stem": original_stem,
        "base_name": base_name,
        "form_number": form_number,
        "is_female": is_female,
        "is_old": is_old,
        "is_additional_art": additional_art_label is not None,
        "additional_art_label": additional_art_label,
        "variant_id": variant_id,
    }


def display_name(parsed: dict) -> str:
    labels = []

    if parsed["form_number"] is not None:
        labels.append(f"Form {parsed['form_number']}")

    if parsed["is_female"]:
        labels.append("Female")

    if parsed["is_old"]:
        labels.append("OLD")

    if not labels:
        return parsed["base_name"]

    return f"{parsed['base_name']} — {' · '.join(labels)}"


def public_asset_url(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    return SITE_BASE + quote(relative, safe="/")


def collect_records() -> dict:
    records = {}

    for asset_key, folder_name in FOLDERS:
        folder = ROOT / folder_name

        if not folder.is_dir():
            continue

        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            parsed = parse_pokemon_filename(path)
            record = records.setdefault(
                parsed["variant_id"],
                {
                    "id": parsed["variant_id"],
                    "parsed": parsed,
                    "assets": {},
                    "additional": {},
                },
            )

            if parsed["is_additional_art"]:
                record["additional"].setdefault(asset_key, []).append(path)
            else:
                record["assets"][asset_key] = path
                record["parsed"] = parsed

    return records


def build_page(record: dict) -> str:
    pokemon_id = record["id"]
    parsed = record["parsed"]
    name = display_name(parsed)

    assets = record["assets"]

    preview_candidates = [
        assets.get("artwork"),
        assets.get("front"),
        assets.get("frontShiny"),
        assets.get("back"),
        assets.get("backShiny"),
        assets.get("icon"),
    ]
    preview_candidates = [path for path in preview_candidates if path]

    title = f"{name} — Team Verdigris Pokémon Assets"
    description = (
        f"{name} artwork, sprites, shiny sprites, icons and additional assets "
        "from Team Verdigris."
    )

    route_url = (
        SITE_BASE
        + "pokemon/"
        + quote(pokemon_id, safe="")
        + "/"
    )
    viewer_url = (
        SITE_BASE
        + "?pokemon="
        + quote(pokemon_id, safe="")
    )

    og_images = ""
    for image_path in preview_candidates[:4]:
        image_url = public_asset_url(image_path)
        og_images += (
            f'    <meta property="og:image" content="{html.escape(image_url, quote=True)}">\n'
        )

    twitter_image = ""
    if preview_candidates:
        image_url = public_asset_url(preview_candidates[0])
        twitter_image = (
            f'    <meta name="twitter:image" content="{html.escape(image_url, quote=True)}">\n'
        )

    relative_viewer_url = "../../?pokemon=" + quote(pokemon_id, safe="")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>{html.escape(title)}</title>

    <meta name="description" content="{html.escape(description, quote=True)}">
    <link rel="canonical" href="{html.escape(route_url, quote=True)}">

    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Team Verdigris Pokémon Assets">
    <meta property="og:title" content="{html.escape(title, quote=True)}">
    <meta property="og:description" content="{html.escape(description, quote=True)}">
    <meta property="og:url" content="{html.escape(route_url, quote=True)}">
{og_images.rstrip()}

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{html.escape(title, quote=True)}">
    <meta name="twitter:description" content="{html.escape(description, quote=True)}">
{twitter_image.rstrip()}

    <script>
        window.location.replace(
            {relative_viewer_url!r}
        );
    </script>
</head>
<body>
    <p>
        Opening
        <a href="{html.escape(relative_viewer_url, quote=True)}">
            {html.escape(name)}
        </a>
        in the Team Verdigris Pokémon Asset Viewer.
    </p>
</body>
</html>
"""


def load_snapshot() -> dict | None:
    candidates = sorted(ROOT.glob("pokemon_snapshot*.json"))
    if not candidates:
        return None

    snapshots = []
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("pokemon"), list):
            snapshots.append((path, data))
    if not snapshots:
        return None
    # Prefer the canonical filename when it is present, matching the website.
    canonical = next((data for path, data in snapshots if path.name == "pokemon_snapshot.json"), None)
    if canonical is not None:
        return canonical
    return max(snapshots, key=lambda item: str(item[1].get("generated_at", "")))[1]


def catalog_description(kind: str, entry: dict) -> str:
    description = str(entry.get("description") or "").strip()
    if kind == "move":
        type_name = (entry.get("type") or {}).get("name")
        category = entry.get("category")
        details = " · ".join(value for value in (type_name, category) if value)
        if details and description:
            return f"{details}. {description}"
        return details or description or "A custom Team Verdigris move."
    return description or "A custom Team Verdigris ability."


def build_catalog_page(kind: str, entry: dict) -> str:
    plural = "moves" if kind == "move" else "abilities"
    label = "Move" if kind == "move" else "Ability"
    entry_id = str(entry["id"])
    name = str(entry.get("name") or entry_id)
    description = catalog_description(kind, entry)
    route_url = SITE_BASE + plural + "/" + quote(entry_id, safe="") + "/"
    relative_viewer_url = f"../../?view={plural}&entry=" + quote(entry_id, safe="")
    title = f"{name} — Verdigris {label}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <meta name="description" content="{html.escape(description, quote=True)}">
    <link rel="canonical" href="{html.escape(route_url, quote=True)}">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Verdigris Dex">
    <meta property="og:title" content="{html.escape(title, quote=True)}">
    <meta property="og:description" content="{html.escape(description, quote=True)}">
    <meta property="og:url" content="{html.escape(route_url, quote=True)}">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{html.escape(title, quote=True)}">
    <meta name="twitter:description" content="{html.escape(description, quote=True)}">
    <script>window.location.replace({relative_viewer_url!r});</script>
</head>
<body>
    <p>Opening <a href="{html.escape(relative_viewer_url, quote=True)}">{html.escape(name)}</a> in the Verdigris Dex.</p>
</body>
</html>
"""


def write_catalog_routes(snapshot: dict | None) -> tuple[int, int]:
    if not snapshot:
        return 0, 0

    counts = []
    for kind, key, output_root in (
        ("move", "moves", MOVE_OUTPUT_ROOT),
        ("ability", "abilities", ABILITY_OUTPUT_ROOT),
    ):
        entries = snapshot.get(key) or []
        if entries:
            output_root.mkdir(parents=True, exist_ok=True)
        written = 0
        for entry in sorted(entries, key=lambda item: str(item.get("id", "")).lower()):
            entry_id = str(entry.get("id") or "").strip()
            if not entry_id:
                continue
            route_dir = output_root / entry_id
            route_dir.mkdir(parents=True, exist_ok=True)
            (route_dir / "index.html").write_text(
                build_catalog_page(kind, entry), encoding="utf-8"
            )
            written += 1
        if entries:
            (output_root / "routes-ready.txt").write_text(
                f"Team Verdigris {key} preview routes are generated.\n",
                encoding="utf-8",
            )
        counts.append(written)
    return counts[0], counts[1]


def main() -> None:
    records = collect_records()

    if not records:
        raise SystemExit(
            "No Pokémon assets were found. Run this script from the root "
            "of the Team-Verdigris/Pokemon repository."
        )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    written = 0

    for pokemon_id, record in sorted(
        records.items(),
        key=lambda item: item[0].lower(),
    ):
        route_dir = OUTPUT_ROOT / pokemon_id
        route_dir.mkdir(parents=True, exist_ok=True)

        (route_dir / "index.html").write_text(
            build_page(record),
            encoding="utf-8",
        )
        written += 1

    (OUTPUT_ROOT / "routes-ready.txt").write_text(
        "Team Verdigris Pokémon preview routes are generated.\n",
        encoding="utf-8",
    )

    move_count, ability_count = write_catalog_routes(load_snapshot())
    print(
        f"Generated {written} Pokémon, {move_count} move, and "
        f"{ability_count} ability preview routes."
    )


if __name__ == "__main__":
    main()
