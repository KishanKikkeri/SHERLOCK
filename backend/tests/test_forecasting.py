"""
SHERLOCK — Forecasting & Early Warning Engine test coverage (Requirement 8).

Covers every module in backend/forecasting/ plus its API surface
(backend/api/forecast.py). Exercises real edge cases explicitly called
for in the brief: empty datasets, single-month datasets, and partial
(incomplete current) month handling — in addition to normal-data paths
against the shared synthetic dataset fixture.
"""

from datetime import datetime

import pytest

from backend.database.config import SessionLocal
from backend.database.models import FIR, Crime, CrimeType, FIRStatus, Location


# ---------------------------------------------------------------------------
# Trend Forecaster
# ---------------------------------------------------------------------------

def test_moving_average_methods_are_pure_stdlib_math():
    from backend.forecasting.trend_forecaster import TrendForecaster

    series = [5.0, 5.0, 5.0, 20.0]
    assert TrendForecaster.moving_average(series, window=2) == pytest.approx(12.5)
    assert TrendForecaster.moving_average([], window=3) == 0.0

    wma = TrendForecaster.weighted_moving_average(series)
    assert wma > TrendForecaster.moving_average(series, window=3)  # recency-weighting should pull the average toward the recent spike

    es = TrendForecaster.exponential_smoothing(series, alpha=0.5)
    assert 5.0 <= es <= 20.0


def test_forecast_crime_volume_has_real_numbers(db_session):
    from backend.forecasting.trend_forecaster import TrendForecaster

    result = TrendForecaster(db_session).forecast_crime_volume()
    assert result["method"] == "weighted_moving_average"
    assert result["months_used"] >= 0
    assert "reason" in result
    assert 0.3 <= result["confidence"] <= 0.95


def test_forecast_by_type_and_district_cover_every_value(db_session):
    from backend.forecasting.trend_forecaster import TrendForecaster

    t = TrendForecaster(db_session)
    by_type = t.forecast_by_type()
    crime_types = {r["crime_type"] for r in by_type}
    assert crime_types == {c.value for c in CrimeType}

    by_district = t.forecast_by_district()
    assert len(by_district) == db_session.query(Location.district).distinct().count()


def test_forecast_next_quarter_and_rolling_forecast_are_sequential_months(db_session):
    from backend.forecasting.trend_forecaster import TrendForecaster, _add_months

    t = TrendForecaster(db_session)
    quarter = t.forecast_next_quarter()
    months = [m["month"] for m in quarter["monthly_breakdown"]]
    assert months == sorted(months)
    for a, b in zip(months, months[1:]):
        assert _add_months(a, 1) == b

    rolling = t.rolling_forecast(periods=4)
    targets = [r["target_month"] for r in rolling]
    for a, b in zip(targets, targets[1:]):
        assert _add_months(a, 1) == b


def test_current_incomplete_month_is_excluded(db_session):
    """Partial-month handling: the latest recorded month is treated as
    incomplete and excluded from the fit, per trend_forecaster's
    reference_now()/data anchoring."""
    from backend.forecasting.trend_forecaster import TrendForecaster, _month_key, reference_now

    t = TrendForecaster(db_session)
    series = t._monthly_series()
    latest_recorded_month = _month_key(reference_now(db_session))
    assert latest_recorded_month not in series


# ---------------------------------------------------------------------------
# Hotspot Forecaster
# ---------------------------------------------------------------------------

def test_predict_hotspots_covers_every_district_and_flags_missing_adjacency(db_session):
    from backend.forecasting.hotspot_forecaster import HotspotForecaster

    h = HotspotForecaster(db_session)
    n_districts = db_session.query(Location.district).distinct().count()
    results = h.predict_hotspots(top_n=n_districts)
    assert len(results) == n_districts
    for r in results:
        assert r["predicted_risk"] in ("High", "Medium", "Low")
        assert r["neighboring_hotspot_influence"]["available"] is False


def test_predict_hotspots_uses_real_adjacency_when_provided(db_session):
    from backend.forecasting.hotspot_forecaster import HotspotForecaster

    h = HotspotForecaster(db_session)
    districts = [d for (d,) in db_session.query(Location.district).distinct().all()]
    adjacency = {d: [x for x in districts if x != d][:2] for d in districts}
    results = h.predict_hotspots(district_adjacency=adjacency)
    assert results[0]["neighboring_hotspot_influence"]["available"] is True


