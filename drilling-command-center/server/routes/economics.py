"""Economics endpoints — combines OSDU wells with live WTI prices to compute NPV/IRR."""
import time
from fastapi import APIRouter
from ..db import db

router = APIRouter()

# Cache aggregates for 15s — Overview + Economics tabs both hit these endpoints.
_CACHE: dict[str, tuple[float, object]] = {}
_TTL_S = 120

def _cache_get(key):
    e = _CACHE.get(key)
    if e and time.time() - e[0] < _TTL_S:
        return e[1]
    return None

def _cache_set(key, val):
    _CACHE[key] = (time.time(), val)


@router.get("/economics/summary")
async def economics_summary():
    """Per-well economics joined with current WTI price."""
    cached = _cache_get("summary")
    if cached: return cached
    latest_price = await db.fetchrow(
        "SELECT price_date, price_usd FROM las.wti_prices ORDER BY price_date DESC LIMIT 1"
    )
    wti_now = float(latest_price["price_usd"]) if latest_price else 0.0
    wti_date = latest_price["price_date"].isoformat() if latest_price and latest_price.get("price_date") else None

    rows = await db.fetch(
        "SELECT e.well_id, w.well_name, w.basin, w.status, w.quality_score, "
        "       e.capex_musd, e.opex_musd_yr, e.peak_rate_bopd, e.decline_pct_yr, "
        "       e.wti_break_even, e.npv10_musd, e.irr_pct, e.payback_years, e.co2_tonnes_yr "
        "FROM las.well_economics e "
        "JOIN las.wells w ON w.well_id = e.well_id "
        "ORDER BY e.npv10_musd DESC NULLS LAST"
    )
    enriched = []
    for r in rows:
        be = float(r.get("wti_break_even") or 0)
        # Margin-based re-rating: positive margin amplifies NPV; negative drags it.
        margin_ratio = (wti_now - be) / max(be, 1.0) if be > 0 else 0.0
        uplift = 1.0 + max(-0.6, min(0.8, margin_ratio))
        base_npv = float(r.get("npv10_musd") or 0)
        enriched.append({
            "well_id":         r["well_id"],
            "well_name":       r["well_name"],
            "basin":           r.get("basin"),
            "status":          r.get("status"),
            "quality_score":   r.get("quality_score"),
            "capex_musd":      float(r.get("capex_musd") or 0),
            "opex_musd_yr":    float(r.get("opex_musd_yr") or 0),
            "peak_rate_bopd":  float(r.get("peak_rate_bopd") or 0),
            "decline_pct_yr":  float(r.get("decline_pct_yr") or 0),
            "wti_break_even":  be,
            "npv10_base_musd": round(base_npv, 2),
            "npv10_live_musd": round(base_npv * uplift, 2),
            "irr_pct":         float(r.get("irr_pct") or 0),
            "payback_years":   float(r.get("payback_years") or 0),
            "co2_tonnes_yr":   float(r.get("co2_tonnes_yr") or 0),
            "margin_per_bbl":  round(wti_now - be, 2),
        })

    out = {
        "wti_spot": wti_now,
        "wti_date": wti_date,
        "total_capex_musd": round(sum(w["capex_musd"] for w in enriched), 1),
        "total_npv_live_musd": round(sum(w["npv10_live_musd"] for w in enriched), 1),
        "total_co2_tonnes_yr": round(sum(w["co2_tonnes_yr"] for w in enriched)),
        "wells": enriched,
    }
    _cache_set("summary", out)
    return out


@router.get("/economics/prices")
async def price_history():
    cached = _cache_get("prices")
    if cached: return cached
    rows = await db.fetch(
        "SELECT price_date, price_usd FROM las.wti_prices ORDER BY price_date"
    )
    out = [
        {"date": r["price_date"].isoformat() if r.get("price_date") else None,
         "price": float(r["price_usd"])}
        for r in rows
    ]
    _cache_set("prices", out)
    return out


@router.get("/economics/{well_id}/curve")
async def well_production_curve(well_id: str):
    """Synthetic 10-year production + cashflow curve using OSDU peak rate + decline."""
    econ = await db.fetchrow(
        "SELECT peak_rate_bopd, decline_pct_yr, opex_musd_yr, capex_musd "
        "FROM las.well_economics WHERE well_id=$1", well_id
    )
    if not econ:
        return {"well_id": well_id, "years": [], "rate_bopd": [], "cashflow_musd": []}
    latest_price = await db.fetchrow(
        "SELECT price_usd FROM las.wti_prices ORDER BY price_date DESC LIMIT 1"
    )
    wti = float(latest_price["price_usd"]) if latest_price else 70.0

    peak = float(econ["peak_rate_bopd"] or 0)
    decl = float(econ["decline_pct_yr"] or 20) / 100.0
    opex_yr = float(econ["opex_musd_yr"] or 0)

    years, rates, cash = [], [], []
    cum = -float(econ["capex_musd"] or 0)
    cum_series = []
    for yr in range(0, 11):
        rate = peak * ((1 - decl) ** yr)
        annual_bbl = rate * 365
        gross_musd = annual_bbl * wti / 1_000_000
        cf = gross_musd - opex_yr
        cum += cf
        years.append(yr)
        rates.append(round(rate))
        cash.append(round(cf, 2))
        cum_series.append(round(cum, 2))

    return {
        "well_id": well_id,
        "wti_assumed": wti,
        "years": years,
        "rate_bopd": rates,
        "cashflow_musd": cash,
        "cumulative_musd": cum_series,
    }
