"""
SHERLOCK — Hotspot Engine (Crime Pattern & Trend Analytics Agent).

Standalone, DB-driven hotspot computation — deliberately not built on
`graph_service.find_location_clusters()` (used today by
`PatternAnalysisAgent` for district/month/type faceting), because that
call needs a live graph backend instance (networkx or neo4j) wired in.
This module only needs a SQLAlchemy `Session`, so it can be called
directly from an API route or a test without standing up the graph
service. The two are complementary, not duplicates: that one facets by
district/type/month; this one facets by *physical location* (lat/lng)
— actual point clustering and heatmap data, which the graph service
does not produce.

Geographic granularity note (see trend_engine.py's module docstring for
the same gap): `Location` has no police-station/ward/city field, only
district + a single lat/lng point per named location. Radius
clustering here operates on that single lat/lng per `Location` row —
it clusters *locations*, not raw incident-level GPS points, because
that's what the schema stores. If per-incident GPS is added to `Crime`
later, `radius_clusters` should switch to clustering on that instead.
"""

from __future__ import annotations

from math import radians, sin, cos, sqrt, atan2
from typing import Optional

from sqlalchemy.orm import Session

from backend.database.models import Crime, Location
from backend.analytics.trend_engine import VictimFilter, _victim_filtered_crime_ids


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _location_crime_counts(session: Session, crime_type: Optional[str] = None,
                            district: Optional[str] = None,
                            victim_filter: Optional[VictimFilter] = None) -> dict:
    """-> {location_id: {"location": Location, "count": int}}"""
    q = session.query(Crime).join(Location, Crime.location_id == Location.id)
    if crime_type:
        q = q.filter(Crime.type == crime_type)
    if district:
        q = q.filter(Location.district == district)
    victim_ids = _victim_filtered_crime_ids(session, victim_filter)
    if victim_ids is not None:
        q = q.filter(Crime.id.in_(victim_ids))

    counts: dict[int, dict] = {}
    for c in q.all():
        entry = counts.setdefault(c.location_id, {"location": c.location, "count": 0})
        entry["count"] += 1
    return counts


def top_hotspots(session: Session, top_n: int = 10, crime_type: Optional[str] = None,
                  district: Optional[str] = None, victim_filter: Optional[VictimFilter] = None) -> list[dict]:
    """Ranked table of individual locations by crime count.
    -> [{"location": str, "district": str, "latitude": float, "longitude": float, "count": int}, ...]
    """
    counts = _location_crime_counts(session, crime_type, district, victim_filter)
    ranked = sorted(counts.values(), key=lambda e: e["count"], reverse=True)[:top_n]
    return [
        {
            "location": e["location"].name,
            "district": e["location"].district,
            "latitude": e["location"].latitude,
            "longitude": e["location"].longitude,
            "count": e["count"],
        }
        for e in ranked
    ]


def heatmap_points(session: Session, crime_type: Optional[str] = None,
                    district: Optional[str] = None, victim_filter: Optional[VictimFilter] = None) -> list[dict]:
    """Point-weight data for a frontend heatmap layer (e.g. Leaflet.heat /
    Mapbox heatmap layer) — one point per location, weighted by count.
    -> [{"lat": float, "lng": float, "weight": int, "location": str}, ...]
    """
    counts = _location_crime_counts(session, crime_type, district, victim_filter)
    return [
        {
            "lat": e["location"].latitude,
            "lng": e["location"].longitude,
            "weight": e["count"],
            "location": e["location"].name,
        }
        for e in counts.values()
    ]


def radius_clusters(session: Session, radius_km: float = 2.0,
                     crime_type: Optional[str] = None, district: Optional[str] = None,
                     min_cluster_count: int = 2, victim_filter: Optional[VictimFilter] = None) -> list[dict]:
    """Greedy radius-based clustering over locations (not raw GPS pings —
    see module docstring): repeatedly take the highest-count remaining
    location as a cluster seed, absorb every other unclustered location
    within `radius_km` of it, then move to the next-highest remaining
    seed. Simple and deterministic rather than a full DBSCAN — adequate
    given the schema's one-point-per-location granularity; revisit if
    per-incident GPS is added.

    -> [{"center": {"location": str, "lat": float, "lng": float},
         "member_locations": [str, ...], "total_count": int, "radius_km": float}, ...]
       sorted by total_count desc, clusters with total_count < min_cluster_count dropped.
    """
    counts = _location_crime_counts(session, crime_type, district, victim_filter)
    remaining = sorted(counts.values(), key=lambda e: e["count"], reverse=True)

    clusters = []
    unclustered = list(remaining)
    while unclustered:
        seed = unclustered.pop(0)
        seed_loc = seed["location"]
        members = [seed]
        still_unclustered = []
        for entry in unclustered:
            loc = entry["location"]
            dist = _haversine_km(seed_loc.latitude, seed_loc.longitude, loc.latitude, loc.longitude)
            if dist <= radius_km:
                members.append(entry)
            else:
                still_unclustered.append(entry)
        unclustered = still_unclustered

        total = sum(m["count"] for m in members)
        clusters.append({
            "center": {"location": seed_loc.name, "lat": seed_loc.latitude, "lng": seed_loc.longitude},
            "member_locations": [m["location"].name for m in members],
            "total_count": total,
            "radius_km": radius_km,
        })

    clusters = [c for c in clusters if c["total_count"] >= min_cluster_count]
    clusters.sort(key=lambda c: c["total_count"], reverse=True)
    return clusters


def location_breakdown(session: Session, location_name: str) -> Optional[dict]:
    """Drill-down for a single hotspot: crime-type breakdown + a monthly
    timeline at that location. Deliberately does NOT include "nearby
    offenders" or "related FIRs" — that's Person/Case-linked data outside
    this agent's domain (Case/Officer/Similar-Case agents own that), and
    fabricating a look-alike here would be exactly the "faked" analytics
    the brief said to avoid. Scoped to what a crime-pattern engine can
    honestly answer: what kinds of crime, how many, and when.

    -> None if the location doesn't exist, else
       {"location": str, "district": str, "total": int,
        "by_crime_type": [{"crime_type": str, "count": int}, ...],
        "monthly_timeline": [{"period": str, "count": int}, ...]}
    """
    from backend.analytics.trend_engine import _bucket_key  # local import — avoids a hard dependency for callers that never drill down

    location = session.query(Location).filter(Location.name == location_name).first()
    if location is None:
        return None

    crimes = session.query(Crime).filter(Crime.location_id == location.id).all()
    by_type: dict[str, int] = {}
    by_month: dict[str, int] = {}
    for c in crimes:
        ctype = c.type.value if hasattr(c.type, "value") else str(c.type)
        by_type[ctype] = by_type.get(ctype, 0) + 1
        month_key = _bucket_key(c.timestamp, "month")
        by_month[month_key] = by_month.get(month_key, 0) + 1

    return {
        "location": location.name,
        "district": location.district,
        "total": len(crimes),
        "by_crime_type": sorted(
            [{"crime_type": t, "count": n} for t, n in by_type.items()],
            key=lambda e: e["count"], reverse=True,
        ),
        "monthly_timeline": [{"period": k, "count": by_month[k]} for k in sorted(by_month.keys())],
    }
