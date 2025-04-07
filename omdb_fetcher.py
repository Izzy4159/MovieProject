import requests
import json
from pathlib import Path

OMDB_API_KEY = "444ceefe"
CACHE_FILE = Path("omdb_cache.json")

# Load cache on startup
if CACHE_FILE.exists():
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
    cache = {}

def get_movie_info(title):
    title_key = title.lower()

    if title_key in cache:
        return cache[title_key]

    print(f"[OMDb] Fetching: {title}")  # Debug print
    url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={title}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True":
                result = {
                    "title": data.get("Title"),
                    "year": data.get("Year"),
                    "rating": data.get("imdbRating"),
                    "plot": data.get("Plot")
                }
                cache[title_key] = result
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cache, f, indent=2)
                return result
    except Exception as e:
        print(f"[OMDb ERROR] {e}")

    return None
