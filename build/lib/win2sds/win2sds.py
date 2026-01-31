#!/usr/bin/env python
"""
Convert WIN-format seismic data files to miniseed in SDS directory structure.

Reads WIN files recursively from a local directory (no server). Maps channel
identifiers to SEED IDs and optional station metadata via a CSV lookup table.
Writes miniseed into SeisComP Data Structure (SDS). If a target SDS file
already exists, appends and merges with no duplicate time ranges.

Usage:
    win2sds -v win_dir sds_dir lookup_table
"""

import csv
import os
import shutil
import argparse
from pathlib import Path

from obspy import read, Stream


def _parse_lookup_table(path, comment_char='#', verbose=False):
    """
    Parse CSV lookup table: win -> mseed, optional lat/lon/elev.
    Skips lines that start with comment_char (after strip).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Lookup table not found: {path}")

    rows = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(comment_char):
                continue
            rows.append(line)

    if not rows:
        raise ValueError(f"Lookup table has no data rows: {path}")

    reader = csv.DictReader(rows, skipinitialspace=True)
    colnames = [c.strip() for c in reader.fieldnames] if reader.fieldnames else []
    if 'win' not in colnames or 'mseed' not in colnames:
        raise ValueError(
            f"Lookup table must have 'win' and 'mseed' columns. Found: {colnames}"
        )

    lookup = {}
    for row in reader:
        # Normalize keys (strip)
        row = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
        win_id = row.get('win', '').strip()
        if not win_id:
            continue
        mseed = row.get('mseed', '').strip()
        if not mseed:
            if verbose:
                print(f"  Skip row: win='{win_id}' has no mseed")
            continue
        parts = mseed.split('.')
        if len(parts) != 4:
            if verbose:
                print(f"  Skip row: mseed must be NET.STA.LOC.CHA, got '{mseed}'")
            continue
        net, sta, loc, chan = parts
        entry = {
            'network': net,
            'station': sta,
            'location': loc,
            'channel': chan,
        }
        for key, attr in [('lat', 'latitude'), ('lon', 'longitude'), ('elev', 'elevation')]:
            if key in row and row[key].strip() != '':
                try:
                    entry[attr] = float(row[key].strip())
                except ValueError:
                    pass
        lookup[win_id] = entry

    return lookup


def _sds_path(sds_dir, network, station, location, channel, year, doy, sds_type='D'):
    """Build SDS file path: sds_dir/YEAR/NET/STA/CHAN.D/NET.STA.LOC.CHA.D.YEAR.DOY.mseed"""
    subdir = os.path.join(
        str(sds_dir), str(year), network, station, f"{channel}.{sds_type}"
    )
    fname = f"{network}.{station}.{location}.{channel}.{sds_type}.{year}.{doy:03d}.mseed"
    return os.path.join(subdir, fname)


def _apply_lookup_and_write(
    tr, lookup_entry, sds_dir, merge_method=-1, reclen=512, verbose=False
):
    """Slice trace by day, optionally merge with existing SDS file, write."""
    net = lookup_entry['network']
    sta = lookup_entry['station']
    loc = lookup_entry['location']
    chan = lookup_entry['channel']

    tr.stats.network = net
    tr.stats.station = sta
    tr.stats.location = loc
    tr.stats.channel = chan
    for attr, key in [('latitude', 'latitude'), ('longitude', 'longitude'), ('elevation', 'elevation')]:
        if key in lookup_entry and hasattr(tr.stats, attr):
            setattr(tr.stats, attr, lookup_entry[key])

    start = tr.stats.starttime
    end = tr.stats.endtime
    current = start.replace(hour=0, minute=0, second=0, microsecond=0)
    day_sec = 86400.0
    written = 0
    while current < end:
        day_end = current + day_sec
        year = current.year
        doy = current.julday
        tr_day = tr.slice(starttime=current, endtime=min(day_end, end))
        if tr_day is None or tr_day.stats.npts == 0:
            current = day_end
            continue

        path = _sds_path(sds_dir, net, sta, loc, chan, year, doy)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            existing = read(path)
            combined = existing + Stream([tr_day])
            combined.merge(method=merge_method, interpolation_samples=0)
            combined.write(path, format='MSEED', reclen=reclen)
        except (OSError, IOError):
            Stream([tr_day]).write(path, format='MSEED', reclen=reclen)

        written += 1
        if verbose:
            print(f"    -> {path}")
        current = day_end

    return written


def win2sds(win_dir, sds_dir, lookup_table, century='20', verbose=True):
    """
    Convert WIN-format files under win_dir to miniseed in SDS structure under sds_dir.

    Parameters
    ----------
    win_dir : str or Path
        Top-level directory containing WIN files (recursively searched).
    sds_dir : str or Path
        Top-level output directory for SDS archive.
    lookup_table : str or Path
        Path to CSV with columns win, mseed; optional lat, lon, elev.
        Lines starting with # are skipped.
    century : str, default '20'
        Century for WIN 2-digit year (e.g. '20' -> 20xx).
    verbose : bool, default True
        Print progress messages.
    """
    win_dir = Path(win_dir)
    sds_dir = Path(sds_dir)
    lookup_table = Path(lookup_table)

    if not win_dir.is_dir():
        raise NotADirectoryError(f"win_dir is not a directory: {win_dir}")
    sds_dir.mkdir(parents=True, exist_ok=True)

    lookup = _parse_lookup_table(lookup_table, verbose=verbose)
    if verbose:
        print(f"Loaded {len(lookup)} lookup entries from {lookup_table}")

    # Recursively find all files
    all_files = [p for p in win_dir.rglob('*') if p.is_file()]
    if verbose:
        print(f"Scanning {len(all_files)} files under {win_dir}")

    total_traces = 0
    total_written = 0
    for fp in sorted(all_files):
        try:
            st = read(str(fp), format='WIN', century=century)
        except Exception:
            continue
        if not st:
            continue
        if verbose:
            print(f"  {fp.relative_to(win_dir)}: {len(st)} trace(s)")

        for tr in st:
            total_traces += 1
            win_id = tr.stats.get('channel', '') or tr.stats.get('station', '')
            if not win_id:
                if verbose:
                    print(f"    Skip trace: no channel/station id")
                continue
            if win_id not in lookup:
                if verbose:
                    print(f"    Skip trace: '{win_id}' not in lookup table")
                continue
            n = _apply_lookup_and_write(
                tr, lookup[win_id], sds_dir, verbose=verbose
            )
            total_written += n

    # Copy lookup table to sds_dir (same filename)
    dest_table = sds_dir / lookup_table.name
    shutil.copy2(lookup_table, dest_table)
    if verbose:
        print(f"Copied lookup table to {dest_table}")
        print(f"Done. Processed {total_traces} traces, wrote {total_written} day files.")


def main():
    parser = argparse.ArgumentParser(
        description='Convert WIN-format seismic files to miniseed in SDS structure (local files only, no server).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('win_dir', help='Directory containing WIN files (recursively searched)')
    parser.add_argument('sds_dir', help='Output SDS archive root directory')
    parser.add_argument('lookup_table', help='CSV: win, mseed; optional lat, lon, elev (# = comment lines)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--century', default='20', help="WIN 2-digit year century (default: '20')")
    args = parser.parse_args()

    win2sds(
        args.win_dir,
        args.sds_dir,
        args.lookup_table,
        century=args.century,
        verbose=args.verbose,
    )


if __name__ == '__main__':
    main()
