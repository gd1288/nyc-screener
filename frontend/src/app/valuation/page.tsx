"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import PropertyWorkspace from "@/components/ValuationWorkspace";
import { api, useApi, type AddressLookupResult, type ImportableListing, type ValuationProperty } from "@/lib/api";
import { Card, Empty, ErrorNote, PageHeader, Tag, buttonCls, ghostButtonCls, inputCls } from "@/components/ui";
import { money, num } from "@/lib/format";

// ---------------------------------------------------------------- page shell (property list + create)

export default function ValuationPage() {
  // useSearchParams needs a Suspense boundary or it opts the whole route out of prerendering.
  return (
    <Suspense fallback={<div className="p-8 text-center text-sm text-stone-500">Loading…</div>}>
      <ValuationWorkspacePage />
    </Suspense>
  );
}

function ValuationWorkspacePage() {
  const { data: properties, error, loading, reload } = useApi<ValuationProperty[]>("/valuation/properties");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);

  // Deep link from a listing page: /valuation?import=<listingId> imports it once on arrival.
  const searchParams = useSearchParams();
  const importParam = searchParams.get("import");
  const autoImported = useRef<string | null>(null);

  useEffect(() => {
    if (!importParam || autoImported.current === importParam) return;
    autoImported.current = importParam;
    api<ValuationProperty>(`/valuation/properties/from-listing/${importParam}`, { method: "POST" })
      .then((p) => {
        setSelectedId(p.id);
        reload();
      })
      .catch(() => setImporting(true)); // fall back to the picker if that listing can't be imported
  }, [importParam, reload]);

  const effectiveSelectedId = selectedId ?? properties?.[0]?.id ?? null;
  const selected = properties?.find((p) => p.id === effectiveSelectedId) ?? null;

  async function remove(id: number) {
    if (!confirm("Delete this saved property?")) return;
    await api(`/valuation/properties/${id}`, { method: "DELETE" });
    if (selectedId === id) setSelectedId(null);
    reload();
  }

  return (
    <div>
      <PageHeader
        title="Valuation"
        subtitle="Run cash-flow scenarios for any property — saved listings or hypothetical ones."
        action={
          <div className="flex gap-2">
            <button className={ghostButtonCls} onClick={() => setImporting(true)}>
              Import from screener
            </button>
            <button className={buttonCls} onClick={() => setCreating(true)}>
              + New property
            </button>
          </div>
        }
      />
      <ErrorNote error={error} />
      {importing && (
        <div className="mb-4">
          <ImportFromScreener
            onImported={(p) => {
              setImporting(false);
              setSelectedId(p.id);
              reload();
            }}
            onCancel={() => setImporting(false)}
          />
        </div>
      )}
      {creating && (
        <div className="mb-4">
          <NewPropertyForm
            onCreated={(p) => {
              setCreating(false);
              setSelectedId(p.id);
              reload();
            }}
            onCancel={() => setCreating(false)}
          />
        </div>
      )}
      {!loading && properties && properties.length === 0 && !creating && (
        <Empty title="No saved properties yet">Create one to start running valuation scenarios.</Empty>
      )}
      {properties && properties.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
          <div className="flex flex-row gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">
            {properties.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                className={`shrink-0 rounded-lg border px-3 py-2 text-left text-sm lg:shrink ${
                  p.id === effectiveSelectedId ? "border-stone-900 bg-stone-900 text-white" : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
                }`}
              >
                <div className="font-medium">{p.label}</div>
                <div className={`text-xs ${p.id === effectiveSelectedId ? "text-stone-300" : "text-stone-500"}`}>{money(p.price, true)}</div>
              </button>
            ))}
          </div>
          {selected && (
            <div className="space-y-2">
              {/* The picker above is component state, which a link can't restore — this is how a
                  scenario gets a URL you can bookmark or send to someone. */}
              <Link href={`/valuation/${selected.id}`} className="inline-block text-sm text-stone-500 underline hover:text-stone-800">
                Open on its own page ↗
              </Link>
              <PropertyWorkspace key={selected.id} property={selected} onDelete={() => remove(selected.id)} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ImportFromScreener({ onImported, onCancel }: { onImported: (p: ValuationProperty) => void; onCancel: () => void }) {
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(q), 250);
    return () => clearTimeout(timer);
  }, [q]);

  const { data: listings, error } = useApi<ImportableListing[]>(
    `/valuation/importable-listings?limit=25${debouncedQ.trim() ? `&q=${encodeURIComponent(debouncedQ.trim())}` : ""}`,
  );

  async function importListing(id: number) {
    setBusyId(id);
    setErr(null);
    try {
      onImported(await api<ValuationProperty>(`/valuation/properties/from-listing/${id}`, { method: "POST" }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card
      title="Import from screener"
      action={
        <button className={ghostButtonCls} onClick={onCancel}>
          Cancel
        </button>
      }
    >
      <input className={inputCls} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by address…" />
      <ErrorNote error={err ?? error} />
      {listings && listings.length === 0 && <p className="mt-3 text-sm text-stone-500">No active listings match.</p>}
      {listings && listings.length > 0 && (
        <ul className="mt-3 divide-y divide-stone-100">
          {listings.map((l) => (
            <li key={l.id} className="flex items-center justify-between gap-3 py-2">
              <div className="min-w-0">
                <div className="truncate text-sm text-stone-800">
                  {l.address}
                  {l.unit && <span className="text-stone-500"> #{l.unit}</span>}
                  {l.ownership === "likely_coop" && (
                    <span className="ml-2">
                      <Tag tone="warn">likely co-op</Tag>
                    </span>
                  )}
                </div>
                <div className="text-xs text-stone-500">
                  {money(l.price, true)}
                  {l.bedrooms != null && ` · ${l.bedrooms} bd`}
                  {l.sqft && ` · ${num(l.sqft)} sqft`}
                </div>
              </div>
              <button
                className={ghostButtonCls}
                onClick={() => importListing(l.id)}
                disabled={busyId === l.id}
              >
                {busyId === l.id ? "Importing…" : l.already_imported ? "Import again" : "Import"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function NewPropertyForm({ onCreated, onCancel }: { onCreated: (p: ValuationProperty) => void; onCancel: () => void }) {
  const [label, setLabel] = useState("");
  const [address, setAddress] = useState("");
  const [price, setPrice] = useState("1000000");
  const [sqft, setSqft] = useState("");
  const [bedrooms, setBedrooms] = useState("");
  const [rentEstimate, setRentEstimate] = useState("");
  const [lookup, setLookup] = useState<AddressLookupResult | null>(null);
  const [lookingUp, setLookingUp] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function doLookup() {
    if (!address.trim()) return;
    setLookingUp(true);
    setErr(null);
    try {
      setLookup(await api<AddressLookupResult>("/valuation/lookup", { method: "POST", body: JSON.stringify({ address }) }));
    } catch (e) {
      setLookup(null);
      setErr((e as Error).message);
    } finally {
      setLookingUp(false);
    }
  }

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      const created = await api<ValuationProperty>("/valuation/properties", {
        method: "POST",
        body: JSON.stringify({
          label: label.trim() || address.trim() || "Untitled property",
          address: lookup?.address ?? (address.trim() || null),
          nta_code: lookup?.nta_code ?? null,
          price: Number(price) || 0,
          sqft: sqft ? Number(sqft) : null,
          bedrooms: bedrooms ? Number(bedrooms) : null,
          rent_estimate: rentEstimate ? Number(rentEstimate) : null,
        }),
      });
      onCreated(created);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="New property">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-xs text-stone-600">
          Label
          <input className={`${inputCls} mt-1`} value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. FiDi 2BR" />
        </label>
        <label className="text-xs text-stone-600 sm:col-span-2">
          Address (optional — resolves the neighborhood)
          <div className="mt-1 flex gap-2">
            <input
              className={inputCls}
              value={address}
              onChange={(e) => {
                setAddress(e.target.value);
                setLookup(null);
              }}
              placeholder="15 William St, New York, NY"
            />
            <button type="button" className={ghostButtonCls} onClick={doLookup} disabled={lookingUp || !address.trim()}>
              {lookingUp ? "Looking up…" : "Look up"}
            </button>
          </div>
          {lookup && (
            <p className="mt-1 text-xs text-emerald-700">
              {lookup.neighborhood_name ? `Resolved to ${lookup.neighborhood_name}` : "Geocoded, but no neighborhood match"}
            </p>
          )}
        </label>
        <label className="text-xs text-stone-600">
          Price
          <input className={`${inputCls} mt-1`} type="number" value={price} onChange={(e) => setPrice(e.target.value)} />
        </label>
        <label className="text-xs text-stone-600">
          Sqft
          <input className={`${inputCls} mt-1`} type="number" value={sqft} onChange={(e) => setSqft(e.target.value)} />
        </label>
        <label className="text-xs text-stone-600">
          Bedrooms
          <input className={`${inputCls} mt-1`} type="number" value={bedrooms} onChange={(e) => setBedrooms(e.target.value)} />
        </label>
        <label className="text-xs text-stone-600">
          Monthly rent (if known)
          <input className={`${inputCls} mt-1`} type="number" value={rentEstimate} onChange={(e) => setRentEstimate(e.target.value)} />
        </label>
      </div>
      <ErrorNote error={err} />
      <div className="mt-3 flex gap-2">
        <button className={buttonCls} onClick={save} disabled={saving || !price}>
          {saving ? "Saving…" : "Save property"}
        </button>
        <button className={ghostButtonCls} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </Card>
  );
}
