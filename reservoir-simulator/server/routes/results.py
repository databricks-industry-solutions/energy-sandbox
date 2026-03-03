from fastapi import APIRouter
from .simulate import _field_summaries, _well_timeseries

router = APIRouter()


@router.get("/results/{run_id}/summary")
async def get_summary(run_id: str):
    """Field totals time series for a run."""
    summaries = _field_summaries.get(run_id, [])
    if not summaries:
        return {"run_id": run_id, "summary": [], "message": "No data available. Run a simulation first."}
    return {"run_id": run_id, "summary": summaries}


@router.get("/results/{run_id}/wells")
async def get_well_results(run_id: str):
    """Per-well time series for a run."""
    series = _well_timeseries.get(run_id, [])
    if not series:
        return {"run_id": run_id, "wells": {}, "well_names": []}

    well_names = sorted(set(w["well_name"] for ts_data in series for w in ts_data))

    wells_data = {wn: [] for wn in well_names}
    for ts_data in series:
        for w in ts_data:
            wells_data[w["well_name"]].append(w)

    return {"run_id": run_id, "wells": wells_data, "well_names": well_names}
