from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "speech": ROOT / "apps/web/components/speech-capture-v19.tsx",
    "shortcut": ROOT / "apps/web/components/speech-shortcut-v19.tsx",
    "medication": ROOT / "apps/web/components/speech-medication-proposal-v19.tsx",
    "input": ROOT / "apps/web/app/input/page.tsx",
    "care": ROOT / "apps/web/app/care/layout.tsx",
    "patient": ROOT / "apps/web/app/patient-record/layout.tsx",
    "med_layout": ROOT / "apps/web/app/medications/layout.tsx",
    "routes": ROOT / "apps/api/app/speech_capture_v19_routes.py",
    "models": ROOT / "apps/api/app/speech_capture_v19_models.py",
}

missing = [str(path.relative_to(ROOT)) for path in FILES.values() if not path.exists()]
assert not missing, f"missing v19 files: {missing}"

source = {name: path.read_text(encoding="utf-8") for name, path in FILES.items()}
combined_web = "\n".join(source[name] for name in ("speech", "shortcut", "medication", "input", "care", "patient", "med_layout"))

for forbidden in ("window.prompt", "window.alert", "window.confirm"):
    assert forbidden not in combined_web, f"browser dialog remains: {forbidden}"

for required in (
    "aria-live",
    "Start microphone",
    "Stop recording",
    "Raw audio",
    "Source transcript",
    "Negation preserved",
    "Uncertainty highlighted",
    "Medication proposals only",
    "reviewed the transcript",
    "min-height:44px",
):
    assert required.lower() in source["speech"].lower(), f"speech UI missing {required}"

assert 'mode="voice_command" createClinicalNote={false}' in source["input"], "Quick Input is not wired to operational speech"
assert 'mode="consultation_transcription"' in source["care"], "Care Brief speech integration missing"
assert 'mode="clinical_dictation"' in source["patient"], "Patient Record speech integration missing"
assert "SpeechMedicationProposalV19" in source["med_layout"], "Medication Safety speech handoff missing"
assert 'createClinicalNote={false}' in source["med_layout"], "Medication speech must not create a clinical note automatically"

routes = source["routes"]
for required in (
    "raw-audio retention is disabled",
    "Medication Foundation v18 must calculate and verify",
    "a verified clinical role must confirm a clinical note",
    "stale speech review",
    "acceptedTaskIds",
    "rejectedSuggestionIds",
    "noticeAcknowledged",
):
    assert required.lower() in routes.lower(), f"speech API missing safety boundary: {required}"

assert "patientRef" not in routes.split("class CaptureCreate", 1)[1].split("class CaptureConfirm", 1)[0], "browser patient reference must not be accepted"
assert "raw_audio_retained: bool = False" in source["models"], "raw audio must default to off"
assert "transcript_text" in source["models"] and "final_text" in source["models"], "transcript and final record evidence are not separated"

print("SPEECH_CAPTURE_V19_USABILITY_AND_SAFETY_AUDIT_PASSED")
