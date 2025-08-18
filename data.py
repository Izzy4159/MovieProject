import requests
import json
from pathlib import Path
import urllib.parse
import difflib
import time

# 🔒 Hardcoded for your local use
OMDB_API_KEY = "444ceefe"  # <-- your key here
CACHE_FILE = Path("omdb_cache.json")

# Load cache on startup
if CACHE_FILE.exists():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
else:
    cache = {}

# --------- Helpers ---------
def _persist_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[CACHE WRITE ERROR] {e}")

def _similar(a: str, b: str) -> float:
    """Return a similarity score between 0 and 1."""
    return difflib.SequenceMatcher(None, (a or "").lower().strip(), (b or "").lower().strip()).ratio()

def get_best_omdb_match(search_results, original_title):
    titles = [item.get("Title", "") for item in search_results or []]
    matches = difflib.get_close_matches(original_title, titles, n=1, cutoff=0.5)
    if matches:
        for item in search_results:
            if item.get("Title") == matches[0]:
                return item.get("imdbID")
    return None

# --------- Jikan (Anime) Fallback (hardened) ---------
def get_anime_info(title, max_retries: int = 2, base_sleep: float = 0.7):
    """
    Robust Jikan lookup:
      - Adds UA header (Jikan requirement)
      - Handles 429 / non-200 with retry
      - Safely parses 'year' even if 'aired' or 'from' is missing/None
      - Requires a reasonable similarity between requested title and returned anime title
    """
    headers = {
        "User-Agent": "MovieProject/1.0 (contact: local)",
        "Accept": "application/json",
    }
    encoded_title = urllib.parse.quote(title)

    url = f"https://api.jikan.moe/v4/anime?q={encoded_title}&limit=3&sfw"  # small set, safe-for-work

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            # Retry on rate limiting or server errors
            if resp.status_code in (429, 500, 502, 503, 504):
                sleep_for = base_sleep + attempt * 0.8
                print(f"[Jikan] HTTP {resp.status_code}, retrying in {sleep_for:.1f}s …")
                time.sleep(sleep_for)
                continue

            if resp.status_code != 200:
                # Non-retriable error
                print(f"[Jikan] HTTP {resp.status_code} for '{title}'")
                return None

            data = resp.json()
            results = data.get("data") or []
            if not results:
                return None

            # Pick the best match by similarity to requested title
            best = None
            best_score = 0.0
            for anime in results:
                candidate_title = anime.get("title") or ""
                score = _similar(title, candidate_title)
                if score > best_score:
                    best = anime
                    best_score = score

            # Only accept if reasonably similar (avoid wild mismatches)
            if not best or best_score < 0.55:
                return None

            # Parse year safely
            year = best.get("year")
            if not year:
                aired = best.get("aired") or {}
                from_date = aired.get("from")
                if isinstance(from_date, str) and len(from_date) >= 4:
                    year = from_date[:4]
                else:
                    year = "N/A"

            info = {
                "title": best.get("title") or title,
                "year": year,
                "rating": best.get("score") or "N/A",
                "plot": best.get("synopsis") or None,
                "source": "jikan",
            }
            return info

        except Exception as e:
            # Catch-all for JSON/connection issues; back off and retry
            print(f"[Jikan ERROR] {e}")
            if attempt < max_retries:
                sleep_for = base_sleep + attempt * 0.8
                time.sleep(sleep_for)
                continue
            return None

    return None

# --------- OMDb Primary Lookup (with fuzzy fallback) ---------
def get_movie_info(title, max_retries: int = 1, base_sleep: float = 0.6):
    """
    Return dict with title/year/rating/plot/source or None on failure.
    Primary: OMDb exact title; fallback: OMDb search + ID; final fallback: Jikan (anime).
    Caches results to omdb_cache.json.
    """
    title_key = title.lower().strip()
    if title_key in cache:
        return cache[title_key]

    encoded_title = urllib.parse.quote(title)

    # Try OMDb exact match with light retry
    for attempt in range(max_retries + 1):
        try:
            url_exact = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={encoded_title}"
            response = requests.get(url_exact, timeout=8)
            if response.status_code != 200:
                raise RuntimeError(f"OMDb HTTP {response.status_code}")

            data = response.json()
            if data.get("Response") == "True":
                result = {
                    "title": data.get("Title"),
                    "year": data.get("Year"),
                    "rating": data.get("imdbRating"),
                    "plot": data.get("Plot"),
                    "source": "omdb",
                }
                cache[title_key] = result
                _persist_cache()
                return result

            # No exact match; try search+fuzzy
            url_search = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={encoded_title}"
            search_response = requests.get(url_search, timeout=8)
            if search_response.status_code == 200:
                search_data = search_response.json()
                if search_data.get("Response") == "True" and "Search" in search_data:
                    imdb_id = get_best_omdb_match(search_data.get("Search"), title)
                    if imdb_id:
                        id_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={imdb_id}&plot=short"
                        id_response = requests.get(id_url, timeout=8)
                        if id_response.status_code == 200:
                            id_data = id_response.json()
                            if id_data.get("Response") == "True":
                                result = {
                                    "title": id_data.get("Title"),
                                    "year": id_data.get("Year"),
                                    "rating": id_data.get("imdbRating"),
                                    "plot": id_data.get("Plot"),
                                    "source": "omdb",
                                }
                                cache[title_key] = result
                                _persist_cache()
                                return result

            # if we got here, attempt failed; maybe back off and retry exact once more
            if attempt < max_retries:
                sleep_for = base_sleep + attempt * 0.6
                time.sleep(sleep_for)
                continue

        except Exception as e:
            print(f"[OMDb ERROR] {e}")
            if attempt < max_retries:
                sleep_for = base_sleep + attempt * 0.6
                time.sleep(sleep_for)
                continue

    # Final fallback: Jikan (anime)
    anime_info = get_anime_info(title)
    if anime_info:
        print(f"[Jikan] Found: {title}")
        cache[title_key] = anime_info
        _persist_cache()
        return anime_info

    # Total miss
    return None
