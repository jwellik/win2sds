"""Convert WIN-format seismic data files to miniseed in SDS directory structure."""

from win2sds.win2sds import main, win2sds

__all__ = ["win2sds", "main"]
__version__ = "0.1.0"
