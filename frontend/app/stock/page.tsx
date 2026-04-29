"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { HospitalShell } from "@/components/hospital-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type StockItem = { id: number; name: string; category: string; location: string; current_quantity: number; reorder_threshold: number; authorised_supplier?: string | null; compliance_note: string; active: boolean };
type StockOrder = { id: number; stock_item_id?: number | null; episode_id?: number | null; item_name: string; reason: string; urgency: string; supplier?: string | null; status: string };

export default function StockPage() {
  const [items, setItems] = useState<StockItem[]>([]);
  const [orders, setOrders] = useState<StockOrder[]>([]);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("clinical");
  const [location, setLocation] = useState("main stock");
  const [quantity, setQuantity] = useState("0");
  const [threshold, setThreshold] = useState("1");
  const [orderName, setOrderName] = useState("");
  const [orderReason, setOrderReason] = useState("");
  const [status, setStatus] = useState("");

  async function load() {
    const [itemRes, orderRes] = await Promise.all([
      fetch(`${API_BASE}/api/stock-items`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/stock-orders`, { cache: "no-store" }),
    ]);
    setItems(await itemRes.json());
    setOrders(await orderRes.json());
  }

  useEffect(() => { load(); }, []);

  async function createItem() {
    if (!name.trim()) return;
    setStatus("Creating stock item...");
    await fetch(`${API_BASE}/api/stock-items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, category, location, current_quantity: Number(quantity), reorder_threshold: Number(threshold), compliance_note: "Added from Stock control" }),
    });
    setName("");
    setStatus("Stock item created.");
    await load();
  }

  async function createOrder() {
    if (!orderName.trim()) return;
    setStatus("Creating stock order...");
    await fetch(`${API_BASE}/api/stock-orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_name: orderName, reason: orderReason || "Stock required for clinical flow", urgency: "amber", status: "needed" }),
    });
    setOrderName(""); setOrderReason("");
    setStatus("Stock order created and linked work generated.");
    await load();
  }

  async function completeOrder(id: number) {
    setStatus("Completing stock order...");
    await fetch(`${API_BASE}/api/stock-orders/${id}/complete`, { method: "POST" });
    setStatus("Stock order completed.");
    await load();
  }

  const low = items.filter((x) => x.current_quantity <= x.reorder_threshold);
  const openOrders = orders.filter((x) => x.status !== "complete");
  const urgent = openOrders.filter((x) => x.urgency === "red" || x.urgency === "amber");

  return (
    <AuthGuard allowedRoles={["ops_manager", "nurse", "admin"]}>
      {() => (
        <HospitalShell title="Stock" subtitle="Ordering pressure, missing items and operational stock blockers">
          {status ? <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12, marginBottom: 16, background: "#0f172a" }}>{status}</div> : null}

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a", marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>Create stock item</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10 }}>
              <label>Name<br /><input value={name} onChange={(e) => setName(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Category<br /><input value={category} onChange={(e) => setCategory(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Location<br /><input value={location} onChange={(e) => setLocation(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Qty<br /><input value={quantity} onChange={(e) => setQuantity(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Reorder threshold<br /><input value={threshold} onChange={(e) => setThreshold(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
            </div>
            <button onClick={createItem} style={{ marginTop: 12, background: "#14b8a6", color: "#020617", border: 0, borderRadius: 10, padding: "10px 14px", fontWeight: 800 }}>Create stock item</button>
          </section>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a", marginBottom: 18 }}>
            <h2 style={{ marginTop: 0 }}>Create stock order</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
              <label>Item name<br /><input value={orderName} onChange={(e) => setOrderName(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
              <label>Reason<br /><input value={orderReason} onChange={(e) => setOrderReason(e.target.value)} style={{ width: "100%", padding: 10, borderRadius: 10 }} /></label>
            </div>
            <button onClick={createOrder} style={{ marginTop: 12, background: "#14b8a6", color: "#020617", border: 0, borderRadius: 10, padding: "10px 14px", fontWeight: 800 }}>Create stock order</button>
          </section>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 18 }}>
            <section style={{ border: "1px solid #7f1d1d", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Low stock</div><div style={{ fontSize: 34 }}>{low.length}</div></section>
            <section style={{ border: "1px solid #78350f", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Urgent orders</div><div style={{ fontSize: 34 }}>{urgent.length}</div></section>
            <section style={{ border: "1px solid #1f2937", borderRadius: 18, padding: 16, background: "#0f172a" }}><div style={{ color: "#94a3b8" }}>Open orders</div><div style={{ fontSize: 34 }}>{openOrders.length}</div></section>
          </div>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden", marginBottom: 18 }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Stock items</div>
            {items.map((item) => (
              <div key={item.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <strong>{item.name}</strong>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{item.category} • {item.location} • qty {item.current_quantity} / reorder {item.reorder_threshold}</div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>supplier {item.authorised_supplier || "-"} • {item.compliance_note || "no compliance note"}</div>
              </div>
            ))}
            {!items.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No stock items yet.</div> : null}
          </section>

          <section style={{ border: "1px solid #1f2937", borderRadius: 18, overflow: "hidden" }}>
            <div style={{ padding: 16, background: "#0f172a", fontWeight: 700 }}>Stock orders</div>
            {orders.map((order) => (
              <div key={order.id} style={{ padding: 16, borderTop: "1px solid #1f2937" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><strong>{order.item_name}</strong><span>{order.urgency} • {order.status}</span></div>
                <div style={{ color: "#94a3b8", marginTop: 6 }}>{order.reason} • supplier {order.supplier || "-"}</div>
                {order.status !== "complete" ? <button onClick={() => completeOrder(order.id)} style={{ marginTop: 10, borderRadius: 10, padding: "8px 10px" }}>Complete</button> : null}
              </div>
            ))}
            {!orders.length ? <div style={{ padding: 16, color: "#94a3b8" }}>No stock orders yet.</div> : null}
          </section>
        </HospitalShell>
      )}
    </AuthGuard>
  );
}
