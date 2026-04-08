#!/usr/bin/env python3
"""
rename_and_cache.py

1. Cleans up all .webp filenames in the posters/ folder
   - Strips junk words (xlg, ver, poster, final, intl, cover)
   - Preserves (YYYY) year if already in the filename
   - Renames files in-place

2. Looks up each title on OMDb (+Jikan fallback) to get the real year
   - Adds (YYYY) to the filename if not already there
   - Updates omdb_cache.json

Run:
    python rename_and_cache.py
    python rename_and_cache.py --sleep 1.2   # slower if you hit rate limits
    python rename_and_cache.py --limit 10    # test on first 10 files
"""

import os
import re
import json
import time
import argparse
import urllib.parse
import difflib
import requests
from pathlib import Path

# ------------------------------------------------------------------ #
#  CONFIG
# ------------------------------------------------------------------ #
POSTERS_DIR = Path("posters")
CACHE_FILE  = Path("omdb_cache.json")
OMDB_API_KEY = "ab30acaf"

IGNORE_WORDS = {"ver", "xlg", "poster", "final", "intl", "cover"}
_YEAR_RE     = re.compile(r'\((\d{4})\)')

# ------------------------------------------------------------------ #
#  TITLE / YEAR HELPERS  (same logic as data.py)
# ------------------------------------------------------------------ #

def parse_stem(stem: str) -> tuple[str, str | None]:
    """Return (clean_title, year_or_None) from a filename stem."""
    year_match = _YEAR_RE.search(stem)
    year = year_match.group(1) if year_match else None
    name = _YEAR_RE.sub("", stem)
    parts = name.replace("_", " ").replace("-", " ").split()
    cleaned = [w for w in parts if not any(w.lower().startswith(ig) for ig in IGNORE_WORDS)]
    title = " ".join(cleaned).strip()
    return title, year

def norm_key(title: str, year: str | None = None) -> str:
    base = "".join(ch.lower() for ch in title if ch.isalnum() or ch.isspace()).strip()
    return f"{base} {year}" if year else base

def safe_filename(title: str, year: str | None) -> str:
    """Build a clean filename stem like 'the thing (1982)'."""
    # Remove characters that are unsafe in Windows filenames
    safe = re.sub(r'[<>:"/\\|?*]', '', title)
    # Strip any (YYYY) already embedded in the title string (OMDb sometimes returns it)
    safe = _YEAR_RE.sub("", safe).strip(". ")
    if year:
        return f"{safe} ({year})"
    return safe

# ------------------------------------------------------------------ #
#  OMDb LOOKUP
# ------------------------------------------------------------------ #

def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(
        None, (a or "").lower().strip(), (b or "").lower().strip()
    ).ratio()

def _best_omdb_id(search_results: list, title: str, year: str | None) -> str | None:
    if not search_results:
        return None
    if year:
        for item in search_results:
            if (item.get("Year") or "")[:4] == year and _similar(title, item.get("Title", "")) > 0.4:
                return item.get("imdbID")
    titles = [i.get("Title", "") for i in search_results]
    # Try difflib first
    matches = difflib.get_close_matches(title, titles, n=1, cutoff=0.4)
    if matches:
        for item in search_results:
            if item.get("Title") == matches[0]:
                return item.get("imdbID")
    # Final fallback: just pick highest similarity score
    best_id, best_score = None, 0.0
    for item in search_results:
        s = _similar(title, item.get("Title", ""))
        if s > best_score:
            best_score, best_id = s, item.get("imdbID")
    return best_id if best_score > 0.35 else None

def omdb_lookup(title: str, year: str | None) -> dict | None:
    enc = urllib.parse.quote(title)

    # 1. Exact title match
    url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={enc}&plot=short"
    if year:
        url += f"&y={year}"
    try:
        d = requests.get(url, timeout=8).json()
        if d.get("Response") == "True":
            return {"title": d["Title"], "year": d.get("Year"), "rating": d.get("imdbRating"), "plot": d.get("Plot"), "source": "omdb"}
    except Exception:
        pass

    # 2. Search + fuzzy pick
    surl = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={enc}"
    if year:
        surl += f"&y={year}"
    try:
        sd = requests.get(surl, timeout=8).json()
        if sd.get("Response") == "True":
            imdb_id = _best_omdb_id(sd.get("Search"), title, year)
            if imdb_id:
                id_d = requests.get(
                    f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={imdb_id}&plot=short",
                    timeout=8
                ).json()
                if id_d.get("Response") == "True":
                    return {"title": id_d["Title"], "year": id_d.get("Year"), "rating": id_d.get("imdbRating"), "plot": id_d.get("Plot"), "source": "omdb"}
    except Exception:
        pass

    # 3. Retry without year if we had one
    if year:
        return omdb_lookup(title, year=None)

    return None

