# win2sds

Convert WIN-format seismic data files to miniseed in SeisComP Data Structure (SDS) directory layout.

Reads WIN files recursively from a local directory (no server). Maps channel identifiers to SEED IDs and optional station metadata via a CSV lookup table. If a target SDS file already exists, appends and merges with no duplicate time ranges.

Try small datasets (~1-2 GB) online in Google Colab.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jwellik/win2sds/blob/main/win2sds_colab.ipynb)

Install the package locally to convert larger datasets :-)

## Install

```bash
cd win2sds
pip install .
# or
uv pip install -e .
```

## Usage

```bash
win2sds -v win_dir sds_dir lookup_table
```

- **win_dir** — Directory containing WIN files (recursively searched)
- **sds_dir** — Output SDS archive root directory
- **lookup_table** — CSV with columns `win`, `mseed`; optional `lat`, `lon`, `elev`. Lines starting with `#` are skipped.

Options: `-v` / `--verbose`, `--century` (default `'20'`).

## Python API

```python
from win2sds import win2sds

win2sds(win_dir="/path/to/win", sds_dir="/path/to/sds", lookup_table="/path/to/lookup.csv", verbose=True)
```

## License

MIT
