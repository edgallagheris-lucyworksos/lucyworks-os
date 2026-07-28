"""Run the v24 connected proof while keeping test-only model aliases out of product modules."""
from __future__ import annotations

import os
import runpy

os.environ.update({
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "pilot-control-v24-smoke-secret-long-enough-for-testing",
    "AUTH_ISSUER": "lucyworks-pilot-v24-smoke",
    "AUTH_AUDIENCE": "lucyworks-pilot-v24-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
})

from app.detailed_hospital_models import ClinicalNoteV8
import app.models as legacy_models

legacy_models.ClinicalNoteV8 = ClinicalNoteV8

runpy.run_path("pilot_control_v24_smoke_test.py", run_name="__main__")
