#!/usr/bin/env python3
"""
Prebuild the metadata cache for every poster: one lookup per movie
(OMDb → AniList → Kitsu → Jikan), shared by all of its variant posters.

Titles cached as not-found are skipped for 7 days; --force re-queries them
(and refreshes existing matches). Manual fixes in metadata_overrides.json are
never touched.
"""
import argparse
from pathlib import Path

from data import lookup, resolve, needs_lookup, poster_ids, is_found

POSTERS_DIR = Path(__file__).resolve().parent / "posters"


def main():
    parser = argparse.ArgumentParser(description="Prebuild the metadata cache for posters.")
    parser.add_argument("--force", action="store_true",
                        help="Re-query every movie, including cached matches and not-found titles")
    parser.add_argument("--limit", type=int, default=0, help="Limit movies to process (0 = all)")
    args = parser.parse_args()

    if not POSTERS_DIR.exists():
        print(f"posters/ not found at: {POSTERS_DIR}")
        return

    posters = sorted((p.name for p in POSTERS_DIR.iterdir()
                      if p.is_file() and p.suffix.lower() == ".webp"), key=str.lower)

    # One job per movie key; ID hints from any of its variant posters
    jobs = {}
    for fn in posters:
        res = resolve(fn)
        if res["ignored"] or res["override"].get("id"):
            continue
        if not args.force and not needs_lookup(res):
            continue
        job = jobs.setdefault(res["key"], {"title": res["title_guess"], "year": res["year_guess"], "hints": []})
        pid = poster_ids.get(fn) or {}
        if pid.get("source") and pid.get("id"):
            job["hints"].append((pid["source"], str(pid["id"])))

    items = list(jobs.items())
    if args.limit > 0:
        items = items[:args.limit]
    print(f"{len(posters)} posters, {len(items)} movies to look up (force={args.force})\n")

    found = missing = unknown = 0
    for i, (key, job) in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {job['title']}" + (f" ({job['year']})" if job["year"] else ""))
        entry = lookup(job["title"], job["year"], force=args.force,
                       id_hints=job["hints"], cache_key=key)
        if entry is None:
            unknown += 1
        elif is_found(entry):
            found += 1
        else:
            missing += 1

    print("\n----- SUMMARY -----")
    print(f"Found:      {found}")
    print(f"Not found:  {missing}  (cached; retried after 7 days or with --force)")
    print(f"No answer:  {unknown}  (provider unreachable; retried next run)")
    print("-------------------")


if __name__ == "__main__":
    main()
