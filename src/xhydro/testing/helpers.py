"""Helper functions for testing data management."""

import importlib.resources as ilr
import logging
import os
from pathlib import Path
from typing import Optional, Union

import pooch

from xhydro import __version__ as __xhydro_version__

__all__ = [
    "DATA_DIR",
    "DATA_UPDATES",
    "DATA_URL",
    "TESTDATA_BRANCH",
    "deveraux",
    "load_registry",
    "populate_testing_data",
]

_default_cache_dir = pooch.os_cache("xhydro-testdata")


def load_registry(file: Optional[Union[str, Path]] = None) -> dict[str, str]:
    """Load the registry file for the test data.

    Parameters
    ----------
    file : str or Path, optional
        Path to the registry file. If not provided, the registry file found within the package data will be used.

    Returns
    -------
    dict
        Dictionary of filenames and hashes.
    """
    # Get registry file from package_data
    if file is None:
        registry_file = ilr.files("xhydro").joinpath("testing/registry.txt")
        if registry_file.is_file():
            logging.info("Registry file found in package_data: %s", registry_file)
    else:
        registry_file = Path(file)
        if not registry_file.is_file():
            raise FileNotFoundError(f"Registry file not found: {registry_file}")

    # Load the registry file
    registry = dict()
    with registry_file.open() as buffer:
        for entry in buffer.readlines():
            registry[entry.split()[0]] = entry.split()[1]

    return registry


DATA_DIR = os.getenv("XHYDRO_DATA_DIR", _default_cache_dir)
"""Sets the directory to store the testing datasets.

If not set, the default location will be used (based on ``platformdirs``, see :func:`pooch.os_cache`).

Notes
-----
When running tests locally, this can be set for both `pytest` and `tox` by exporting the variable:

.. code-block:: console

    $ export XHYDRO_DATA_DIR="/path/to/my/data"

or setting the variable at runtime:

.. code-block:: console

    $ env XHYDRO_DATA_DIR="/path/to/my/data" pytest
"""

DATA_UPDATES = bool(os.getenv("XHYDRO_DATA_UPDATES", False))
"""Sets whether to allow updates to the testing datasets.

If set to ``True``, the data files will be downloaded even if the upstream hashes do not match.

Notes
-----
When running tests locally, this can be set for both `pytest` and `tox` by exporting the variable:

.. code-block:: console

    $ export XHYDRO_DATA_UPDATES=True

or setting the variable at runtime:

.. code-block:: console

    $ env XHYDRO_DATA_UPDATES=True pytest
"""

TESTDATA_BRANCH = os.getenv("XHYDRO_TESTDATA_BRANCH", "main")
"""Sets the branch of hydrologie/xhydro-testdata to use when fetching testing datasets.

Notes
-----
When running tests locally, this can be set for both `pytest` and `tox` by exporting the variable:

.. code-block:: console

    $ export XHYDRO_TESTDATA_BRANCH="my_testing_branch"

or setting the variable at runtime:

.. code-block:: console

    $ env XHYDRO_TESTDATA_BRANCH="my_testing_branch" pytest
"""

DATA_URL = f"https://github.com/hydrologie/xhydro-testdata/raw/{TESTDATA_BRANCH}/data/"


def deveraux(  # noqa: PR01
    data_dir: Union[str, Path] = DATA_DIR,
    data_updates: bool = DATA_UPDATES,
    data_url: str = DATA_URL,
):
    """Pooch registry instance for xhydro test data.

    Parameters
    ----------
    data_dir : str or Path
        Path to the directory where the data files are stored.
    data_updates : bool
        If True, allow updates to the data files.
    data_url : str
        Base URL to download the data files.

    Returns
    -------
    pooch.Pooch
        Pooch instance for the xhydro test data.

    Notes
    -----
    There are three environment variables that can be used to control the behaviour of this registry:

        - ``XHYDRO_DATA_DIR``: If this environment variable is set, it will be used as the base directory to store the data
          files. The directory should be an absolute path (i.e., it should start with ``/``). Otherwise,
          the default location will be used (based on ``platformdirs``, see :py:func:`pooch.os_cache`).
        - ``XHYDRO_DATA_UPDATES``: If this environment variable is set, then the data files will be downloaded even if the
          upstream hashes do not match. This is useful if you want to always use the latest version of the data files.
        - ``XHYDRO_DATA_URL``: If this environment variable is set, it will be used as the base URL to download the data files.

    Examples
    --------
    Using the registry to download a file:

    .. code-block:: python

        import xarray as xr
        from xhydro.testing.helpers import deveraux

        example_file = devereaux().fetch("example.nc")
        data = xr.open_dataset(example_file)
    """
    return pooch.create(
        path=data_dir,
        base_url=data_url,
        version=__xhydro_version__,
        version_dev="main",
        allow_updates=data_updates,
        registry=load_registry(),
    )


def populate_testing_data(
    registry_file: Optional[Union[str, Path]] = None,
    temp_folder: Optional[Path] = None,
    branch: str = TESTDATA_BRANCH,
    _local_cache: Path = _default_cache_dir,
) -> None:
    """Populate the local cache with the testing data.

    Parameters
    ----------
    registry_file : str or Path, optional
        Path to the registry file. If not provided, the registry file from package_data will be used.
    temp_folder : Path, optional
        Path to a temporary folder to use as the local cache. If not provided, the default location will be used.
    branch : str, optional
        Branch of hydrologie/xhydro-testdata to use when fetching testing datasets.
    _local_cache : Path, optional
        Path to the local cache. Defaults to the location set by the platformdirs library.
        The testing data will be downloaded to this local cache.

    Returns
    -------
    dict
        The registry dictionary of files and their locations.
    """
    # Get registry file from package_data or provided path
    registry = load_registry(registry_file)
    # Set the local cache to the temp folder
    if temp_folder is not None:
        _local_cache = temp_folder

    # Create the Pooch instance
    d = deveraux()

    # Set the branch
    d.version_dev = branch
    # Set the local cache
    d.path = _local_cache

    # Download the files
    for file in registry.keys():
        d.fetch(file, processor=pooch.Unzip())
