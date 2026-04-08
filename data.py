import requests
import json
import re
from pathlib import Path
import urllib.parse
import difflib
import time

# 🔒 Hardcoded for your local use
OMDB_API_KEY = "444ceefe"
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

# --------- Title / Year Parsing ---------

# Matches (2024), (1999), etc. anywhere in the filename
_YEAR_RE = re.compile(r'\((\d{4})\)')

# Words to strip from filenames that are never part of a real title
_IGNORE_WORDS = {"ver", "xlg", "poster", "intl", "cover"}

def parse_filename(raw_name: str) -> tuple[str, str | None]:
    """
    Given a filename stem (no extension), return (clean_title, year_or_None).

    Examples
    --------
    "dune part two (2024)"        -> ("dune part two", "2024")
    "the thing (1982) final"      -> ("the thing", "1982")
    "inception"                   -> ("inception", None)
    "avatar the way of water xlg" -> ("avatar the way of water", None)
    """
    # Extract year first so it doesn't end up in the title
    year_match = _YEAR_RE.search(raw_name)
    year = year_match.group(1) if year_match else None

    # Remove the (YYYY) token and any trailing/leading junk
    name = _YEAR_RE.sub("", raw_name)

    # Replace separators, split, drop ignore words
    parts = name.replace("_", " ").replace("-", " ").split()
    cleaned = [w for w in parts if not any(w.lower().startswith(ig) for ig in _IGNORE_WORDS)]

    title = " ".join(cleaned).strip()
    return title, year


def norm_key(title: str, year: str | None = None) -> str:
    """Stable cache key: lowercase alphanum + spaces, optionally with year."""
    base = "".join(ch.lower() for ch in title if ch.isalnum() or ch.isspace()).strip()
    return f"{base} {year}" if year else base


# --------- Helpers ---------

def _persist_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[CACHE WRITE ERROR] {e}")


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(
        None,
        (a or "").lower().strip(),
        (b or "").lower().strip()
    ).ratio()


def _best_omdb_match(search_results: list, original_title: str, year: str | None) -> str | None:
    """
    Pick the best imdbID from OMDb search results.
    If a year hint is available, prefer results whose Year matches.
    Falls back to fuzzy title match.
    """
    if not search_results:
        return None

    # If we have a year, try an exact year+title match first
    if year:
        for item in search_results:
            item_year = (item.get("Year") or "")[:4]
            if item_year == year and _similar(original_title, item.get("Title", "")) > 0.5:
                return item.get("imdbID")

    # Fall back to fuzzy title match
    titles = [item.get("Title", "") for item in search_results]
    matches = difflib.get_close_matches(original_title, titles, n=1, cutoff=0.5)
    if matches:
        for item in search_results:
            if item.get("Title") == matches[0]:
                return item.get("imdbID")

    return None


# --------- Jikan (Anime) Fallback ---------

def get_anime_info(title: str, max_retries: int = 2, base_sleep: float = 0.7):
    headers = {
        "User-Agent": "MovieProject/1.0 (contact: local)",
        "Accept": "application/json",
    }
    encoded_title = urllib.parse.quote(title)
    url = f"https://api.jikan.moe/v4/anime?q={encoded_title}&limit=3&sfw"

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code in (429, 500, 502, 503, 504):
                sleep_for = base_sleep + attempt * 0.8
                print(f"[Jikan] HTTP {resp.status_code}, retrying in {sleep_for:.1f}s …")
                time.sleep(sleep_for)
                continue
            if resp.status_code != 200:
                print(f"[Jikan] HTTP {resp.status_code} for '{title}'")
                return None

            results = resp.json().get("data") or []
            if not results:
                return None

            best, best_score = None, 0.0
            for anime in results:
                score = _similar(title, anime.get("title") or "")
                if score > best_score:
                    best, best_score = anime, score

            if not best or best_score < 0.55:
                return None

            year = best.get("year")
            if not year:
                aired = best.get("aired") or {}
                from_date = aired.get("from")
                year = from_date[:4] if isinstance(from_date, str) and len(from_date) >= 4 else "N/A"

            return {
                "title": best.get("title") or title,
                "year": year,
                "rating": best.get("score") or "N/A",
                "plot": best.get("synopsis") or None,
                "source": "jikan",
            }

        except Exception as e:
            print(f"[Jikan ERROR] {e}")
            if attempt < max_retries:
                time.sleep(base_sleep + attempt * 0.8)
            continue

    return None


# --------- OMDb Primary Lookup ---------

def get_movie_info(title: str, year: str | None = None, max_retries: int = 1, base_sleep: float = 0.6):
    """
    Return dict with title/year/rating/plot/source, or None on total failure.

    Parameters
    ----------
    title : str   Clean title string (no year, no junk words)
    year  : str   4-digit year extracted from filename, or None

    Lookup order
    ------------
    1. Cache hit
    2. OMDb exact title match  (+ year hint if available)
    3. OMDb search + fuzzy/year pick -> ID lookup
    4. Jikan anime fallback
    """
    key = norm_key(title, year)
    if key in cache:
        return cache[key]

    encoded_title = urllib.parse.quote(title)

    for attempt in range(max_retries + 1):
        try:
            # --- Step 1: OMDb exact title (+ optional year) ---
            url_exact = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={encoded_title}&plot=short"
            if year:
                url_exact += f"&y={year}"

            resp = requests.get(url_exact, timeout=8)
            if resp.status_code != 200:
                raise RuntimeError(f"OMDb HTTP {resp.status_code}")

            data = resp.json()
            if data.get("Response") == "True":
                result = {
                    "title": data.get("Title"),
                    "year": data.get("Year"),
                    "rating": data.get("imdbRating"),
                    "plot": data.get("Plot"),
                    "source": "omdb",
                }
                cache[key] = result
                _persist_cache()
                return result

            # --- Step 2: OMDb search + smart pick ---
            url_search = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={encoded_title}"
            if year:
                url_search += f"&y={year}"

            s_resp = requests.get(url_search, timeout=8)
            if s_resp.status_code == 200:
                s_data = s_resp.json()
                if s_data.get("Response") == "True":
                    imdb_id = _best_omdb_match(s_data.get("Search"), title, year)
                    if imdb_id:
                        id_resp = requests.get(
                            f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={imdb_id}&plot=short",
                            timeout=8
                        )
                        if id_resp.status_code == 200:
                            id_data = id_resp.json()
                            if id_data.get("Response") == "True":
                                result = {
                                    "title": id_data.get("Title"),
                                    "year": id_data.get("Year"),
                                    "rating": id_data.get("imdbRating"),
                                    "plot": id_data.get("Plot"),
                                    "source": "omdb",
                                }
                                cache[key] = result
                                _persist_cache()
                                return result

            # If year search found nothing, retry without year constraint once
            if year and attempt == max_retries:
                print(f"[OMDb] Retrying '{title}' without year hint …")
                return get_movie_info(title, year=None, max_retries=0)

            if attempt < max_retries:
                time.sleep(base_sleep + attempt * 0.6)

        except Exception as e:
            print(f"[OMDb ERROR] {e}")
            if attempt < max_retries:
                time.sleep(base_sleep + attempt * 0.6)

    # --- Step 3: Jikan anime fallback ---
    anime_info = get_anime_info(title)
    if anime_info:
        print(f"[Jikan] Found: {title}")
        cache[key] = anime_info
        _persist_cache()
        return anime_info

    return None