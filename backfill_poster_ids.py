"""
Scan posters/ and produce poster_ids.json mapping filename -> {source,id}.
This script is read-only for existing caches and writes only poster_ids.json.
"""
import os
import json
import urllib.parse
import time
from pathlib import Path

import requests

# Import helper parsing from routes to keep filename parsing consistent
from routes import POSTERS_DIR, BASE_DIR, _parse_poster_filename
import data

OMDB_API_KEY = getattr(data, 'OMDB_API_KEY', None)

OUT_PATH = Path(BASE_DIR) / "poster_ids.json"


def _find_omdb_id(title: str, year: str | None):
    if not OMDB_API_KEY:
        return None
    encoded = urllib.parse.quote(title)
    # exact
    try:
        url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={encoded}&plot=short"
        if year:
            url += f"&y={year}"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            d = r.json()
            if d.get('Response') == 'True' and d.get('imdbID'):
                return d.get('imdbID')
    except Exception:
        pass

    # search
    try:
        url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={encoded}"
        if year:
            url += f"&y={year}"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            sd = r.json()
            if sd.get('Response') == 'True':
                imdb_id = data._best_omdb_match(sd.get('Search'), title, year)
                if imdb_id:
                    return imdb_id
    except Exception:
        pass

    return None


def _find_jikan_id(title: str):
    encoded_title = urllib.parse.quote(title)
    url = f"https://api.jikan.moe/v4/anime?q={encoded_title}&limit=3&sfw"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return None
        results = resp.json().get('data') or []
        if not results:
            return None
        best, best_score = None, 0.0
        for anime in results:
            score = data._similar(title, anime.get('title') or "")
            if score > best_score:
                best, best_score = anime, score
        if not best or best_score < 0.55:
            return None
        return best.get('mal_id')
    except Exception:
        return None


def main():
    mapping = {}
    if not os.path.isdir(POSTERS_DIR):
        print(f"Posters dir not found: {POSTERS_DIR}")
        return

    files = [f for f in os.listdir(POSTERS_DIR) if f.lower().endswith('.webp')]
    files.sort(key=str.lower)
    for fn in files:
        stem = os.path.splitext(fn)[0]
        title_guess, year = _parse_poster_filename(stem)
        print(f"Checking: {fn} -> '{title_guess}' ({year})")

        # Try OMDb first
        omdb_id = _find_omdb_id(title_guess, year)
        if omdb_id:
            mapping[fn] = {"source": "omdb", "id": omdb_id}
            print(f"  -> OMDb id {omdb_id}")
            # Persist progress after each found id
            try:
                with open(OUT_PATH, 'w', encoding='utf-8') as f:
                    json.dump(mapping, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Failed writing progress: {e}")
            time.sleep(0.2)
            continue

        # Try Jikan
        jikan_id = _find_jikan_id(title_guess)
        if jikan_id:
            mapping[fn] = {"source": "jikan", "id": jikan_id}
            print(f"  -> Jikan id {jikan_id}")
            try:
                with open(OUT_PATH, 'w', encoding='utf-8') as f:
                    json.dump(mapping, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Failed writing progress: {e}")
            time.sleep(0.2)
            continue

        print("  -> no id found")

    # Write poster_ids.json
    try:
        with open(OUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        print(f"Wrote {OUT_PATH} with {len(mapping)} entries")
    except Exception as e:
        print(f"Failed to write {OUT_PATH}: {e}")


if __name__ == '__main__':
    main()
