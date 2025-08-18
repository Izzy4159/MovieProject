# routes.py
import os, json, time
from flask import Blueprint, send_from_directory, render_template
from data import get_movie_info  # keep this import if you still want to backfill misses

main_bp = Blueprint("main", __name__)

POSTERS_DIR = "posters"
ITEMS_PER_PAGE = 50
CACHE_PATH = "omdb_cache.json"

# --------------- Load cache ONCE ---------------
def _load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

CACHE = _load_cache()    # dict like { "normalized title": {...} }

def clean_title(raw_name: str) -> str:
    ignore_words = {"ver", "xlg", "poster", "final", "intl", "cover"}
    parts = raw_name.replace("_", " ").split()
    cleaned = [w for w in parts if not any(w.lower().startswith(ig) for ig in ignore_words)]
    return " ".join(cleaned).strip()

def norm_key(title: str) -> str:
    return "".join(ch.lower() for ch in title if ch.isalnum() or ch.isspace()).strip()

def generate_grid_items():
    start_time = time.time()

    # Faster dir scan on big folders
    poster_files = []
    with os.scandir(POSTERS_DIR) as it:
        for e in it:
            if e.is_file() and e.name.endswith(".webp"):
                poster_files.append(e.name)
    poster_files.sort(key=str.lower)

    grid_items = []

    for i, poster in enumerate(poster_files):
        base_name = os.path.splitext(poster)[0]
        title_guess = clean_title(base_name)
        key = norm_key(title_guess)

        info = CACHE.get(key)
        # Optional: lazy backfill misses once, but NOT on every request
        # if info is None:
        #     info = get_movie_info(title_guess)
        #     CACHE[key] = info or {
        #         "title": title_guess, "year": "N/A", "rating": "N/A", "plot": "No plot available"
        #     }
        if info:
            title = info.get("title") or title_guess
            year = info.get("year") or "N/A"
            rating = info.get("rating") if info.get("rating") not in (None, "N/A") else "N/A"
            plot = info.get("plot") or "No plot available"
        else:
            title, year, rating, plot = title_guess, "N/A", "N/A", "No plot available"

        page = i // ITEMS_PER_PAGE + 1

        # IMPORTANT: URL-encode only in the src (template string can contain special chars)
        item_html = f'''
        <div class="grid-item page-{page}" style="display:none;"
             data-title="{title}" data-year="{year}" data-rating="{rating}" data-plot="{plot}">
          <img loading="lazy" decoding="async" fetchpriority="low"
               src="/posters/{poster}"
               alt="{base_name}"
               onclick="openLightbox('/posters/{poster}', this)">
        </div>
        '''
        grid_items.append(item_html)

    html = "\n".join(grid_items)
    print(f"[FAST] grid items in {time.time()-start_time:.2f}s (no API calls)")
    return html

@main_bp.route("/")
def index():
    grid_html = generate_grid_items()
    return render_template("index.html", grid_items=grid_html)

@main_bp.route("/posters/<path:filename>")
def poster(filename):
    # Long-cache images
    return send_from_directory(POSTERS_DIR, filename, cache_timeout=60*60*24*365)
