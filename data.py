"""
Poster filename parsing, the metadata cache (omdb_cache.json), manual
overrides (metadata_overrides.json) and the lookup orchestration.

Cache keys
----------
"<norm title> <year>"      shared by every variant poster of one movie
"<poster filename>.webp"   per-file entries: uploads, renames, edits, linked
"id:<source>:<id>"         entries fetched for a manual override

Entries are either a match
    {title, year, rating: {value, scale, source} | None, plot, source, id,
     type, confidence, checked}
or a negative-cache record (not retried for NEGATIVE_TTL unless forced)
    {not_found: true, checked, title, year, best_guess}
"""
import difflib
import json
import os
import re
import threading
import time
from pathlib import Path

import providers as P
from providers import ProviderError

# Absolute paths: main.py may be launched from another working directory
_BASE_DIR = Path(__file__).resolve().parent

# OMDb key comes from the environment (or a local, git-ignored .env file)
try:
    from dotenv import load_dotenv
    load_dotenv(_BASE_DIR / ".env")
except ImportError:
    pass
OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "").strip()
if not OMDB_API_KEY:
    print("[WARN] OMDB_API_KEY is not set: OMDb lookups will fail (see .env.example)")

CACHE_FILE            = _BASE_DIR / "omdb_cache.json"
OVERRIDES_FILE        = _BASE_DIR / "metadata_overrides.json"
POSTER_IDS_FILE       = _BASE_DIR / "poster_ids.json"
MANUAL_OVERRIDES_FILE = _BASE_DIR / "manual_overrides.json"   # legacy, read-only

NEGATIVE_TTL = 7 * 24 * 3600

# Cached from the filename rather than a real lookup
PLACEHOLDER_SOURCES = ("uploaded", "unknown", "none")
# Chosen by hand: always trusted
MANUAL_SOURCES = ("linked", "manual")

_io_lock = threading.RLock()


def _load_json(path: Path, default):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[DATA] could not read {path.name}: {e}")
    return default


