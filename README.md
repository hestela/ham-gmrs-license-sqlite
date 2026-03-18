# Ham/GMRS License SQLite DB Generator

Downloads and builds SQLite databases from the FCC Universal Licensing System (ULS) bulk data exports for ham radio and GMRS licenses.
the SQL table by default will provide:
- callsign
- first name + last initial
- zip code, city, state
- grid square (calculated from zip code)
- license type (individual, government, club, etc)
- status (expired, active, cancelled)
Optionally includes:
- Address
- Last name

## Requirements
- Python 3.13
- `pgeocode` (for Maidenhead grid square lookup)
- `requests` (optional, falls back to `urllib` if not available)

Install dependencies:

```
pip install -r requirements.txt
```

## Usage

```
python3 license_db_manager.py [--ham] [--gmrs] [--force] [--build-db] [--extended-info]
```

If neither `--ham` nor `--gmrs` is given, both are processed.

### Flags

| Flag | Description |
|------|-------------|
| `--ham` | Download and/or build the amateur radio database |
| `--gmrs` | Download and/or build the GMRS database |
| `--force` | Re-download ZIP files and overwrite extracted `.dat` files |
| `--build-db` | Build SQLite databases from the extracted `.dat` files |
| `--extended-info` | Add full last name and street address columns to the database |

### Examples

Download both datasets:

```
python3 license_db_manager.py
```

Download and build both databases:

```
python3 license_db_manager.py --build-db
```

Rebuild the HAM database with extended info (without re-downloading):

```
python3 license_db_manager.py --ham --build-db --extended-info
```

Re-download and rebuild everything:

```
python3 license_db_manager.py --force --build-db
```

## Output

### Files

| File | Description |
|------|-------------|
| `l_amat.zip` | Downloaded HAM ULS export |
| `l_gmrs.zip` | Downloaded GMRS ULS export |
| `ham/` | Extracted `.dat` files for HAM |
| `gmrs/` | Extracted `.dat` files for GMRS |
| `ham_licenses.db` | SQLite database for HAM licensees |
| `gmrs_licenses.db` | SQLite database for GMRS licensees |

### Database schema

**HAM (`ham_licenses.db`)**

| Column | Description |
|--------|-------------|
| `call_sign` | FCC call sign (primary key) |
| `first_name` | First name, or full organization name for clubs |
| `last_initial` | First letter of last name (individuals only) |
| `city` | City |
| `state` | State abbreviation |
| `zip_code` | 5-digit ZIP code |
| `operator_class` | License class (Technician, General, Amateur Extra, etc.) |
| `grid_square` | 6-character Maidenhead grid square derived from ZIP code |
| `status` | License status (Active, Expired, Cancelled, Terminated) |
| `type` | Entity type (Individual, Amateur Club, Corporation, etc.) |

**GMRS (`gmrs_licenses.db`)**

| Column | Description |
|--------|-------------|
| `call_sign` | FCC call sign (primary key) |
| `first_name` | First name |
| `last_initial` | First letter of last name |
| `city` | City |
| `state` | State abbreviation |
| `zip_code` | 5-digit ZIP code |
| `grid_square` | 6-character Maidenhead grid square derived from ZIP code |
| `status` | License status (Active, Expired, Cancelled, Terminated) |
| `type` | Entity type (Individual, Corporation, etc.) |

When `--extended-info` is used, two additional columns are appended to both tables:

| Column | Description |
|--------|-------------|
| `last_name` | Full last name (individuals only; empty for HAM clubs) |
| `address` | Street address |

## Data source

Data comes from the FCC ULS bulk download page at `data.fcc.gov`. The full dataset is updated weekly. Both exports include all entity types and all license statuses.

The downloader uses a `Wget/1.21.1` user agent, retries up to 3 times with exponential backoff, and skips files that are already present on disk unless `--force` is given.

## Data format notes

The FCC exports use pipe-delimited `.dat` files. Each file corresponds to a record type and records are linked across files by a license key. The files used by this project are:

| File | Contents |
|------|----------|
| `EN.dat` | Entity records: name, address, call sign |
| `HD.dat` | Header records: license status, grant and expiry dates |
| `AM.dat` | Amateur-specific records: operator class (HAM only) |
