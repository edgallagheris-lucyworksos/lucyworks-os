type DialogMode = "evidence" | "notice";

type DialogOptions = {
  title: string;
  initialValue?: string;
  mode: DialogMode;
};

function openDialog({ title, initialValue = "", mode }: DialogOptions): Promise<string | null> {
  if (typeof document === "undefined") return Promise.resolve(null);

  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;z-index:10000;background:rgba(2,6,23,.72);display:grid;place-items:center;padding:16px";

    const panel = document.createElement("section");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-labelledby", "lucyworks-evidence-dialog-title");
    panel.style.cssText = "width:min(100%,560px);max-height:90vh;overflow:auto;background:#fff;color:#0f172a;border-radius:16px;padding:18px;box-shadow:0 24px 80px rgba(0,0,0,.35);font-family:Inter,system-ui,sans-serif";

    const heading = document.createElement("h2");
    heading.id = "lucyworks-evidence-dialog-title";
    heading.textContent = title;
    heading.style.cssText = "margin:0 0 12px;font-size:22px;line-height:1.25";
    panel.appendChild(heading);

    let input: HTMLTextAreaElement | null = null;
    if (mode === "evidence") {
      const label = document.createElement("label");
      label.textContent = "Evidence, reason or reference";
      label.style.cssText = "display:grid;gap:7px;font-weight:750";
      input = document.createElement("textarea");
      input.value = initialValue;
      input.rows = 5;
      input.style.cssText = "width:100%;box-sizing:border-box;min-height:120px;border:1px solid #64748b;border-radius:10px;padding:11px;font:inherit;resize:vertical";
      label.appendChild(input);
      panel.appendChild(label);
    } else {
      const text = document.createElement("p");
      text.textContent = "Review this information, then acknowledge it to continue.";
      text.style.cssText = "color:#475569";
      panel.appendChild(text);
    }

    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;justify-content:flex-end;gap:9px;flex-wrap:wrap;margin-top:16px";

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = mode === "notice" ? "Close" : "Cancel";
    cancel.style.cssText = "min-height:48px;padding:10px 16px;border:1px solid #64748b;border-radius:10px;background:#fff;color:#0f172a;font-weight:800;cursor:pointer";
    actions.appendChild(cancel);

    let confirm: HTMLButtonElement | null = null;
    if (mode === "evidence") {
      confirm = document.createElement("button");
      confirm.type = "button";
      confirm.textContent = "Confirm evidence";
      confirm.style.cssText = "min-height:48px;padding:10px 16px;border:0;border-radius:10px;background:#0f766e;color:#fff;font-weight:850;cursor:pointer";
      actions.appendChild(confirm);
    }

    panel.appendChild(actions);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    const finish = (value: string | null) => {
      document.removeEventListener("keydown", onKeyDown);
      overlay.remove();
      resolve(value);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") finish(null);
    };
    document.addEventListener("keydown", onKeyDown);
    cancel.addEventListener("click", () => finish(null));
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) finish(null);
    });
    confirm?.addEventListener("click", () => {
      const value = input?.value.trim() || "";
      if (!value) {
        input?.focus();
        input?.setAttribute("aria-invalid", "true");
        return;
      }
      finish(value);
    });

    requestAnimationFrame(() => (input || cancel).focus());
  });
}

export function requestEvidence(title: string, initialValue = ""): Promise<string | null> {
  return openDialog({ title, initialValue, mode: "evidence" });
}

export function showEvidenceNotice(message: string): Promise<string | null> {
  return openDialog({ title: message, mode: "notice" });
}
