"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type DomainPressure = {
  discharge_blocked: number;
  pharmacy_open: number;
  stock_orders_open: number;
  low_stock: number;
};

function border(value: number) {
  if (value >= 5) return "1px solid #7f1d1d";
  if (value >= 2) return "1px solid #78350f";
  return "1px solid #14532d";
}

export function DomainPressurePanel() {
  const [domain, setDomain] = useState<DomainPressure | null>(null);

  useEffect(() => {
    async function load() {
      const res = await fetch(`${API_BASE}/api/domain-pressure`, { cache: "no-store" });
      setDomain(await res.json());
    }
    load();
  }, []);

  if (!domain) return null;

  const cards: [string, number, string, string][] = [
    ["Blocked discharge", domain.discharge_blocked, "Discharge readiness records that are not ready.", "/discharge"],
    ["Pharmacy open", domain.pharmacy_open, "Open medication and compliance-linked pharmacy requests.", "/pharmacy"],
    ["Stock orders open", domain.stock_orders_open, "Stock orders still needed for flow.", "/stock"],
    ["Low stock", domain.low_stock, "Items at or below reorder threshold.", "/stock"],
  ];

  return (
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
      {cards.map(([label, value, text, href]) => (
        <Link key={label} href={href} style={{ border: border(value), borderRadius: 18, padding: 16, background: "#0f172a", display: "block" }}>
          <div style={{ color: "#94a3b8" }}>{label}</div>
          <div style={{ fontSize: 36, marginTop: 8 }}>{value}</div>
          <div style={{ color: "#94a3b8", marginTop: 8 }}>{text}</div>
        </Link>
      ))}
    </section>
  );
}
