"use client";

import { useCallback, useEffect, useState } from "react";

export type ListingRow = {
  id: number;
  source: string;
  url: string | null;
  address: string;
  unit: string | null;
  neighborhood_code: string | null;
  neighborhood: string | null;
  borough: string | null;
  latitude: number | null;
  longitude: number | null;
  price: number;
  original_price: number;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  price_per_sqft: number | null;
  year_built: number | null;
  status: "active" | "off_market" | "sold" | "withdrawn";
  ownership: "condo" | "likely_coop" | "unknown";
  listed_date: string;
  first_seen: string;
  is_new: boolean;
  days_on_market: number;
  off_market_date: string | null;
  sold_date: string | null;
  sold_price: number | null;
  sold_vs_list_pct: number | null;
  sold_vs_original_pct: number | null;
  price_cuts: number;
  price_increases: number;
  price_change_pct: number;
  last_price_change: string | null;
  times_relisted: number;
  growth_score: number | null;
  gross_yield: number | null;
  cap_rate: number | null;
  cash_on_cash: number | null;
  monthly_cash_flow: number;
  irr_10y_base: number | null;
  comps_ratio: number | null;
  comps_basis: string | null;
  opportunity_score: number | null;
  estimated_fields: string[];
  notes: string | null;
};

export type MetricDetail = {
  label: string;
  fmt: "pct" | "num" | "money" | "km";
  higher_is_better: boolean;
  value: number | null;
  percentile: number | null;
};

export type PillarDetail = {
  label: string;
  weight: number;
  score?: number | null;
  points?: number | null;
  floodplain_share?: number | null;
  metrics?: Record<string, MetricDetail>;
};

export type CashFlowYear = {
  year: number;
  noi: number;
  mortgage: number;
  cash_flow: number;
  cumulative_cash_flow: number;
  dscr: number | null;
  property_value: number;
  loan_balance: number;
  equity: number;
  sale_proceeds_if_exit_now: number;
};

export type Projection = {
  value: number;
  equity_at_exit: number;
  cumulative_cash_flow: number;
  profit: number;
  equity_multiple: number | null;
  irr: number | null;
  cash_flow_positive_year: number | null;
  payback_year: number | null;
  path: CashFlowYear[];
};

export type Assumptions = {
  down_payment_pct: number;
  interest_rate: number;
  loan_years: number;
  vacancy_pct: number;
  management_pct: number;
  maintenance_monthly: number;
  insurance_monthly: number;
  rent_growth: number;
  expense_growth: number;
  exit_cost_pct: number;
  new_development: boolean;
  appreciation_override: number | null;
  scenario_spread: number;
};

export type Analysis = {
  assumptions: Assumptions;
  estimated_fields: string[];
  rent_basis: string;
  purchase_costs: Record<string, number>;
  cash_invested: number;
  loan_amount: number;
  monthly: Record<string, number>;
  gross_yield: number | null;
  cap_rate: number | null;
  cash_on_cash: number | null;
  appreciation: Record<"bear" | "base" | "bull", number>;
  projections: Record<"bear" | "base" | "bull", Record<"10" | "20", Projection>>;
};

export type ListingDetail = ListingRow & {
  analysis: Analysis;
  history: { date: string; event: string; price: number | null; status: string }[];
  building_sales: { date: string; unit: string | null; price: number }[];
  neighborhood_sales: { sales_2y: number; median_price_2y: number | null } | null;
  neighborhood_score: { score: number | null; rank: number | null; coverage: number; pillars: Record<string, PillarDetail> } | null;
};

export type NeighborhoodRow = {
  code: string;
  name: string;
  borough: string;
  score: number | null;
  rank: number | null;
  coverage: number;
  pillars: Record<string, number | null>;
  metrics: Record<string, number | null>;
  active_listings: number;
};

