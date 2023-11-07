"""Utilities for testing and releasing xhydro."""
import os
import pathlib
import re
from io import StringIO
from pathlib import Path
from typing import Optional, TextIO, Union

import numpy as np
import pandas as pd
import xarray as xr
import yaml
from xclim.testing.helpers import test_timeseries as timeseries

testing_data = Path(__file__).parent / "data"


def fake_hydrotel_project(
    directory: Union[str, os.PathLike],
    name: str,
    *,
    meteo: Optional[Union[bool, xr.Dataset]] = None,
    debit_aval: Optional[Union[bool, xr.Dataset]] = None,
):
    """Create a fake Hydrotel project in the given directory.

    Parameters
    ----------
    directory : str or os.PathLike
        Directory where the project will be created.
    name : str
        Name of the project.
    meteo : bool or xr.Dataset, optional
        Fake meteo timeseries. If True, a 2-year timeseries of zeros (tasmin) and ones (tasmax, pr) is created. Alternatively, provide a Dataset.
        Leave None to create a fake file.
    debit_aval : bool or xr.Dataset, optional
        Fake debit_aval timeseries. If True, a 2-year timeseries of zeros is created. Alternatively, provide a Dataset.
        Leave None to create a fake file.

    Notes
    -----
    Uses the directory structure specified in xhydro/testing/hydrotel_structure.yml.
    Most files are fake and empty, except for the projet.csv, simulation.csv and output.csv files, which are filled with
    default options taken from xhydro/modelling/data/hydrotel_defaults.yml. If their respective arguments are None,
    the meteo/SLNO_meteo_GC3H.nc and simulation/simulation/resultat/debit_aval.nc files will also be fake.
    """
    project = Path(directory) / name
    with open(testing_data / "hydrotel_structure.yml") as f:
        struc = yaml.safe_load(f)["structure"]
    with open(
        Path(__file__).parent.parent / "modelling" / "data" / "hydrotel_defaults.yml"
    ) as f:
        defaults = yaml.safe_load(f)

    project.mkdir(exist_ok=True, parents=True)
    for k, v in struc.items():
        if k != "_main":
            project.joinpath(k).mkdir(exist_ok=True, parents=True)
            for file in v:
                if file in ["simulation.csv", "output.csv"]:
                    opt = defaults[f"{file.split('.')[0]}_options"]
                    df = pd.DataFrame.from_dict(opt, orient="index")
                    df = df.replace({None: ""})
                    df.to_csv(
                        project / k / file,
                        sep=";",
                        header=False,
                        columns=[0],
                    )
                elif file is not None and Path(file).suffix != ".nc":
                    (project / k / file).touch()
    for file in struc["_main"]:
        if file in ["projet.csv"]:
            opt = defaults["project_options"]
            df = pd.DataFrame.from_dict(opt, orient="index")
            df = df.replace({None: ""})
            df.to_csv(
                project / file,
                sep=";",
                header=False,
                columns=[0],
            )
        elif file is not None:
            (project / file).touch()

    # Create fake meteo and debit_aval files
    if isinstance(meteo, bool) and meteo:
        meteo = timeseries(
            np.zeros(365 * 2),
            start="2001-01-01",
            freq="D",
            variable="tasmin",
            as_dataset=True,
            units="degC",
        )
        meteo["tasmax"] = timeseries(
            np.ones(365 * 2),
            start="2001-01-01",
            freq="D",
            variable="tasmax",
            units="degC",
        )
        meteo["pr"] = timeseries(
            np.ones(365 * 2) * 10,
            start="2001-01-01",
            freq="D",
            variable="pr",
            units="mm",
        )
        meteo = meteo.expand_dims("stations").assign_coords(stations=["010101"])
        meteo = meteo.assign_coords(coords={"lat": 46, "lon": -77, "z": 0})
        for c in ["lat", "lon", "z"]:
            meteo[c] = meteo[c].expand_dims("stations")
    if isinstance(meteo, xr.Dataset):
        meteo.to_netcdf(project / "meteo" / "SLNO_meteo_GC3H.nc")
        cfg = pd.Series(
            {
                "TYPE (STATION/GRID)": "STATION",
                "STATION_DIM_NAME": "stations",
                "LATITUDE_NAME": "lat",
                "LONGITUDE_NAME": "lon",
                "ELEVATION_NAME": "z",
                "TIME_NAME": "time",
                "TMIN_NAME": "tasmin",
                "TMAX_NAME": "tasmax",
                "PRECIP_NAME": "pr",
            }
        )
        cfg.to_csv(
            project / "meteo" / "SLNO_meteo_GC3H.nc.config",
            sep=";",
            header=False,
            columns=[0],
        )
    else:
        (project / "meteo" / "SLNO_meteo_GC3H.nc").touch()
        (project / "meteo" / "SLNO_meteo_GC3H.nc.config").touch()

    if isinstance(debit_aval, bool) and debit_aval:
        debit_aval = timeseries(
            np.zeros(365 * 2),
            start="2001-01-01",
            freq="D",
            variable="streamflow",
            as_dataset=True,
        )
        debit_aval = debit_aval.expand_dims("troncon").assign_coords(troncon=[0])
        debit_aval = debit_aval.assign_coords(coords={"idtroncon": 0})
        debit_aval["idtroncon"] = debit_aval["idtroncon"].expand_dims("troncon")
        debit_aval = debit_aval.rename({"streamflow": "debit_aval"})
        debit_aval["debit_aval"].attrs = {
            "units": "m3/s",
            "description": "Debit en aval du troncon",
        }
    if isinstance(debit_aval, xr.Dataset):
        debit_aval.to_netcdf(
            project / "simulation" / "simulation" / "resultat" / "debit_aval.nc"
        )
    else:
        (project / "simulation" / "simulation" / "resultat" / "debit_aval.nc").touch()


