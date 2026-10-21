"""
Grid thumbnails: small .webp copies of each poster in posters/thumbs/.

Thumbs are created lazily the first time /thumbs/<file> is requested (and
eagerly on upload/rename). A thumb is regenerated whenever the source poster
is newer than it.

Each thumb's dominant colour (used for hover glow and the theater backdrop
tint) is cached in posters/thumbs/colors.json.

CLI:  python thumbs.py          # pre-build every missing/stale thumb + colour
      python thumbs.py --force  # rebuild all
"""
import os
import json
import colorsys
import threading

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
POSTERS_DIR = os.path.join(BASE_DIR, "posters")
THUMBS_DIR  = os.path.join(POSTERS_DIR, "thumbs")

THUMB_WIDTH   = 400
THUMB_QUALITY = 80
COLORS_PATH   = os.path.join(THUMBS_DIR, "colors.json")

# One lock per filename so concurrent requests don't encode the same thumb twice
_locks      = {}
_locks_lock = threading.Lock()


def _lock_for(filename: str) -> threading.Lock:
    with _locks_lock:
        return _locks.setdefault(filename, threading.Lock())


# ── Dominant colours (posters/thumbs/colors.json) ────────────────────────────

_colors_lock = threading.Lock()
_save_timer  = None

def _load_colors():
    try:
        with open(COLORS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

_colors = _load_colors()


def _save_colors_now():
    global _save_timer
    with _colors_lock:
        _save_timer = None
        data = dict(_colors)
    try:
        os.makedirs(THUMBS_DIR, exist_ok=True)
        tmp = COLORS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=0, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, COLORS_PATH)
    except OSError as e:
        print(f"[COLORS WRITE ERROR] {e}")


def _schedule_save(delay: float = 2.0):
    """Coalesce bursts of updates (e.g. 50 thumbs on first page load) into one write."""
    global _save_timer
    with _colors_lock:
        if _save_timer is None:
            _save_timer = threading.Timer(delay, _save_colors_now)
            _save_timer.daemon = True
            _save_timer.start()


def _dominant_color(img) -> str:
    """
    Pick a representative, glow-friendly colour: quantize a tiny copy, favour
    frequent *and* saturated swatches over near-black/near-white ones, then
    clamp lightness so it reads as a glow on a dark background.
    """
    from PIL import Image
    small = img.convert("RGB").resize((48, 72))
    q     = small.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    pal   = q.getpalette() or []
    best, best_score = (128, 128, 128), -1.0
    for count, idx in q.getcolors() or []:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        _, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        weight  = 0.15 if (l < 0.1 or l > 0.92) else 1.0
        score   = count * (0.25 + s) * weight
        if score > best_score:
            best, best_score = (r, g, b), score
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in best))
    l = min(max(l, 0.45), 0.62)
    if s > 0.15:
        s = max(s, 0.55)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def get_color(filename: str):
    return _colors.get(os.path.basename(filename or ""))


def all_colors() -> dict:
    with _colors_lock:
        return dict(_colors)


def compute_color(filename: str):
    """Colour for `filename`, computing it from the thumb if not cached yet."""
    name = os.path.basename(filename or "")
    if name in _colors:
        return _colors[name]
    path = ensure_thumb(name)          # also stores the colour when it builds a thumb
    if name in _colors or not path:
        return _colors.get(name)
    try:
        from PIL import Image
        with Image.open(path) as img:
            color = _dominant_color(img)
    except Exception as e:
        print(f"[COLOR ERROR] {name}: {e}")
        return None
    with _colors_lock:
        _colors[name] = color
    _schedule_save()
    return color


def _paths(filename: str):
    """Return (source_path, thumb_path) or (None, None) if filename is unsafe."""
    filename = os.path.basename(filename or "")
    if not filename.lower().endswith(".webp"):
        return None, None
    src = os.path.join(POSTERS_DIR, filename)
    dst = os.path.join(THUMBS_DIR, filename)
    return src, dst


def ensure_thumb(filename: str, force: bool = False):
    """Create the thumb for `filename` if missing/stale. Returns thumb path or None."""
    src, dst = _paths(filename)
    if not src or not os.path.isfile(src):
        return None

    def fresh():
        return (not force and os.path.isfile(dst)
                and os.path.getmtime(dst) >= os.path.getmtime(src))

    if fresh():
        return dst

    with _lock_for(os.path.basename(src)):
        if fresh():
            return dst
        try:
            from PIL import Image
        except ImportError:
            return None
        os.makedirs(THUMBS_DIR, exist_ok=True)
        tmp = dst + f".{threading.get_ident()}.tmp"
        try:
            with Image.open(src) as img:
                img = img.convert("RGBA" if img.mode in ("P", "LA", "RGBA") else "RGB")
                if img.width > THUMB_WIDTH:
                    h = round(img.height * THUMB_WIDTH / img.width)
                    img = img.resize((THUMB_WIDTH, h), Image.LANCZOS)
                img.save(tmp, "WEBP", quality=THUMB_QUALITY, method=4)
                color = _dominant_color(img)
            with _colors_lock:
                _colors[os.path.basename(src)] = color
            _schedule_save()
            try:
                os.replace(tmp, dst)
            except OSError:
                # Windows: target may be open by a concurrent reader — keep the existing one
                if not os.path.isfile(dst):
                    raise
        except Exception as e:
            print(f"[THUMB ERROR] {filename}: {e}")
            return dst if os.path.isfile(dst) else None
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    return dst


def remove_thumb(filename: str):
    with _colors_lock:
        removed = _colors.pop(os.path.basename(filename or ""), None)
    if removed:
        _schedule_save()
    _, dst = _paths(filename)
    if dst and os.path.isfile(dst):
        try:
            os.remove(dst)
        except OSError as e:
            print(f"[THUMB REMOVE ERROR] {filename}: {e}")


def rename_thumb(old_filename: str, new_filename: str):
    """Drop the old thumb and build one for the new name."""
    remove_thumb(old_filename)
    ensure_thumb(new_filename)


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    names = sorted(f for f in os.listdir(POSTERS_DIR) if f.lower().endswith(".webp"))
    for i, name in enumerate(names, 1):
        ensure_thumb(name, force=force)
        compute_color(name)
        if i % 50 == 0 or i == len(names):
            print(f"[thumbs] {i}/{len(names)}")
    _save_colors_now()
