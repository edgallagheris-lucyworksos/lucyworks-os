#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "apps/api/app/medication_foundation_v18_routes.py"
text = PATH.read_text()


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one medication backend target, found {count}: {old[:80]}")
    text = text.replace(old, new, 1)


replace_once(
    'def stable_ref(prefix: str, *parts: str) -> str:\n',
    '''def route_key(value: str) -> str:\n    item = normalise(value).replace("intravenous", "iv").replace("intramuscular", "im").replace("subcutaneous", "sc")\n    aliases = {"iv use": "iv", "im use": "im", "sc use": "sc", "oral use": "oral", "by mouth": "oral"}\n    return aliases.get(item, item)\n\n\ndef split_values(values: list[str]) -> list[str]:\n    output: list[str] = []\n    for value in values:\n        for part in re.split(r"[,;]|\\band\\b", value, flags=re.I):\n            cleaned = part.strip()\n            if cleaned and cleaned not in output:\n                output.append(cleaned)\n    return output\n\n\ndef stable_ref(prefix: str, *parts: str) -> str:\n''',
)
replace_once('        canonical = item.model_dump(mode="json")\n', '        canonical = item.model_dump()\n')
replace_once('            active_substances=_texts(node, active_aliases),\n            target_species=_texts(node, species_aliases),\n            routes=_texts(node, route_aliases),\n', '            active_substances=split_values(_texts(node, active_aliases)),\n            target_species=split_values(_texts(node, species_aliases)),\n            routes=split_values(_texts(node, route_aliases)),\n')
replace_once('    if product.routes and normalise(protocol.route) not in {normalise(item) for item in product.routes}:\n', '    if product.routes and route_key(protocol.route) not in {route_key(item) for item in product.routes}:\n')

PATH.write_text(text)
print("Medication foundation v18 backend hardening applied")
