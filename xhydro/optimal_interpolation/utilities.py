"""Utilities required for managing data in the interpolation toolbox."""

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

__all__ = [
    "plot_results",
    "prepare_flow_percentiles_dataset",
]


def plot_results(kge, kge_l1o, nse, nse_l1o):
    """Generate a plot of the results of model evaluation using various metrics.

    Parameters
    ----------
    kge : array-like
        Kling-Gupta Efficiency for the entire dataset.
    kge_l1o : array-like
        Kling-Gupta Efficiency for leave-one-out cross-validation.
    nse : array-like
        Nash-Sutcliffe Efficiency for the entire dataset.
    nse_l1o : array-like
        Nash-Sutcliffe Efficiency for leave-one-out cross-validation.

    Returns
    -------
    None :
        No return.
    """
    fig, (ax1, ax2) = plt.subplots(2)
    ax1.scatter(kge, kge_l1o)
    ax1.set_xlabel("KGE")
    ax1.set_ylabel("KGE Leave-one-out OI")
    ax1.axline((0, 0), (1, 1), linewidth=2)
    ax1.set_xlim(0.3, 1)
    ax1.set_ylim(0.3, 1)

    ax2.scatter(nse, nse_l1o)
    ax2.set_xlabel("NSE")
    ax2.set_ylabel("NSE Leave-one-out OI")
    ax2.axline((0, 0), (1, 1), linewidth=2)
    ax2.set_xlim(0.3, 1)
    ax2.set_ylim(0.3, 1)

    plt.show()


def prepare_flow_percentiles_dataset(
    station_id, lon, lat, drain_area, time, percentile, discharge
):
    """Write discharge data as an xarray.Dataset.

    Parameters
    ----------
    station_id : array-like
        List of station IDs.
    lon : array-like
        List of longitudes corresponding to each station.
    lat : array-like
        List of latitudes corresponding to each station.
    drain_area : array-like
        List of drainage areas corresponding to each station.
    time : array-like
        List of datetime objects representing time.
    percentile : list or None
        List of percentiles or None if not applicable.
    discharge : numpy.ndarray
        3D array of discharge data, dimensions (percentile, station, time).

    Returns
    -------
    xr.Dataset :
        The dataset containing the flow percentiles as generated by the optimal interpolation code.

    Notes
    -----
    - The function creates and returns an xarray Dataset using the provided data.
    - The function includes appropriate metadata and attributes for each variable.
    """
    # Create dataset
    ds = xr.Dataset()
    discharge = np.array(discharge)
    axis_time = np.where(np.array(discharge.shape) == len(time))
    axis_stations = np.where(np.array(discharge.shape) == len(drain_area))

    # Prepare discharge data
    if percentile:
        axis_percentile = np.where(np.array(discharge.shape) == len(percentile))
        ds["streamflow"] = (
            ["percentile", "station_id", "time"],
            np.transpose(
                discharge, (axis_percentile[0][0], axis_stations[0][0], axis_time[0][0])
            ),
        )
        ds = ds.assign_coords(percentile=("percentile", percentile))

    else:
        ds["streamflow"] = (
            ["station_id", "time"],
            np.transpose(discharge, (axis_stations[0][0], axis_time[0][0])),
        )

    ds["lat"] = ("station_id", lat)
    ds["lon"] = ("station_id", lon)
    ds["drainage_area"] = ("station_id", drain_area)

    ds.assign_coords(
        station_id=("station_id", station_id),
        time=("time", time),
        lat=("station_id", lat),
        lon=("station_id", lon),
        drainage_area=("station_id", drain_area),
    )

    # Time bounds
    ta = np.array(time)
    time_bnds = np.array([ta - 1, time]).T
    ds["time_bnds"] = (("time", "nbnds"), time_bnds)

    # Set attributes
    ds["time"].attrs = {
        "long_name": "time",
        "standard_name": "time",
        "axis": "T",
        "bounds": "time_bnds",
    }
    ds["streamflow"].attrs = {
        "long_name": "Streamflow",
        "standard_name": "outgoing_water_volume_transport_along_river_channel",
        "units": "m3 s-1",
        "cell_methods": "time: mean",
        "coverage_content_type": "modelResult",
    }

    ds["lat"].attrs = {
        "long_name": "latitude_of_river_stretch_outlet",
        "standard_name": "latitude",
        "units": "degrees_north",
        "axis": "Y",
    }
    ds["lon"].attrs = {
        "long_name": "longitude_of_river_stretch_outlet",
        "standard_name": "longitude",
        "units": "degrees_east",
        "axis": "X",
    }

    ds["drainage_area"].attrs = {
        "long_name": "drainage_area_at_river_stretch_outlet",
        "standard_name": "drainage_area",
        "units": "km2",
        "coverage_content_type": "auxiliaryInformation",
    }

    ds["station_id"].attrs = {"long_name": "Station ID", "cf_role": "timeseries_id"}

    return ds
