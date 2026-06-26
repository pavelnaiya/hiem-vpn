#!/usr/bin/env python3
"""Scrape all Framer community members via the public/unified members API.

The /community/members page uses infinite scroll that calls a JSON endpoint
under www.framer.com/creators/api/unified/members/ with cursor-based
pagination. This script walks that cursor until every member is fetched.

Usage:
    python framer_members_scraper.py
    python framer_members_scraper.py --sort popular --limit 100 --output members.csv
    python framer_members_scraper.py --type experts
    python framer_members_scraper.py --max-pages 5      # quick test run
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import requests

MEMBERS_URL = "https://www.framer.com/creators/api/unified/members/"
COUNT_URL = "https://www.framer.com/creators/api/unified/members/count/"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.framer.com/community/members/",
    "Origin": "https://www.framer.com",
}

CSV_FIELDS = [
    "framerUserId",
    "name",
    "slug",
    "handle",
    "url",
    "avatar",
    "description",
    "badges",
    "followerCount",
    "followingCount",
]


def row_from_member(m: dict) -> dict:
    slug = m.get("slug") or ""
    return {
        "framerUserId": m.get("framerUserId", ""),
        "name": m.get("name", ""),
        "slug": slug,
        "handle": m.get("handle", f"@{slug}" if slug else ""),
        "url": f"https://www.framer.com/@{slug}" if slug else "",
        "avatar": m.get("avatar", "") or "",
        "description": (m.get("description") or "").replace("\n", " ").strip(),
        "badges": ";".join(m.get("badges") or []),
        "followerCount": m.get("followerCount", ""),
        "followingCount": m.get("followingCount", ""),
    }


def fetch_count(session: requests.Session, params: dict) -> int:
    try:
        r = session.get(COUNT_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
        r.raise_for_status()
        return int(r.json().get("count", 0))
    except Exception as e:
        print(f"[warn] could not fetch count: {e}", file=sys.stderr)
        return 0


def fetch_page(session: requests.Session, params: dict, cursor: str | None,
               retries: int = 4) -> tuple[list[dict], str | None]:
    p = dict(params)
    if cursor:
        p["after"] = cursor
    backoff = 2.0
    for attempt in range(retries):
        try:
            r = session.get(MEMBERS_URL, params=p, headers=DEFAULT_HEADERS, timeout=30)
            if r.status_code == 429:
                wait = backoff * (attempt + 1)
                print(f"[rate-limit] 429, sleeping {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            return data.get("data", []), (data.get("pagination") or {}).get("next")
        except requests.RequestException as e:
            wait = backoff * (attempt + 1)
            print(f"[retry {attempt+1}/{retries}] {e}; sleeping {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"failed after {retries} retries at cursor={cursor}")


def run(args: argparse.Namespace) -> None:
    params: dict = {"limit": args.limit, "sort": args.sort}
    if args.type and args.type != "all":
        params["memberType"] = args.type

    total_expected = fetch_count(args.session if hasattr(args, "session") else requests.Session(), params)
    print(f"Reported member count: {total_expected:,}", file=sys.stderr)

    out_path = Path(args.output)
    write_header = not out_path.exists() or args.overwrite
    mode = "w" if args.overwrite else "a"

    session = requests.Session()
    cursor: str | None = None
    fetched = 0
    page_idx = 0
    start = time.time()

    with out_path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()

        while True:
            page_idx += 1
            members, cursor = fetch_page(session, params, cursor)
            if not members:
                print(f"[page {page_idx}] empty page, done.", file=sys.stderr)
                break

            for m in members:
                writer.writerow(row_from_member(m))
            f.flush()
            fetched += len(members)

            elapsed = time.time() - start
            pct = (fetched / total_expected * 100) if total_expected else 0
            print(
                f"[page {page_idx}] +{len(members)} | total {fetched:,}"
                f" ({pct:.1f}% of {total_expected:,}) | {elapsed:.0f}s",
                file=sys.stderr,
            )

            if args.max_pages and page_idx >= args.max_pages:
                print(f"[stop] reached --max-pages {args.max_pages}", file=sys.stderr)
                break

            if not cursor:
                print("[done] no next cursor.", file=sys.stderr)
                break

            time.sleep(args.delay)

    print(f"Wrote {fetched:,} members to {out_path}", file=sys.stderr)

    if args.json:
        json_path = out_path.with_suffix(".json")
        rows = []
        with out_path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {len(rows):,} rows to {json_path}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Scrape Framer community members.")
    ap.add_argument("-o", "--output", default="framer_members.csv", help="CSV output path")
    ap.add_argument("--sort", default="popular", help="sort order (popular|newest|...)")
    ap.add_argument("--type", default="all", help="memberType filter (all|creators|experts)")
    ap.add_argument("--limit", type=int, default=50, help="page size (max ~50)")
    ap.add_argument("--delay", type=float, default=0.3, help="seconds between requests")
    ap.add_argument("--max-pages", type=int, default=0, help="stop after N pages (0 = unlimited)")
    ap.add_argument("--overwrite", action="store_true", help="overwrite output instead of appending")
    ap.add_argument("--json", action="store_true", help="also emit a .json file")
    return ap.parse_args()


if __name__ == "__main__":
    run(parse_args())