# ---------------------------------------------------------------------------
# Repeat Alert Engine
# ---------------------------------------------------------------------------

def test_repeat_accused_alerts_match_a_direct_fir_tally(db_session):
    from backend.database.models import Accused
    from backend.forecasting.repeat_alert_engine import RepeatAlertEngine
    from collections import defaultdict

    alerts = RepeatAlertEngine(db_session).detect_repeat_accused(min_crimes=2)

    fir_ids_by_person = defaultdict(set)
    for pid, fir_id in db_session.query(Accused.person_id, Accused.fir_id).all():
        fir_ids_by_person[pid].add(fir_id)
    expected_ids = {pid for pid, firs in fir_ids_by_person.items() if len(firs) >= 2}

    assert {a["person_id"] for a in alerts} == expected_ids
    for a in alerts:
        assert a["occurrences"] == len(fir_ids_by_person[a["person_id"]])


def test_generate_alerts_returns_all_five_categories(db_session):
    from backend.forecasting.repeat_alert_engine import RepeatAlertEngine

    alerts = RepeatAlertEngine(db_session).generate_alerts()
    assert set(alerts.keys()) == {
        "repeat_locations", "repeat_accused", "repeat_mo",
        "repeat_victim_groups", "repeat_crime_types",
    }


# ---------------------------------------------------------------------------
# Gang Alert Engine
# ---------------------------------------------------------------------------

def test_gang_graph_has_no_self_loops_and_communities_meet_min_size(db_session):
    from backend.forecasting.gang_alert_engine import GangAlertEngine

    g = GangAlertEngine(db_session)
    graph = g.build_graph()
    assert not any(graph.has_edge(n, n) for n in graph.nodes)

    alerts = g.get_gang_alerts(min_size=3)
    for a in alerts:
        assert a["members"] >= 3
        assert a["risk"] in ("Critical", "High", "Medium", "Low")
        assert a["category"] in ("Emerging", "Growing", "High-risk", "Dormant", "Stable")


def test_gang_graph_builds_every_edge_kind_from_real_data(empty_session):
    """The shared synthetic-dataset fixture doesn't happen to generate
    org memberships, phone calls, transactions, or vehicle/weapon-in-FIR
    links that overlap between two people — so those branches of
    build_graph() go untested against it. This constructs a minimal
    scenario that exercises every edge kind directly."""
    from backend.database.models import (
        FIR, Accused, BankAccount, CallRecord, Crime, CrimeType, FIRStatus, Gender,
        Location, Organization, OrganizationMembership, OrganizationType, Person,
        Phone, Transaction, Vehicle, Weapon, WeaponType, PropertyStatus,
    )
    from backend.forecasting.gang_alert_engine import GangAlertEngine

    s = empty_session
    loc = Location(name="Test Rd", district="D1", state="Karnataka", latitude=1.0, longitude=1.0)
    s.add(loc)
    s.commit()

    people = [Person(name=f"P{i}", gender=Gender.MALE, age=30, occupation="unspecified") for i in range(4)]
    s.add_all(people)
    s.commit()
    p1, p2, p3, p4 = people

    org = Organization(name="Test Gang", org_type=OrganizationType.GANG, registration_number="ORG-1")
    s.add(org)
    s.commit()
    s.add_all([
        OrganizationMembership(person_id=p1.id, organization_id=org.id, role="member"),
        OrganizationMembership(person_id=p2.id, organization_id=org.id, role="member"),
    ])

    crime = Crime(type=CrimeType.ASSAULT, timestamp=datetime(2026, 5, 1), location_id=loc.id, modus_operandi="test")
    s.add(crime)
    s.commit()
    fir = FIR(crime_id=crime.id, fir_number="FIR-GANG-1", status=FIRStatus.OPEN)
    s.add(fir)
    s.commit()
    s.add_all([
        Accused(person_id=p3.id, fir_id=fir.id, raw_name_used=p3.name),
        Accused(person_id=p4.id, fir_id=fir.id, raw_name_used=p4.name),
    ])

    phone1 = Phone(number="1000000001", owner_id=p1.id)
    phone2 = Phone(number="1000000002", owner_id=p2.id)
    s.add_all([phone1, phone2])
    s.commit()
    s.add(CallRecord(caller_phone_id=phone1.id, receiver_phone_id=phone2.id, timestamp=datetime(2026, 5, 1), duration_seconds=60))

    acct1 = BankAccount(bank="Test Bank", account_number="ACC-1", owner_id=p1.id)
    acct2 = BankAccount(bank="Test Bank", account_number="ACC-2", owner_id=p2.id)
    s.add_all([acct1, acct2])
    s.commit()
    s.add(Transaction(amount=100.0, timestamp=datetime(2026, 5, 1), sender_account_id=acct1.id, receiver_account_id=acct2.id))

    s.add(Vehicle(registration_number="KA-01-TEST", owner_id=p1.id, vehicle_type="car", used_in_fir_id=fir.id))
    s.add(Weapon(weapon_type=WeaponType.BLADE, description="test", used_in_fir_id=fir.id,
                 recovered_from_person_id=p2.id, status=PropertyStatus.SEIZED))
    s.commit()

    engine = GangAlertEngine(s)
    graph = engine.build_graph()

    edge_kinds = {kind for a, b in graph.edges() for kind in graph[a][b]["kinds"]}
    assert "org_membership" in edge_kinds
    assert "phone_call" in edge_kinds
    assert "transaction" in edge_kinds
    assert "co_accused_fir" in edge_kinds
    assert "vehicle_link" in edge_kinds
    assert "weapon_link" in edge_kinds

    # p1-p2 carries two distinct signals (org membership AND phone calls) —
    # both must be retained on the same edge, not the second overwriting the first.
    assert {"org_membership", "phone_call"}.issubset(graph[p1.id][p2.id]["kinds"])

    alerts = engine.get_gang_alerts(min_size=2)
    gang_alert = next((a for a in alerts if p1.id in a["member_person_ids"] and p2.id in a["member_person_ids"]), None)
    assert gang_alert is not None
    assert gang_alert["confirmed_org_membership"] is True