# ------------------------------------------------------------------ #
#  JIKAN (ANIME) FALLBACK
# ------------------------------------------------------------------ #

def jikan_lookup(title: str) -> dict | None:
    enc = urllib.parse.quote(title)
    headers = {"User-Agent": "MovieProject/1.0", "Accept": "application/json"}
    try:
        resp = requests.get(f"https://api.jikan.moe/v4/anime?q={enc}&limit=3&sfw", headers=headers, timeout=8)
        if resp.status_code != 200:
            return None
        results = resp.json().get("data") or []
        best, best_score = None, 0.0
        for a in results:
            s = _similar(title, a.get("title") or "")
            if s > best_score:
                best, best_score = a, s
        if not best or best_score < 0.55:
            return None
        year = best.get("year")
        if not year:
            aired = best.get("aired") or {}
            fd = aired.get("from")
            year = fd[:4] if isinstance(fd, str) and len(fd) >= 4 else None
        return {"title": best.get("title") or title, "year": year, "rating": best.get("score"), "plot": best.get("synopsis"), "source": "jikan"}
    except Exception:
        return None

# ------------------------------------------------------------------ #
#  CACHE
# ------------------------------------------------------------------ #

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

# ------------------------------------------------------------------ #
#  MAIN
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="Rename posters and rebuild OMDb cache.")
    parser.add_argument("--sleep",   type=float, default=0.8, help="Seconds between API calls (default: 0.8)")
    parser.add_argument("--limit",   type=int,   default=0,   help="Only process first N files (0 = all)")
    args = parser.parse_args()

    if not POSTERS_DIR.exists():
        print(f"❌  posters/ folder not found at {POSTERS_DIR.resolve()}")
        return

    posters = sorted(
        [p for p in POSTERS_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".webp"],
        key=lambda p: p.name.lower()
    )
    if args.limit:
        posters = posters[:args.limit]

    cache = load_cache()
    total = len(posters)
    renamed = already_ok = cached_only = failed = 0

    print(f"Found {total} .webp files in {POSTERS_DIR.resolve()}\n")

    for idx, p in enumerate(posters, 1):
        title_guess, year_from_file = parse_stem(p.stem)

        if not title_guess:
            print(f"[{idx}/{total}] ⚠️  Could not parse title from: {p.name}")
            failed += 1
            continue

        year_hint = f" ({year_from_file})" if year_from_file else ""
        print(f"[{idx}/{total}] {title_guess}{year_hint}")

        # --- API lookup ---
        info = omdb_lookup(title_guess, year_from_file) or jikan_lookup(title_guess)

        if info:
            real_title  = info.get("title") or title_guess
            # year can be int (Jikan) or string like "2015" or "2013–2015"
            raw_year    = info.get("year")
            real_year   = str(raw_year)[:4] if raw_year else year_from_file
            source      = info.get("source", "?")
            print(f"  ✅  {real_title} ({real_year}) [{source}] ⭐ {info.get('rating') or 'N/A'}")
        else:
            # Couldn't get data — still clean the filename, keep file-year if any
            real_title = title_guess
            real_year  = year_from_file
            print(f"  ❌  No API match — using cleaned filename")
            failed += 1

        # --- Build new filename ---
        new_stem = safe_filename(real_title, real_year)
        new_name = new_stem + ".webp"
        new_path = POSTERS_DIR / new_name

        if new_path == p:
            already_ok += 1
        elif new_path.exists():
            # Avoid overwriting a different file
            print(f"  ⚠️  Target already exists, skipping rename: {new_name}")
            already_ok += 1
        else:
            p.rename(new_path)
            print(f"  📝  {p.name}  →  {new_name}")
            renamed += 1
            p = new_path  # update reference for cache key

        # --- Update cache ---
        if info:
            key = norm_key(real_title, real_year)
            cache[key] = {
                "title":  real_title,
                "year":   real_year or "N/A",
                "rating": str(info.get("rating") or "N/A"),
                "plot":   info.get("plot") or "No plot available",
                "source": info.get("source") or "unknown",
            }
            save_cache(cache)
            cached_only += 1

        time.sleep(args.sleep)

    print("\n========= SUMMARY =========")
    print(f"Total files : {total}")
    print(f"Renamed     : {renamed}")
    print(f"Already OK  : {already_ok}")
    print(f"Cached      : {cached_only}")
    print(f"Failed      : {failed}")
    print("============================")
    print("\nDone! You can now run main.py — the cache is ready.")

if __name__ == "__main__":
    main()