"""Convert WIN-format seismic data files to miniseed in SDS directory structure."""

from win2sds.win2sds import main, win2sds

__all__ = ["win2sds", "main", "win2sds_upload_download"]
__version__ = "0.1.0"


def __getattr__(name):
    if name == "win2sds_upload_download":
        from win2sds.colab import win2sds_upload_download
        return win2sds_upload_download
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
