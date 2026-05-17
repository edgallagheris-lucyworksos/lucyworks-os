import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "catalogue_smoke_test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.catalogue_models import DiagnosticCatalogueItem, FormularyCatalogueItem, ProcedureCatalogueItem
from app.database import engine
from app.main import app
from app.models import ProcedureType, StockItem

print("\n--- RUNNING CATALOGUE IMPORT SMOKE TEST ---\n")

PROCEDURES = [
    {"code":"ECC-PERI","name":"Pericardiocentesis","specialty":"ECC","duration_est_minutes":30,"kit_list":"['US probe','sterile chest tap kit']","staffing_requirements":"['SV','JV or nurse']","risks":"arrhythmia, hemorrhage","SOP_link":"/sop/ecc-peri"},
    {"code":"ECC-THOR","name":"Thoracocentesis","specialty":"ECC","duration_est_minutes":30,"kit_list":"['thoracocentesis kit']","staffing_requirements":"['SV or ECC vet','nurse']","risks":"lung laceration, infection","SOP_link":"/sop/ecc-thor"},
    {"code":"ORTH-ARTHRO","name":"Arthroscopy (shoulder/elbow/stifle)","specialty":"Ortho","duration_est_minutes":120,"kit_list":"['arthroscopy tower','shaver','pump']","staffing_requirements":"['Ortho surgeon','nurse or tech']","risks":"fluid extravasation","SOP_link":"/sop/ortho-arthro"},
    {"code":"ST-TECA","name":"Total Ear Canal Ablation","specialty":"SoftTissue","duration_est_minutes":160,"kit_list":"['microsurgery kit','ligasure']","staffing_requirements":"['Soft tissue surgeon','anaesthetist','nurse']","risks":"facial nerve damage","SOP_link":"/sop/st-teca"},
    {"code":"NEU-FMD","name":"Foramen Magnum Decompression","specialty":"Neuro","duration_est_minutes":180,"kit_list":"['neuro kit','microscope']","staffing_requirements":"['Neuro surgeon','anaesthetist','scrub nurse']","risks":"bleeding, edema","SOP_link":"/sop/neu-fmd"},
    {"code":"OPH-PHACO","name":"Phacoemulsification","specialty":"Ophtho","duration_est_minutes":100,"kit_list":"['phaco machine','IOL set']","staffing_requirements":"['Ophthalmologist','nurse']","risks":"uveitis, lens remnants","SOP_link":"/sop/oph-phaco"},
    {"code":"DENT-MAND","name":"Mandibulectomy","specialty":"Dental","duration_est_minutes":150,"kit_list":"['maxillofacial kit']","staffing_requirements":"['Dental surgeon','nurse']","risks":"hemorrhage, malocclusion","SOP_link":"/sop/dent-mand"},
    {"code":"EXOT-SHELL","name":"Chelonian Shell Repair","specialty":"Exotics","duration_est_minutes":90,"kit_list":"['orthopaedic kit','resin/PMMA']","staffing_requirements":"['Exotics vet','nurse']","risks":"infection, delayed healing","SOP_link":"/sop/exot-shell"},
]

FORMULARY = [
    {"drug_id":"AN-LIDO-CRI","name":"Lidocaine (CRI)","species_allowed":"dog;cat","dose_ranges":"dog: 25-50 mcg/kg/min; cat: 10-25 mcg/kg/min","routes":"IV","interactions":"beta-blockers (caution)","CD_schedule":"None","storage":"room temp"},
    {"drug_id":"AN-KET-CRI","name":"Ketamine (CRI)","species_allowed":"dog;cat","dose_ranges":"dog: 5-20 mcg/kg/min; cat: 5-10 mcg/kg/min","routes":"IV","interactions":"seizure risk (history)","CD_schedule":"None","storage":"room temp"},
    {"drug_id":"AN-FEN-FENT","name":"Fentanyl Patch","species_allowed":"dog;cat","dose_ranges":"dog: 2-5 mcg/kg/h; cat: 2-3 mcg/kg/h","routes":"Transdermal","interactions":"MAOIs (contraindicated)","CD_schedule":"CD Sch 2","storage":"locked cabinet"},
    {"drug_id":"NSA-ROBE","name":"Robenacoxib","species_allowed":"dog;cat","dose_ranges":"dog: 2 mg/kg q24h; cat: 1-2 mg/kg q24h","routes":"PO","interactions":"steroids (avoid), renal dz","CD_schedule":"None","storage":"room temp"},
    {"drug_id":"GI-MARO","name":"Maropitant","species_allowed":"dog;cat","dose_ranges":"dog: 1 mg/kg q24h; cat: 1 mg/kg q24-48h","routes":"PO;SC","interactions":"liver impairment (dose adjust)","CD_schedule":"None","storage":"refrigerate after opening"},
]

DIAGNOSTICS = [
    {"test_code":"CBC-HCT","name":"Hematocrit","species":"dog","method":"haematology","ref_range_low":37,"ref_range_high":55,"auto_flag_rules":"if <30 then anemia; if >60 then dehydration/polycythemia"},
    {"test_code":"BIO-T4","name":"Thyroxine (T4)","species":"cat","method":"chemistry","ref_range_low":15,"ref_range_high":60,"auto_flag_rules":"if <15 then hypothyroid; if >60 then hyperthyroid"},
    {"test_code":"BIO-SDMA","name":"SDMA","species":"dog","method":"chemistry","ref_range_low":0,"ref_range_high":14,"auto_flag_rules":"if >14 then renal concern"},
]

with TestClient(app) as client:
    r = client.get("/api/health")
    assert r.status_code == 200, r.text

    payload = {"procedures": PROCEDURES, "formulary": FORMULARY, "diagnostics": DIAGNOSTICS, "assignments": [], "actor_name": "Catalogue Test"}
    r = client.post("/api/catalogues/import", json=payload)
    assert r.status_code == 200, r.text
    counts = r.json()["counts"]
    assert counts["procedures"] == 8
    assert counts["formulary"] == 5
    assert counts["diagnostics"] == 3

    r = client.get("/api/catalogues")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["summary"]["procedures"] >= 8
    assert data["summary"]["formulary"] >= 5
    assert data["summary"]["diagnostics"] >= 3
    assert data["summary"]["restricted_formulary"] >= 1
    assert data["summary"]["cold_chain"] >= 1

    with Session(engine) as session:
        assert len(session.exec(select(ProcedureCatalogueItem)).all()) >= 8
        assert len(session.exec(select(FormularyCatalogueItem)).all()) >= 5
        assert len(session.exec(select(DiagnosticCatalogueItem)).all()) >= 3
        assert len(session.exec(select(ProcedureType)).all()) >= 8
        assert session.exec(select(StockItem).where(StockItem.name == "Fentanyl Patch")).first() is not None

print("\n--- CATALOGUE IMPORT TEST PASSED ---\n")
