import os, json, time, re, threading
from flask import Blueprint, send_from_directory, render_template, request, jsonify
from data import get_movie_info, parse_filename, norm_key, cache as data_cache

main_bp = Blueprint("main", __name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
POSTERS_DIR = os.path.join(BASE_DIR, "posters")
CACHE_PATH   = os.path.join(BASE_DIR, "omdb_cache.json")
WATCHED_PATH = os.path.join(BASE_DIR, "watched.json")
RATINGS_PATH = os.path.join(BASE_DIR, "personal_ratings.json")

ITEMS_PER_PAGE       = 50
BACKFILL_PER_REQUEST  = 8
COLLECTIONS_PATH     = os.path.join(BASE_DIR, "collections.json")
ZOOM_PATH            = os.path.join(BASE_DIR, "poster_zoom.json")

# Regex: valid year paren — exactly 4 digits starting with 19 or 20
_YEAR_PAT    = re.compile(r'\(((?:19|20)\d{2})\)')
# Any parenthetical group (used to strip non-year parens like (2), (3))
_NONYR_PAREN = re.compile(r'\([^)]*\)')

# In-memory grid HTML cache — keyed by folder + omdb_cache.json mtimes
_GRID_CACHE = {'html': '', 'mtime_posters': -1.0, 'mtime_cache': -1.0}

# ── JSON helpers ──────────────────────────────────────────────────────────────

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

def _load_watched():
    if os.path.exists(WATCHED_PATH):
        try:
            with open(WATCHED_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Migrate legacy boolean True → "watched"
            migrated = {}
            changed = False
            for k, v in raw.items():
                if v is True:
                    migrated[k] = "watched"
                    changed = True
                elif v in ("watched", "want_to_watch"):
                    migrated[k] = v
                # else: False or unknown — drop it
            if changed:
                _save_watched(migrated)
            return migrated
        except Exception:
            return {}
    return {}

def _save_watched(data: dict):
    try:
        with open(WATCHED_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WATCHED WRITE ERROR] {e}")

def _load_ratings():
    if os.path.exists(RATINGS_PATH):
        try:
            with open(RATINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_ratings(data: dict):
    try:
        with open(RATINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[RATINGS WRITE ERROR] {e}")

# ── Security helper ───────────────────────────────────────────────────────────

def _safe_poster_path(filename: str):
    """Return absolute path only if filename stays within POSTERS_DIR."""
    filename = os.path.basename(filename)
    if not filename:
        return None
    path = os.path.abspath(os.path.join(POSTERS_DIR, filename))
    if not path.startswith(os.path.abspath(POSTERS_DIR) + os.sep):
        return None
    return path

# ── In-memory cache (populated at startup) ────────────────────────────────────

CACHE = _load_cache()

# ── Utilities ─────────────────────────────────────────────────────────────────

def _get_grid_mtimes():
    t1 = os.path.getmtime(POSTERS_DIR) if os.path.isdir(POSTERS_DIR) else 0.0
    t2 = os.path.getmtime(CACHE_PATH)  if os.path.exists(CACHE_PATH)  else 0.0
    return t1, t2

def _run_backfill(misses):
    """Background thread: fetch OMDb data for up to BACKFILL_PER_REQUEST misses."""
    updated = 0
    for poster_fn, title_guess, year in misses[:BACKFILL_PER_REQUEST]:
        info = get_movie_info(title_guess, year=year)
        if info:
            CACHE[poster_fn] = {
                "title":  info.get("title")  or title_guess,
                "year":   info.get("year")   or year or "N/A",
                "rating": info.get("rating") or "N/A",
                "plot":   info.get("plot")   or "No plot available",
                "source": info.get("source") or "unknown",
            }
            updated += 1
            time.sleep(0.2)
    if updated:
        _save_cache(CACHE)
        _GRID_CACHE['html'] = ''  # invalidate so next request regenerates with new data

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

def _lookup_cache(filename: str, title_guess: str, year):
    """Try filename key first (new system), fall back to norm_key (legacy)."""
    info = CACHE.get(filename)
    if info:
        return info
    return CACHE.get(norm_key(title_guess, year))

# Ignore tokens that data.parse_filename also drops
_IGNORE_TOKENS = {'ver', 'xlg', 'poster', 'intl', 'cover'}

def _parse_poster_filename(base_name: str):
    """
    Return (display_title, year_or_None) for a poster filename stem.

    Rules vs data.parse_filename:
    - A parenthetical is a YEAR only if it is exactly 4 digits starting with
      19 or 20.  Anything else — (2), (3), (#4), etc. — is stripped entirely.
    - Everything AFTER the first valid year parenthetical is DISCARDED so that
      variant tags ("v2", "xlg", "#4") and duplicate year suffixes never bleed
      into the display title.
    - Same ignore-word set as data.parse_filename (ver, xlg, poster, intl, cover).

    Examples
    --------
    "2 Fast 2 Furious (2)"               -> ("2 Fast 2 Furious", None)
    "28 Years Later (2025) v2 (2025)"    -> ("28 Years Later", "2025")
    "28 Years Later (2025) #4 (2025)"    -> ("28 Years Later", "2025")
    "mortal kombat 2 (2026) xlg (2026)"  -> ("mortal kombat 2", "2026")
    "no country for old men ver4 (2007)" -> ("no country for old men", "2007")
    "Alien (1979)"                       -> ("Alien", "1979")
    """
    ym   = _YEAR_PAT.search(base_name)
    year = ym.group(1) if ym else None

    # Keep only text BEFORE the first year paren — drops variant suffixes
    name = base_name[:ym.start()].rstrip() if ym else base_name

    # Strip any remaining non-year parentheticals, e.g. (2), (3)
    name = _NONYR_PAREN.sub('', name)

    # Replicate data.parse_filename cleanup
    parts   = name.replace('_', ' ').replace('-', ' ').split()
    cleaned = [w for w in parts
               if not any(w.lower().startswith(ig) for ig in _IGNORE_TOKENS)]
    title   = ' '.join(cleaned).strip()
    return title, year

# ── Collections helpers ───────────────────────────────────────────────────────

def _load_collections():
    if os.path.exists(COLLECTIONS_PATH):
        try:
            with open(COLLECTIONS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_collections(data: dict):
    try:
        with open(COLLECTIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[COLLECTIONS WRITE ERROR] {e}")

def _load_zoom():
    if os.path.exists(ZOOM_PATH):
        try:
            with open(ZOOM_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_zoom_data(data: dict):
    try:
        with open(ZOOM_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ZOOM WRITE ERROR] {e}")

# ── Grid generation ───────────────────────────────────────────────────────────

def generate_grid_items():
    t1, t2 = _get_grid_mtimes()
    if (_GRID_CACHE['html'] and
            t1 == _GRID_CACHE['mtime_posters'] and
            t2 == _GRID_CACHE['mtime_cache']):
        return _GRID_CACHE['html']

    start_time  = time.time()
    watched     = _load_watched()
    ratings     = _load_ratings()
    collections = _load_collections()
    zooms       = _load_zoom()

    poster_files = []
    if os.path.isdir(POSTERS_DIR):
        with os.scandir(POSTERS_DIR) as it:
            for e in it:
                if e.is_file() and e.name.lower().endswith(".webp"):
                    poster_files.append(e.name)
    poster_files.sort(key=str.lower)

    grid_items = []
    misses = []  # (poster_filename, title_guess, year)

    for i, poster in enumerate(poster_files):
        base_name          = os.path.splitext(poster)[0]
        # Use our stricter parser — strips (2)/(3) parens and variant suffixes
        title_guess, year  = _parse_poster_filename(base_name)

        info = _lookup_cache(poster, title_guess, year)
        if info:
            title  = info.get("title")  or title_guess
            yr     = info.get("year")   or year or "N/A"
            rating = info.get("rating") if info.get("rating") not in (None, "N/A") else "N/A"
            plot   = info.get("plot")   or "No plot available"
        else:
            title, yr, rating, plot = title_guess, year or "N/A", "N/A", "No plot available"
            misses.append((poster, title_guess, year))

        watch_status    = watched.get(poster, "")
        personal_rating = int(ratings.get(poster, 0))
        collection      = collections.get(poster, "")
        zoom            = round(float(zooms.get(poster, 1.0)), 3)
        page = i // ITEMS_PER_PAGE + 1

        item_html = (
            f'<div class="grid-item page-{page}" style="display:none;"'
            f' data-title="{html_escape(title)}" data-year="{html_escape(yr)}"'
            f' data-rating="{html_escape(rating)}" data-plot="{html_escape(plot)}"'
            f' data-filename="{html_escape(poster)}"'
            f' data-watched="{html_escape(watch_status)}"'
            f' data-personal-rating="{personal_rating}"'
            f' data-collection="{html_escape(collection)}"'
            f' data-zoom="{zoom}">'
            f'<img loading="lazy" decoding="async" fetchpriority="low"'
            f' src="/posters/{poster}"'
            f' alt="{html_escape(base_name)}"'
            f' onclick="openLightbox(this.src, this)">'
            f'</div>'
        )
        grid_items.append(item_html)

    html = "\n".join(grid_items)
    _GRID_CACHE.update({'html': html, 'mtime_posters': t1, 'mtime_cache': t2})

    # Fire backfill in a daemon thread — does not block the response
    if misses:
        threading.Thread(target=_run_backfill, args=(misses,), daemon=True).start()

    print(f"[FAST] grid in {time.time()-start_time:.2f}s ({len(misses)} queued for backfill)")
    return html

# ── Routes ────────────────────────────────────────────────────────────────────

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

    # Move cache entry: filename key preferred; also clear any legacy norm_key entry
    old_title_g, old_yr = _parse_poster_filename(os.path.splitext(old_filename)[0])
    old_norm   = norm_key(old_title_g, old_yr)
    old_entry  = CACHE.pop(old_filename, None) or CACHE.pop(old_norm, {})
    data_cache.pop(old_filename, None)
    data_cache.pop(old_norm,     None)

    new_entry = {
        "title":  safe_title,
        "year":   year or old_entry.get("year") or "N/A",
        "rating": old_entry.get("rating") or "N/A",
        "plot":   old_entry.get("plot")   or "No plot available",
        "source": old_entry.get("source") or "unknown",
    }
    CACHE[new_filename]      = new_entry
    data_cache[new_filename] = new_entry
    _save_cache(CACHE)
    _GRID_CACHE['html'] = ''

    # Migrate watched + personal-rating + collection entries to the new filename
    watched = _load_watched()
    if old_filename in watched:
        watched[new_filename] = watched.pop(old_filename)
        _save_watched(watched)
    ratings = _load_ratings()
    if old_filename in ratings:
        ratings[new_filename] = ratings.pop(old_filename)
        _save_ratings(ratings)
    colls = _load_collections()
    if old_filename in colls:
        colls[new_filename] = colls.pop(old_filename)
        _save_collections(colls)

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

    stem     = f"{safe_title} ({year})" if year else safe_title
    filename = stem + ".webp"
    save_path = _safe_poster_path(filename)
    if not save_path:
        return jsonify(error="Invalid filename"), 400

    # Deduplicate: append counter suffix if name already taken
    if os.path.exists(save_path):
        counter = 2
        while True:
            filename  = f"{stem} {counter}.webp"
            save_path = _safe_poster_path(filename)
            if save_path and not os.path.exists(save_path):
                break
            counter += 1

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

    new_entry = {
        "title":  safe_title,
        "year":   year or "N/A",
        "rating": "N/A",
        "plot":   "No plot available",
        "source": "uploaded",
    }
    CACHE[filename]      = new_entry
    data_cache[filename] = new_entry
    _save_cache(CACHE)
    _GRID_CACHE['html'] = ''

    return jsonify(filename=filename, title=safe_title, year=year or "N/A")


@main_bp.route("/delete_poster", methods=["DELETE"])
def delete_poster():
    body     = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    if not filename:
        return jsonify(error="Missing filename"), 400

    path = _safe_poster_path(filename)
    if not path or not os.path.isfile(path):
        return jsonify(error="Poster not found"), 404

    os.remove(path)
    _GRID_CACHE['html'] = ''

    # Remove from both caches (filename key + legacy norm_key)
    title_g, yr = _parse_poster_filename(os.path.splitext(filename)[0])
    old_norm = norm_key(title_g, yr)
    CACHE.pop(filename, None)
    CACHE.pop(old_norm, None)
    data_cache.pop(filename, None)
    data_cache.pop(old_norm, None)
    _save_cache(CACHE)

    # Remove watched + rating + collection state
    watched = _load_watched()
    if filename in watched:
        watched.pop(filename)
        _save_watched(watched)
    ratings = _load_ratings()
    if filename in ratings:
        ratings.pop(filename)
        _save_ratings(ratings)
    colls = _load_collections()
    if filename in colls:
        colls.pop(filename)
        _save_collections(colls)

    return jsonify(ok=True)


@main_bp.route("/toggle_watched", methods=["POST"])
def toggle_watched():
    """Card eye-button: simple toggle between '' and 'watched'."""
    body     = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    if not filename or not _safe_poster_path(filename):
        return jsonify(error="Invalid filename"), 400

    watched    = _load_watched()
    current    = watched.get(filename, "")
    new_status = "watched" if current != "watched" else ""
    if new_status:
        watched[filename] = new_status
    else:
        watched.pop(filename, None)
    _save_watched(watched)
    _GRID_CACHE['html'] = ''
    return jsonify(filename=filename, status=new_status)


@main_bp.route("/set_watched", methods=["POST"])
def set_watched():
    """Lightbox buttons: set explicit status ('watched', 'want_to_watch', or '' to clear)."""
    body     = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    status   = (body.get("status")   or "").strip()
    if not filename or not _safe_poster_path(filename):
        return jsonify(error="Invalid filename"), 400
    if status not in ("watched", "want_to_watch", ""):
        return jsonify(error="Invalid status"), 400

    watched = _load_watched()
    if status:
        watched[filename] = status
    else:
        watched.pop(filename, None)
    _save_watched(watched)
    _GRID_CACHE['html'] = ''
    return jsonify(filename=filename, status=status)


@main_bp.route("/set_rating", methods=["POST"])
def set_rating():
    body     = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    rating   = body.get("rating")
    if not filename or rating is None or not _safe_poster_path(filename):
        return jsonify(error="Missing or invalid fields"), 400
    try:
        rating = int(rating)
        if not 0 <= rating <= 5:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify(error="Rating must be 0-5"), 400

    ratings = _load_ratings()
    if rating == 0:
        ratings.pop(filename, None)
    else:
        ratings[filename] = rating
    _save_ratings(ratings)
    return jsonify(filename=filename, rating=rating)


@main_bp.route("/update_metadata", methods=["POST"])
def update_metadata():
    body      = request.get_json(silent=True) or {}
    filename  = (body.get("filename") or "").strip()
    new_title = (body.get("title")    or "").strip()
    new_year  = (body.get("year")     or "").strip()
    new_plot  = (body.get("plot")     or "").strip()

    if not filename:
        return jsonify(error="Missing filename"), 400

    path = _safe_poster_path(filename)
    if not path or not os.path.isfile(path):
        return jsonify(error="Poster not found"), 404

    title_g, yr  = _parse_poster_filename(os.path.splitext(filename)[0])
    old_norm     = norm_key(title_g, yr)
    existing     = CACHE.get(filename) or CACHE.get(old_norm) or {}

    updated = {
        "title":  new_title or existing.get("title")  or title_g,
        "year":   new_year  or existing.get("year")   or "N/A",
        "rating": existing.get("rating") or "N/A",
        "plot":   new_plot  or existing.get("plot")   or "No plot available",
        "source": existing.get("source") or "manual",
    }

    CACHE[filename]      = updated
    data_cache[filename] = updated
    # Remove stale legacy norm_key entry if it was separate
    if old_norm in CACHE and old_norm != filename:
        CACHE.pop(old_norm, None)
        data_cache.pop(old_norm, None)
    _save_cache(CACHE)
    _GRID_CACHE['html'] = ''

    return jsonify(title=updated["title"], year=updated["year"], plot=updated["plot"])


@main_bp.route("/set_collection", methods=["POST"])
def set_collection():
    body     = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    group    = (body.get("group")    or "").strip()

    if not filename or not _safe_poster_path(filename):
        return jsonify(error="Invalid filename"), 400

    collections = _load_collections()
    if group:
        collections[filename] = group
    else:
        collections.pop(filename, None)
    _save_collections(collections)
    _GRID_CACHE['html'] = ''
    return jsonify(ok=True, filename=filename, group=group)


@main_bp.route("/collection_groups")
def collection_groups():
    """Return sorted list of all known group names (from collections + omdb cache titles)."""
    colls  = _load_collections()
    groups = set(colls.values())
    for entry in CACHE.values():
        if isinstance(entry, dict):
            t = entry.get("title")
            if t:
                groups.add(t)
    return jsonify(sorted(groups, key=str.lower))


RECENT_COUNT = 12

@main_bp.route("/recently_added")
def recently_added():
    """
    Return the RECENT_COUNT most recently modified poster files.
    Reads the filesystem fresh on every call — never cached — so newly uploaded
    or manually dropped-in posters appear immediately the next time the
    'Recently Added' dropdown is opened.
    """
    entries = []
    if os.path.isdir(POSTERS_DIR):
        with os.scandir(POSTERS_DIR) as it:
            for e in it:
                if not (e.is_file() and e.name.lower().endswith(".webp")):
                    continue
                try:
                    mtime = e.stat().st_mtime
                except OSError:
                    mtime = 0.0
                title_guess, year = _parse_poster_filename(os.path.splitext(e.name)[0])
                info  = _lookup_cache(e.name, title_guess, year)
                title = (info or {}).get("title") or title_guess
                yr    = (info or {}).get("year")  or year or "N/A"
                entries.append({
                    "filename": e.name,
                    "title":    title,
                    "year":     yr,
                    "mtime":    mtime,
                })

    entries.sort(key=lambda x: x["mtime"], reverse=True)
    for r in entries:
        del r["mtime"]          # client doesn't need the raw timestamp
    return jsonify(entries[:RECENT_COUNT])


@main_bp.route("/save_zoom", methods=["POST"])
def save_zoom():
    """Save a per-poster zoom preference (0.5–2.0) to poster_zoom.json."""
    body     = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    zoom_raw = body.get("zoom")
    if not filename or not _safe_poster_path(filename):
        return jsonify(error="Invalid filename"), 400
    try:
        zoom = float(zoom_raw)
        if not 0.5 <= zoom <= 2.0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify(error="Zoom must be between 0.5 and 2.0"), 400

    zoom_data = _load_zoom()
    if abs(zoom - 1.0) < 0.005:      # close enough to default — drop the entry
        zoom_data.pop(filename, None)
    else:
        zoom_data[filename] = round(zoom, 3)
    _save_zoom_data(zoom_data)
    _GRID_CACHE['html'] = ''          # next page load will encode the new zoom in data-zoom
    return jsonify(ok=True, filename=filename, zoom=round(zoom, 3))


@main_bp.route("/cache_entries")
def cache_entries():
    """
    Return every unique (title, year) entry in omdb_cache.json, sorted alphabetically.
    Used by the Link Metadata modal to populate its full browsable list.
    """
    seen = {}  # (title_lower, year) -> entry dict
    for key, entry in CACHE.items():
        if not isinstance(entry, dict):
            continue
        title = (entry.get("title") or "").strip()
        year  = (entry.get("year")  or "").strip()
        if not title:
            continue
        dedup = (title.lower(), year)
        if dedup not in seen:
            seen[dedup] = {
                "key":    key,
                "title":  title,
                "year":   year,
                "rating": entry.get("rating") or "N/A",
                "plot":   entry.get("plot")   or "",
            }

    results = sorted(seen.values(), key=lambda x: x["title"].lower())
    print(f"[CACHE ENTRIES] {len(results)} unique entries returned")
    return jsonify(results)


@main_bp.route("/link_metadata", methods=["POST"])
def link_metadata():
    """
    Write a full metadata payload to omdb_cache.json under the poster's filename key.
    Accepts: { filename, title, year, rating, plot }
    """
    body     = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    title    = (body.get("title")    or "").strip()
    year     = (body.get("year")     or "").strip()
    rating   = (body.get("rating")   or "N/A").strip()
    plot     = (body.get("plot")     or "").strip()

    if not filename or not title:
        print(f"[LINK METADATA] Bad request — filename={filename!r}, title={title!r}")
        return jsonify(error="Missing filename or title"), 400

    if not _safe_poster_path(filename):
        print(f"[LINK METADATA] Path traversal attempt: {filename!r}")
        return jsonify(error="Invalid filename"), 400

    entry = {
        "title":  title,
        "year":   year   if year   else "N/A",
        "rating": rating if rating else "N/A",
        "plot":   plot   if plot   else "No plot available",
        "source": "linked",
    }

    print(f"[LINK METADATA] {filename!r}  <-  '{title}' ({entry['year']})  rating={entry['rating']}")

    CACHE[filename]      = entry
    data_cache[filename] = entry

    try:
        _save_cache(CACHE)
    except Exception as exc:
        print(f"[LINK METADATA ERROR] cache write failed: {exc}")
        return jsonify(error="Cache write failed"), 500

    _GRID_CACHE["html"] = ""

    return jsonify(
        ok     = True,
        title  = entry["title"],
        year   = entry["year"],
        rating = entry["rating"],
        plot   = entry["plot"],
    )