def test_gang_metrics_report_real_graph_stats(db_session):
    from backend.forecasting.gang_alert_engine import GangAlertEngine

    g = GangAlertEngine(db_session)
    metrics = g.compute_metrics()
    assert metrics["nodes"] >= 0
    assert metrics["connected_components"] >= 0
    if metrics["nodes"]:
        assert len(metrics["degree_centrality"]) == metrics["nodes"]


# ---------------------------------------------------------------------------
# Anomaly Engine
# ---------------------------------------------------------------------------

def test_anomaly_zscores_are_computed_against_the_series_own_stats(db_session):
    from backend.forecasting.anomaly_engine import AnomalyEngine

    anomalies = AnomalyEngine(db_session).detect_all()
    for group in anomalies.values():
        for a in group:
            assert a["direction"] in ("spike", "drop")
            assert abs(a["z_score"]) >= 2.0  # DEFAULT_Z_THRESHOLD
            assert (a["z_score"] > 0) == (a["direction"] == "spike")


# ---------------------------------------------------------------------------
# Risk Forecaster / Early Warning / Summary
# ---------------------------------------------------------------------------

def test_risk_forecaster_generate_all_shape(db_session):
    from backend.forecasting.risk_forecaster import RiskForecaster

    out = RiskForecaster(db_session).generate_all()
    assert set(out.keys()) == {"crime_type_risk", "district_risk", "offender_risk"}


def test_early_warnings_are_severity_sorted(db_session):
    from backend.forecasting.early_warning_engine import EarlyWarningEngine

    warnings = EarlyWarningEngine(db_session).generate_warnings()
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    ranks = [order[w["severity"]] for w in warnings]
    assert ranks == sorted(ranks)
    for w in warnings:
        assert w["evidence"]
        assert w["recommended_actions"]


def test_generate_forecast_dashboard_has_all_required_sections(db_session):
    from backend.forecasting.summary_engine import generate_forecast_dashboard

    dashboard = generate_forecast_dashboard(db_session)
    for key in (
        "executive_summary", "forecast_cards", "upcoming_hotspots", "emerging_crime_types",
        "gang_alerts", "repeat_alerts", "prediction_timeline", "recommendations", "early_warnings",
    ):
        assert key in dashboard


# ---------------------------------------------------------------------------
# Edge cases: empty dataset
# ---------------------------------------------------------------------------

