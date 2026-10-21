"""
Grid thumbnails: small .webp copies of each poster in posters/thumbs/.

Thumbs are created lazily the first time /thumbs/<file> is requested (and
eagerly on upload/rename). A thumb is regenerated whenever the source poster
is newer than it.

CLI:  python thumbs.py          # pre-build every missing/stale thumb
      python thumbs.py --force  # rebuild all
"""
import os
import threading

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
POSTERS_DIR = os.path.join(BASE_DIR, "posters")
THUMBS_DIR  = os.path.join(POSTERS_DIR, "thumbs")

THUMB_WIDTH   = 400
THUMB_QUALITY = 80

# One lock per filename so concurrent requests don't encode the same thumb twice
_locks      = {}
_locks_lock = threading.Lock()


def _lock_for(filename: str) -> threading.Lock:
    with _locks_lock:
        return _locks.setdefault(filename, threading.Lock())


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
        if i % 50 == 0 or i == len(names):
            print(f"[thumbs] {i}/{len(names)}")
