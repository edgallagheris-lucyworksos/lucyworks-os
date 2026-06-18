"use client";

import type { OperationalTarget } from "@/lib/operational-actions";

function updateText(target: OperationalTarget) {
  const subject = target.label.replace(/^.*?\/ /, "");
  const blocker = target.blocker || "the next step is being confirmed";
  const next = target.nextAction || "the team will update again once the next action is complete";
  return `${subject} is currently being progressed. Current blocker: ${blocker}. Next action: ${next}. We will update again once this is complete or if the plan changes.`;
}

export function ContactUpdateDraft({ target }: { target: OperationalTarget }) {
  const text = updateText(target);
  const note = `Internal note: ${target.label}. Blocker: ${target.blocker || "none"}. Next: ${target.nextAction || "not set"}.`;
  return <section className="cud"><style>{css}</style><b>Generated contact update</b><p>{text}</p><div><button type="button" onClick={() => navigator.clipboard?.writeText(text)}>Copy update</button><button type="button" onClick={() => navigator.clipboard?.writeText(note)}>Copy internal note</button></div></section>;
}

const css = `.cud{border:1px solid #31557f;background:#0b1628;border-radius:16px;padding:12px;margin:12px 0}.cud b{display:block;margin-bottom:8px}.cud p{color:#dbeafe;line-height:1.45}.cud div{display:flex;gap:8px;flex-wrap:wrap}.cud button{border:1px solid #31557f;background:#10223c;color:#e6edf7;border-radius:12px;padding:9px 10px}`;
