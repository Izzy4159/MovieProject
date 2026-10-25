import os, json, time, re, threading
from urllib.parse import quote
from flask import Blueprint, send_from_directory, render_template, request, jsonify, url_for
import providers as P
from providers import ProviderError
from data import (lookup, resolve, display, needs_lookup, parse_poster_filename,
                  id_key, is_found, fetch_by_id, search_candidates, parse_id_input,
                  save_cache, save_overrides, poster_ids, overrides as OVERRIDES,
                  cache as data_cache)
from thumbs import (ensure_thumb, remove_thumb, rename_thumb, THUMBS_DIR,
                    get_color, compute_color, all_colors)

main_bp = Blueprint("main", __name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
POSTERS_DIR = os.path.join(BASE_DIR, "posters")
CACHE_PATH   = os.path.join(BASE_DIR, "omdb_cache.json")
OVERRIDES_PATH = os.path.join(BASE_DIR, "metadata_overrides.json")
WATCHED_PATH = os.path.join(BASE_DIR, "watched.json")
RATINGS_PATH = os.path.join(BASE_DIR, "personal_ratings.json")

ITEMS_PER_PAGE       = 50
COLLECTIONS_PATH     = os.path.join(BASE_DIR, "collections.json")
ZOOM_PATH            = os.path.join(BASE_DIR, "poster_zoom.json")
STACK_COVERS_PATH    = os.path.join(BASE_DIR, "stack_covers.json")

# In-memory grid HTML cache — keyed by folder + omdb_cache.json + overrides mtimes
_GRID_CACHE = {'html': '', 'mtime_posters': -1.0, 'mtime_cache': -1.0}

# ── JSON helpers ──────────────────────────────────────────────────────────────

def _save_cache(_cache=None):
    save_cache()

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

# The one shared metadata dict (data.cache) — every writer saves through data.save_cache
CACHE = data_cache

# ── Utilities ─────────────────────────────────────────────────────────────────

def _get_grid_mtimes():
    t1 = os.path.getmtime(POSTERS_DIR) if os.path.isdir(POSTERS_DIR) else 0.0
    t2 = os.path.getmtime(CACHE_PATH)  if os.path.exists(CACHE_PATH)  else 0.0
    t3 = os.path.getmtime(OVERRIDES_PATH) if os.path.exists(OVERRIDES_PATH) else 0.0
    return t1, max(t2, t3)

_BACKFILL = {"running": False}

def _run_backfill(jobs):
    """Background thread: one lookup per movie (cache key), however many variant posters share it."""
    try:
        done = 0
        for kind, key, title, year, hints in jobs:
            if kind == "id":
                src, pid = hints
                try:
                    entry = fetch_by_id(src, pid)
                except (ProviderError, ValueError):
                    entry = None
            else:
                entry = lookup(title, year, id_hints=hints, cache_key=key)
            if entry is not None:
                done += 1
                _GRID_CACHE['html'] = ''   # next page load shows the new metadata
        if jobs:
            print(f"[BACKFILL] {len(jobs)} lookups finished ({done} answered)")
    finally:
        _BACKFILL["running"] = False

_COLOR_BACKFILL = {"running": False}

def _run_color_backfill(names):
    """Background thread: compute dominant colours for posters that don't have one yet."""
    try:
        for name in names:
            compute_color(name)
        _GRID_CACHE['html'] = ''   # next page load embeds the new colours
        print(f"[COLORS] computed {len(names)} poster colours")
    finally:
        _COLOR_BACKFILL["running"] = False

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

_parse_poster_filename = parse_poster_filename


def _poster_files() -> list[str]:
    names = []
    if os.path.isdir(POSTERS_DIR):
        with os.scandir(POSTERS_DIR) as it:
            names = [e.name for e in it if e.is_file() and e.name.lower().endswith(".webp")]
    return sorted(names, key=str.lower)


def _poster_meta(filename: str, res: dict | None = None) -> dict:
    """Metadata fields for one poster file, as rendered into the grid's data-* attributes."""
    res = res or resolve(filename)
    d   = display(res)
    r   = d["rating"]
    return {
        "title":       d["title"],
        "year":        d["year"],
        "rating":      str(r["value"]) if r else "N/A",
        "ratingScale": str(r["scale"]) if r else "",
        "ratingSrc":   r["source"] if r else "",
        "ratingNorm":  str(P.rating_norm(r)) if r else "",
        "plot":        d["plot"],
        "metaSrc":     d["source"] if res.get("entry") else "",
        "metaConf":    f"{d['confidence']:.2f}" if d["confidence"] is not None else "",
    }


_META_ATTRS = (("title", "data-title"), ("year", "data-year"), ("rating", "data-rating"),
               ("ratingScale", "data-rating-scale"), ("ratingSrc", "data-rating-src"),
               ("ratingNorm", "data-rating-norm"), ("plot", "data-plot"),
               ("metaSrc", "data-meta-src"), ("metaConf", "data-meta-conf"))

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

def _load_stack_covers():
    """{stack key: filename} — chosen cover poster for each stacked movie."""
    if os.path.exists(STACK_COVERS_PATH):
        try:
            with open(STACK_COVERS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_stack_covers(data: dict):
    try:
        with open(STACK_COVERS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[STACK COVERS WRITE ERROR] {e}")

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

    poster_files = _poster_files()

    grid_items = []
    jobs = {}    # one lookup per movie key (or per overridden id), however many variants
    color_misses = []

    for i, poster in enumerate(poster_files):
        base_name = os.path.splitext(poster)[0]
        res  = resolve(poster)
        meta = _poster_meta(poster, res)
        if needs_lookup(res):
            ov = res["override"]
            if res["origin"] == "override-missing":
                k = id_key(ov["source"], ov["id"])
                jobs.setdefault(k, ("id", k, None, None, (ov["source"], ov["id"])))
            else:
                job  = jobs.setdefault(res["key"], ("title", res["key"], res["title_guess"],
                                                     res["year_guess"], []))
                pid = poster_ids.get(poster) or {}
                if pid.get("source") and pid.get("id") and (pid["source"], pid["id"]) not in job[4]:
                    job[4].append((pid["source"], str(pid["id"])))

        watch_status    = watched.get(poster, "")
        personal_rating = int(ratings.get(poster, 0))
        collection      = collections.get(poster, "")
        zoom            = round(float(zooms.get(poster, 1.0)), 3)
        color           = get_color(poster)
        if not color:
            color_misses.append(poster)
        page = i // ITEMS_PER_PAGE + 1

        style = "display:none;" + (f"--pc:{color};" if color else "")
        meta_attrs = "".join(f' {attr}="{html_escape(meta[k])}"' for k, attr in _META_ATTRS)
        item_html = (
            f'<div class="grid-item page-{page}" style="{style}"'
            f'{meta_attrs}'
            f' data-filename="{html_escape(poster)}"'
            f' data-watched="{html_escape(watch_status)}"'
            f' data-personal-rating="{personal_rating}"'
            f' data-collection="{html_escape(collection)}"'
            f' data-zoom="{zoom}"'
            f' data-color="{color or ""}">'
            f'<img loading="lazy" decoding="async" fetchpriority="low"'
            f' width="400" height="600"'
            f' src="/thumbs/{quote(poster)}"'
            f' alt="{html_escape(base_name)}"'
            f' onclick="openLightbox(this.src, this)">'
            f'</div>'
        )
        grid_items.append(item_html)

    html = "\n".join(grid_items)
    _GRID_CACHE.update({'html': html, 'mtime_posters': t1, 'mtime_cache': t2})

    # Fire backfill in a daemon thread — does not block the response. Every
    # movie is queried at most once per session (data.lookup), so the queue drains.
    jobs = list(jobs.values())
    if jobs and not _BACKFILL["running"]:
        _BACKFILL["running"] = True
        threading.Thread(target=_run_backfill, args=(jobs,), daemon=True).start()
    if color_misses and not _COLOR_BACKFILL["running"]:
        _COLOR_BACKFILL["running"] = True
        threading.Thread(target=_run_color_backfill, args=(color_misses,), daemon=True).start()

    print(f"[FAST] grid in {time.time()-start_time:.2f}s ({len(jobs)} movies queued for lookup)")
    return html

# ── Routes ────────────────────────────────────────────────────────────────────

@main_bp.route("/")
def index():
    grid_html = generate_grid_items()
    return render_template("index.html", grid_items=grid_html, stack_covers=_load_stack_covers())

@main_bp.route("/posters/<path:filename>")
def poster(filename):
    try:
        return send_from_directory(POSTERS_DIR, filename, max_age=60*60*24*365)
    except TypeError:
        resp = send_from_directory(POSTERS_DIR, filename)
        resp.cache_control.public = True
        resp.cache_control.max_age = 60*60*24*365
        return resp

@main_bp.route("/thumbs/<path:filename>")
def thumb(filename):
    """Grid thumbnail — generated on first request, then served from posters/thumbs/."""
    path = ensure_thumb(filename)
    if not path:
        return jsonify(error="Poster not found"), 404
    return send_from_directory(THUMBS_DIR, os.path.basename(path), max_age=60*60*24*7)

@main_bp.route("/poster_colors")
def poster_colors():
    """{filename: "#rrggbb"} for every poster whose dominant colour is known."""
    return jsonify(all_colors())

# ── PWA ───────────────────────────────────────────────────────────────────────

STATIC_DIR = os.path.join(BASE_DIR, "static")

@main_bp.app_template_global()
def static_v(filename):
    """url_for('static') with an mtime query string so browsers/SW pick up edits."""
    try:
        v = int(os.path.getmtime(os.path.join(STATIC_DIR, filename)))
    except OSError:
        v = 0
    return url_for("static", filename=filename, v=v)

@main_bp.route("/sw.js")
def service_worker():
    # Served from the root so its scope covers the whole app
    resp = send_from_directory(STATIC_DIR, "sw.js", max_age=0)
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Cache-Control"] = "no-cache"
    return resp

@main_bp.route("/manifest.webmanifest")
def manifest():
    resp = send_from_directory(STATIC_DIR, "manifest.webmanifest", max_age=60*60)
    resp.headers["Content-Type"] = "application/manifest+json"
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
        rename_thumb(old_filename, new_filename)

    # Per-file entry for the new name, carrying over the metadata this poster showed.
    # The shared per-movie entry stays: other variant posters still use it.
    old_res   = resolve(old_filename)
    old_entry = dict(old_res["entry"] or old_res["placeholder"] or {})
    CACHE.pop(old_filename, None)
    old_entry.pop("not_found", None)
    old_entry.update({
        "title":  safe_title,
        "year":   year or old_entry.get("year") or "N/A",
        "source": old_entry.get("source") or "unknown",
    })
    CACHE[new_filename] = old_entry
    _save_cache(CACHE)
    _GRID_CACHE['html'] = ''

    if old_filename in OVERRIDES:
        OVERRIDES[new_filename] = OVERRIDES.pop(old_filename)
        save_overrides()

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
    covers = _load_stack_covers()
    if old_filename in covers.values():
        _save_stack_covers({k: (new_filename if v == old_filename else v) for k, v in covers.items()})

    # Migrate poster_ids.json entry (if present) — keep same id/source value
    try:
        pid_path = os.path.join(BASE_DIR, "poster_ids.json")
        if os.path.exists(pid_path):
            try:
                with open(pid_path, "r", encoding="utf-8") as f:
                    pid_map = json.load(f)
            except Exception:
                pid_map = {}
            if old_filename in pid_map:
                pid_map[new_filename] = pid_map.pop(old_filename)
                try:
                    with open(pid_path, "w", encoding="utf-8") as f:
                        json.dump(pid_map, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"[POSTER_IDS WRITE ERROR] {e}")
    except Exception:
        pass

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

    ensure_thumb(filename)

    new_entry = {
        "title":  safe_title,
        "year":   year or "N/A",
        "rating": None,
        "plot":   None,
        "source": "uploaded",
    }
    CACHE[filename] = new_entry
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
    remove_thumb(filename)
    _GRID_CACHE['html'] = ''

    # Drop the per-file entry and override. The shared per-movie entry stays:
    # other variant posters (or a re-added poster) still use it.
    if CACHE.pop(filename, None) is not None:
        _save_cache(CACHE)
    if OVERRIDES.pop(filename, None) is not None:
        save_overrides()

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
    covers = _load_stack_covers()
    if filename in covers.values():
        _save_stack_covers({k: v for k, v in covers.items() if v != filename})

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

    # Edits become this file's own entry; the shared per-movie entry is left alone
    res     = resolve(filename)
    shown   = display(res)
    updated = dict(res["entry"] or {})
    updated.update({
        "title":  new_title or shown["title"],
        "year":   new_year  or shown["year"] or "N/A",
        "rating": updated.get("rating"),
        "plot":   new_plot  or updated.get("plot"),
        "source": updated.get("source") or "manual",
    })
    if not res["entry"]:
        updated["source"] = "manual"

    CACHE[filename] = updated
    _save_cache(CACHE)
    _GRID_CACHE['html'] = ''

    return jsonify(title=updated["title"], year=updated["year"],
                   plot=updated["plot"] or "No plot available")


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


@main_bp.route("/set_stack_cover", methods=["POST"])
def set_stack_cover():
    """Choose which poster represents a stacked movie. Body: {key, filename}."""
    body     = request.get_json(silent=True) or {}
    key      = (body.get("key")      or "").strip()
    filename = (body.get("filename") or "").strip()
    path     = _safe_poster_path(filename) if filename else None
    if not key or len(key) > 300 or not path or not os.path.isfile(path):
        return jsonify(error="Invalid stack key or filename"), 400

    covers = _load_stack_covers()
    covers[key] = filename
    _save_stack_covers(covers)
    return jsonify(ok=True, key=key, filename=filename)


@main_bp.route("/collection_groups")
def collection_groups():
    """Return sorted list of all known group names (from collections + omdb cache titles)."""
    colls  = _load_collections()
    groups = set(colls.values())
    for entry in CACHE.values():
        if is_found(entry):
            groups.add(entry["title"])
    return jsonify(sorted(groups, key=str.lower))


# ── Stats page ────────────────────────────────────────────────────────────────

def _compute_stats():
    watched     = _load_watched()
    ratings     = _load_ratings()
    collections = _load_collections()

    posters = []
    if os.path.isdir(POSTERS_DIR):
        with os.scandir(POSTERS_DIR) as it:
            posters = [e.name for e in it if e.is_file() and e.name.lower().endswith(".webp")]

    decades, unique = {}, set()
    for fn in posters:
        d     = display(resolve(fn))
        title = (d["title"] or "").strip().lower()
        m     = re.search(r"(1[89]\d\d|20\d\d)", str(d["year"] or ""))
        yr    = int(m.group(1)) if m else None
        unique.add((title, yr))
        key = f"{yr // 10 * 10}s" if yr else "Unknown"
        decades[key] = decades.get(key, 0) + 1

    total      = len(posters)
    names      = set(posters)
    n_watched  = sum(1 for fn, s in watched.items() if s == "watched" and fn in names)
    n_want     = sum(1 for fn, s in watched.items() if s == "want_to_watch" and fn in names)
    rated      = [int(v) for fn, v in ratings.items() if fn in names and int(v) > 0]
    stars      = {i: rated.count(i) for i in range(1, 6)}

    sizes = {}
    for fn, g in collections.items():
        if fn in names and g:
            sizes[g] = sizes.get(g, 0) + 1
    largest = sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:10]

    decade_rows = sorted(((k, v) for k, v in decades.items() if k != "Unknown"), key=lambda kv: kv[0])
    if "Unknown" in decades:
        decade_rows.append(("Unknown", decades["Unknown"]))

    return {
        "total":        total,
        "unique":       len(unique),
        "watched":      n_watched,
        "watched_pct":  round(100 * n_watched / total, 1) if total else 0,
        "want":         n_want,
        "rated":        len(rated),
        "avg_rating":   round(sum(rated) / len(rated), 2) if rated else None,
        "stars":        stars,
        "decades":      decade_rows,
        "decade_max":   max([v for _, v in decade_rows] or [1]),
        "collections":  largest,
        "coll_max":     max([v for _, v in largest] or [1]),
        "n_collections": len(sizes),
    }

@main_bp.route("/stats")
def stats():
    return render_template("stats.html", s=_compute_stats())


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
                d = display(resolve(e.name))
                entries.append({
                    "filename": e.name,
                    "title":    d["title"],
                    "year":     d["year"],
                    "mtime":    mtime,
                })

    entries.sort(key=lambda x: x["mtime"], reverse=True)
    for r in entries:
        del r["mtime"]          # client doesn't need the raw timestamp
    try:
        limit = int(request.args.get("limit", RECENT_COUNT))
    except ValueError:
        limit = RECENT_COUNT
    # limit=0 → every poster, newest first (Big Picture's "Recently added" sort)
    return jsonify(entries if limit == 0 else entries[:max(1, min(limit, 100))])


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
        if not is_found(entry):
            continue
        title = str(entry.get("title") or "").strip()
        year  = str(entry.get("year")  or "").strip()
        dedup = (title.lower(), year)
        if dedup not in seen:
            seen[dedup] = {
                "key":    key,
                "title":  title,
                "year":   year,
                "rating": P.rating_label(entry.get("rating")) or "N/A",
                "plot":   entry.get("plot")   or "",
            }

    results = sorted(seen.values(), key=lambda x: x["title"].lower())
    print(f"[CACHE ENTRIES] {len(results)} unique entries returned")
    return jsonify(results)


@main_bp.route("/link_metadata", methods=["POST"])
def link_metadata():
    """
    Copy an existing cache entry onto this poster (per-file "linked" entry).
    Accepts: { filename, key } — or the older { filename, title, year, plot }.
    """
    body     = request.get_json(silent=True) or {}
    filename = (body.get("filename") or "").strip()
    key      = (body.get("key")      or "").strip()

    if not filename or not _safe_poster_path(filename):
        print(f"[LINK METADATA] Bad request — filename={filename!r}")
        return jsonify(error="Missing or invalid filename"), 400

    src = CACHE.get(key) if key else None
    if is_found(src):
        entry = dict(src)
    else:
        title = (body.get("title") or "").strip()
        if not title:
            return jsonify(error="Missing title"), 400
        entry = {"title": title, "year": (body.get("year") or "").strip() or "N/A",
                 "rating": None, "plot": (body.get("plot") or "").strip() or None}
    entry["linked_from"] = entry.get("source")
    entry["source"]      = "linked"

    print(f"[LINK METADATA] {filename!r}  <-  '{entry['title']}' ({entry.get('year')})")
    CACHE[filename] = entry
    _save_cache(CACHE)
    _GRID_CACHE["html"] = ""
    return jsonify(ok=True, poster=_poster_meta(filename))


# ── Needs Fix panel ───────────────────────────────────────────────────────────

_REASON_ORDER = ("not_found", "low_confidence", "missing", "mismatch")


def _cluster_posters(infos):
    """
    Group posters that stack together visually: same display title (numbers,
    punctuation and a leading article normalised), split by release year.
    Posters without a year join the title's only year group.
    """
    by_title = {}
    for info in infos:
        by_title.setdefault(P.match_form(info["d"]["title"]) or info["fn"].lower(), []).append(info)
    clusters = []
    for members in by_title.values():
        years, loose = {}, []
        for m in members:
            y, _ = P.year_range(m["d"]["year"])
            if y is None:
                loose.append(m)
                continue
            near = next((k for k in years if abs(k - y) <= 1), None)
            years.setdefault(near if near is not None else y, []).append(m)
        groups = list(years.values())
        if len(groups) == 1:
            groups[0].extend(loose)
        elif loose:
            groups.append(loose)
        clusters.extend(groups)
    return clusters


def _compute_needs_fix():
    infos = []
    for fn in _poster_files():
        res = resolve(fn)
        infos.append({"fn": fn, "res": res, "d": display(res)})

    rows, ignored = [], []
    for ci, members in enumerate(_cluster_posters(infos)):
        files = [m["fn"] for m in members]
        # Mismatch: auto-matched variants that resolved to different titles (or to
        # different IDs at the same provider), or some matched and some not
        auto    = [m for m in members if not m["res"]["override"]]
        matched = [m for m in auto if m["res"]["entry"]]
        works   = {(P.match_form(m["res"]["entry"].get("title")), P.year_range(m["res"]["entry"].get("year"))[0])
                   for m in matched}
        per_src = {}
        for m in matched:
            if m["d"]["id"]:
                per_src.setdefault(m["d"]["source"], set()).add(m["d"]["id"])
        mixed = len(auto) > 1 and (len(works) > 1 or any(len(v) > 1 for v in per_src.values())
                                   or 0 < len(matched) < len(auto))

        for m in members:
            res, d, ov = m["res"], m["d"], m["res"]["override"]
            if ov.get("ignore"):
                ignored.append({"filename": m["fn"], "title": d["title"], "stack": files})
                continue
            if ov:                        # manual fix: never flagged again
                continue
            reasons = []
            e = res["entry"]
            if not e:
                reasons.append("not_found")
            else:
                if d["confidence"] is not None and d["confidence"] < P.LOW_CONF:
                    reasons.append("low_confidence")
                missing = [f for f, bad in (("year", d["year"] in (None, "", "N/A")),
                                            ("rating", d["rating"] is None),
                                            ("plot", d["plot"] in (None, "", "No plot available")))
                           if bad]
                if missing:
                    reasons.append("missing")
            if mixed:
                reasons.append("mismatch")
            if not reasons:
                continue
            neg = res["negative"] or {}
            rows.append({
                "filename": m["fn"],
                "title":    d["title"],
                "query":    res["title_guess"],
                "year":     res["year_guess"] or "",
                "reasons":  reasons,
                "missing":  missing if e else [],
                "pending":  not e and needs_lookup(res),
                "match": ({"title": e.get("title"), "year": d["year"], "source": d["source"],
                           "id": d["id"], "confidence": d["confidence"]} if e else None),
                "closest":  neg.get("best_guess"),
                "stack":    files,
                "stack_id": ci,
            })
    rows.sort(key=lambda r: (r["title"].lower(), r["filename"].lower()))
    ignored.sort(key=lambda r: r["title"].lower())
    return {"count": len(rows), "items": rows, "ignored": ignored}


@main_bp.route("/needs_fix")
def needs_fix():
    return jsonify(_compute_needs_fix())


@main_bp.route("/fix_search")
def fix_search():
    q        = (request.args.get("q") or "").strip()
    provider = (request.args.get("provider") or "auto").strip().lower()
    year     = (request.args.get("year") or "").strip() or None
    if not q:
        return jsonify(results=[], errors=[])
    exact = parse_id_input(q, provider)
    try:
        if exact:
            e = fetch_by_id(*exact)
            if not e:
                return jsonify(results=[], errors=[f"No {P.PROVIDER_LABELS.get(exact[0], exact[0])} record for {exact[1]}"])
            e = dict(e, score=1.0, rating_label=P.rating_label(e.get("rating")))
            return jsonify(results=[e], errors=[], exact=True)
        return jsonify(**search_candidates(q, provider, year))
    except ProviderError as err:
        return jsonify(results=[], errors=[str(err)]), 502
    except ValueError as err:
        return jsonify(results=[], errors=[str(err)]), 400


def _valid_targets(files) -> list[str]:
    out = []
    for f in files or []:
        f = str(f or "").strip()
        p = _safe_poster_path(f) if f else None
        if p and os.path.isfile(p) and f not in out:
            out.append(f)
    return out


@main_bp.route("/fix_match", methods=["POST"])
def fix_match():
    """Link posters to an exact provider record. Body: {files, source, id, display_title?}."""
    body   = request.get_json(silent=True) or {}
    files  = _valid_targets(body.get("files"))
    source = (body.get("source") or "").strip().lower()
    pid    = str(body.get("id") or "").strip()
    dtitle = (body.get("display_title") or "").strip()
    if not files or source not in P.BY_ID or not pid:
        return jsonify(error="Missing files, source or id"), 400
    try:
        entry = fetch_by_id(source, pid)
    except ProviderError as err:
        return jsonify(error=str(err)), 502
    if not entry:
        return jsonify(error=f"No {P.PROVIDER_LABELS.get(source, source)} record {pid}"), 404

    for f in files:
        ov = {k: v for k, v in (OVERRIDES.get(f) or {}).items() if k == "display_title"}
        ov.update({"source": source, "id": str(entry["id"])})
        if dtitle:
            ov["display_title"] = dtitle
        OVERRIDES[f] = ov
    save_overrides()
    _GRID_CACHE["html"] = ""
    print(f"[FIX] {len(files)} poster(s) → {entry['title']} ({entry.get('year')}) "
          f"[{P.PROVIDER_LABELS.get(source)} {entry['id']}]")
    nf = _compute_needs_fix()
    return jsonify(ok=True, posters={f: _poster_meta(f) for f in files}, count=nf["count"])


@main_bp.route("/fix_ignore", methods=["POST"])
def fix_ignore():
    """Mark posters as intentionally unmatched (or undo). Body: {files, ignore}."""
    body   = request.get_json(silent=True) or {}
    files  = _valid_targets(body.get("files"))
    ignore = bool(body.get("ignore", True))
    if not files:
        return jsonify(error="Missing files"), 400
    for f in files:
        ov = dict(OVERRIDES.get(f) or {})
        if ignore:
            ov = {k: v for k, v in ov.items() if k == "display_title"}
            ov["ignore"] = True
        else:
            ov.pop("ignore", None)
        if ov:
            OVERRIDES[f] = ov
        else:
            OVERRIDES.pop(f, None)
    save_overrides()
    _GRID_CACHE["html"] = ""
    nf = _compute_needs_fix()
    return jsonify(ok=True, posters={f: _poster_meta(f) for f in files}, count=nf["count"])
