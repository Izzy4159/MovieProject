import requests
import json
from pathlib import Path
import os
import urllib.parse
import difflib

OMDB_API_KEY = os.getenv("OMDB_API_KEY", "missing-key")
CACHE_FILE = Path("omdb_cache.json")

# Load cache on startup
if CACHE_FILE.exists():
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
    cache = {}

def get_best_omdb_match(search_results, original_title):
    titles = [item.get("Title", "") for item in search_results]
    matches = difflib.get_close_matches(original_title, titles, n=1, cutoff=0.5)
    if matches:
        for item in search_results:
            if item["Title"] == matches[0]:
                return item["imdbID"]
    return None

def get_anime_info(title):
    try:
        encoded_title = urllib.parse.quote(title)
        jikan_url = f"https://api.jikan.moe/v4/anime?q={encoded_title}&limit=1"
        response = requests.get(jikan_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            results = data.get("data")
            if results:
                anime = results[0]
                return {
                    "title": anime.get("title"),
                    "year": anime.get("year") or anime.get("aired", {}).get("from", "")[:4],
                    "rating": anime.get("score"),
                    "plot": anime.get("synopsis"),
                    "source": "jikan"
                }
    except Exception as e:
        print(f"[Jikan ERROR] {e}")
    return None

def get_movie_info(title):
    title_key = title.lower()

    if title_key in cache:
        return cache[title_key]

    print(f"[OMDb] Fetching: {title}")
    encoded_title = urllib.parse.quote(title)

    # Try exact match
    url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&t={encoded_title}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True":
                result = {
                    "title": data.get("Title"),
                    "year": data.get("Year"),
                    "rating": data.get("imdbRating"),
                    "plot": data.get("Plot"),
                    "source": "omdb"
                }
                cache[title_key] = result
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cache, f, indent=2)
                return result

        # Fallback to search with fuzzy match
        search_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&s={encoded_title}"
        search_response = requests.get(search_url, timeout=5)
        if search_response.status_code == 200:
            search_data = search_response.json()
            if search_data.get("Response") == "True" and "Search" in search_data:
                imdb_id = get_best_omdb_match(search_data["Search"], title)
                if imdb_id:
                    id_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={imdb_id}"
                    id_response = requests.get(id_url, timeout=5)
                    if id_response.status_code == 200:
                        id_data = id_response.json()
                        if id_data.get("Response") == "True":
                            result = {
                                "title": id_data.get("Title"),
                                "year": id_data.get("Year"),
                                "rating": id_data.get("imdbRating"),
                                "plot": id_data.get("Plot"),
                                "source": "omdb"
                            }
                            cache[title_key] = result
                            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                                json.dump(cache, f, indent=2)
                            return result

    except Exception as e:
        print(f"[OMDb ERROR] {e}")

    # Fallback to anime API
    anime_info = get_anime_info(title)
    if anime_info:
        print(f"[Jikan] Found: {title}")
        cache[title_key] = anime_info
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        return anime_info

    return None
