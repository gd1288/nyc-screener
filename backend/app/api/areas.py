"""Areas API: any US geography, scored within its own metro.

Separate from `routes.py` (NYC listings and neighbourhoods) on purpose — that surface still serves
the NYC screener unchanged, and this one is what generalizes. Every response carries the
`comparison_set` a score was computed in, because a percentile with no stated comparison set is the
one number in this system that can be silently misread.
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Area, AreaScore, Region
from app.pipeline.areas import KNOWN_REGIONS, comparison_set_for, ensure_region, resolve_region, sync_nyc_ntas
from app.scoring.area import PILLARS, recompute_area_scores

router = APIRouter(prefix="/api")


def db():
    with SessionLocal() as session:
        yield session


@router.get("/regions")
def list_regions(session: Session = Depends(db)):
    loaded = {r.code: r for r in session.query(Region)}
    counts = {}
    for area in session.query(Area).filter(Area.kind == "tract"):
        counts[area.cbsa] = counts.get(area.cbsa, 0) + 1
    return {
        "loaded": [
            {
                "id": r.id,
                "kind": r.kind,
                "code": r.code,
                "name": r.name,
                "watched": r.watched,
                "tracts": counts.get(r.code, 0),
                "comparison_set": f"{r.kind}:{r.code}",
            }
            for r in loaded.values()
        ],
        "available": [
            {"key": key, "code": known.code, "name": known.name, "loaded": known.code in loaded}
            for key, known in sorted(KNOWN_REGIONS.items())
        ],
    }


class RegionIn(BaseModel):
    key: str  # a KNOWN_REGIONS nickname, e.g. "austin"


@router.post("/regions")
def add_region(body: RegionIn, session: Session = Depends(db)):
    """Load a metro's tracts on demand. Synchronous and slow (one TIGERweb request per county) —
    acceptable because a region is loaded once, not per page view."""
    from app.sources.base import SourceContext
    from app.sources.tigerweb import TigerwebTracts

    known = resolve_region(body.key)
    if known is None:
        raise HTTPException(404, f"Unknown region {body.key!r}. Known: {', '.join(sorted(KNOWN_REGIONS))}")
    region = ensure_region(session, known.kind, known.code, known.name, known.state_fips)
    with httpx.Client(follow_redirects=True) as http:
        ctx = SourceContext(session=session, settings=get_settings(), http=http, region=region)
        tracts = TigerwebTracts("tigerweb_tracts", known_region=known).run(ctx)
    ntas = sync_nyc_ntas(session) if known.code == "35620" else 0
    scored = recompute_area_scores(session, f"{known.kind}:{known.code}")
    return {"region": known.name, "tracts": tracts, "ntas_mirrored": ntas, "areas_scored": scored}


def _area_row(area: Area, score: AreaScore | None) -> dict:
    return {
        "id": area.id,
        "kind": area.kind,
        "code": area.code,
        "name": area.name,
        "state_fips": area.state_fips,
        "county_fips": area.county_fips,
        "cbsa": area.cbsa,
        "area_km2": area.area_km2,
        "comparison_set": comparison_set_for(area),
        "score": score.score if score else None,
        "rank": score.rank if score else None,
        # Share of the scoring weight actually backed by data. A score at 50 with coverage 0.07 is
        # "we don't know", not "average" — the UI must show them together.
        "coverage": score.coverage if score else None,
    }


@router.get("/areas")
def list_areas(
    comparison_set: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(db),
):
    query = session.query(Area)
    if kind:
        query = query.filter(Area.kind == kind)
    if q:
        query = query.filter(Area.name.ilike(f"%{q.strip()}%"))
    areas = [a for a in query if comparison_set is None or comparison_set_for(a) == comparison_set]
    scores = {
        s.area_id: s for s in session.query(AreaScore).filter(AreaScore.area_id.in_([a.id for a in areas] or [0]))
    }
    rows = [_area_row(a, scores.get(a.id)) for a in areas]
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    return rows[:limit]


@router.get("/areas/{area_id}")
def get_area(area_id: int, session: Session = Depends(db)):
    area = session.get(Area, area_id)
    if area is None:
        raise HTTPException(404, "No such area")
    score = session.get(AreaScore, area_id)
    peers = (
        session.query(AreaScore).filter(AreaScore.comparison_set == comparison_set_for(area)).count() if score else 0
    )
    return {
        **_area_row(area, score),
        "geometry": area.geometry,
        "pillars": score.pillars if score else {},
        "peers_in_comparison_set": peers,
        # Named so the UI can say *which* signals are missing rather than just showing a low number.
        "pillars_without_data": (
            sorted(p for p, detail in (score.pillars or {}).items() if detail.get("score") is None)
            if score
            else sorted(PILLARS)
        ),
    }
