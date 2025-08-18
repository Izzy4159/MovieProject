import os, json, time
from flask import Blueprint, send_from_directory, render_template
from data import get_movie_info

main_bp = Blueprint("main", __name__)

# Absolute paths so Flask is consistent anywhere you run it
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSTERS_DIR = os.path.join(BASE_DIR, "posters")
CACHE_PATH = os.path.join(BASE_DIR, "omdb_cache.json")

ITEMS_PER_PAGE = 50
BACKFILL_PER_REQUEST = 8  # fetch a few missing infos per request (keeps UI fast)

def _load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_cache(cache: dict):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[CACHE WRITE ERROR] {e}")

CACHE = _load_cache()

def clean_title(raw_name: str) -> str:
    ignore_words = {"ver", "xlg", "poster", "final", "intl", "cover"}
    parts = raw_name.replace("_", " ").replace("-", " ").split()
    cleaned = [w for w in parts if not any(w.lower().startswith(ig) for ig in ignore_words)]
    return " ".join(cleaned).strip()

def norm_key(title: str) -> str:
    return "".join(ch.lower() for ch in title if ch.isalnum() or ch.isspace()).strip()

def html_escape(s: str) -> str:
    """Minimal escape for embedding text in HTML attributes."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

def generate_grid_items():
    start_time = time.time()

    poster_files = []
    if os.path.isdir(POSTERS_DIR):
        with os.scandir(POSTERS_DIR) as it:
            for e in it:
                if e.is_file() and e.name.lower().endswith(".webp"):
                    poster_files.append(e.name)
    poster_files.sort(key=str.lower)

    grid_items = []
    misses = []

    for i, poster in enumerate(poster_files):
        base_name = os.path.splitext(poster)[0]
        title_guess = clean_title(base_name)
        key = norm_key(title_guess)

        info = CACHE.get(key)
        if info:
            title = info.get("title") or title_guess
            year = info.get("year") or "N/A"
            rating = info.get("rating") if info.get("rating") not in (None, "N/A") else "N/A"
            plot = info.get("plot") or "No plot available"
        else:
            title, year, rating, plot = title_guess, "N/A", "N/A", "No plot available"
            misses.append((key, title_guess))

        page = i // ITEMS_PER_PAGE + 1

        # Escape for safe embedding in data-* attributes
        title_a = html_escape(title)
        year_a = html_escape(year)
        rating_a = html_escape(rating)
        plot_a = html_escape(plot)

        item_html = f'''
        <div class="grid-item page-{page}" style="display:none;"
             data-title="{title_a}" data-year="{year_a}" data-rating="{rating_a}" data-plot="{plot_a}">
          <img loading="lazy" decoding="async" fetchpriority="low"
               src="/posters/{poster}"
               alt="{html_escape(base_name)}"
               onclick="openLightbox('/posters/{poster}', this)">
        </div>
        '''
        grid_items.append(item_html)

    # Trickle backfill so new posters gradually get details
    if misses:
        to_fetch = misses[:BACKFILL_PER_REQUEST]
        updated = 0
        for key, title_guess in to_fetch:
            info = get_movie_info(title_guess)
            if info:
                CACHE[key] = {
                    "title": info.get("title") or title_guess,
                    "year": info.get("year") or "N/A",
                    "rating": info.get("rating") or "N/A",
                    "plot": info.get("plot") or "No plot available",
                    "source": info.get("source") or "unknown",
                }
                updated += 1
                time.sleep(0.2)  # be gentle with the API
        if updated:
            _save_cache(CACHE)

    html = "\n".join(grid_items)
    print(f"[FAST] grid in {time.time()-start_time:.2f}s (backfilled {min(len(misses), BACKFILL_PER_REQUEST)})")
    return html

@main_bp.route("/")
def index():
    grid_html = generate_grid_items()
    return render_template("index.html", grid_items=grid_html)

@main_bp.route("/posters/<path:filename>")
def poster(filename):
    try:
        # Newer Flask/Werkzeug signature
        return send_from_directory(POSTERS_DIR, filename, max_age=60*60*24*365)
    except TypeError:
        # Older fallback
        resp = send_from_directory(POSTERS_DIR, filename)
        resp.cache_control.public = True
        resp.cache_control.max_age = 60*60*24*365
        return resp
