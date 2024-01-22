import xhydro.optimal_interpolation.cross_validation as cv
from xhydro.optimal_interpolation import constants
import numpy as np
from pytest import approx
from xhydro.optimal_interpolation.functions.testdata import get_file

def test_cross_validation_execute():


    station_info_file = get_file(name="data/optimal_interpolation/Info_Station.csv",
                        github_url="https://github.com/Mayetea/xhydro-testdata",
                        branch="optimal_interpolation")
    corresponding_station_file = get_file(name="data/optimal_interpolation/Correspondance_Station.csv",
                                 github_url="https://github.com/Mayetea/xhydro-testdata",
                                 branch="optimal_interpolation")
    selected_station_file = get_file(name="data/optimal_interpolation/stations_retenues_validation_croisee.csv",
                                 github_url="https://github.com/Mayetea/xhydro-testdata",
                                 branch="optimal_interpolation")
    flow_obs_info_file = get_file(name="data/optimal_interpolation/A20_HYDOBS_TEST.nc",
                                 github_url="https://github.com/Mayetea/xhydro-testdata",
                                 branch="optimal_interpolation")
    flow_sim_info_file = get_file(name="data/optimal_interpolation/A20_HYDREP_TEST.nc",
                                 github_url="https://github.com/Mayetea/xhydro-testdata",
                                 branch="optimal_interpolation")

    files = [
        station_info_file,
        corresponding_station_file,
        selected_station_file,
        flow_obs_info_file,
        flow_sim_info_file
    ]

    start_date = '2018-01-01'
    end_date = '2019-01-01'

    result_flows = cv.execute(start_date, end_date, files, False)

    # Test some output flow values
    assert result_flows[0][-1, 0] == 5.123947496179254
    assert result_flows[0][-2, 0] == 5.1971198658408735

    # To randomize to test direct values
    assert np.nanmean(result_flows[1][:, :]) == approx(33, 0.5)
    assert np.nanmean(result_flows[2][:, :]) == approx(59, 0.5)

    # Test the time range duration
    assert len(result_flows[0]) == 365
    assert len(result_flows[1]) == 365
    assert len(result_flows[2]) == 365

    # Test a different data range to verify that the last entry is different
    start_date = '2016-01-01'
    end_date = '2019-01-01'

    result_flows = cv.execute(start_date, end_date, files, False)

    # Test some output flow values
    assert result_flows[0][-1, 0] == 7.969284260715307
    assert result_flows[0][-2, 0] == 8.281532335108624

    # To randomize to test direct values
    assert np.nanmean(result_flows[1][:, :]) == approx(52, 0.5)
    assert np.nanmean(result_flows[2][:, :]) == approx(94, 0.5)

    # Test the time range duration
    assert len(result_flows[0]) == 1096
    assert len(result_flows[1]) == 1096
    assert len(result_flows[2]) == 1096

def test_cross_validation_execute_parralelize():
    start_date = '2018-01-01'
    end_date = '2019-01-01'
    files = [
        constants.DATA_PATH + "Table_Info_Station_Hydro_2020.csv",
        constants.DATA_PATH + "Table_Correspondance_Station_Troncon.csv",
        constants.DATA_PATH + "stations_retenues_validation_croisee.csv",
        constants.DATA_PATH + 'A20_HYDOBS.nc',
        constants.DATA_PATH + 'A20_HYDREP.nc'
    ]

    result_flows = cv.execute(start_date, end_date, files)

    # Test some output flow values
    assert np.nanmean(result_flows[1][:, :]) == approx(33, 0.5)
    assert np.nanmean(result_flows[2][:, :]) == approx(59, 0.5)
