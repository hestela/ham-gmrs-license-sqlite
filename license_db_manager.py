#!/usr/bin/env python3
"""
license_db_manager.py
Downloads and extracts FCC ULS license database files.
Usage: python3 license_db_manager.py [--ham] [--gmrs] [--force] [--build-db]
       (defaults to both if no flags are given)
"""

import argparse
import os
import sqlite3
import sys
import time
import zipfile

LICENSES = {
    "ham": {
        "url": "https://data.fcc.gov/download/pub/uls/complete/l_amat.zip",
        "zip": "l_amat.zip",
        "dest_dir": "ham",
    },
    "gmrs": {
        "url": "https://data.fcc.gov/download/pub/uls/complete/l_gmrs.zip",
        "zip": "l_gmrs.zip",
        "dest_dir": "gmrs",
    },
}

CLASS_MAP = {
    "T": "Technician",
    "G": "General",
    "E": "Amateur Extra",
    "A": "Advanced",
    "N": "Novice",
    "P": "Technician Plus",
}

STATUS_MAP = {
    "A": "Active",
    "E": "Expired",
    "C": "Cancelled",
    "T": "Terminated",
}

US_STATES = frozenset({
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC","GU","PR","VI","AS","MP",
})

TYPE_MAP = {
    "B": "Amateur Club",
    "C": "Corporation",
    "D": "General Partnership",
    "E": "Limited Partnership",
    "F": "Limited Liability Partnership",
    "G": "Governmental Entity",
    "H": "Other",
    "I": "Individual",
    "J": "Joint Venture",
    "L": "Limited Liability Company",
    "M": "Military Recreation",
    "N": "Tribal Entity",
    "O": "Consortium",
    "P": "Partnership",
    "R": "RACES",
    "T": "Trust",
    "U": "Unincorporated Association",
    "Z": "Tribal Entity Controlled by a Business",
}

def maidenhead(lat, lon):
    """Return 6-character Maidenhead grid square for the given lat/lon."""
    lon += 180
    lat += 90
    field_lon = int(lon / 20)
    field_lat = int(lat / 10)
    lon %= 20
    lat %= 10
    square_lon = int(lon / 2)
    square_lat = int(lat)
    lon %= 2
    lat %= 1
    sub_lon = int(lon * 12)
    sub_lat = int(lat * 24)
    return (
        chr(ord("A") + field_lon)
        + chr(ord("A") + field_lat)
        + str(square_lon)
        + str(square_lat)
        + chr(ord("a") + sub_lon)
        + chr(ord("a") + sub_lat)
    )


def build_zip_grid_cache():
    """Return a dict mapping US zip code -> 6-char Maidenhead grid square."""
    import pgeocode
    nomi = pgeocode.Nominatim("us")
    df = nomi._data_frame[["postal_code", "latitude", "longitude"]].dropna()
    cache = {}
    for _, row in df.iterrows():
        cache[row["postal_code"]] = maidenhead(row["latitude"], row["longitude"])
    return cache


# Use a Wget-like user agent string
HEADERS = {"User-Agent": "Wget/1.21.1 (linux-gnu)"}

# Retry parameters
MAX_RETRIES = 3
TIMEOUT = 30  # seconds
CHUNK_SIZE = 8192  # bytes


def download_with_requests(url, dest):
    import requests

    with requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        total = r.headers.get("Content-Length")
        total = int(total) if total and total.isdigit() else None

        downloaded = 0
        start = time.time()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    percent = downloaded * 100.0 / total
                    print(f"\r{os.path.basename(dest)}: {downloaded}/{total} bytes ({percent:.1f}%)", end="", flush=True)
                else:
                    print(f"\r{os.path.basename(dest)}: {downloaded} bytes", end="", flush=True)
        elapsed = time.time() - start
        print(f"\nCompleted {os.path.basename(dest)} in {elapsed:.1f}s")