def publish_release_notes(
    style: str = "md", file: Optional[Union[os.PathLike, StringIO, TextIO]] = None
) -> Optional[str]:
    """Format release history in Markdown or ReStructuredText.

    Parameters
    ----------
    style : {"rst", "md"}
        Use ReStructuredText (`rst`) or Markdown (`md`) formatting. Default: Markdown.
    file : {od.PathLike, StringIO, TextIO}, optional
        If provided, prints to the given file-like object. Otherwise, returns a string.

    Returns
    -------
    str, optional

    Notes
    -----
    This function exists solely for development purposes.
    Adapted from xclim.testing.utils.publish_release_notes.
    """
    history_file = Path(__file__).parent.parent.parent.joinpath("HISTORY.rst")

    if not history_file.exists():
        raise FileNotFoundError("History file not found in xhydro file tree.")

    with open(history_file) as hf:
        history = hf.read()

    if style == "rst":
        hyperlink_replacements = {
            r":issue:`([0-9]+)`": r"`GH/\1 <https://github.com/hydrologie/xhydro/issues/\1>`_",
            r":pull:`([0-9]+)`": r"`PR/\1 <https://github.com/hydrologie/xhydro/pull/\>`_",
            r":user:`([a-zA-Z0-9_.-]+)`": r"`@\1 <https://github.com/\1>`_",
        }
    elif style == "md":
        hyperlink_replacements = {
            r":issue:`([0-9]+)`": r"[GH/\1](https://github.com/hydrologie/xhydro/issues/\1)",
            r":pull:`([0-9]+)`": r"[PR/\1](https://github.com/hydrologie/xhydro/pull/\1)",
            r":user:`([a-zA-Z0-9_.-]+)`": r"[@\1](https://github.com/\1)",
        }
    else:
        raise NotImplementedError(f"Style {style} not implemented.")

    for search, replacement in hyperlink_replacements.items():
        history = re.sub(search, replacement, history)

    if style == "md":
        history = history.replace("=======\nHistory\n=======", "# History")

        titles = {r"\n(.*?)\n([\-]{1,})": "-", r"\n(.*?)\n([\^]{1,})": "^"}
        for title_expression, level in titles.items():
            found = re.findall(title_expression, history)
            for grouping in found:
                fixed_grouping = (
                    str(grouping[0]).replace("(", r"\(").replace(")", r"\)")
                )
                search = rf"({fixed_grouping})\n([\{level}]{'{' + str(len(grouping[1])) + '}'})"
                replacement = f"{'##' if level=='-' else '###'} {grouping[0]}"
                history = re.sub(search, replacement, history)

        link_expressions = r"[\`]{1}([\w\s]+)\s<(.+)>`\_"
        found = re.findall(link_expressions, history)
        for grouping in found:
            search = rf"`{grouping[0]} <.+>`\_"
            replacement = f"[{str(grouping[0]).strip()}]({grouping[1]})"
            history = re.sub(search, replacement, history)

    if not file:
        return history
    print(history, file=file)
