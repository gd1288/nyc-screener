from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ListingStatus:
    ACTIVE = "active"
    OFF_MARKET = "off_market"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"
    ALL = (ACTIVE, OFF_MARKET, SOLD, WITHDRAWN)


class Neighborhood(Base):
    __tablename__ = "neighborhoods"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)  # 2020 NTA code, e.g. MN0101
    name: Mapped[str] = mapped_column(String(120))
    borough: Mapped[str] = mapped_column(String(20))
    residential: Mapped[bool] = mapped_column(default=True)  # False for parks, airports, cemeteries
    geometry: Mapped[dict] = mapped_column(JSON)  # GeoJSON (WGS84)
    area_km2: Mapped[float] = mapped_column(Float)


class NeighborhoodMetric(Base):
    __tablename__ = "neighborhood_metrics"
    __table_args__ = (UniqueConstraint("nta_code", "metric"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nta_code: Mapped[str] = mapped_column(ForeignKey("neighborhoods.code"), index=True)
    metric: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64))
    as_of: Mapped[str] = mapped_column(String(32))  # period the value describes, e.g. "2025" or "2021-2025"
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class NeighborhoodScore(Base):
    __tablename__ = "neighborhood_scores"

    nta_code: Mapped[str] = mapped_column(ForeignKey("neighborhoods.code"), primary_key=True)
    score: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    pillars: Mapped[dict] = mapped_column(JSON)  # pillar -> {score, metrics: {metric: {value, pct}}}
    coverage: Mapped[float] = mapped_column(Float)  # share of total weight backed by data
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class Region(Base):
    """A metro or county the screener has loaded. Added on demand; only `watched` regions refresh on
    schedule, so loading Austin to look at it once doesn't commit every later refresh to fetching it."""

    __tablename__ = "regions"
    __table_args__ = (UniqueConstraint("kind", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))  # cbsa | county
    code: Mapped[str] = mapped_column(String(12), index=True)  # CBSA code (35620) or county FIPS (36061)
    name: Mapped[str] = mapped_column(String(160))
    state_fips: Mapped[str | None] = mapped_column(String(2))
    watched: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Area(Base):
    """Any geography the screener can score, anywhere in the US.

    Census tracts are the universal unit — every national source either reports by tract or rolls up
    to one. NYC's NTAs live here too (`kind="nta"`, linked back to their `Neighborhood` row), which
    is what lets the existing NYC pages keep working unchanged while Austin is scored through the
    same tables: the NYC-specific `neighborhoods` tables are not migrated, they are overlaid.
    """

    __tablename__ = "areas"
    __table_args__ = (UniqueConstraint("kind", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), index=True)  # tract | zcta | nta | custom
    code: Mapped[str] = mapped_column(String(16), index=True)  # tract GEOID (36061000100) or NTA code
    name: Mapped[str] = mapped_column(String(160))
    state_fips: Mapped[str | None] = mapped_column(String(2), index=True)
    county_fips: Mapped[str | None] = mapped_column(String(5), index=True)
    # The default comparison set: percentiles are ranked within a metro, never across incomparable
    # markets. An area with no CBSA (rural) falls back to its state — see `scoring/area.py`.
    cbsa: Mapped[str | None] = mapped_column(String(5), index=True)
    residential: Mapped[bool] = mapped_column(default=True)
    geometry: Mapped[dict | None] = mapped_column(JSON)  # GeoJSON (WGS84)
    area_km2: Mapped[float | None] = mapped_column(Float)
    nta_code: Mapped[str | None] = mapped_column(ForeignKey("neighborhoods.code"), index=True)


class AreaMetric(Base):
    __tablename__ = "area_metrics"
    __table_args__ = (UniqueConstraint("area_id", "metric"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64))
    as_of: Mapped[str] = mapped_column(String(32))


