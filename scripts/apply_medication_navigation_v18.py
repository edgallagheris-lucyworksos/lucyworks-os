#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"Expected one navigation target in {relative}, found {text.count(old)}")
    path.write_text(text.replace(old, new, 1))


replace_once(
    "apps/web/app/system-control/page.tsx",
    '  ["/episode-command", "Episode decisions"], ["/patient-record", "Patient record"], ["/clinical-execution", "Patient work"],\n  ["/patient-record/controlled-actions", "Controlled clinical actions"],',
    '  ["/episode-command", "Episode decisions"], ["/patient-record", "Patient record"], ["/clinical-execution", "Patient work"],\n  ["/medications", "Medication safety"], ["/medications/protocols", "Medication protocol governance"],\n  ["/patient-record/controlled-actions", "Controlled clinical actions"],',
)

replace_once(
    "apps/web/components/care-brief-v16.tsx",
    '<section className="actions"><Link href={data.links.episodeCommand}>Episode decisions</Link><Link href={data.links.patientRecord}>Patient record</Link><Link href={data.links.clinicalExecution}>Patient work</Link><Link href={data.links.hospitalBoard}>Hospital board</Link></section>',
    '<section className="actions"><Link href={data.links.episodeCommand}>Episode decisions</Link><Link href={data.links.patientRecord}>Patient record</Link><Link href={`/medications?episode=${encodeURIComponent(data.episodeRef)}`}>Medication safety</Link><Link href={data.links.clinicalExecution}>Patient work</Link><Link href={data.links.hospitalBoard}>Hospital board</Link></section>',
)

replace_once(
    "apps/web/app/clinical-execution/page.tsx",
    '<Link href={episodeRef ? `/patient-record?episode=${encodeURIComponent(episodeRef)}` : "/patient-record"} style={{ color: "white" }}>Patient record</Link><Link href={episodeRef ? `/episode-command?episode=${encodeURIComponent(episodeRef)}` : "/episode-command"} style={{ color: "white" }}>Episode decisions</Link>',
    '<Link href={episodeRef ? `/patient-record?episode=${encodeURIComponent(episodeRef)}` : "/patient-record"} style={{ color: "white" }}>Patient record</Link><Link href={episodeRef ? `/medications?episode=${encodeURIComponent(episodeRef)}` : "/medications"} style={{ color: "white" }}>Medication safety</Link><Link href={episodeRef ? `/episode-command?episode=${encodeURIComponent(episodeRef)}` : "/episode-command"} style={{ color: "white" }}>Episode decisions</Link>',
)

replace_once(
    "apps/web/components/detailed-patient-record-workspace.tsx",
    '<Link href={episodeRef ? `/episode-command?episode=${encodeURIComponent(episodeRef)}` : "/episode-command"} style={{ color: "white" }}>Episode decisions</Link><Link href={episodeRef ? `/clinical-execution?episode=${encodeURIComponent(episodeRef)}` : "/clinical-execution"} style={{ color: "white" }}>Patient work</Link>',
    '<Link href={episodeRef ? `/episode-command?episode=${encodeURIComponent(episodeRef)}` : "/episode-command"} style={{ color: "white" }}>Episode decisions</Link><Link href={episodeRef ? `/medications?episode=${encodeURIComponent(episodeRef)}` : "/medications"} style={{ color: "white" }}>Medication safety</Link><Link href={episodeRef ? `/clinical-execution?episode=${encodeURIComponent(episodeRef)}` : "/clinical-execution"} style={{ color: "white" }}>Patient work</Link>',
)

print("Medication navigation v18 applied")
