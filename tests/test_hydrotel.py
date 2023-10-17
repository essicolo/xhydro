import os

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from xclim.testing.helpers import test_timeseries as timeseries

import xhydro
from xhydro.modelling import Hydrotel


class TestHydrotel:
    def test_options(self, tmpdir):
        xhydro.testing.utils.fake_hydrotel_project(tmpdir, "fake")
        ht = Hydrotel(
            tmpdir / "fake",
            default_options=True,
            project_options={"PROJET HYDROTEL VERSION": "2.1.0"},
            simulation_options={"SIMULATION HYDROTEL VERSION": "1.0.5"},
            output_options={"TMAX_JOUR": 1},
        )

        assert ht.simulation_name == "simulation"
        assert ht.project.name == "fake"

        def _eval_df(df):
            # convert to int, where possible
            for row in df.itertuples():
                try:
                    df.loc[row.Index, 1] = eval(row[1])
                except (TypeError, ValueError):
                    pass
            return df

        # Check that the options have been updated and that the files have been overwritten
        assert ht.project_options["PROJET HYDROTEL VERSION"] == "2.1.0"
        df = _eval_df(
            pd.read_csv(
                ht.project / "projet.csv", sep=";", header=None, index_col=0
            ).replace([np.nan], [None])
        ).to_dict()[1]
        assert ht.project_options == df

        assert ht.simulation_options["SIMULATION HYDROTEL VERSION"] == "1.0.5"
        df = _eval_df(
            pd.read_csv(
                ht.project / "simulation" / ht.simulation_name / "simulation.csv",
                sep=";",
                header=None,
                index_col=0,
            ).replace([np.nan], [None])
        ).to_dict()[1]
        assert ht.simulation_options == df

        assert ht.output_options["TMAX_JOUR"] == 1
        df = _eval_df(
            pd.read_csv(
                ht.project / "simulation" / ht.simulation_name / "output.csv",
                sep=";",
                header=None,
                index_col=0,
            ).replace([np.nan], [None])
        ).to_dict()[1]
        assert ht.output_options == df

        ht2 = Hydrotel(tmpdir / "fake", default_options=False)
        assert ht2.project_options == ht.project_options
        assert ht2.simulation_options == ht.simulation_options
        assert ht2.output_options == ht.output_options

    def test_get_data(self, tmpdir):
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
        meteo = meteo.assign_coords(
            coords={"lat": 46, "lon": -77, "x": 0, "y": 0, "z": 0}
        )
        for c in ["lat", "lon", "x", "y", "z"]:
            meteo[c] = meteo[c].expand_dims("stations")

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

        xhydro.testing.utils.fake_hydrotel_project(
            tmpdir, "fake", meteo=meteo, debit_aval=debit_aval
        )

        ht = Hydrotel(
            tmpdir / "fake",
            default_options=True,
            simulation_options={"FICHIER STATIONS METEO": r"meteo\SLNO_meteo_GC3H.nc"},
        )
        ds = ht.get_input()
        assert all(v in ds.variables for v in ["tasmin", "tasmax", "pr"])
        np.testing.assert_array_equal(ds.tasmin, meteo.tasmin)
        np.testing.assert_array_equal(ds.tasmax.mean(), 1)

        ds = ht.get_streamflow()
        assert all(v in ds.variables for v in ["debit_aval"])
        np.testing.assert_array_equal(ds.dims, ["time", "troncon"])
        np.testing.assert_array_equal(ds.debit_aval.mean(), 0)

    @pytest.mark.parametrize("test", ["ok", "option", "file", "health"])
    def test_basic(self, tmpdir, test):
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
        meteo = meteo.assign_coords(
            coords={"lat": 46, "lon": -77, "x": 0, "y": 0, "z": 0}
        )
        for c in ["lat", "lon", "x", "y", "z"]:
            meteo[c] = meteo[c].expand_dims("stations")
        if test == "health":
            meteo = meteo.reset_coords("z", drop=True).squeeze()
            meteo = meteo.convert_calendar("noleap")
            meteo["tasmin"].attrs["units"] = "K"
            meteo = xr.concat(
                (
                    meteo.sel(time=slice("2001-01-01", "2001-12-30")),
                    meteo.sel(time=slice("2002-01-01", "2002-12-30")),
                ),
                dim="time",
            )

        xhydro.testing.utils.fake_hydrotel_project(tmpdir, "fake", meteo=meteo)
        date_debut = "2001-10-01" if test != "health" else "1999-01-01"
        simulation_options = {
            "FICHIER STATIONS METEO": r"meteo\SLNO_meteo_GC3H.nc",
            "DATE DEBUT": date_debut,
            "DATE FIN": "2002-12-30",
            "PAS DE TEMPS": 24,
        }
        if test == "option":
            df = pd.DataFrame.from_dict(simulation_options, orient="index")
            df = df.replace({None: ""})
            df.to_csv(
                tmpdir / "fake" / "simulation" / "simulation" / "simulation.csv",
                sep=";",
                header=False,
                columns=[0],
            )
        elif test == "file":
            os.remove(
                tmpdir / "fake" / "simulation" / "simulation" / "lecture_tempsol.csv"
            )

        ht = Hydrotel(
            tmpdir / "fake",
            default_options=True if test != "option" else False,
            simulation_options=simulation_options,
        )

        if test == "ok":
            ht._basic_checks()
        elif test == "option":
            with pytest.raises(
                ValueError, match="is missing from the simulation file."
            ):
                ht._basic_checks()
        elif test == "file":
            with pytest.raises(
                FileNotFoundError, match="lecture_tempsol.csv does not exist."
            ):
                ht._basic_checks()
        elif test == "health":
            with pytest.raises(
                ValueError,
                match="The following health checks failed:\n  "
                "- The dimension 'stations' is missing.\n  "
                "- The coordinate 'z' is missing.\n  "
                "- The calendar is not 'standard'. Received 'noleap'.\n  "
                "- The start date is not at least 1999-01-01 00:00:00. Received 2001-01-01 00:00:00.\n  "
                "- The variable 'tasmin' does not have the expected units 'degC'. Received 'K'.\n  "
                "- The timesteps are irregular or cannot be inferred by xarray.",
            ):
                ht._basic_checks()

    def test_standard(self, tmpdir):
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

        xhydro.testing.utils.fake_hydrotel_project(
            tmpdir, "fake", debit_aval=debit_aval
        )

        ht = Hydrotel(tmpdir / "fake", default_options=True)
        ds_orig = ht.get_streamflow().copy()
        ht._standardise_outputs()
        ds = ht.get_streamflow()

        # To make sure the original dataset was not modified prior to standardisation
        assert list(ds_orig.data_vars) == ["debit_aval"]
        np.testing.assert_array_equal(ds_orig.dims, ["time", "troncon"])

        assert list(ds.data_vars) == ["streamflow"]
        np.testing.assert_array_equal(ds.dims, ["time", "station_id"])
        assert ds.streamflow.attrs == {
            "units": "m^3 s-1",
            "description": "Streamflow at the outlet of the river reach",
            "standard_name": "outgoing_water_volume_transport_along_river_channel",
            "long_name": "Streamflow",
            "original_name": "debit_aval",
            "original_description": "Debit en aval du troncon",
            "coordinates": "idtroncon",
        }
