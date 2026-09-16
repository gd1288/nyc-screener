import type { ReactNode } from "react";
import { scoreTone } from "@/lib/format";

export function ScoreBadge({ score, size = "sm" }: { score: number | null | undefined; size?: "sm" | "lg" }) {
  const cls = size === "lg" ? "px-3 py-1 text-2xl font-semibold" : "px-2 py-0.5 text-xs font-semibold";
  return (
    <span className={`inline-flex min-w-9 justify-center rounded-md tabular-nums ring-1 ring-inset ${scoreTone(score)} ${cls}`}>
      {score == null ? "—" : Math.round(score)}
    </span>
  );
}

export function Card({ title, action, children, className = "" }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-stone-200 bg-white ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-stone-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-stone-800">{title}</h2>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "text-emerald-700" : tone === "bad" ? "text-rose-700" : "text-stone-900";
  return (
    <div className="min-w-0">
      <div className="text-xs text-stone-500">{label}</div>
      <div className={`truncate text-lg font-semibold tabular-nums ${color}`}>{value}</div>
      {sub && <div className="text-xs text-stone-500">{sub}</div>}
    </div>
  );
}

export function Tag({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "new" | "drop" | "warn" | "sold" }) {
  const tones = {
    neutral: "bg-stone-100 text-stone-700",
    new: "bg-sky-100 text-sky-800",
    drop: "bg-rose-100 text-rose-800",
    warn: "bg-amber-100 text-amber-800",
    sold: "bg-violet-100 text-violet-800",
  };
  return <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${tones[tone]}`}>{children}</span>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-stone-300 bg-white px-6 py-12 text-center">
      <p className="font-medium text-stone-800">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-xl text-sm text-stone-600">{children}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
      {error.includes("fetch") || error.startsWith("5")
        ? "Can't reach the backend. Start it with: cd backend && uv run uvicorn app.main:app"
        : error}
    </div>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-stone-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-stone-600">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export const inputCls =
  "w-full rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-sm text-stone-900 placeholder:text-stone-400 focus:border-stone-500 focus:outline-none";

export const buttonCls =
  "inline-flex items-center justify-center gap-2 rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700 disabled:cursor-not-allowed disabled:opacity-50";

export const ghostButtonCls =
  "inline-flex items-center justify-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-1.5 text-sm font-medium text-stone-800 hover:bg-stone-50 disabled:opacity-50";
