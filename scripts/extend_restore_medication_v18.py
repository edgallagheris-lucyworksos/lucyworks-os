#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/restore-rehearsal.sh"
text = path.read_text()


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one restore target, found {count}: {old[:90]}")
    text = text.replace(old, new, 1)


replace_once(
    '[[ "$version" == "0012_referral_identity" ]] || { echo "restored migration version is $version, expected 0012_referral_identity" >&2; exit 1; }',
    '[[ "$version" == "0013_medication_v18" ]] || { echo "restored migration version is $version, expected 0013_medication_v18" >&2; exit 1; }',
)
replace_once(
    '  referralidentityintakev12 identitymatchreviewv12 referraldocumentv12 referraltriagev12 accessreviewv12; do',
    '  referralidentityintakev12 identitymatchreviewv12 referraldocumentv12 referraltriagev12 accessreviewv12 \\\n  productimportbatchv18 veterinaryproductv18 medicationprotocolv18 dosecalculationv18 medicationproposalv18; do',
)
replace_once(
    "  'accessReviews', (select count(*) from accessreviewv12)\n)",
    "  'accessReviews', (select count(*) from accessreviewv12),\n  'productImports', (select count(*) from productimportbatchv18),\n  'veterinaryProducts', (select count(*) from veterinaryproductv18),\n  'medicationProtocols', (select count(*) from medicationprotocolv18),\n  'doseCalculations', (select count(*) from dosecalculationv18),\n  'medicationProposals', (select count(*) from medicationproposalv18)\n)",
)

path.write_text(text)
print("Restore rehearsal extended through medication foundation v18")
