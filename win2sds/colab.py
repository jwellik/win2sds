"""
Colab helpers: upload WIN zip + CSV, run win2sds, download SDS zip.

Use only in Google Colab. Requires google.colab.
"""

import os
import shutil
import zipfile
from pathlib import Path


def win2sds_upload_download(win_dir, sds_dir, lookup_table, century="20", verbose=True):
    """
    In Google Colab: prompt for file upload (WIN zip + lookup CSV), run win2sds,
    then offer the SDS output as a zip download.

    Parameters
    ----------
    win_dir : str or Path
        Directory on the Colab VM where WIN files will be extracted (e.g. "/content/win_data").
    sds_dir : str or Path
        Directory on the Colab VM for SDS output (e.g. "/content/sds_output").
    lookup_table : str or Path
        Path on the Colab VM for the lookup CSV. The uploaded CSV will be used;
        this can be the path where it lands (e.g. "/content/lookup.csv").
    century : str, default "20"
        Century for WIN 2-digit year.
    verbose : bool, default True
        Print progress.
    """
    from google.colab import files

    from win2sds.win2sds import win2sds

    uploaded = files.upload()
    if not uploaded:
        raise SystemExit("No files uploaded. Select your WIN zip and lookup CSV.")

    names = list(uploaded.keys())
    zip_name = next((n for n in names if n.lower().endswith(".zip")), None)
    csv_name = next((n for n in names if n.lower().endswith(".csv")), None)
    if not zip_name or not csv_name:
        raise SystemExit(
            "Need one .zip (WIN directory) and one .csv (lookup table). "
            f"Uploaded: {names}"
        )

    if verbose:
        total_mb = sum(len(b) for b in uploaded.values()) / (1024 * 1024)
        print(f"Uploaded: {zip_name}, {csv_name} ({total_mb:.1f} MB total)")
        if total_mb > 1500:
            print("  Warning: large uploads may be slow or time out.")

    win_dir = Path(win_dir)
    sds_dir = Path(sds_dir)
    if win_dir.exists():
        shutil.rmtree(win_dir)
    win_dir.mkdir(parents=True)

    with zipfile.ZipFile(zip_name, "r") as zf:
        zf.extractall(win_dir)

    subdirs = [d for d in win_dir.iterdir() if d.is_dir()]
    if len(subdirs) == 1 and not any(
        win_dir.joinpath(f).is_file()
        for f in os.listdir(win_dir)
        if not f.startswith(".")
    ):
        win_dir = subdirs[0]

    lookup_path = Path(lookup_table).resolve()
    csv_resolved = Path(csv_name).resolve()
    if csv_resolved != lookup_path:
        shutil.copy2(csv_resolved, lookup_path)
    sds_dir.mkdir(parents=True, exist_ok=True)

    win2sds(str(win_dir), str(sds_dir), str(lookup_path), century=century, verbose=verbose)

    zip_out = sds_dir.parent / "sds_output.zip"
    if zip_out.exists():
        zip_out.unlink()
    shutil.make_archive(str(zip_out.with_suffix("")), "zip", sds_dir)
    files.download(str(zip_out))
    if verbose:
        print("Download started. Get sds_output.zip from your browser downloads.")
