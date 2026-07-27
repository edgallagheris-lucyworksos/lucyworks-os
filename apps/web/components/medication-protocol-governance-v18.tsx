"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";
import type { SessionUser } from "@/lib/session";
import styles from "./medication-safety-workspace-v18.module.css";

type Product = {
  product_ref: string; source_product_id: string; territory: string; product_name: string;
  active_substances: string[]; target_species: string[]; routes: string[];
  authorisation_status: string; concentration_mg_per_ml?: number | null; spc_version?: string | null;
};
type Protocol = {
  protocol_ref: string; generic_name: string; species: string; indication: string; route: string;
  recommended_mg_per_kg: number; minimum_mg_per_kg?: number | null; maximum_mg_per_kg?: number | null;
  maximum_single_dose_mg?: number | null; interval_hours?: number | null; source_type: string;
  source_reference: string; source_version: string; status: string; version: number;
};

function number(value?: number | null) {
  return value == null ? "—" : new Intl.NumberFormat("en-GB", { maximumFractionDigits: 4 }).format(value);
}

export function MedicationProtocolGovernanceV18({ user }: { user: SessionUser }) {
  const [episodeRef, setEpisodeRef] = useState("");
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [product, setProduct] = useState<Product | null>(null);
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [draft, setDraft] = useState<Protocol | null>(null);
  const [form, setForm] = useState({
    organisation: "reference", generic: "", species: "Dog", indication: "", route: "IV",
    recommended: "", minimum: "", maximum: "", maximumSingle: "", interval: "",
    sourceType: "customer_approved_protocol", sourceReference: "", sourceVersion: "1.0",
  });
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Select an authorised product and record a governed source");
  const [error, setError] = useState("");

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("episode");
    if (initial) setEpisodeRef(initial);
  }, []);

  async function searchProducts() {
    setBusy(true); setError("");
    try {
      const params = new URLSearchParams({ status: "current", limit: "100" });
      if (query.trim()) params.set("q", query.trim());
      const data = await apiGet<{ products: Product[] }>(`/api/v18/medications/catalogue?${params}`);
      setProducts(data.products); setStatus(`${data.products.length} current products found`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Catalogue search failed"); }
    finally { setBusy(false); }
  }

  async function chooseProduct(selected: Product) {
    setProduct(selected); setDraft(null); setBusy(true); setError("");
    setForm(current => ({ ...current, generic: selected.active_substances[0] || selected.product_name, species: selected.target_species[0] || current.species, route: selected.routes[0] || current.route }));
    try {
      const data = await apiGet<{ protocols: Protocol[] }>(`/api/v18/medications/protocols?product_ref=${encodeURIComponent(selected.product_ref)}&status=`);
      setProtocols(data.protocols); setStatus(`${data.protocols.length} protocol record${data.protocols.length === 1 ? "" : "s"} found`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Protocol lookup failed"); }
    finally { setBusy(false); }
  }

  async function createDraft() {
    if (!product) return;
    setBusy(true); setError("");
    try {
      const data = await apiJson<{ protocol: Protocol }>("/api/v18/medications/protocols", {
        method: "POST",
        body: JSON.stringify({
          organisation_ref: form.organisation, product_ref: product.product_ref,
          generic_name: form.generic, species: form.species, indication: form.indication, route: form.route,
          recommended_mg_per_kg: Number(form.recommended),
          minimum_mg_per_kg: form.minimum ? Number(form.minimum) : null,
          maximum_mg_per_kg: form.maximum ? Number(form.maximum) : null,
          maximum_single_dose_mg: form.maximumSingle ? Number(form.maximumSingle) : null,
          interval_hours: form.interval ? Number(form.interval) : null,
          source_type: form.sourceType, source_reference: form.sourceReference,
          source_version: form.sourceVersion,
          reason: "Governed medication protocol drafted from a named accountable source",
        }),
      });
      setDraft(data.protocol); setProtocols(current => [...current.filter(item => item.protocol_ref !== data.protocol.protocol_ref), data.protocol]);
      setStatus("Draft saved. It cannot drive calculations until an authorised reviewer approves it.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Protocol could not be created"); }
    finally { setBusy(false); }
  }

  async function approveDraft() {
    if (!draft) return;
    setBusy(true); setError("");
    try {
      const data = await apiJson<{ protocol: Protocol }>(`/api/v18/medications/protocols/${encodeURIComponent(draft.protocol_ref)}/approve`, {
        method: "PATCH",
        body: JSON.stringify({ expected_version: draft.version, reason: "Product, species, indication, route, range and source version reviewed and approved" }),
      });
      setDraft(data.protocol); setProtocols(current => [...current.filter(item => item.protocol_ref !== data.protocol.protocol_ref), data.protocol]);
      setStatus("Protocol approved and available for deterministic patient calculations.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Protocol approval failed"); }
    finally { setBusy(false); }
  }

  const back = episodeRef ? `/medications?episode=${encodeURIComponent(episodeRef)}` : "/medications";
  return <main className={styles.page}>
    <header className={styles.hero}><div><span>LUCYWORKS OS · PROTOCOL GOVERNANCE V18</span><h1>Medication protocols</h1><p>Separate product identity from clinical dose guidance. Every rule has a source, version, approval state and accountable reviewer.</p></div><nav className={styles.nav}><Link href={back}>Medication safety</Link><Link href="/system-control">System control</Link></nav></header>
    <section className={styles.boundary}>Signed in as {user.name} · {user.role}. LucyWorks does not supply or invent dose guidance; only licensed, authorised or customer-approved content should be entered.</section>
    {error && <div className={styles.error} aria-live="assertive"><b>Unable to continue</b><span>{error}</span></div>}
    <section className={styles.columns}>
      <article className={styles.panel}><div><small className={styles.eyebrow}>1 · PRODUCT IDENTITY</small><h2>Find the product</h2></div><div className={styles.inline}><input className={styles.input} value={query} onChange={e => setQuery(e.target.value)} placeholder="Product, active substance or VM number" /><button className={styles.button} disabled={busy} onClick={() => void searchProducts()}>Search</button></div><div className={styles.results}>{products.map(item => <button className={`${styles.choice} ${product?.product_ref === item.product_ref ? styles.selected : ""}`} key={item.product_ref} onClick={() => void chooseProduct(item)}><b>{item.product_name}</b><span>{item.active_substances.join(", ") || "Active substance not parsed"}</span><small>{item.territory} · {item.source_product_id} · {item.authorisation_status}</small></button>)}</div></article>
      <article className={styles.panel}><div><small className={styles.eyebrow}>EXISTING RULES</small><h2>{protocols.length}</h2></div>{protocols.length ? protocols.map(item => <div className={styles.ledger} key={item.protocol_ref}><b>{item.indication} · {item.status}</b><span>{number(item.recommended_mg_per_kg)} mg/kg · {item.species} · {item.route}</span><small>{item.source_type} · {item.source_reference} · {item.source_version}</small></div>) : <p className={styles.muted}>Select a product to inspect its protocol history.</p>}</article>
    </section>
    <section className={`${styles.panel} ${styles.calculation}`}><div className={styles.sectionHead}><div><small className={styles.eyebrow}>2 · VERSIONED RULE</small><h2>{product ? product.product_name : "Select a product first"}</h2></div><strong aria-live="polite">{status}</strong></div><div className={styles.formGrid}><label className={styles.label}>Organisation<input className={styles.input} value={form.organisation} onChange={e => setForm({ ...form, organisation: e.target.value })} /></label><label className={styles.label}>Generic name<input className={styles.input} value={form.generic} onChange={e => setForm({ ...form, generic: e.target.value })} /></label><label className={styles.label}>Species<input className={styles.input} value={form.species} onChange={e => setForm({ ...form, species: e.target.value })} /></label><label className={styles.label}>Route<input className={styles.input} value={form.route} onChange={e => setForm({ ...form, route: e.target.value })} /></label><label className={styles.label}>Clinical indication<input className={styles.input} value={form.indication} onChange={e => setForm({ ...form, indication: e.target.value })} /></label><label className={styles.label}>Recommended mg/kg<input className={styles.input} type="number" step="any" value={form.recommended} onChange={e => setForm({ ...form, recommended: e.target.value })} /></label><label className={styles.label}>Minimum mg/kg<input className={styles.input} type="number" step="any" value={form.minimum} onChange={e => setForm({ ...form, minimum: e.target.value })} /></label><label className={styles.label}>Maximum mg/kg<input className={styles.input} type="number" step="any" value={form.maximum} onChange={e => setForm({ ...form, maximum: e.target.value })} /></label><label className={styles.label}>Maximum single dose mg<input className={styles.input} type="number" step="any" value={form.maximumSingle} onChange={e => setForm({ ...form, maximumSingle: e.target.value })} /></label><label className={styles.label}>Interval hours<input className={styles.input} type="number" step="any" value={form.interval} onChange={e => setForm({ ...form, interval: e.target.value })} /></label><label className={styles.label}>Source type<select className={styles.select} value={form.sourceType} onChange={e => setForm({ ...form, sourceType: e.target.value })}><option value="customer_approved_protocol">Customer-approved protocol</option><option value="licensed_formulary">Licensed formulary</option><option value="product_spc">Product SPC</option><option value="peer_reviewed_source">Peer-reviewed source</option></select></label><label className={styles.label}>Source reference<input className={styles.input} value={form.sourceReference} onChange={e => setForm({ ...form, sourceReference: e.target.value })} /></label><label className={styles.label}>Source version<input className={styles.input} value={form.sourceVersion} onChange={e => setForm({ ...form, sourceVersion: e.target.value })} /></label></div><div className={styles.inline}><button className={styles.button} disabled={busy || !product || !form.generic || !form.species || !form.indication || !form.recommended || !form.sourceReference} onClick={() => void createDraft()}>Save governed draft</button><button className={`${styles.button} ${styles.blue}`} disabled={busy || !draft || draft.status !== "draft"} onClick={() => void approveDraft()}>Approve current draft</button></div></section>
  </main>;
}
