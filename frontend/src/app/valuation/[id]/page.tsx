"use client";

/**
 * One property, at its own URL — so a valuation can be linked to, bookmarked and reopened, which
 * the list page's in-memory `selectedId` could not do. Renders the same `PropertyWorkspace` as the
 * list page rather than a second copy of the sliders.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use } from "react";
import PropertyWorkspace from "@/components/ValuationWorkspace";
import { Empty, ErrorNote, PageHeader, ghostButtonCls } from "@/components/ui";
import { api, useApi, type ValuationProperty } from "@/lib/api";
import { money } from "@/lib/format";

export default function ValuationPropertyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: property, error, loading } = useApi<ValuationProperty>(`/valuation/properties/${id}`);

  async function remove() {
    if (!confirm("Delete this saved property?")) return;
    await api(`/valuation/properties/${id}`, { method: "DELETE" });
    router.push("/valuation");
  }

  return (
    <div>
      <PageHeader
        title={property?.label ?? "Valuation"}
        subtitle={property ? `${money(property.price, true)}${property.address ? ` · ${property.address}` : ""}` : undefined}
        action={
          <Link className={ghostButtonCls} href="/valuation">
            All properties
          </Link>
        }
      />
      <ErrorNote error={error} />
      {!loading && !property && !error && (
        <Empty title="Property not found">
          It may have been deleted. <Link href="/valuation" className="underline">Back to all properties</Link>.
        </Empty>
      )}
      {property && <PropertyWorkspace property={property} onDelete={remove} />}
    </div>
  );
}
