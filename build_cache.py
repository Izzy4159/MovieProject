#!/usr/bin/env python3
import os
import json
import time
import argparse
from pathlib import Path
from typing import Dict

# Reuse your data module (OMDb + Jikan + fuzzy fallback)
from data import get_movie_info

POSTERS_DIR = Path("posters")
CACHE_FILE = Path("omdb_cache.json")

IGNORE_WORDS = {"ver", "xlg", "poster", "final", "intl", "cover"}

def clean_title(raw_name: str) -> str:
    parts = raw_name.replace("_", " ").replace("-", " ").split()
    cleaned = [w for w in parts if not any(w.lower().startswith(ig) for ig in IGNORE_WORDS)]
    return " ".join(cleaned).strip()

def norm_key(title: str) -> str:
    return "".join(ch.lower() for ch in title if ch.isalnum() or ch.isspace()).strip()

def load_cache() -> Dict[str, dict]:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache: Dict[str, dict]):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def needs_update(entry: dict, force: bool) -> bool:
    """
    Decide whether an existing cache entry should be refreshed.
    """
    if force:
        return True
    if not entry:
        return True
    # Refresh placeholders / blanks
    if (entry.get("plot") in (None, "", "No plot available")) or (entry.get("title") in (None, "", "N/A")):
        return True
    return False

def robust_lookup(title_guess: str, retries: int, sleep_secs: float) -> dict | None:
    """
    Call get_movie_info with basic retry/backoff to survive OMDb rate limits.
    """
    attempt = 0
    while attempt <= retries:
        info = get_movie_info(title_guess)
        if info:
            return info
        # Heuristic: if None returned, we might be rate-limited or the title failed to match.
        # Back off and retry a bit.
        backoff = sleep_secs + attempt * 0.6
        time.sleep(backoff)
        attempt += 1
    return None

def main():
    parser = argparse.ArgumentParser(description="Prebuild OMDb/Jikan metadata cache for posters.")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between API calls (default: 1.0)")
    parser.add_argument("--retries", type=int, default=2, help="Retries per title on failure (default: 2)")
    parser.add_argument("--force", action="store_true", help="Force refresh even if entry exists")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of posters to process (0 = all)")
    args = parser.parse_args()

    cache = load_cache()

    if not POSTERS_DIR.exists():
        print(f"❌ posters/ not found at: {POSTERS_DIR.resolve()}")
        return

    posters = sorted(
        [p for p in POSTERS_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".webp"],
        key=lambda p: p.name.lower()
    )

    if args.limit > 0:
        posters = posters[:args.limit]

    total = len(posters)
    added = updated = skipped = failed = 0

    print(f"Scanning {total} posters in {POSTERS_DIR.resolve()}")
    print(f"Options: sleep={args.sleep}s, retries={args.retries}, force={args.force}, limit={args.limit or 'ALL'}")

    for idx, p in enumerate(posters, 1):
        base = p.stem
        title_guess = clean_title(base)
        key = norm_key(title_guess)

        existing = cache.get(key)
        if existing and not needs_update(existing, args.force):
            skipped += 1
            if idx % 25 == 0:
                print(f"… {idx}/{total} processed (skipping cached OK entries)")
            continue

        print(f"[{idx}/{total}] lookup: {title_guess}")
        info = robust_lookup(title_guess, retries=args.retries, sleep_secs=args.sleep)

        if info:
            entry = {
                "title": info.get("title") or title_guess,
                "year": info.get("year") or "N/A",
                "rating": info.get("rating") or "N/A",
                "plot": info.get("plot") or "No plot available",
                "source": info.get("source") or "unknown",
            }
            if existing:
                updated += 1
            else:
                added += 1
            cache[key] = entry
        else:
            failed += 1
            # Keep a placeholder (so the script won't hammer the same item repeatedly)
            cache[key] = {
                "title": title_guess, "year": "N/A", "rating": "N/A",
                "plot": "No plot available", "source": "none"
            }

        save_cache(cache)
        time.sleep(args.sleep)

    print("\n----- SUMMARY -----")
    print(f"Total posters: {total}")
    print(f"Added new:     {added}")
    print(f"Updated:       {updated}")
    print(f"Skipped:       {skipped}")
    print(f"Failed:        {failed}")
    print("-------------------")

if __name__ == "__main__":
    main()