@pytest.fixture()
def empty_session(tmp_path):
    import os
    original_url = os.environ.get("DATABASE_URL")
    db_path = tmp_path / "empty.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    import importlib
    import backend.database.config as config_module
    importlib.reload(config_module)
    import backend.database.models as models_module
    models_module.Base.metadata.create_all(config_module.engine)

    session = config_module.SessionLocal()
    yield session
    session.close()

    if original_url is not None:
        os.environ["DATABASE_URL"] = original_url
    importlib.reload(config_module)


def test_all_engines_handle_empty_dataset_without_raising(empty_session):
    from backend.forecasting.trend_forecaster import TrendForecaster
    from backend.forecasting.hotspot_forecaster import HotspotForecaster
    from backend.forecasting.repeat_alert_engine import RepeatAlertEngine
    from backend.forecasting.gang_alert_engine import GangAlertEngine
    from backend.forecasting.anomaly_engine import AnomalyEngine
    from backend.forecasting.risk_forecaster import RiskForecaster
    from backend.forecasting.early_warning_engine import EarlyWarningEngine
    from backend.forecasting.summary_engine import generate_forecast_dashboard

    s = empty_session
    result = TrendForecaster(s).forecast_crime_volume()
    assert result["current"] == 0
    assert result["months_used"] == 0
    assert "insufficient" in result["reason"].lower()

    assert HotspotForecaster(s).predict_hotspots() == []
    assert all(v == [] for v in RepeatAlertEngine(s).generate_alerts().values())
    assert GangAlertEngine(s).get_gang_alerts() == []
    assert all(v == [] for v in AnomalyEngine(s).detect_all().values())
    assert all(v == [] for v in RiskForecaster(s).generate_all().values())
    assert EarlyWarningEngine(s).generate_warnings() == []

    dashboard = generate_forecast_dashboard(s)
    assert dashboard["forecast_cards"]["overall"]["current"] == 0
    assert dashboard["upcoming_hotspots"] == []


# ---------------------------------------------------------------------------
# Edge case: single-month dataset (insufficient history, not fabricated)
# ---------------------------------------------------------------------------

@pytest.fixture()
def single_month_session(tmp_path):
    import os
    original_url = os.environ.get("DATABASE_URL")
    db_path = tmp_path / "single_month.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    import importlib
    import backend.database.config as config_module
    importlib.reload(config_module)
    import backend.database.models as models_module
    models_module.Base.metadata.create_all(config_module.engine)

    session = config_module.SessionLocal()
    loc = Location(name="Test St", district="TestDistrict", state="Karnataka", latitude=12.9, longitude=77.5)
    session.add(loc)
    session.commit()
    for i in range(3):
        crime = Crime(type=CrimeType.THEFT, timestamp=datetime(2026, 5, 10 + i), location_id=loc.id, modus_operandi="test mo")
        session.add(crime)
        session.commit()
        session.add(FIR(crime_id=crime.id, fir_number=f"FIR-SINGLE-{i}", status=FIRStatus.OPEN))
        session.commit()

    yield session
    session.close()

    if original_url is not None:
        os.environ["DATABASE_URL"] = original_url
    importlib.reload(config_module)


def test_single_month_dataset_reports_insufficient_history_not_a_fabricated_trend(single_month_session):
    """All 3 crimes fall in the same (latest, therefore incomplete) month
    — it must be excluded entirely, leaving 0 usable months, and the
    engine must say so rather than inventing a trend from a single point."""
    from backend.forecasting.trend_forecaster import TrendForecaster

    result = TrendForecaster(single_month_session).forecast_crime_volume()
    assert result["months_used"] == 0
    assert result["confidence"] == 0.3
    assert "insufficient" in result["reason"].lower()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/forecast/dashboard", "/forecast/summary", "/forecast/hotspots",
    "/forecast/trends", "/forecast/repeat-alerts", "/forecast/gang-alerts", "/forecast/risk",
])
def test_forecast_endpoints_return_200(api_client, path):
    resp = api_client.get(path)
    assert resp.status_code == 200
    assert resp.json() is not None


def test_forecast_dashboard_endpoint_shape(api_client):
    resp = api_client.get("/forecast/dashboard")
    body = resp.json()
    assert "executive_summary" in body
    assert "gang_alerts" in body
    assert "early_warnings" in body
