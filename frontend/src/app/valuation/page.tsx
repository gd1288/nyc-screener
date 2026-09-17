"use client";

import { useEffect, useMemo, useState } from "react";
import { api, useApi, type AddressLookupResult, type ValuationProperty, type ValuationRun } from "@/lib/api";
import { Card, Empty, ErrorNote, PageHeader, Tag, buttonCls, ghostButtonCls, inputCls } from "@/components/ui";
import { money, num, pct } from "@/lib/format";

export default function ValuationPage() {
  const { data: properties, error, loading, reload } = useApi<ValuationProperty[]>("/valuation/properties");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);

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
          <button className={buttonCls} onClick={() => setCreating(true)}>
            + New property
          </button>
        }
      />
      <ErrorNote error={error} />
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
          {selected && <QuickMode key={selected.id} property={selected} onDelete={() => remove(selected.id)} />}
        </div>
      )}
    </div>
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

function factorBadge(key: string, run: ValuationRun | null) {
  const est = run?.factors?.[key];
  if (est) return <Tag tone="neutral">market: {est.source}</Tag>;
  if (run?.estimated_factors?.includes(key)) return <Tag tone="warn">no live source — estimated default</Tag>;
  return null;
}

function QuickMode({ property, onDelete }: { property: ValuationProperty; onDelete: () => void }) {
  const [price, setPrice] = useState(property.price);
  const [rent, setRent] = useState(property.rent_estimate ?? 0);
  const [rate, setRate] = useState(0.065);
  const [appreciation, setAppreciation] = useState<number | null>(null);
  const [horizon, setHorizon] = useState<"10" | "20">("10");
  const [run, setRun] = useState<ValuationRun | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  // QuickMode is remounted via `key={property.id}` in the parent when the selection changes,
  // so slider state above naturally resets to this property's own values - no reset effect needed.

  useEffect(() => {
    const timer = setTimeout(async () => {
      setPending(true);
      setErr(null);
      try {
        const overrides: Record<string, number> = { interest_rate: rate };
        if (appreciation != null) overrides.appreciation_override = appreciation;
        const result = await api<ValuationRun>(`/valuation/properties/${property.id}/run`, {
          method: "POST",
          body: JSON.stringify({ overrides, property_overrides: { price, rent_estimate: rent } }),
        });
        setRun(result);
        if (appreciation == null) setAppreciation(result.appreciation.base);
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setPending(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [property.id, price, rent, rate, appreciation]);

  const projection = run?.projections.base?.[horizon];

  return (
    <div className="space-y-4">
      <Card
        title={property.label}
        action={
          <button className={ghostButtonCls} onClick={onDelete}>
            Delete
          </button>
        }
      >
        {property.address && <p className="mb-3 text-sm text-stone-600">{property.address}</p>}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <SliderField label="Price" value={price} min={price * 0.5} max={price * 1.5} step={5000} format={(v) => money(v, true)} onChange={setPrice} />
          <SliderField label="Monthly rent" value={rent} min={0} max={Math.max(rent * 2, 5000)} step={50} format={(v) => money(v)} onChange={setRent} />
          <div>
            <SliderField label="Mortgage rate" value={rate} min={0.02} max={0.1} step={0.001} format={(v) => pct(v, 2)} onChange={setRate} />
            {factorBadge("interest_rate", run)}
          </div>
          <div>
            <SliderField
              label="Appreciation (annual)"
              value={appreciation ?? 0}
              min={-0.02}
              max={0.08}
              step={0.001}
              format={(v) => pct(v, 2)}
              onChange={setAppreciation}
            />
            {factorBadge("appreciation_override", run)}
          </div>
        </div>
        <div className="mt-4 flex items-center gap-2 text-sm">
          <span className="text-stone-600">Hold period:</span>
          {(["10", "20"] as const).map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className={`rounded-md px-2.5 py-1 ${horizon === h ? "bg-stone-900 text-white" : "border border-stone-300 text-stone-700 hover:bg-stone-50"}`}
            >
              {h} years
            </button>
          ))}
          {pending && <span className="text-xs text-stone-400">updating…</span>}
        </div>
      </Card>
      <ErrorNote error={err} />
      {run && projection && <ResultsPanel run={run} projection={projection} />}
    </div>
  );
}

function SliderField({
  label, value, min, max, step, format, onChange,
}: {
  label: string; value: number; min: number; max: number; step: number; format: (v: number) => string; onChange: (v: number) => void;
}) {
  return (
    <label className="block text-xs text-stone-600">
      <div className="mb-1 flex items-baseline justify-between">
        <span>{label}</span>
        <span className="font-semibold tabular-nums text-stone-900">{format(value)}</span>
      </div>
      <input
        type="range"
        className="w-full accent-stone-900"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

function ResultsPanel({ run, projection }: { run: ValuationRun; projection: { irr: number | null; equity_multiple: number | null; profit: number; value: number } }) {
  const cards = useMemo(
    () => [
      { label: "Cap rate", value: pct(run.cap_rate, 2) },
      { label: "Cash on cash", value: pct(run.cash_on_cash, 2) },
      { label: "Monthly cash flow", value: money(run.monthly.cash_flow) },
      { label: "IRR", value: pct(projection.irr, 1) },
      { label: "Equity multiple", value: projection.equity_multiple ? `${projection.equity_multiple}×` : "—" },
      { label: "Projected value", value: money(projection.value, true) },
    ],
    [run, projection],
  );
  return (
    <Card title="Results">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {cards.map((c) => (
          <div key={c.label}>
            <div className="text-xs text-stone-500">{c.label}</div>
            <div className="text-lg font-semibold tabular-nums text-stone-900">{c.value}</div>
          </div>
        ))}
      </div>
      {run.estimated_factors.length > 0 && (
        <p className="mt-4 text-xs text-stone-500">
          Using fixed defaults (no live data source) for: {run.estimated_factors.join(", ")}. These are candidates for{" "}
          <code className="rounded bg-stone-100 px-1">/research-sources</code>.
        </p>
      )}
      <p className="mt-2 text-xs text-stone-500">Estimated inputs: {run.estimated_fields.join(", ") || "none"}. Rent basis: {run.rent_basis}.</p>
      <p className="mt-1 text-xs text-stone-400">
        {num(run.purchase_costs.total)} in estimated purchase costs · {money(run.cash_invested)} cash invested.
      </p>
    </Card>
  );
}