class AreaScore(Base):
    __tablename__ = "area_scores"

    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), primary_key=True)
    # Which areas this was ranked against, e.g. "cbsa:12420". A percentile is only meaningful
    # relative to its comparison set, and storing it is what stops an Austin-CBSA score from being
    # read, compared or charted as if it were national.
    comparison_set: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    pillars: Mapped[dict] = mapped_column(JSON)
    coverage: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class AgentRun(Base):
    """One headless `claude -p` run started from the Workbench.

    Exists to make unattended runs accountable: what was asked, what it cost, where the work landed,
    and whether it finished. Without a durable row, a run that spends its budget and dies leaves no
    evidence it happened — which is exactly when you most want to know.
    """

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # plan | implement | debug | research
    issue_number: Mapped[int | None] = mapped_column(Integer, index=True)
    prompt: Mapped[str] = mapped_column(Text)
    branch: Mapped[str | None] = mapped_column(String(120))
    worktree_path: Mapped[str | None] = mapped_column(String(400))
    budget_usd: Mapped[float] = mapped_column(Float)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    turns: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), index=True)  # running | ok | error | timeout
    result: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Sale(Base):
    """Closed condo sales (DOF annualized/rolling sales)."""

    __tablename__ = "sales"
    __table_args__ = (UniqueConstraint("bbl", "sale_date", "price"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bbl: Mapped[str] = mapped_column(String(10), index=True)
    building_key: Mapped[str] = mapped_column(String(16), index=True)  # borough-block: groups a condo building's units
    address: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str | None] = mapped_column(String(20))
    zip_code: Mapped[str | None] = mapped_column(String(5), index=True)
    nta_code: Mapped[str | None] = mapped_column(String(8), index=True)
    price: Mapped[float] = mapped_column(Float)
    sale_date: Mapped[date] = mapped_column(Date, index=True)
    year_built: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(80))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64))


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(500))

    address: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str | None] = mapped_column(String(20))
    zip_code: Mapped[str | None] = mapped_column(String(5))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    bbl: Mapped[str | None] = mapped_column(String(10), index=True)
    nta_code: Mapped[str | None] = mapped_column(ForeignKey("neighborhoods.code"), index=True)

    price: Mapped[float] = mapped_column(Float)
    original_price: Mapped[float] = mapped_column(Float)
    bedrooms: Mapped[float | None] = mapped_column(Float)
    bathrooms: Mapped[float | None] = mapped_column(Float)
    sqft: Mapped[float | None] = mapped_column(Float)
    year_built: Mapped[int | None] = mapped_column(Integer)
    common_charges: Mapped[float | None] = mapped_column(Float)  # monthly
    property_taxes: Mapped[float | None] = mapped_column(Float)  # monthly
    rent_estimate: Mapped[float | None] = mapped_column(Float)  # monthly, if the source provides one
    notes: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(16), index=True, default=ListingStatus.ACTIVE)
    listed_date: Mapped[date] = mapped_column(Date)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    missed_fetches: Mapped[int] = mapped_column(Integer, default=0)
    off_market_date: Mapped[date | None] = mapped_column(Date)
    sold_date: Mapped[date | None] = mapped_column(Date)
    sold_price: Mapped[float | None] = mapped_column(Float)
    sold_document_id: Mapped[str | None] = mapped_column(String(32))

    snapshots: Mapped[list["ListingSnapshot"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan", order_by="ListingSnapshot.observed_at"
    )


class ListingSnapshot(Base):
    """One row per observed change in price or status."""

    __tablename__ = "listing_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    event: Mapped[str] = mapped_column(String(24))  # listed, price_change, off_market, relisted, sold, withdrawn
    price: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))

    listing: Mapped[Listing] = relationship(back_populates="snapshots")


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16))  # running, ok, error, skipped
    records: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class ValuationProperty(Base):
    """A saved property to run valuation scenarios against (not necessarily an active listing)."""

    __tablename__ = "valuation_properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    property_type: Mapped[str] = mapped_column(String(24), default="condo")  # condo, coop, multifamily, land, ...
    # Set when this was imported from a screener listing, so the valuation can show how the live
    # list price has moved since. SET NULL (not CASCADE): a listing going away shouldn't delete
    # analysis work, it just stops being live.
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id", ondelete="SET NULL"), index=True)
    address: Mapped[str | None] = mapped_column(String(200))
    nta_code: Mapped[str | None] = mapped_column(ForeignKey("neighborhoods.code"), index=True)
    price: Mapped[float] = mapped_column(Float)
    sqft: Mapped[float | None] = mapped_column(Float)
    bedrooms: Mapped[float | None] = mapped_column(Float)
    common_charges: Mapped[float | None] = mapped_column(Float)  # monthly
    property_taxes: Mapped[float | None] = mapped_column(Float)  # monthly
    rent_estimate: Mapped[float | None] = mapped_column(Float)  # monthly
    assumption_overrides: Mapped[dict] = mapped_column(
        JSON, default=dict
    )  # partial Assumptions, e.g. {"interest_rate": 0.07}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
