#!/usr/bin/env python3
"""Extract the newest Canva design_id from this machine's browser history.

Why this exists
---------------
`generate-design` returns *suggestion* links shaped like

    https://www.canva.cn/d/V5U4YghpJDrT-oA

That trailing slug is NOT a design_id. Passing it to read-design / export-design
fails with:

    Input validation error: Must be a design ID or a full Canva design share URL
    Input validation error: String must contain exactly 11 character(s)

Only after the link is opened in a browser that is logged into Canva does the
real id show up, as  /design/<11-char id>/...  in the address bar. That visit
lands in the browser History, which this script reads.

Usage
-----
    python design-id.py                  # newest id, Edge
    python design-id.py --browser chrome
    python design-id.py --within 10      # only visits in the last 10 minutes
    python design-id.py --all            # list every distinct id, newest first

Exits non-zero (with a diagnostic) when no design URL was ever visited, which
almost always means the candidate link hit a login wall or a region block.
"""

import argparse
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time

DESIGN_RE = re.compile(r"https?://(?:www\.)?canva\.(?:cn|com)/design/([A-Za-z0-9_-]{11})")

BROWSER_ROOTS = {
    "edge": ("Microsoft", "Edge"),
    "chrome": ("Google", "Chrome"),
}


def history_paths(browser):
    """Every plausible History database for this browser, newest profile first."""
    head, tail = BROWSER_ROOTS[browser]
    root = os.path.join(os.environ["LOCALAPPDATA"], head, tail)
    if not os.path.isdir(root):
        return []
    paths = [os.path.join(root, "User Data", "Default", "History")]
    for name in sorted(os.listdir(root)):
        if name.startswith("Profile "):
            paths.append(os.path.join(root, "User Data", name, "History"))
    return [p for p in paths if os.path.isfile(p)]


def read_rows(history):
    """Copy the (locked) database aside and return (url, last_visit_time) rows.

    A running browser holds History open, so a plain open fails with
    "database is locked". Copying the file under a permissive share mode is
    enough because we only need a read-only snapshot.
    """
    tmpdir = tempfile.mkdtemp(prefix="canva-hist-")
    tmp = os.path.join(tmpdir, "History")
    try:
        with open(history, "rb") as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
        conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        try:
            return conn.execute(
                "SELECT url, last_visit_time FROM urls "
                "WHERE url LIKE '%/design/%' ORDER BY last_visit_time DESC"
            ).fetchall()
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def chrome_time_to_epoch(value):
    """Chrome/Edge timestamps are microseconds since 1601-01-01 UTC."""
    return value / 1_000_000 - 11644473600


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--browser", choices=sorted(BROWSER_ROOTS), default="edge")
    ap.add_argument("--within", type=int, default=0, metavar="MINUTES",
                    help="only visits newer than this many minutes (0 = no limit)")
    ap.add_argument("--all", action="store_true", help="print every distinct id, newest first")
    ap.add_argument("--check", action="store_true", help="report history access only")
    args = ap.parse_args()

    paths = history_paths(args.browser)
    if not paths:
        sys.exit(f"no {args.browser} history found; open the candidate link in {args.browser} first")

    cutoff = time.time() - args.within * 60 if args.within else 0
    seen, ordered = set(), []
    for path in paths:
        try:
            rows = read_rows(path)
        except Exception as exc:  # noqa: BLE001 - any failure just means "try the next profile"
            if args.check:
                print(f"skip {path}: {exc}", file=sys.stderr)
            continue
        for url, visited in rows:
            if cutoff and chrome_time_to_epoch(visited) < cutoff:
                continue
            match = DESIGN_RE.search(url)
            if match and match.group(1) not in seen:
                seen.add(match.group(1))
                ordered.append(match.group(1))

    if args.check:
        print(f"histories: {len(paths)}, design ids: {len(ordered)}")
        return

    if not ordered:
        sys.exit(
            "no /design/<id> URL in history.\n"
            "The candidate link most likely never loaded (Canva login wall, or the "
            "international canva.com region block). Open it manually in a logged-in "
            "browser, confirm the address bar shows /design/<id>/..., then retry."
        )

    for design_id in (ordered if args.all else ordered[:1]):
        print(design_id)


if __name__ == "__main__":
    main()
