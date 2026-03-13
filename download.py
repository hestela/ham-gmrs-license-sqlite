#!/usr/bin/env python3
"""
download_fcc.py
Downloads two FCC ZIP files with a wget-like User-Agent header.
Usage: python3 download_fcc.py
"""

import os
import sys
import time

URLS = [
    "https://data.fcc.gov/download/pub/uls/complete/l_amat.zip",
    "https://data.fcc.gov/download/pub/uls/complete/l_gmrs.zip",
]

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
    from urllib.error import URLError, HTTPError

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
            # Prefer requests if available
            try:
                import requests  # noqa: F401
                download_with_requests(url, dest)
            except Exception:
                # If requests isn't available or download_with_requests fails, try urllib
                download_with_urllib(url, dest)
            return
        except Exception as e:
            last_exc = e
            wait = 2 ** (attempt - 1)
            print(f"\nAttempt {attempt} failed for {url}: {e}. Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"Failed to download {url} after {MAX_RETRIES} attempts") from last_exc


def main():
    for url in URLS:
        filename = os.path.basename(url)
        if os.path.exists(filename):
            print(f"File already exists, skipping: {filename}")
            continue
        print(f"Downloading {url} -> {filename}")
        try:
            download_with_retries(url, filename)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
