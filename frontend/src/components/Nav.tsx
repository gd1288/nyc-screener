"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Summary } from "@/lib/api";
import { dateTime } from "@/lib/format";

const LINKS = [
  { href: "/", label: "Screener" },
  { href: "/sold", label: "Sold & off-market" },
  { href: "/neighborhoods", label: "Neighborhoods" },
  { href: "/areas", label: "Areas" },
  { href: "/compare", label: "Compare" },
  { href: "/valuation", label: "Valuation" },
  { href: "/add", label: "Add listings" },
  { href: "/sources", label: "Data sources" },
  { href: "/workbench", label: "Workbench" },
];

export default function Nav() {
  const pathname = usePathname();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const s = await api<Summary>("/summary");
        setSummary(s);
        timer = setTimeout(poll, s.refreshing ? 3000 : 30000);
      } catch {
        timer = setTimeout(poll, 10000);
      }
    };
    poll();
    return () => clearTimeout(timer);
  }, []);

  async function refresh() {
    setStarting(true);
    try {
      await api("/refresh", { method: "POST", body: "{}" });
      setSummary((s) => (s ? { ...s, refreshing: true } : s));
      setTimeout(async () => setSummary(await api<Summary>("/summary")), 1500);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setStarting(false);
    }
  }

  const active = (href: string) => (href === "/" ? pathname === "/" || pathname.startsWith("/listing") : pathname.startsWith(href));

  return (
    <header className="sticky top-0 z-30 border-b border-stone-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5">
        <Link href="/" className="text-sm font-semibold tracking-tight text-stone-900">
          NYC Condo Screener
        </Link>
        <nav className="flex flex-wrap gap-1">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-md px-2.5 py-1 text-sm ${active(l.href) ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"}`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-xs text-stone-500">
          {summary && <span className="hidden sm:inline">Updated {dateTime(summary.last_refresh)}</span>}
          <button
            onClick={refresh}
            disabled={starting || summary?.refreshing}
            className="inline-flex items-center gap-2 rounded-md border border-stone-300 px-2.5 py-1 text-sm font-medium text-stone-800 hover:bg-stone-50 disabled:opacity-60"
          >
            {summary?.refreshing && <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />}
            {summary?.refreshing ? "Refreshing…" : "Refresh now"}
          </button>
        </div>
      </div>
    </header>
  );
}
