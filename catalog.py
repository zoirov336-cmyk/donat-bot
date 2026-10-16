import json
import os
import sys

_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog.json")

with open(_path, encoding="utf-8") as f:
    _raw = json.load(f)

CURRENCY: str = _raw.get("currency", "so'm")
CATEGORIES: list[dict] = _raw["categories"]
ITEMS: dict[str, dict] = {}

for _cat in CATEGORIES:
    for _it in _cat["items"]:
        if _it["id"] in ITEMS:
            print(f"XATO: catalog.json da takrorlangan id: {_it['id']}", file=sys.stderr)
            sys.exit(1)
        if not _it.get("commands"):
            print(f"XATO: '{_it['id']}' uchun commands bo'sh", file=sys.stderr)
            sys.exit(1)
        _it["category_id"] = _cat["id"]
        _it["full_title"] = f"{_cat['title']} • {_it['title']}"
        ITEMS[_it["id"]] = _it


def money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + f" {CURRENCY}"
