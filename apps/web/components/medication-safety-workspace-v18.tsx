"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiJson } from "@/lib/api-client";
import type { SessionUser } from "@/lib/session";
import styles from "./medication-safety-workspace-v18.module.css";

type Patient = { patient_ref: string; display_name: string; species: string; breed?: string | null };
type Episode = { episode_ref: string; phase: string; current_area_ref?: string | null; owner_role: string };
type Weight = { weight_ref: string; weight_kg: number; measured_at: string };
type Allergy = { allergy_ref: string; substance_name: string; reaction: string; severity: string; confirmed: boolean };
type ActiveOrder = { order_ref: string; medication_name: string; dose: string; route: string; frequency: string };
type Product = {
  product_ref: string; source_product_id: string; territory: string; product_name: string;
  distribution_category?: string | null; authorisation_status: string; active_substances: string[];
  target_species: string[]; routes: string[]; concentration_mg_per_ml?: number | null;
  spc_version?: string | null; source_updated_at?: string | null;
};
type Protocol = {
  protocol_ref: string; indication: string; route: string; recommended_mg_per_kg: number;
  minimum_mg_per_kg?: number | null; maximum_mg_per_kg?: number | null;
  maximum_single_dose_mg?: number | null; interval_hours?: number | null;
  source_type: string; source_reference: string; source_version: string;
};
type Finding = { code?: string; message?: string; severity?: string };
type Calculation = {
  calculation_ref: string; weight_kg: number; dose_mg_per_kg: number; calculated_dose_mg: number;
  concentration_mg_per_ml?: number | null; calculated_volume_ml?: number | null;
  rounded_volume_ml?: number | null; route: string; outcome: string;
  warnings: Finding[]; blockers: Finding[];
};
type Proposal = {
  proposal_ref: string; medication_name: string; dose_mg: number; volume_ml?: number | null;
  route: string; status: string; version: number;
};
type Workspace = {
  episode: Episode; patient: Patient; weight?: Weight | null; allergies: Allergy[];
  activeOrders: ActiveOrder[]; calculations: Calculation[]; proposals: Proposal[];
  clinicalBoundary: string;
};

const prescriberRoles = new Set(["clinician", "clinical_director", "senior_clinician", "supervisor"]);
const syncRoles = new Set(["admin", "clinical_director", "governance_lead", "hospital_director"]);

function localDateTime(offsetMinutes = 30) {
  const value = new Date(Date.now() + offsetMinutes * 60_000);
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}
function label(value?: string | null) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase()) : "Not recorded";
}
function when(value?: string | null) {
  return value ? new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "Not recorded";
}
function number(value?: number | null, digits = 3) {
  return value == null ? "—" : new Intl.NumberFormat("en-GB", { maximumFractionDigits: digits }).format(value);
}
function findingText(item: Finding) { return item.message || label(item.code); }

