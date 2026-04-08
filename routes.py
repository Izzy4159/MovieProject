import os, json, time, re
from flask import Blueprint, send_from_directory, render_template, request, jsonify
from data import get_movie_info, parse_filename, norm_key, cache as data_cache

main_bp = Blueprint("main", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSTERS_DIR = os.path.join(BASE_DIR, "posters")
CACHE_PATH = os.path.join(BASE_DIR, "omdb_cache.json")

ITEMS_PER_PAGE = 50
BACKFILL_PER_REQUEST = 8

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

def _safe_poster_path(filename: str):
    """Return absolute path only if filename stays within POSTERS_DIR. Returns None on traversal attempt."""
    filename = os.path.basename(filename)
    if not filename:
        return None
    path = os.path.abspath(os.path.join(POSTERS_DIR, filename))
    if not path.startswith(os.path.abspath(POSTERS_DIR) + os.sep):
        return None
    return path

CACHE = _load_cache()

def html_escape(s) -> str:
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
    misses = []  # list of (key, title, year)

    for i, poster in enumerate(poster_files):
        base_name = os.path.splitext(poster)[0]
        title_guess, year = parse_filename(base_name)
        key = norm_key(title_guess, year)

        info = CACHE.get(key)
        if info:
            title   = info.get("title") or title_guess
            yr      = info.get("year") or year or "N/A"
            rating  = info.get("rating") if info.get("rating") not in (None, "N/A") else "N/A"
            plot    = info.get("plot") or "No plot available"
        else:
            title, yr, rating, plot = title_guess, year or "N/A", "N/A", "No plot available"
            misses.append((key, title_guess, year))

        page = i // ITEMS_PER_PAGE + 1

        item_html = f'''
        <div class="grid-item page-{page}" style="display:none;"
             data-title="{html_escape(title)}" data-year="{html_escape(yr)}"
             data-rating="{html_escape(rating)}" data-plot="{html_escape(plot)}">
          <img loading="lazy" decoding="async" fetchpriority="low"
               src="/posters/{poster}"
               alt="{html_escape(base_name)}"
               onclick="openLightbox(this.src, this)">
        </div>
        '''
        grid_items.append(item_html)

    # Trickle backfill
    if misses:
        to_fetch = misses[:BACKFILL_PER_REQUEST]
        updated = 0
        for key, title_guess, year in to_fetch:
            info = get_movie_info(title_guess, year=year)
            if info:
                CACHE[key] = {
                    "title":  info.get("title") or title_guess,
                    "year":   info.get("year") or year or "N/A",
                    "rating": info.get("rating") or "N/A",
                    "plot":   info.get("plot") or "No plot available",
                    "source": info.get("source") or "unknown",
                }
                updated += 1
                time.sleep(0.2)
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
        return send_from_directory(POSTERS_DIR, filename, max_age=60*60*24*365)
    except TypeError:
        resp = send_from_directory(POSTERS_DIR, filename)
        resp.cache_control.public = True
        resp.cache_control.max_age = 60*60*24*365
        return resp

@main_bp.route("/rename", methods=["POST"])
def rename_poster():
    body         = request.get_json(silent=True) or {}
    old_filename = (body.get("old_filename") or "").strip()
    new_title    = (body.get("new_title")    or "").strip()
    year         = (body.get("year")         or "").strip()

    if not old_filename or not new_title:
        return jsonify(error="Missing fields"), 400

    old_path = _safe_poster_path(old_filename)
    if not old_path or not os.path.isfile(old_path):
        return jsonify(error="Poster not found"), 404

    safe_title = re.sub(r'[<>:"/\\|?*]', '', new_title).strip(". ")
    if not safe_title:
        return jsonify(error="Invalid title"), 400

    new_stem     = f"{safe_title} ({year})" if year else safe_title
    new_filename = new_stem + ".webp"
    new_path     = _safe_poster_path(new_filename)
    if not new_path:
        return jsonify(error="Invalid new filename"), 400

    if old_path != new_path:
        if os.path.exists(new_path):
            return jsonify(error="A poster with that name already exists"), 409
        os.rename(old_path, new_path)

    # Update both in-memory caches to stay in sync
    old_title_g, old_yr = parse_filename(os.path.splitext(old_filename)[0])
    old_key   = norm_key(old_title_g, old_yr)
    new_key   = norm_key(safe_title, year or None)
    old_entry = CACHE.pop(old_key, {})
    data_cache.pop(old_key, None)

    new_entry = {
        "title":  safe_title,
        "year":   year or old_entry.get("year") or "N/A",
        "rating": old_entry.get("rating") or "N/A",
        "plot":   old_entry.get("plot") or "No plot available",
        "source": old_entry.get("source") or "unknown",
    }
    CACHE[new_key]      = new_entry
    data_cache[new_key] = new_entry
    _save_cache(CACHE)

    return jsonify(new_filename=new_filename, new_title=safe_title)


@main_bp.route("/upload", methods=["POST"])
def upload_poster():
    file  = request.files.get("file")
    title = (request.form.get("title") or "").strip()
    year  = (request.form.get("year")  or "").strip()

    if not file or not title:
        return jsonify(error="Missing file or title"), 400

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        return jsonify(error="Unsupported file type. Use jpg, png, or webp."), 400

    safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip(". ")
    if not safe_title:
        return jsonify(error="Invalid title"), 400

    stem      = f"{safe_title} ({year})" if year else safe_title
    filename  = stem + ".webp"
    save_path = _safe_poster_path(filename)
    if not save_path:
        return jsonify(error="Invalid filename"), 400

    if os.path.exists(save_path):
        return jsonify(error="A poster with that name already exists"), 409

    if ext == ".webp":
        file.save(save_path)
    else:
        try:
            from PIL import Image
            from io import BytesIO
            with Image.open(BytesIO(file.read())) as img:
                img = img.convert("RGBA" if img.mode in ("P", "LA") else "RGB")
                img.save(save_path, "WEBP", quality=95, method=6)
        except ImportError:
            return jsonify(error="Pillow is required for jpg/png conversion. Run: pip install Pillow"), 500

    key = norm_key(safe_title, year or None)
    new_entry = {
        "title":  safe_title,
        "year":   year or "N/A",
        "rating": "N/A",
        "plot":   "No plot available",
        "source": "uploaded",
    }
    CACHE[key]      = new_entry
    data_cache[key] = new_entry
    _save_cache(CACHE)

    return jsonify(filename=filename, title=safe_title, year=year or "N/A")