"""Module to compute geospatial operations useful in hydrology."""

import os
import tempfile
import urllib.request
import warnings
from pathlib import Path

import geopandas as gpd
import leafmap
import numpy as np
import pandas as pd
import xarray as xr
from shapely import Point

__all__ = [
    "watershed_delineation",
    "watershed_properties",
]


def watershed_delineation(
    coordinates: list[tuple] | tuple | None = None,
    map: leafmap.Map | None = None,
) -> gpd.GeoDataFrame:
    """Watershed delineation can be computed at any location in North America using HydroBASINS (hybas_na_lev01-12_v1c).
    The process involves assessing all upstream sub-basins from a specified pour point and consolidating them into a
    unified watershed.

    Parameters
    ----------
    coordinates : list of tuple, tuple, optional
        Geographic coordinates (longitude, latitude) for the location where watershed delineation will be conducted.
    map : leafmap.Map, optional
        If the function receives both a map and coordinates as inputs, it will generate and display watershed
        boundaries on the map. Additionally, any markers present on the map will be transformed into
        corresponding watershed boundaries for each marker.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame containing the watershed boundaries.

    """
    # level 12 HydroBASINS polygons dataset url (North-Ameroca only at the moment)
    url = "https://s3.us-east-1.wasabisys.com/hydrometric/shapefiles/polygons.parquet"

    coordinates = [coordinates] if isinstance(coordinates, tuple) else coordinates

    # combine coordinates from both coordinates argument and markers on the map, if they exist
    if map is not None and any(map.draw_features):
        if coordinates is None:
            coordinates = []
        gdf_markers = gpd.GeoDataFrame.from_features(map.draw_features)[["geometry"]]
        gdf_markers = gdf_markers.loc[gdf_markers.type == "Point"]

        marker_coordinates = list(zip(gdf_markers.geometry.x, gdf_markers.geometry.y))
        coordinates = coordinates + marker_coordinates

    # cache and read level 12 HydroBASINS polygons' file
    proxies = urllib.request.getproxies()
    proxy = urllib.request.ProxyHandler(proxies)
    opener = urllib.request.build_opener(proxy)
    urllib.request.install_opener(opener)

    tmp_dir = os.path.join(tempfile.gettempdir(), "polygons")
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    polygon_path = os.path.join(tmp_dir, os.path.basename(url))

    if not os.path.isfile(polygon_path):
        urllib.request.urlretrieve(url, polygon_path)

    gdf_hydrobasins = gpd.read_parquet(polygon_path)

    # compute watershed boundaries
    if coordinates is not None:
        gdf = (
            pd.concat(
                [
                    _compute_watershed_boundaries(tuple(coords), gdf_hydrobasins)
                    for coords in coordinates
                ]
            )[["HYBAS_ID", "UP_AREA", "geometry"]]
            .rename(columns={"UP_AREA": "Upstream Area (sq. km)."})
            .reset_index(drop=True)
        )

    # plot resulting geodataframe on map, if available
    if map is not None:
        style = {"fillOpacity": 0.65}
        hover_style = {"fillOpacity": 0.9}
        map.add_data(
            gdf,
            column="Upstream Area (sq. km).",
            scheme="Quantiles",
            cmap="YlGnBu",
            hover_style=hover_style,
            style=style,
            legend_title="Upstream Area (sq. km).",
            layer_name="Basins",
        )

    return gdf


def watershed_properties(
    gdf: gpd.GeoDataFrame,
    unique_id: str = None,
    projected_crs: int = 6622,
    output_format: str = "geopandas",
) -> gpd.GeoDataFrame | xr.Dataset:
    """Watershed properties extracted from gpd.GeoDataFrame

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        GeoDataFrame containing watershed polygons. Must have a defined .crs attribute
    unique_id : string
        GeoDataFrame containing watershed polygons. Must have a defined .crs attribute
    projected_crs : int
        GeoDataFrame containing watershed polygons. Must have a defined .crs attribute
    output_format : str
        One of either `xarray` (or `xr.Dataset`) or `geopandas` (or `gpd.GeoDataFrame`)

    Returns
    -------
    gpd.GeoDataFrame or xr.Dataset
        Output dataset containing the watershed properties.
    """
    if not gdf.crs:
        raise ValueError("The provided gpd.GeoDataFrame is missing the crs attributes.")
    projected_gdf = gdf.to_crs(projected_crs)

    # Calculate watershed properties
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        output_dataset = gdf.loc[:, gdf.columns != gdf.geometry.name]
        output_dataset["area"] = projected_gdf.area
        output_dataset["perimeter"] = projected_gdf.length
        output_dataset["gravelius"] = (
            output_dataset.perimeter / 2 / np.sqrt(np.pi * output_dataset.area)
        )
        output_dataset["centroid"] = gdf.centroid.apply(lambda x: (x.x, x.y))

    if unique_id is not None:
        output_dataset.set_index(unique_id, inplace=True)

    if output_format in ("xarray", "xr.Dataset"):
        # TODO : Determine if cf-compliant names exist for physiographical data (area, perimeter, etc.)
        output_dataset = output_dataset.to_xarray()
        output_dataset["area"].attrs = {"units": "m2"}
        output_dataset["perimeter"].attrs = {"units": "m"}
        output_dataset["gravelius"].attrs = {"units": "m/m"}
        output_dataset["centroid"].attrs = {"units": ("degreesE", "degreesN")}

    return output_dataset