export function MedicationSafetyWorkspaceV18({ user }: { user: SessionUser }) {
  const [episodeRef, setEpisodeRef] = useState("");
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [product, setProduct] = useState<Product | null>(null);
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [protocol, setProtocol] = useState<Protocol | null>(null);
  const [doseMgKg, setDoseMgKg] = useState("");
  const [rounding, setRounding] = useState("0.01");
  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [frequency, setFrequency] = useState("once");
  const [startsAt, setStartsAt] = useState(localDateTime());
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Open a patient episode to begin");
  const [error, setError] = useState("");

  const canPrescribe = prescriberRoles.has(user.role);
  const canSync = syncRoles.has(user.role);

  const loadWorkspace = useCallback(async (reference = episodeRef) => {
    const ref = reference.trim();
    if (!ref) return;
    setBusy(true); setError(""); setStatus("Loading patient medication context");
    try {
      const data = await apiGet<Workspace>(`/api/v18/medications/episodes/${encodeURIComponent(ref)}/workspace`);
      setWorkspace(data); setEpisodeRef(data.episode.episode_ref);
      window.history.replaceState(null, "", `/medications?episode=${encodeURIComponent(data.episode.episode_ref)}`);
      setStatus(`Live · updated ${new Date().toLocaleTimeString("en-GB")}`);
    } catch (reason) {
      setWorkspace(null); setError(reason instanceof Error ? reason.message : "Unable to load medication context");
    } finally { setBusy(false); }
  }, [episodeRef]);

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("episode");
    if (initial) { setEpisodeRef(initial); void loadWorkspace(initial); }
  }, [loadWorkspace]);

  async function searchProducts() {
    setBusy(true); setError("");
    try {
      const params = new URLSearchParams({ status: "current", limit: "100" });
      if (query.trim()) params.set("q", query.trim());
      if (workspace?.patient.species) params.set("species", workspace.patient.species);
      const data = await apiGet<{ products: Product[] }>(`/api/v18/medications/catalogue?${params}`);
      setProducts(data.products); setStatus(`${data.products.length} current products found`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Catalogue search failed"); }
    finally { setBusy(false); }
  }

  async function chooseProduct(selected: Product) {
    setProduct(selected); setProtocol(null); setCalculation(null); setProposal(null); setDoseMgKg("");
    setBusy(true); setError("");
    try {
      const params = new URLSearchParams({ product_ref: selected.product_ref, status: "approved" });
      if (workspace?.patient.species) params.set("species", workspace.patient.species);
      const data = await apiGet<{ protocols: Protocol[] }>(`/api/v18/medications/protocols?${params}`);
      setProtocols(data.protocols);
      if (data.protocols.length === 1) chooseProtocol(data.protocols[0]);
      setStatus(data.protocols.length ? `${data.protocols.length} approved protocol${data.protocols.length === 1 ? "" : "s"} available` : "No approved protocol exists for this product and species");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Protocol lookup failed"); }
    finally { setBusy(false); }
  }

  function chooseProtocol(selected: Protocol) {
    setProtocol(selected); setDoseMgKg(String(selected.recommended_mg_per_kg));
    setFrequency(selected.interval_hours ? `every ${number(selected.interval_hours)} hours` : "once");
    setCalculation(null); setProposal(null);
  }

  async function calculate() {
    if (!workspace || !product || !protocol) return;
    setBusy(true); setError(""); setCalculation(null); setProposal(null);
    try {
      const data = await apiJson<{ calculation: Calculation }>("/api/v18/medications/calculate", {
        method: "POST",
        body: JSON.stringify({
          episode_ref: workspace.episode.episode_ref,
          product_ref: product.product_ref,
          protocol_ref: protocol.protocol_ref,
          requested_mg_per_kg: Number(doseMgKg),
          rounding_increment_ml: Number(rounding),
          reason: "Patient-specific deterministic calculation reviewed in LucyWorks",
        }),
      });
      setCalculation(data.calculation);
      setStatus(data.calculation.outcome === "blocked" ? "Blocked — resolve the safety findings" : "Calculation ready for prescriber review");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Dose calculation failed"); }
    finally { setBusy(false); }
  }

  async function reviewCalculation() {
    if (!calculation) return;
    setBusy(true); setError("");
    try {
      const data = await apiJson<{ proposal: Proposal }>(`/api/v18/medications/calculations/${encodeURIComponent(calculation.calculation_ref)}/review`, {
        method: "POST",
        body: JSON.stringify({ frequency, reason: "Prescriber reviewed patient, weight, source product, protocol, formula and warnings" }),
      });
      setProposal(data.proposal); setStatus("Prescriber review recorded — prescription not yet issued");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Prescriber review failed"); }
    finally { setBusy(false); }
  }

  async function prescribe() {
    if (!proposal) return;
    setBusy(true); setError("");
    try {
      const start = new Date(startsAt).toISOString();
      const data = await apiJson<{ proposal: Proposal }>(`/api/v18/medications/proposals/${encodeURIComponent(proposal.proposal_ref)}/prescribe`, {
        method: "POST",
        body: JSON.stringify({
          expected_version: proposal.version, frequency, starts_at: start, scheduled_times: [start],
          reason: "Verified veterinary prescriber issued the reviewed prescription",
        }),
      });
      setProposal(data.proposal); setStatus("Prescription issued and first administration task scheduled");
      await loadWorkspace(episodeRef);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Prescription could not be issued"); }
    finally { setBusy(false); }
  }

  async function syncVmd() {
    setBusy(true); setError(""); setStatus("Synchronising the official VMD product snapshot");
    try {
      const data = await apiJson<{ batch: { product_count: number; created_count: number; updated_count: number; unchanged_count: number } }>("/api/v18/medications/catalogue/sync-vmd", { method: "POST" });
      const b = data.batch;
      setStatus(`VMD sync complete · ${b.product_count} products · ${b.created_count} new · ${b.updated_count} updated · ${b.unchanged_count} unchanged`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "VMD synchronisation failed"); }
    finally { setBusy(false); }
  }

  const formula = useMemo(() => calculation ? {
    dose: `${number(calculation.dose_mg_per_kg)} mg/kg × ${number(calculation.weight_kg)} kg = ${number(calculation.calculated_dose_mg)} mg`,
    volume: calculation.concentration_mg_per_ml && calculation.calculated_volume_ml != null
      ? `${number(calculation.calculated_dose_mg)} mg ÷ ${number(calculation.concentration_mg_per_ml)} mg/ml = ${number(calculation.calculated_volume_ml)} ml → ${number(calculation.rounded_volume_ml)} ml`
      : "No governed liquid concentration recorded — volume not calculated",
  } : null, [calculation]);

  const episodeQuery = episodeRef ? `?episode=${encodeURIComponent(episodeRef)}` : "";

  return <main className={styles.page}>
    <header className={styles.hero}>
      <div><span>LUCYWORKS OS · MEDICATION SAFETY V18</span><h1>Medication safety</h1><p>Versioned product identity, governed protocols and deterministic arithmetic. LucyWorks checks and prepares; the verified veterinary prescriber remains responsible.</p></div>
      <nav className={styles.nav}><Link href={`/care${episodeQuery}`}>Care brief</Link><Link href={`/patient-record${episodeQuery}`}>Patient record</Link><Link href={`/clinical-execution${episodeQuery}`}>Patient work</Link><Link href="/workspace">Patients</Link></nav>
    </header>

    <section className={styles.finder}><label className={styles.label}>Patient episode<input className={styles.input} value={episodeRef} onChange={e => setEpisodeRef(e.target.value)} placeholder="EP-..." /></label><button className={styles.button} disabled={busy || !episodeRef.trim()} onClick={() => void loadWorkspace()}>{busy ? "Working…" : "Open patient"}</button><strong aria-live="polite">{status}</strong></section>
    {error && <div className={styles.error} aria-live="assertive"><b>Unable to continue</b><span>{error}</span></div>}

    {!workspace ? <section className={styles.empty}><h2>No patient selected</h2><p>Open this page from a patient’s Care Brief, or enter the episode above.</p><Link href="/workspace">Open Patient Command</Link></section> : <>
      <section className={styles.identity}>
        <div><small>PATIENT</small><h2>{workspace.patient.display_name}</h2><p>{workspace.patient.species} · {workspace.patient.breed || "Breed not recorded"}</p></div>
        <div><small>EPISODE</small><h3>{label(workspace.episode.phase)}</h3><p>{workspace.episode.episode_ref} · {workspace.episode.current_area_ref || "No location"}</p></div>
        <div className={workspace.weight ? styles.good : styles.bad}><small>CURRENT WEIGHT</small><h3>{workspace.weight ? `${number(workspace.weight.weight_kg)} kg` : "Missing"}</h3><p>{workspace.weight ? when(workspace.weight.measured_at) : "Dose calculation blocked"}</p></div>
        <div className={workspace.allergies.some(x => x.severity === "red") ? styles.bad : styles.good}><small>ALLERGIES / ALERTS</small><h3>{workspace.allergies.length}</h3><p>{workspace.allergies.length ? workspace.allergies.map(x => x.substance_name).join(", ") : "None recorded"}</p></div>
      </section>
      <p className={styles.boundary}>{workspace.clinicalBoundary}</p>

      <section className={styles.columns}>
        <article className={styles.panel}>
          <div className={styles.sectionHead}><div><small className={styles.eyebrow}>1 · PRODUCT</small><h2>Find the exact product</h2></div>{canSync && <button className={`${styles.button} ${styles.secondary}`} disabled={busy} onClick={() => void syncVmd()}>Sync official VMD catalogue</button>}</div>
          <div className={styles.inline}><input className={styles.input} value={query} onChange={e => setQuery(e.target.value)} placeholder="Product, active substance or VM number" /><button className={styles.button} disabled={busy} onClick={() => void searchProducts()}>Search</button></div>
          <div className={styles.results}>{products.map(item => <button className={`${styles.choice} ${product?.product_ref === item.product_ref ? styles.selected : ""}`} key={item.product_ref} onClick={() => void chooseProduct(item)}><b>{item.product_name}</b><span>{item.active_substances.join(", ") || "Active substance not parsed"}</span><small>{item.territory} · {item.source_product_id} · {item.distribution_category || "Category not recorded"}</small></button>)}{!products.length && <p className={styles.muted}>Search the current catalogue. Authorised catalogue roles can synchronise the official snapshot.</p>}</div>
        </article>

        <article className={styles.panel}>
          <small className={styles.eyebrow}>2 · PROTOCOL</small><h2>Choose an approved dose rule</h2>
          {product ? <ProductSummary product={product} /> : <p className={styles.muted}>Select a product first.</p>}
          <div className={styles.results}>{protocols.map(item => <button className={`${styles.choice} ${protocol?.protocol_ref === item.protocol_ref ? styles.selected : ""}`} key={item.protocol_ref} onClick={() => chooseProtocol(item)}><b>{item.indication}</b><span>{number(item.recommended_mg_per_kg)} mg/kg · {item.route}{item.interval_hours ? ` · every ${number(item.interval_hours)} hours` : ""}</span><small>{item.source_type} · {item.source_reference} · version {item.source_version}</small></button>)}{product && !protocols.length && <p className={styles.muted}>No approved protocol exists for this product and species. LucyWorks will not invent a dose. Use Protocol governance to add a licensed or customer-approved source.</p>}</div>
          <Link href={`/medications/protocols${episodeQuery}`}>Open protocol governance →</Link>
        </article>
      </section>

      <section className={`${styles.panel} ${styles.calculation}`}><div><small className={styles.eyebrow}>3 · CALCULATE</small><h2>Deterministic patient-specific calculation</h2></div><div className={styles.formGrid}><label className={styles.label}>Requested dose mg/kg<input className={styles.input} type="number" step="any" value={doseMgKg} onChange={e => setDoseMgKg(e.target.value)} /></label><label className={styles.label}>Volume rounding increment ml<input className={styles.input} type="number" step="any" value={rounding} onChange={e => setRounding(e.target.value)} /></label><label className={styles.label}>Weight<input className={styles.input} value={workspace.weight ? `${number(workspace.weight.weight_kg)} kg` : "Missing"} disabled /></label><label className={styles.label}>Product concentration<input className={styles.input} value={product?.concentration_mg_per_ml ? `${number(product.concentration_mg_per_ml)} mg/ml` : "Not recorded"} disabled /></label></div><button className={styles.button} disabled={busy || !workspace.weight || !product || !protocol || !doseMgKg || Number(doseMgKg) <= 0} onClick={() => void calculate()}>Calculate and run safety checks</button></section>

      {calculation && formula && <section className={`${styles.resultPanel} ${styles[calculation.outcome as "warning" | "blocked"] || ""}`}><header className={styles.resultHeader}><div><small className={styles.eyebrow}>CALCULATION RESULT</small><h2>{label(calculation.outcome)}</h2></div><b>{product?.product_name}</b></header><div className={styles.formula}><strong>{formula.dose}</strong><strong>{formula.volume}</strong></div><div className={styles.metrics}><div><small>DOSE</small><b>{number(calculation.calculated_dose_mg)} mg</b></div><div><small>VOLUME</small><b>{calculation.rounded_volume_ml != null ? `${number(calculation.rounded_volume_ml)} ml` : "Not available"}</b></div><div><small>ROUTE</small><b>{calculation.route}</b></div><div><small>SOURCE</small><b>{protocol?.source_reference}</b></div></div>{calculation.blockers.length > 0 && <FindingList title="Blocks prescription" items={calculation.blockers} />}{calculation.warnings.length > 0 && <FindingList title="Warnings requiring review" items={calculation.warnings} amber />}{calculation.blockers.length === 0 && calculation.warnings.length === 0 && <div className={styles.clear}>No recorded product, protocol, weight, species, route, allergy, duplicate-order or dose-range conflicts.</div>}<div className={styles.review}><label className={styles.label}>Frequency<input className={styles.input} value={frequency} onChange={e => setFrequency(e.target.value)} /></label>{canPrescribe ? <button className={styles.button} disabled={busy || calculation.outcome === "blocked" || !frequency.trim()} onClick={() => void reviewCalculation()}>Record prescriber review</button> : <div className={styles.authority}>A verified veterinary prescriber must review this calculation. Your role can prepare it but cannot prescribe.</div>}</div></section>}

      {proposal && <section className={`${styles.panel} ${styles.prescribe}`}><div><small className={styles.eyebrow}>4 · PRESCRIBE</small><h2>{proposal.status === "prescribed" ? "Prescription issued" : "Final prescriber confirmation"}</h2></div><div className={styles.summary}><b>{proposal.medication_name}</b><span>{number(proposal.dose_mg)} mg{proposal.volume_ml != null ? ` · ${number(proposal.volume_ml)} ml` : ""} · {proposal.route} · {frequency}</span></div>{proposal.status !== "prescribed" ? <><label className={styles.label}>First administration time<input className={styles.input} type="datetime-local" value={startsAt} onChange={e => setStartsAt(e.target.value)} /></label><p className={styles.muted}>Issuing creates a medication order and first administration task. It does not record that the medicine was given.</p><button className={`${styles.button} ${styles.blue}`} disabled={busy || !canPrescribe || !startsAt} onClick={() => void prescribe()}>Issue prescription and schedule administration</button></> : <div className={styles.clear}>Order created. Administration remains a separate accountable action in Patient Work.</div>}</section>}

      <section className={`${styles.columns} ${styles.lower}`}><article className={styles.panel}><small className={styles.eyebrow}>ACTIVE MEDICATIONS</small><h2>{workspace.activeOrders.length}</h2>{workspace.activeOrders.length ? workspace.activeOrders.map(item => <div className={styles.ledger} key={item.order_ref}><b>{item.medication_name}</b><span>{item.dose} · {item.route} · {item.frequency}</span></div>) : <p className={styles.muted}>No active medication orders.</p>}</article><article className={styles.panel}><small className={styles.eyebrow}>ALLERGIES / ALERTS</small><h2>{workspace.allergies.length}</h2>{workspace.allergies.length ? workspace.allergies.map(item => <div className={`${styles.ledger} ${styles[item.severity as "red" | "amber"] || ""}`} key={item.allergy_ref}><b>{item.substance_name}</b><span>{item.reaction} · {item.confirmed ? "confirmed" : "unconfirmed"}</span></div>) : <p className={styles.muted}>No allergy or medicine alert recorded.</p>}</article></section>
    </>}
  </main>;
}

function ProductSummary({ product }: { product: Product }) {
  return <div className={styles.product}><b>{product.product_name}</b><span>{product.active_substances.join(", ") || "Active substance not parsed"}</span><small>{product.territory} · {product.source_product_id} · {product.authorisation_status.toUpperCase()}</small><small>{product.target_species.join(", ") || "Species not parsed"} · {product.routes.join(", ") || "Routes not parsed"}</small><small>{product.concentration_mg_per_ml ? `${number(product.concentration_mg_per_ml)} mg/ml` : "No liquid concentration recorded"} · SPC {product.spc_version || "version not recorded"}</small></div>;
}

function FindingList({ title, items, amber = false }: { title: string; items: Finding[]; amber?: boolean }) {
  return <div className={`${styles.findings} ${amber ? styles.amber : ""}`}><h3>{title}</h3>{items.map((item, index) => <div className={styles.finding} key={`${item.code || "finding"}-${index}`}><b>{label(item.code)}</b><span>{findingText(item)}</span></div>)}</div>;
}