def download_with_urllib(url, dest):
    from urllib.request import Request, urlopen

    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=TIMEOUT) as r:
        meta = r.info()
        total = meta.get("Content-Length")
        total = int(total) if total and total.isdigit() else None

        downloaded = 0
        start = time.time()
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    percent = downloaded * 100.0 / total
                    print(f"\r{os.path.basename(dest)}: {downloaded}/{total} bytes ({percent:.1f}%)", end="", flush=True)
                else:
                    print(f"\r{os.path.basename(dest)}: {downloaded} bytes", end="", flush=True)
        elapsed = time.time() - start
        print(f"\nCompleted {os.path.basename(dest)} in {elapsed:.1f}s")


def download_with_retries(url, dest):
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            try:
                import requests  # noqa: F401
                download_with_requests(url, dest)
            except ImportError:
                download_with_urllib(url, dest)
            return
        except Exception as e:
            last_exc = e
            wait = 2 ** (attempt - 1)
            print(f"\nAttempt {attempt} failed for {url}: {e}. Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"Failed to download {url} after {MAX_RETRIES} attempts") from last_exc


def extract_dat_files(zip_path, dest_dir, force=False):
    """Extract only .dat files from zip_path into dest_dir, skipping existing files unless force=True."""
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        dat_files = [name for name in zf.namelist() if name.lower().endswith(".dat")]
        skipped = 0
        for name in dat_files:
            out_path = os.path.join(dest_dir, os.path.basename(name))
            if os.path.exists(out_path) and not force:
                skipped += 1
                continue
            with zf.open(name) as src, open(out_path, "wb") as dst:
                dst.write(src.read())
            print(f"  Extracted: {os.path.basename(name)}")
        if skipped:
            print(f"  Skipped {skipped} existing .dat file(s) in {dest_dir}/")


def missing_dat_files(zip_path, dest_dir):
    """Return list of .dat filenames present in the ZIP but missing from dest_dir."""
    if not os.path.exists(zip_path):
        return None  # Can't check without the ZIP; assume missing
    with zipfile.ZipFile(zip_path, "r") as zf:
        dat_files = [os.path.basename(n) for n in zf.namelist() if n.lower().endswith(".dat")]
    return [f for f in dat_files if not os.path.exists(os.path.join(dest_dir, f))]


def process(license_type, force=False):
    cfg = LICENSES[license_type]
    url, zip_path, dest_dir = cfg["url"], cfg["zip"], cfg["dest_dir"]

    # Check if all .dat files already exist (skip only when not forcing)
    if not force:
        missing = missing_dat_files(zip_path, dest_dir)
        if missing is not None and len(missing) == 0:
            print(f"[{license_type}] All .dat files already present in {dest_dir}/, skipping.")
            return

    # Download ZIP (always when forcing, otherwise only if absent)
    if force or not os.path.exists(zip_path):
        print(f"[{license_type}] Downloading {url} -> {zip_path}")
        try:
            download_with_retries(url, zip_path)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return
    else:
        print(f"[{license_type}] ZIP already present: {zip_path}")

    # Extract .dat files
    print(f"[{license_type}] Extracting .dat files into {dest_dir}/")
    extract_dat_files(zip_path, dest_dir, force=force)


def load_hd_status(hd_path):
    """Return a dict mapping license_key -> status string from HD.dat."""
    status = {}
    with open(hd_path, "r", encoding="latin-1") as f:
        for line in f:
            fields = line.split("|")
            if len(fields) > 5:
                status[fields[1]] = STATUS_MAP.get(fields[5].strip(), fields[5].strip())
    return status


def parse_en_location_and_type(fields):
    """
    Return (city, state, zip_code, address, entity_type_code, shift) from an EN record.

    Some records have embedded pipe characters in the name field, which shifts all
    subsequent field indices. We detect this by searching for a valid US state code
    near field [17], then scan forward for the applicant type code.
    """
    shift = 0
    for offset in range(0, 8):
        idx = 17 + offset
        if idx < len(fields) and fields[idx].strip() in US_STATES:
            shift = offset
            break

    city     = fields[16 + shift].strip() if 16 + shift < len(fields) else ""
    state    = fields[17 + shift].strip() if 17 + shift < len(fields) else ""
    zip_code = fields[18 + shift].strip()[:5] if 18 + shift < len(fields) else ""
    address  = fields[15 + shift].strip() if 15 + shift < len(fields) else ""

    entity_type_code = ""
    for i in range(22 + shift, min(32 + shift, len(fields))):
        val = fields[i].strip()
        if val in TYPE_MAP:
            entity_type_code = val
            break

    return city, state, zip_code, address, entity_type_code


def build_ham_db(force=False, extended_info=False):
    """Build ham_licenses.db from ham/AM.dat, ham/HD.dat, and ham/EN.dat."""
    db_path = "ham_licenses.db"
    am_path = os.path.join("ham", "AM.dat")
    en_path = os.path.join("ham", "EN.dat")
    hd_path = os.path.join("ham", "HD.dat")

    for path in (am_path, en_path, hd_path):
        if not os.path.exists(path):
            print(f"ERROR: {path} not found. Run with --ham first to extract data.", file=sys.stderr)
            return

    if os.path.exists(db_path):
        os.remove(db_path)

    print(f"[ham] Building {db_path}...")
    print("[ham] Loading zip code grid square cache...")
    zip_grid = build_zip_grid_cache()

    # Pass 1: load operator class from AM.dat
    am_class = {}
    with open(am_path, "r", encoding="latin-1") as f:
        for line in f:
            fields = line.split("|")
            if len(fields) > 5:
                am_class[fields[1]] = CLASS_MAP.get(fields[5], fields[5])

    print(f"[ham] Loaded {len(am_class):,} operator class records from AM.dat")

    # Pass 2: load status from HD.dat
    hd_status = load_hd_status(hd_path)
    print(f"[ham] Loaded {len(hd_status):,} status records from HD.dat")

    # Pass 3: stream EN.dat and insert into SQLite
    con = sqlite3.connect(db_path)
    extended_cols = ",\n            last_name      TEXT,\n            address        TEXT" if extended_info else ""
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS licensees (
            call_sign      TEXT PRIMARY KEY,
            first_name     TEXT,
            last_initial   TEXT,
            city           TEXT,
            state          TEXT,
            zip_code       TEXT,
            operator_class TEXT,
            grid_square    TEXT,
            status         TEXT,
            type           TEXT{extended_cols}
        )
    """)

    placeholders = "?,?,?,?,?,?,?,?,?,?,?,?" if extended_info else "?,?,?,?,?,?,?,?,?,?"
    batch = []
    total = 0
    with open(en_path, "r", encoding="latin-1") as f:
        for line in f:
            fields = line.split("|")
            if len(fields) <= 24:
                continue
            license_key = fields[1]
            call_sign = fields[4].strip()
            if not call_sign:
                continue
            city, state, zip_code, address, entity_type = parse_en_location_and_type(fields)
            if entity_type != "I":
                first_name = fields[7].strip()
                last_initial = ""
                last_name = ""
            else:
                first_name = fields[8].strip()
                last_name = fields[10].strip()
                last_initial = last_name[0] if last_name else ""
            op_class = am_class.get(license_key, "")
            grid_square = zip_grid.get(zip_code, "")
            status = hd_status.get(license_key, "")
            entity_type_str = TYPE_MAP.get(entity_type, entity_type)
            row = (call_sign, first_name, last_initial, city, state, zip_code, op_class, grid_square, status, entity_type_str)
            if extended_info:
                row += (last_name, address)
            batch.append(row)
            if len(batch) >= 10000:
                con.executemany(f"INSERT OR REPLACE INTO licensees VALUES ({placeholders})", batch)
                total += len(batch)
                batch = []

    if batch:
        con.executemany(f"INSERT OR REPLACE INTO licensees VALUES ({placeholders})", batch)
        total += len(batch)

    con.commit()
    con.close()
    print(f"[ham] Inserted {total:,} records into {db_path}")


def build_gmrs_db(force=False, extended_info=False):
    """Build gmrs_licenses.db from gmrs/EN.dat and gmrs/HD.dat."""
    db_path = "gmrs_licenses.db"
    en_path = os.path.join("gmrs", "EN.dat")
    hd_path = os.path.join("gmrs", "HD.dat")

    for path in (en_path, hd_path):
        if not os.path.exists(path):
            print(f"ERROR: {path} not found. Run with --gmrs first to extract data.", file=sys.stderr)
            return

    if os.path.exists(db_path):
        os.remove(db_path)

    print(f"[gmrs] Building {db_path}...")
    print("[gmrs] Loading zip code grid square cache...")
    zip_grid = build_zip_grid_cache()

    hd_status = load_hd_status(hd_path)
    print(f"[gmrs] Loaded {len(hd_status):,} status records from HD.dat")

    con = sqlite3.connect(db_path)
    extended_cols = ",\n            last_name    TEXT,\n            address      TEXT" if extended_info else ""
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS licensees (
            call_sign    TEXT PRIMARY KEY,
            first_name   TEXT,
            last_initial TEXT,
            city         TEXT,
            state        TEXT,
            zip_code     TEXT,
            grid_square  TEXT,
            status       TEXT,
            type         TEXT{extended_cols}
        )
    """)

    placeholders = "?,?,?,?,?,?,?,?,?,?,?" if extended_info else "?,?,?,?,?,?,?,?,?"
    batch = []
    total = 0
    with open(en_path, "r", encoding="latin-1") as f:
        for line in f:
            fields = line.split("|")
            if len(fields) <= 23:
                continue
            call_sign = fields[4].strip()
            if not call_sign:
                continue
            city, state, zip_code, address, entity_type = parse_en_location_and_type(fields)
            if entity_type != "I":
                first_name = fields[7].strip()
                last_initial = ""
                last_name = ""
            else:
                first_name = fields[8].strip()
                last_name = fields[10].strip()
                last_initial = last_name[0] if last_name else ""
            grid_square = zip_grid.get(zip_code, "")
            license_key = fields[1]
            status = hd_status.get(license_key, "")
            entity_type_str = TYPE_MAP.get(entity_type, entity_type)
            row = (call_sign, first_name, last_initial, city, state, zip_code, grid_square, status, entity_type_str)
            if extended_info:
                row += (last_name, address)
            batch.append(row)
            if len(batch) >= 10000:
                con.executemany(f"INSERT OR REPLACE INTO licensees VALUES ({placeholders})", batch)
                total += len(batch)
                batch = []

    if batch:
        con.executemany(f"INSERT OR REPLACE INTO licensees VALUES ({placeholders})", batch)
        total += len(batch)

    con.commit()
    con.close()
    print(f"[gmrs] Inserted {total:,} records into {db_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Download and extract FCC ULS license databases."
    )
    parser.add_argument("--ham", action="store_true", help="Download amateur radio (HAM) database")
    parser.add_argument("--gmrs", action="store_true", help="Download GMRS database")
    parser.add_argument("--force", action="store_true", help="Re-download ZIP and overwrite existing .dat files")
    parser.add_argument("--build-db", action="store_true", help="Build SQLite database from extracted .dat files")
    parser.add_argument("--extended-info", action="store_true", help="Include full last name and street address in the database")
    args = parser.parse_args()

    # Default to both if neither flag is given
    targets = []
    if args.ham or args.gmrs:
        if args.ham:
            targets.append("ham")
        if args.gmrs:
            targets.append("gmrs")
    else:
        targets = ["ham", "gmrs"]

    for license_type in targets:
        process(license_type, force=args.force)

    if args.build_db:
        if "ham" in targets:
            build_ham_db(force=args.force, extended_info=args.extended_info)
        if "gmrs" in targets:
            build_gmrs_db(force=args.force, extended_info=args.extended_info)


if __name__ == "__main__":
    main()