def _write_json(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


cache: dict      = _load_json(CACHE_FILE, {})
poster_ids: dict = _load_json(POSTER_IDS_FILE, {})
overrides: dict  = _load_json(OVERRIDES_FILE, {})
for _fn, _ov in _load_json(MANUAL_OVERRIDES_FILE, {}).items():
    if isinstance(_ov, dict) and _ov.get("source") and _ov.get("id"):
        overrides.setdefault(_fn, {"source": _ov["source"], "id": str(_ov["id"])})


def save_cache():
    with _io_lock:
        try:
            _write_json(CACHE_FILE, dict(cache))
        except Exception as e:
            print(f"[CACHE WRITE ERROR] {e}")


def save_overrides():
    with _io_lock:
        try:
            _write_json(OVERRIDES_FILE, dict(sorted(overrides.items(), key=lambda kv: kv[0].lower())))
        except Exception as e:
            print(f"[OVERRIDES WRITE ERROR] {e}")


# --------- Title / Year Parsing ---------

# A parenthetical is a year only if it is exactly 4 digits starting with 19 or 20
_YEAR_PAT    = re.compile(r'\(((?:19|20)\d{2})\)')
_NONYR_PAREN = re.compile(r'\([^)]*\)')

# Variant/junk tokens that are never part of a real title: ver, ver2, v2, xlg,
# xlgg, poster, intl, cover, #4.  Whole-token match only, so "Vertigo" or
# "Covenant" survive.
VARIANT_TOKEN_RE = re.compile(r'^(?:ver\d*|v\d{1,3}|xlg+|poster|intl|cover|#\d+)$', re.I)


def is_variant_token(word: str) -> bool:
    return bool(VARIANT_TOKEN_RE.match(word))


def parse_poster_filename(base_name: str) -> tuple[str, str | None]:
    """
    Return (clean_title, year_or_None) for a poster filename stem.

    - A parenthetical is a YEAR only if it is exactly 4 digits starting with
      19 or 20.  Anything else — (2), (3), (#4), etc. — is stripped entirely.
    - A bare 4-digit number is never a year: "1917", "1984", "2046 xlg" keep
      it as the title.  "1917 (2019)" -> ("1917", "2019").
    - Everything AFTER the first valid year parenthetical is DISCARDED so that
      variant tags ("v2", "xlg", "#4") and duplicate year suffixes never bleed
      into the title.

    Examples
    --------
    "2 Fast 2 Furious (2)"               -> ("2 Fast 2 Furious", None)
    "28 Years Later (2025) v2 (2025)"    -> ("28 Years Later", "2025")
    "mortal kombat two ver24 xlg (2026)" -> ("mortal kombat two", "2026")
    "spiderman_brand_new_day_ver10_xlg"  -> ("spiderman brand new day", None)
    "1917 (3)"                           -> ("1917", None)
    """
    ym   = _YEAR_PAT.search(base_name)
    year = ym.group(1) if ym else None
    name = base_name[:ym.start()].rstrip() if ym else base_name
    name = _NONYR_PAREN.sub('', name)
    parts = name.replace('_', ' ').replace('-', ' ').split()
    title = ' '.join(w for w in parts if not is_variant_token(w)).strip()
    return title, year


# Older name kept for the CLI scripts
parse_filename = parse_poster_filename


def clean_title(title: str) -> str:
    """Strip (2)/(3) counters and variant tokens (ver2, xlg, v2 …) from a title string."""
    name  = _NONYR_PAREN.sub('', str(title or ''))
    parts = name.replace('_', ' ').split()
    return ' '.join(w for w in parts if not is_variant_token(w)).strip()


def norm_key(title: str, year: str | None = None) -> str:
    """Stable cache key: lowercase alphanum + spaces, optionally with year."""
    base = "".join(ch.lower() for ch in title if ch.isalnum() or ch.isspace()).strip()
    return f"{base} {year}" if year else base


def id_key(source: str, pid) -> str:
    return f"id:{source}:{pid}"


# --------- Cache migration ---------

_RATING_SOURCE = {"omdb": "imdb", "jikan": "jikan", "anilist": "anilist", "kitsu": "kitsu"}


def _migrate_entry(e: dict) -> bool:
    """imdbRating strings → rating objects; old 'none' failures → stale negative entries."""
    changed = False
    if e.get("source") == "none" and not e.get("not_found"):
        title, year = e.get("title"), e.get("year")
        e.clear()
        e.update({"not_found": True, "checked": 0, "title": title, "year": year or "N/A"})
        return True
    r = e.get("rating")
    if r is not None and not isinstance(r, dict):
        src = _RATING_SOURCE.get(e.get("source"), "imdb")
        e["rating"] = P.make_rating(r, 100 if src in ("anilist", "kitsu") else 10, src)
        changed = True
    if e.get("plot") in ("N/A", "No plot available", ""):
        e["plot"] = None
        changed = True
    return changed


def _migrate_cache():
    n = sum(1 for e in cache.values() if isinstance(e, dict) and _migrate_entry(e))
    if n:
        print(f"[CACHE] migrated {n} entries (native rating objects, negative cache)")
        save_cache()


_migrate_cache()


# --------- Resolution (what a poster file shows) ---------

def is_found(e) -> bool:
    return (isinstance(e, dict) and not e.get("not_found") and bool(e.get("title"))
            and e.get("source") not in PLACEHOLDER_SOURCES)


def negative_is_fresh(e) -> bool:
    return (isinstance(e, dict) and bool(e.get("not_found"))
            and time.time() - float(e.get("checked") or 0) < NEGATIVE_TTL)


def resolve(filename: str) -> dict:
    """Everything the UI needs to know about one poster file's metadata."""
    stem = os.path.splitext(filename)[0]
    title_guess, year = parse_poster_filename(stem)
    key = norm_key(title_guess, year)
    ov  = overrides.get(filename) or {}
    res = {"filename": filename, "title_guess": title_guess, "year_guess": year, "key": key,
           "override": ov, "ignored": bool(ov.get("ignore")),
           "entry": None, "origin": None, "negative": None, "placeholder": None}

    if ov.get("source") and ov.get("id"):
        e = cache.get(id_key(ov["source"], ov["id"]))
        res["origin"] = "override" if is_found(e) else "override-missing"
        if is_found(e):
            res["entry"] = e
    if not res["entry"]:
        fe = cache.get(filename)
        ke = cache.get(key)
        if is_found(fe):
            res["entry"], res["origin"] = fe, res["origin"] or "file"
        elif is_found(ke):
            res["entry"], res["origin"] = ke, res["origin"] or "key"
        else:
            if isinstance(ke, dict) and ke.get("not_found"):
                res["negative"] = ke
            if isinstance(fe, dict) and fe.get("source") in PLACEHOLDER_SOURCES:
                res["placeholder"] = fe
    return res


def confidence(res: dict) -> float | None:
    e = res.get("entry")
    if not e:
        return None
    if res.get("origin") == "override" or e.get("source") in MANUAL_SOURCES or e.get("manual"):
        return 1.0
    if isinstance(e.get("confidence"), (int, float)):
        return float(e["confidence"])
    # Legacy entries: score the stored match against the filename now
    return P.score_match(res["title_guess"], res["year_guess"], [e.get("title")], e.get("year"))


def display(res: dict) -> dict:
    """Title / year / rating / plot shown for a resolved poster."""
    e, ov = res.get("entry"), res.get("override") or {}
    if e:
        title, year = e.get("title") or res["title_guess"], e.get("year")
    elif res.get("placeholder"):
        ph = res["placeholder"]
        title = clean_title(ph.get("title")) or res["title_guess"]
        year  = ph.get("year")
    else:
        title, year = res["title_guess"], None
    if ov.get("display_title"):
        title = ov["display_title"]
    if not year or year == "N/A":
        year = res["year_guess"] or "N/A"
    rating = e.get("rating") if e else None
    return {
        "title":      title,
        "year":       year,
        "rating":     rating if isinstance(rating, dict) else None,
        "plot":       (e.get("plot") if e else None) or "No plot available",
        "source":     (e.get("source") if e else "") or "",
        "id":         (e.get("id") if e else "") or "",
        "confidence": confidence(res),
    }


def needs_lookup(res: dict) -> bool:
    if res["ignored"]:
        return False
    if res["origin"] == "override-missing":
        return True
    if res["entry"]:
        return False
    return not negative_is_fresh(res["negative"])


# --------- Lookups ---------

_flight_lock = threading.Lock()
_inflight: dict[str, threading.Event] = {}
_attempted: set[str] = set()          # keys already queried this session


def lookup(title: str, year: str | None = None, *, force: bool = False,
           id_hints=(), cache_key: str | None = None) -> dict | None:
    """
    Look a movie up once and cache the outcome under `cache_key` (default
    norm_key(title, year)), shared by every variant poster.

    Returns the cached entry (a match or a not_found record), or None when no
    provider could answer (network trouble) — nothing is cached then, and the
    key is not retried again this session.
    """
    key = cache_key or norm_key(title, year)
    with _flight_lock:
        ev = _inflight.get(key)
        if ev is None:
            if not force and key in _attempted:
                return cache.get(key)
            if not force and (is_found(cache.get(key)) or negative_is_fresh(cache.get(key))):
                return cache.get(key)
            ev = _inflight[key] = threading.Event()
            _attempted.add(key)
            owner = True
        else:
            owner = False
    if not owner:
        ev.wait(120)                 # another thread is fetching this movie
        return cache.get(key)
    try:
        entry = _do_lookup(title, year, id_hints)
        if entry is not None:
            cache[key] = entry
            save_cache()
        return entry
    finally:
        with _flight_lock:
            _inflight.pop(key, None)
        ev.set()


def _label(e: dict) -> str:
    conf = e.get("confidence")
    rl = P.rating_label(e.get("rating"))
    return (f"{e.get('title')} ({e.get('year')}) [{P.PROVIDER_LABELS.get(e.get('source'), e.get('source'))}"
            f"{', ' + rl if rl else ''}{f', {conf:.0%} match' if conf is not None else ''}]")


def _do_lookup(title: str, year: str | None, id_hints=()) -> dict | None:
    q = f"'{title}'" + (f" ({year})" if year else "")

    # 1. Stable IDs recorded by backfill_poster_ids.py
    for src, pid in id_hints:
        fetch = P.BY_ID.get(src)
        if not fetch:
            continue
        try:
            e = fetch(pid, OMDB_API_KEY) if src == "omdb" else fetch(pid)
        except ProviderError:
            e = None
        if e:
            score = P.score_match(title, year, [e.get("title"), *(e.pop("_titles", None) or [])], e.get("year"))
            e.pop("_alt", None)
            if score >= P.ACCEPT_SCORE:
                e.update(confidence=score, checked=int(time.time()))
                print(f"[Metadata] {q} → {_label(e)} via stored ID", flush=True)
                return e

    # "beauty and the beast 2017" → try "beauty and the beast" with 2017 as the
    # year first, then the title as written
    attempts = [(title, year)]
    split = P.split_trailing_year(title)
    if split and (not year or year == split[1]):
        attempts.insert(0, split)

    # 2. OMDb. A network error is NOT a not-found: don't fall back, don't cache
    guess = None
    for t, y in attempts:
        try:
            e, g = P.omdb_lookup(t, y, OMDB_API_KEY)
        except ProviderError:
            return None
        if e:
            e["checked"] = int(time.time())
            print(f"[Metadata] {q} → {_label(e)}", flush=True)
            return e
        if g and (not guess or g["confidence"] > guess["confidence"]):
            guess = g

    # 3. Anime fallbacks, only after OMDb definitively found nothing
    title, year = attempts[0]
    e, a_guess, definitive = P.anime_lookup(title, year)
    if e:
        e["checked"] = int(time.time())
        print(f"[Metadata] {q} → {_label(e)}", flush=True)
        return e
    if not definitive:
        return None

    guesses = [g for g in (guess, a_guess) if g]
    best = max(guesses, key=lambda g: g["confidence"]) if guesses else None
    hint = (f" (closest: {best['title']} ({best['year']}), {P.PROVIDER_LABELS.get(best['source'])}, "
            f"{best['confidence']:.0%})") if best else ""
    print(f"[Metadata] not found: {q}{hint} — not retrying for 7 days", flush=True)
    return {"not_found": True, "checked": int(time.time()), "title": title,
            "year": year or "N/A", "best_guess": best}


def fetch_by_id(source: str, pid: str) -> dict | None:
    """Fetch one exact provider record (manual fix) and cache it under id:<source>:<id>."""
    fetch = P.BY_ID.get(source)
    if not fetch:
        raise ValueError(f"Unknown source {source!r}")
    e = fetch(pid, OMDB_API_KEY) if source == "omdb" else fetch(pid)
    if not e:
        return None
    e.pop("_titles", None)
    e.pop("_alt", None)
    e.update(confidence=1.0, manual=True, checked=int(time.time()))
    cache[id_key(source, e["id"])] = e
    save_cache()
    return e


def search_candidates(query: str, provider: str = "auto", year: str | None = None, limit: int = 5) -> dict:
    """Fix-panel search. Returns {"results": [...], "errors": [...]} — top `limit` by score."""
    results, errors = [], []
    plan = {"omdb": ["omdb"], "anilist": ["anilist"], "kitsu": ["kitsu"], "jikan": ["jikan"],
            "auto": ["omdb", "anilist", "kitsu"]}.get(provider, ["omdb"])
    search = {"omdb": lambda: P.omdb_search(query, year, OMDB_API_KEY),
              "anilist": lambda: P.anilist_search(query, year),
              "kitsu": lambda: P.kitsu_search(query, year),
              "jikan": lambda: P.jikan_search(query, year)}
    for src in plan:
        try:
            cands = search[src]()
        except ProviderError as e:
            errors.append(str(e))
            continue
        if src != "omdb":
            cands = P.score_candidates(query, year, cands)
        results += cands
    results.sort(key=lambda c: -c.get("score", 0))
    top = results[:limit]
    # OMDb search results carry no rating/plot: fetch details for the ones shown
    for c in top:
        if c["source"] == "omdb" and "rating" not in c:
            try:
                full = P.omdb_by_id(c["id"], OMDB_API_KEY)
            except ProviderError:
                full = None
            if full:
                c.update({k: full[k] for k in ("rating", "plot", "type") if full.get(k)})
                c["poster"] = c.get("poster") or full.get("poster")
    for c in top:
        c.pop("_titles", None)
        c.pop("_alt", None)
        c["rating_label"] = P.rating_label(c.get("rating"))
    return {"results": top, "errors": errors}


_ID_PATTERNS = [
    (re.compile(r"\b(tt\d{6,10})\b", re.I),                         "omdb"),
    (re.compile(r"anilist\.co/anime/(\d+)", re.I),                  "anilist"),
    (re.compile(r"kitsu\.(?:io|app)/anime/([\w-]+)", re.I),         "kitsu"),
    (re.compile(r"myanimelist\.net/anime/(\d+)", re.I),             "jikan"),
    (re.compile(r"^\s*(anilist|kitsu|jikan|mal)\s*[:#]\s*([\w-]+)\s*$", re.I), None),
]


def parse_id_input(text: str, provider: str = "auto") -> tuple[str, str] | None:
    """tt1234567 / AniList URL / Kitsu URL or slug / "anilist:123" / a bare id with a provider picked."""
    text = (text or "").strip()
    for pat, src in _ID_PATTERNS:
        m = pat.search(text)
        if m:
            if src is None:
                s = m.group(1).lower()
                return ("jikan" if s == "mal" else s), m.group(2)
            return src, m.group(1)
    if text.isdigit() and provider in ("anilist", "kitsu", "jikan"):
        return provider, text
    return None


# --------- Compatibility helpers (used by backfill_poster_ids.py) ---------

def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, (a or "").lower().strip(), (b or "").lower().strip()).ratio()


def _best_omdb_match(search_results: list, original_title: str, year: str | None) -> str | None:
    """Best imdbID from OMDb search results, year-aware."""
    scored = sorted(((P.score_match(original_title, year, [r.get("Title")], r.get("Year")), r)
                     for r in (search_results or [])), key=lambda x: -x[0])
    if scored and scored[0][0] >= P.ACCEPT_SCORE:
        return scored[0][1].get("imdbID")
    return None
