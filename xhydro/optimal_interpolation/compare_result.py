"""Compare results between simulations and observations."""

import sys

import numpy as np
import xarray as xr

import xhydro.optimal_interpolation.utilities as util
from xhydro.modelling.obj_funcs import get_objective_function

__all__ = ["compare"]


def compare(
    flow_obs: xr.Dataset,
    flow_sim: xr.Dataset,
    flow_l1o: xr.Dataset,
    station_correspondence: xr.Dataset,
    crossvalidation_stations: list,
    percentile_to_plot: int = 50,
    show_comparison: bool = True,
):
    """Start the computation of the comparison method.

    Parameters
    ----------
    flow_obs : xr.Dataset
        Streamflow and catchment properties dataset for observed data.
    flow_sim : xr.Dataset
        Streamflow and catchment properties dataset for simulated data.
    flow_l1o : xr.Dataset
        Streamflow and catchment properties dataset for simulated leave-one-out cross-validation results.
    station_correspondence: xr.Dataset
        Matching between the tag in the HYDROTEL simulated files and the observed station number for the obs dataset.
    crossvalidation_stations: list
        Observed hydrometric dataset stations to be used in the cross-validation step.
    percentile_to_plot : int
        Percentile value to plot (default is 50).
    show_comparison : bool
        Whether to display the comparison plots (default is True).
    """
    time_range = len(flow_obs["time"].values)

    # Read percentiles list (which percentile thresholds were used)
    percentile = flow_l1o["percentile"]

    # Find position of the desired percentile
    idx_pct = np.where(percentile == percentile_to_plot)[0]
    if idx_pct is None:
        sys.exit(
            "The desired percentile is not computed in the results file \
             provided. Please make sure your percentile value is expressed \
             in percent (i.e. 50th percentile = 50)"
        )

    station_count = len(crossvalidation_stations)
    selected_flow_sim = np.empty((time_range, station_count)) * np.nan
    selected_flow_obs = np.empty((time_range, station_count)) * np.nan
    selected_flow_l1o = np.empty((time_range, station_count)) * np.nan

    for i in range(0, station_count):
        print("Lecture des données..." + str(i + 1) + "/" + str(station_count))
        # For each validation station:
        cv_station_id = crossvalidation_stations[i]

        # Get the station number from the obs database which has the same codification for station ids.
        index_correspondence = np.where(
            station_correspondence["station_id"] == cv_station_id
        )[0][0]
        station_code = station_correspondence["reach_id"][index_correspondence]

        # Search for data in the Qsim file
        index_in_sim = np.where(flow_sim["station_id"].values == station_code.data)[0]
        sup_sim = flow_sim["drainage_area"].values[index_in_sim]
        selected_flow_sim[:, i] = (
            flow_sim["streamflow"].isel(station=index_in_sim) / sup_sim
        )

        # Get data in Qobs file
        index_in_obs = np.where(flow_obs["station_id"] == cv_station_id)[0]
        sup_obs = flow_obs["drainage_area"].values[index_in_obs]
        selected_flow_obs[:, i] = (
            flow_obs["streamflow"].isel(station=index_in_obs) / sup_obs
        )

        # Get data in Leave one out file
        index_in_l1o = np.where(flow_l1o["station_id"] == cv_station_id)[0]
        sup_l1o = flow_obs["drainage_area"].values[index_in_l1o]
        selected_flow_l1o[:, i] = (
            flow_l1o["streamflow"]
            .isel(station=index_in_l1o, percentile=idx_pct)
            .squeeze()
            / sup_l1o
        )

    # Prepare the arrays for kge results
    kge = np.empty(station_count) * np.nan
    nse = np.empty(station_count) * np.nan
    kge_l1o = np.empty(station_count) * np.nan
    nse_l1o = np.empty(station_count) * np.nan

    for n in range(0, station_count):
        kge[n] = get_objective_function(
            selected_flow_obs[:, n], selected_flow_sim[:, n], "kge"
        )
        nse[n] = get_objective_function(
            selected_flow_obs[:, n], selected_flow_sim[:, n], "nse"
        )
        kge_l1o[n] = get_objective_function(
            selected_flow_obs[:, n], selected_flow_l1o[:, n], "kge"
        )
        nse_l1o[n] = get_objective_function(
            selected_flow_obs[:, n], selected_flow_l1o[:, n], "nse"
        )

    if show_comparison:
        util.plot_results(kge, kge_l1o, nse, nse_l1o)