export type NeighborhoodDetail = {
  code: string;
  name: string;
  borough: string;
  area_km2: number;
  score: number | null;
  rank: number | null;
  coverage: number | null;
  total_ranked: number;
  pillars: Record<string, PillarDetail>;
  metric_sources: Record<string, { as_of: string; source: string }>;
  value_history: { year: number; value: number }[];
  catalysts: { name: string; type: string; status: string; weight: number }[];
  sales: { sales_2y: number; median_price_2y: number | null };
  active_listings: number;
};

export type Summary = {
  active: number;
  likely_coops_hidden: number;
  off_market: number;
  sold: number;
  withdrawn: number;
  new: number;
  price_drops: number;
  neighborhoods_scored: number;
  last_refresh: string | null;
  refreshing: boolean;
};

export type SourceInfo = {
  name: string;
  kind: string;
  description: string;
  enabled: boolean;
  schedule: string | null;
  missing_settings: string[];
  last_run: { status: string; records: number; message: string | null; started_at: string; finished_at: string | null } | null;
  last_success: string | null;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export type FactorInfo = { key: string; label: string };

export type ValuationProperty = {
  id: number;
  label: string;
  property_type: string;
  address: string | null;
  nta_code: string | null;
  price: number;
  sqft: number | null;
  bedrooms: number | null;
  common_charges: number | null;
  property_taxes: number | null;
  rent_estimate: number | null;
  assumption_overrides: Record<string, number>;
  listing_id: number | null;
  /** Live state of the linked screener listing, if this was imported from one. */
  listing: { id: number; status: string; price: number; url: string | null; price_drift_pct: number | null } | null;
  created_at: string;
  updated_at: string;
};

export type ImportableListing = {
  id: number;
  address: string;
  unit: string | null;
  neighborhood_code: string | null;
  price: number;
  bedrooms: number | null;
  sqft: number | null;
  ownership: "condo" | "likely_coop" | "unknown";
  already_imported: boolean;
};

export type AddressLookupResult = {
  address: string;
  latitude: number;
  longitude: number;
  nta_code: string | null;
  neighborhood_name: string | null;
};

export type FactorEstimate = {
  key: string;
  label: string;
  value: number;
  p10: number;
  p90: number;
  source: string;
  as_of: string | null;
};

export type ValuationRun = Analysis & {
  factors: Record<string, FactorEstimate | null>;
  estimated_factors: string[];
};

export type ScenarioResult = {
  name: string;
  assumptions: Assumptions;
  cap_rate: number | null;
  cash_on_cash: number | null;
  monthly_cash_flow: number;
  irr_10: number | null;
  irr_20: number | null;
  equity_multiple_10: number | null;
  equity_multiple_20: number | null;
  payback_year_10: number | null;
  estimated_factors: string[];
};

export type SensitivityRow = {
  factor: string;
  label: string;
  low_value: number;
  high_value: number;
  /** null when the IRR is unsolvable at that end of the range — the row is still returned, not dropped. */
  low_irr: number | null;
  high_irr: number | null;
  base_irr: number | null;
  backed_by_source: boolean;
  undefined: boolean;
  swing: number | null;
};

export type DataTableResult = {
  x_factor: string;
  y_factor: string;
  x_values: number[];
  y_values: number[];
  irr_grid: (number | null)[][];
};

export type MonteCarloResult = {
  n: number;
  valid_n: number;
  randomized_factors: string[];
  held_at_default: string[];
  p10: number | null;
  p50: number | null;
  p90: number | null;
  prob_loss: number | null;
  histogram: { bin_start: number; bin_end: number; count: number }[];
};

/** Fetches `path` on mount and whenever it changes; `reload` refetches. `path: null` skips fetching. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [settled, setSettled] = useState<string | null>(null);
  const requestKey = path === null ? null : `${path}#${version}`;

  useEffect(() => {
    if (requestKey === null || path === null) return;
    let cancelled = false;
    api<T>(path)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setError(null);
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setSettled(requestKey));
    return () => {
      cancelled = true;
    };
  }, [path, requestKey]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, loading: requestKey !== null && settled !== requestKey, reload, setData };
}