def _compute_watershed_boundaries(
    coordinates: tuple,
    gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Algorithm for watershed delineation using HydroBASINS (hybas_na_lev01-12_v1c). The process involves assessing
    all upstream sub-basins from a specified pour point and consolidating them into a unified watershed.

    Parameters
    ----------
    coordinates : tuple
        Geographic coordinates (longitude, latitude) for the location where watershed delineation will be conducted.
    gdf : gpd.GeoDataFrame
        Hydrobasins level 12 dataset in GeodataFrame format

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame containing the watershed boundaries.

    """
    spatial_index = gdf.sindex
    point = Point(coordinates)

    # find index of sub-basin (polygon) on which the selected coordinate/pour point falls on
    possible_matches = gdf.iloc[list(spatial_index.intersection(point.bounds))]
    polygon_index = possible_matches[possible_matches.intersects(point)]

    # find all sub-basins indexes upstream of polygon_index
    gdf_main_basin = gdf[gdf["MAIN_BAS"].isin(polygon_index["MAIN_BAS"])]
    all_sub_basins_indexes = _recursive_upstream_lookup(
        gdf_main_basin, polygon_index["HYBAS_ID"].to_list()
    )
    all_sub_basins_indexes.extend(polygon_index["HYBAS_ID"])

    # create GeoDataFrame from all sub-basins indexes and dissolve to a unique basin (new unique index)
    gdf_sub_basins = gdf_main_basin[
        gdf_main_basin["HYBAS_ID"].isin(set(all_sub_basins_indexes))
    ]
    gdf_basin = gdf_sub_basins.dissolve(by="MAIN_BAS")

    # # keep largest polygon if MultiPolygon
    if len(gdf_basin) > 0 and gdf_basin.iloc[0].geometry.geom_type == "MultiPolygon":
        gdf_basin_exploded = gdf_basin.explode()
        gdf_basin = gdf_basin_exploded.loc[[gdf_basin_exploded.area.idxmax()]]

    # Raise warning for invalid or out of extent coordinates
    if len(gdf_basin) == 0:
        warnings.warn(
            f"Could not return a watershed boundary for coordinates {coordinates}."
        )
    return gdf_basin


def _recursive_upstream_lookup(
    gdf: gpd.GeoDataFrame,
    direct_upstream_indexes: list,
    all_upstream_indexes: list = None,
):
    """Recursive function to iterate over each upstream sub-basin until all sub-basins in
    a watershed are identifed

    Parameters
    ----------
    gdf :  gpd.GeoDataFrame
        Hydrobasins level 12 dataset in GeodataFrame format stream of the pour point.
    direct_upstream_indexes : list
        List of all sub-basins indexes directly upstream.
    all_upstream_indexes : list
        Cumulative upstream indexes from `direct_upstream_indexes` accumulated during each iteration.

    Returns
    -------
    all_upstream_indexes
        Cumulative upstream indexes from `direct_upstream_indexes` accumulated during each iteration.
    """
    if all_upstream_indexes is None:
        all_upstream_indexes = []

    # get direct upstream indexes
    direct_upstream_indexes = gdf[gdf["NEXT_DOWN"].isin(direct_upstream_indexes)][
        "HYBAS_ID"
    ].to_list()
    if len(direct_upstream_indexes) > 0:
        all_upstream_indexes.extend(direct_upstream_indexes)
        _recursive_upstream_lookup(gdf, direct_upstream_indexes, all_upstream_indexes)
    return all_upstream_indexes
