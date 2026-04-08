#!/usr/bin/env python3
import json
import time
import argparse
from pathlib import Path
from typing import Dict
 
from data import get_movie_info, parse_filename, norm_key
 
POSTERS_DIR = Path("posters")
CACHE_FILE = Path("omdb_cache.json")
 
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
    if force or not entry:
        return True
    if (entry.get("plot") in (None, "", "No plot available")) or \
       (entry.get("title") in (None, "", "N/A")):
        return True
    return False
 
def robust_lookup(title: str, year: str | None, retries: int, sleep_secs: float) -> dict | None:
    for attempt in range(retries + 1):
        info = get_movie_info(title, year=year)
        if info:
            return info
        time.sleep(sleep_secs + attempt * 0.6)
    return None
 
def main():
    parser = argparse.ArgumentParser(description="Prebuild OMDb/Jikan metadata cache for posters.")
    parser.add_argument("--sleep",   type=float, default=1.0, help="Seconds between API calls (default: 1.0)")
    parser.add_argument("--retries", type=int,   default=2,   help="Retries per title on failure (default: 2)")
    parser.add_argument("--force",   action="store_true",     help="Force refresh even if entry exists")
    parser.add_argument("--limit",   type=int,   default=0,   help="Limit posters to process (0 = all)")
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
    print(f"Options: sleep={args.sleep}s, retries={args.retries}, force={args.force}, limit={args.limit or 'ALL'}\n")
 
    for idx, p in enumerate(posters, 1):
        title_guess, year = parse_filename(p.stem)
        key = norm_key(title_guess, year)
 
        existing = cache.get(key)
        if existing and not needs_update(existing, args.force):
            skipped += 1
            if idx % 25 == 0:
                print(f"  … {idx}/{total} processed")
            continue
 
        year_hint = f" ({year})" if year else ""
        print(f"[{idx}/{total}] {title_guess}{year_hint}")
 
        info = robust_lookup(title_guess, year, retries=args.retries, sleep_secs=args.sleep)
 
        if info:
            entry = {
                "title":  info.get("title") or title_guess,
                "year":   info.get("year") or year or "N/A",
                "rating": info.get("rating") or "N/A",
                "plot":   info.get("plot") or "No plot available",
                "source": info.get("source") or "unknown",
            }
            print(f"  ✅ {entry['title']} ({entry['year']}) [{entry['source']}] ⭐ {entry['rating']}")
            if existing:
                updated += 1
            else:
                added += 1
            cache[key] = entry
        else:
            print(f"  ❌ No match found")
            failed += 1
            cache[key] = {
                "title": title_guess, "year": year or "N/A",
                "rating": "N/A", "plot": "No plot available", "source": "none"
            }
 
        save_cache(cache)
        time.sleep(args.sleep)
 
    print("\n----- SUMMARY -----")
    print(f"Total:    {total}")
    print(f"Added:    {added}")
    print(f"Updated:  {updated}")
    print(f"Skipped:  {skipped}")
    print(f"Failed:   {failed}")
    print("-------------------")
 
if __name__ == "__main__":
    main()