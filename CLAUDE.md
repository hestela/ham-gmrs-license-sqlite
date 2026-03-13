# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project downloads and organizes FCC Universal Licensing System (ULS) database exports for amateur (HAM) radio and GMRS licenses. Data comes from `data.fcc.gov` as ZIP archives containing pipe-delimited `.dat` files.

## Commands

```bash
# Download both HAM and GMRS databases (default)
python3 license_db_manager.py

# Download only one database
python3 license_db_manager.py --ham
python3 license_db_manager.py --gmrs

# Activate virtual environment (Python 3.13)
source venv/bin/activate
```

No build system, test suite, or linter is configured.

## Data Architecture

The FCC exports use a multi-table flat-file format. Each `.dat` file corresponds to a record type:

| File | Record Type | Contents |
|------|-------------|----------|
| `EN.dat` | Entity | Licensee name, address, call sign |
| `HD.dat` | Header | License status, grant/expiry dates |
| `HS.dat` | History | License status change history |
| `CO.dat` | Comment | License comments |
| `LA.dat` | License Attachment | Attachment metadata |
| `SC.dat` | Special Condition | Special conditions on license |
| `AM.dat` | Amateur | Amateur-specific fields (ham only) |
| `SF.dat` | Short Form | Short form data (ham only) |

Records are pipe-delimited (`|`) with CRLF line endings. The first field is always the record type identifier (e.g., `EN`, `HD`). Records across files are linked by the license record key (field 2).

Extracted data lives in `ham/` and `gmrs/` directories. Each directory also contains a `counts` file with the FCC export timestamp and per-file record counts.

## Download Script Notes

- `license_db_manager.py` prefers `requests` library but falls back to `urllib` if unavailable
- Uses a `Wget/1.21.1` User-Agent to avoid FCC server blocks
- Retries up to 3 times with exponential backoff (1s, 2s, 4s)
- Files are saved to the working directory as `l_amat.zip` and `l_gmrs.zip`
- Re-running skips files that already exist on disk
