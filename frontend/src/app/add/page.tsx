"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Card, PageHeader, buttonCls, inputCls } from "@/components/ui";
import { api, type ListingRow } from "@/lib/api";

const FIELDS: { key: string; label: string; placeholder?: string; required?: boolean; type?: string }[] = [
  { key: "address", label: "Street address", placeholder: "15 William Street", required: true },
  { key: "unit", label: "Unit", placeholder: "15C" },
  { key: "price", label: "Asking price ($)", placeholder: "1150000", required: true },
  { key: "listed_date", label: "Listed on", type: "date" },
  { key: "bedrooms", label: "Bedrooms", placeholder: "1" },
  { key: "bathrooms", label: "Bathrooms", placeholder: "1" },
  { key: "sqft", label: "Square feet", placeholder: "750" },
  { key: "year_built", label: "Year built", placeholder: "2008" },
  { key: "common_charges", label: "Common charges ($/mo)", placeholder: "850" },
  { key: "property_taxes", label: "Property taxes ($/mo)", placeholder: "720" },
  { key: "rent_estimate", label: "Expected rent ($/mo)", placeholder: "4500" },
  { key: "url", label: "Listing URL", placeholder: "https://streeteasy.com/…" },
];

const NUMERIC = new Set(["price", "bedrooms", "bathrooms", "sqft", "year_built", "common_charges", "property_taxes", "rent_estimate"]);

const SAMPLE_CSV = `address,unit,price,listed_date,bedrooms,bathrooms,sqft,common_charges,property_taxes,rent_estimate,url
15 William Street,15C,1150000,2026-09-01,1,1,750,850,720,4500,https://example.com/listing`;

export default function AddPage() {
  const router = useRouter();
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [csv, setCsv] = useState("");
  const [csvResult, setCsvResult] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(form)) {
      if (v.trim() === "") continue;
      body[k] = NUMERIC.has(k) ? Number(v.replace(/[$,]/g, "")) : v.trim();
    }
    try {
      const listing = await api<ListingRow>("/listings", { method: "POST", body: JSON.stringify(body) });
      router.push(`/listing/${listing.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  async function importCsv() {
    setBusy(true);
    setCsvResult(null);
    try {
      const r = await api<{ new: number; updated: number; price_changes: number; errors: string[] }>("/listings/import", {
        method: "POST",
        body: JSON.stringify({ csv }),
      });
      setCsvResult(`${r.new} added, ${r.updated} updated (${r.price_changes} price changes).${r.errors.length ? ` Problems: ${r.errors.join("; ")}` : ""}`);
    } catch (err) {
      setCsvResult((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Add listings"
        subtitle="Track listings you find yourself (StreetEasy, broker emails, open houses). They get the same neighborhood score, investment analysis and sold detection as automatic listings."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Add one listing">
          <form onSubmit={submit} className="grid grid-cols-2 gap-3">
            {FIELDS.map((f) => (
              <label key={f.key} className={f.key === "address" || f.key === "url" ? "col-span-2 block" : "block"}>
                <span className="mb-1 block text-xs text-stone-500">{f.label}{f.required && " *"}</span>
                <input
                  className={inputCls}
                  type={f.type ?? "text"}
                  required={f.required}
                  placeholder={f.placeholder}
                  value={form[f.key] ?? ""}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                />
              </label>
            ))}
            <p className="col-span-2 text-xs text-stone-500">
              Unit number matters: it&apos;s how the app finds the recorded deed in ACRIS when the unit sells. Leave costs blank to use estimates.
            </p>
            {error && <p className="col-span-2 text-sm text-rose-700">{error}</p>}
            <div className="col-span-2">
              <button className={buttonCls} disabled={busy}>{busy ? "Adding…" : "Add & analyze"}</button>
            </div>
          </form>
        </Card>
        <Card title="Import from CSV">
          <p className="mb-2 text-sm text-stone-600">Paste rows with a header. Only <code>address</code> and <code>price</code> are required. Re-importing the same address + unit updates it and logs price changes.</p>
          <textarea className={`${inputCls} h-48 font-mono text-xs`} value={csv} onChange={(e) => setCsv(e.target.value)} placeholder={SAMPLE_CSV} />
          <div className="mt-2 flex items-center gap-3">
            <button className={buttonCls} disabled={busy || !csv.trim()} onClick={importCsv}>Import</button>
            <button className="text-xs text-stone-500 hover:text-stone-900" onClick={() => setCsv(SAMPLE_CSV)}>Use sample format</button>
          </div>
          {csvResult && <p className="mt-3 text-sm text-stone-700">{csvResult} <Link className="underline" href="/">Go to screener</Link></p>}
        </Card>
      </div>
    </>
  );
}
