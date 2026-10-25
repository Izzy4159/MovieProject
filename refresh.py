"""
Metadata refresh jobs (the nav "↻ Refresh" button, the lightbox ↻ and uploads).

Modes
-----
smart  posters added/modified since the last refresh, not-found (ignoring the
       7-day negative cache), missing year/rating/plot, confidence < 0.85,
       ambiguous, and no-year matches never checked for remakes
full   every poster
files  the given posters (a stack from the lightbox, or a fresh upload)

Rules: one lookup per cache key (a whole stack), posters with a manual fix or
Ignore in metadata_overrides.json are never touched, and data.merge_refresh
never replaces good data with worse data. One job runs at a time in a
background thread; uploads queue onto a running job.
"""
import json
import os
import threading
import time
from collections import deque
from pathlib import Path

import data
import providers as P

_BASE = Path(__file__).resolve().parent
POSTERS_DIR = _BASE / "posters"
STATE_FILE  = _BASE / "refresh_state.json"      # local-only: {"last_refresh": ts}
SECONDS_PER_LOOKUP = 1.5                         # for the "Refresh everything" estimate
# Older no-year matches get a one-time remake check (2–6 OMDb requests each).
# Spread them over several smart refreshes so one click can't eat a free
# key's ~1,000 requests/day.
REMAKE_CHECKS_PER_REFRESH = 60

# Per-file entries a human wrote: a refresh never overwrites them
_HUMAN_FLAGS = ("edited",)

_lock  = threading.RLock()     # status() is also called while holding it
_job   = {"running": False, "mode": None, "total": 0, "done": 0, "updated": 0,
          "still_unmatched": 0, "ambiguous": 0, "skipped_manual": 0,
          "started": None, "finished": None, "current": None}
_queue = deque()
_changes = []              # [(seq, filename)] — posters whose shown metadata changed
_seq   = [0]
_on_change = [None]        # callback set by routes: invalidate the grid HTML cache


def set_on_change(fn):
    _on_change[0] = fn


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict):
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[REFRESH] could not save state: {e}")


def _poster_files() -> list[str]:
    if not POSTERS_DIR.is_dir():
        return []
    return sorted((e.name for e in os.scandir(POSTERS_DIR)
                   if e.is_file() and e.name.lower().endswith(".webp")), key=str.lower)


def _refreshable_file_entry(e) -> bool:
    """A per-file entry the refresh may replace (automatic lookups, not human edits)."""
    return (isinstance(e, dict) and e.get("source") not in data.MANUAL_SOURCES
            and not any(e.get(f) for f in _HUMAN_FLAGS))


def _smart_reasons(res: dict, mtime: float, since: float | None) -> list[str]:
    d = data.display(res)
    reasons = []
    if since is not None and mtime > since:
        reasons.append("new")
    if res["ambiguous"] is not None:
        reasons.append("ambiguous")
    if not res["entry"]:
        reasons.append("unmatched")
    else:
        if d["confidence"] is not None and d["confidence"] < P.LOW_CONF:
            reasons.append("low_confidence")
        if (d["year"] in (None, "", "N/A") or d["rating"] is None
                or d["plot"] in (None, "", "No plot available")):
            reasons.append("missing")
        e = res["entry"]
        if (not res["year_guess"] and e.get("source") == "omdb" and not e.get("ambiguity_checked")
                and res["origin"] in ("key", "file")):
            reasons.append("unchecked_remake")
    return reasons


def plan(mode: str, files=None) -> dict:
    """Group the posters to refresh by cache key: {"groups": [...], "posters": n, "skipped_manual": n}."""
    state = _load_state()
    since = state.get("last_refresh")              # None on the very first smart refresh
    names = list(files) if mode == "files" else _poster_files()
    groups, skipped, posters = {}, 0, 0
    for fn in names:
        path = POSTERS_DIR / fn
        if not path.is_file():
            continue
        res = data.resolve(fn)
        if res["manual"]:
            skipped += 1
            continue
        if mode == "smart":
            reasons = _smart_reasons(res, path.stat().st_mtime, since)
            if not reasons:
                continue
        else:
            reasons = [mode]
        posters += 1
        g = groups.setdefault(res["key"], {"key": res["key"], "title": res["title_guess"],
                                           "year": res["year_guess"], "files": [], "hints": [],
                                           "reasons": set()})
        g["files"].append(fn)
        g["reasons"].update(reasons)
        pid = data.poster_ids.get(fn) or {}
        if pid.get("source") and pid.get("id") and (pid["source"], str(pid["id"])) not in g["hints"]:
            g["hints"].append((pid["source"], str(pid["id"])))
    out = list(groups.values())
    if mode == "smart":
        checks = [g for g in out if g["reasons"] == {"unchecked_remake"}]
        drop = {id(g) for g in checks[REMAKE_CHECKS_PER_REFRESH:]}
        if drop:
            posters -= sum(len(g["files"]) for g in out if id(g) in drop)
            out = [g for g in out if id(g) not in drop]
    return {"groups": out, "posters": posters, "skipped_manual": skipped}


def estimate(mode: str) -> dict:
    p = plan(mode)
    n = len(p["groups"])
    return {"movies": n, "posters": p["posters"], "skipped_manual": p["skipped_manual"],
            "seconds": round(n * SECONDS_PER_LOOKUP)}


def status(since: int = 0) -> dict:
    with _lock:
        st = {k: v for k, v in _job.items()}
        st["queued"] = len(_queue)
        st["seq"] = _seq[0]
        st["changed"] = sorted({fn for s, fn in _changes if s > since})
    return st


def start(mode: str, files=None) -> dict:
    """Start a job, or report the running one. Uploads ("files" with queue=True) join a running job."""
    p = plan(mode, files)
    with _lock:
        if _job["running"]:
            if mode == "files" and files and _job["mode"] == "files":
                _queue.extend(p["groups"])
                _job["total"] += len(p["groups"])
                return dict(status(), queued_files=list(files))
            return dict(status(), already_running=True)
        _job.update(running=True, mode=mode, total=len(p["groups"]), done=0, updated=0,
                    still_unmatched=0, ambiguous=0, skipped_manual=p["skipped_manual"],
                    started=time.time(), finished=None, current=None)
        _queue.clear()
        _queue.extend(p["groups"])
    print(f"[REFRESH] {mode}: {len(p['groups'])} movies ({p['posters']} posters), "
          f"{p['skipped_manual']} manual fixes / ignored skipped", flush=True)
    threading.Thread(target=_run, args=(mode,), daemon=True).start()
    return status()


def start_upload(files) -> dict:
    """Upload: refresh just these posters, joining a running upload job if there is one."""
    with _lock:
        busy_other = _job["running"] and _job["mode"] != "files"
    if busy_other:
        # A smart/full job is running: add the upload to it rather than waiting
        p = plan("files", files)
        with _lock:
            _queue.extend(p["groups"])
            _job["total"] += len(p["groups"])
        return status()
    return start("files", files)


def _shown(fn: str) -> tuple:
    d = data.display(data.resolve(fn))
    return (d["title"], d["year"], json.dumps(d["rating"], sort_keys=True), d["plot"], d["source"], d["id"])


def _run(mode: str):
    try:
        while True:
            with _lock:
                if not _queue:
                    break
                g = _queue.popleft()
                _job["current"] = g["title"]
            try:
                _refresh_group(g)
            except Exception as e:                       # one bad title must not kill the job
                print(f"[REFRESH] error on '{g['title']}': {e}", flush=True)
            with _lock:
                _job["done"] += 1
        if mode in ("smart", "full"):
            state = _load_state()
            state["last_refresh"] = _job["started"]
            _save_state(state)
    finally:
        with _lock:
            _job.update(running=False, finished=time.time(), current=None)
        print(f"[REFRESH] done: {_job['done']}/{_job['total']} movies · {_job['updated']} updated · "
              f"{_job['still_unmatched']} still unmatched · {_job['ambiguous']} ambiguous", flush=True)


def _refresh_group(g: dict):
    key, title, year = g["key"], g["title"], g["year"]
    before = {fn: _shown(fn) for fn in g["files"]}

    # Old no-year matches that only need the remake check (cheaper than a full lookup)
    only_check = g["reasons"] == {"unchecked_remake"}
    if only_check:
        new = None
        for src in [data.cache.get(key)] + [data.cache.get(fn) for fn in g["files"]]:
            if data.is_found(src):
                new = data.recheck_ambiguity(title, src)
                break
    else:
        new = data.fetch_fresh(title, year, key, g["hints"])

    outcomes = []
    store, outcome = data.merge_refresh(data.cache.get(key), new, title, year)
    if store is not None:
        data.cache[key] = store
    outcomes.append(outcome)
    # Per-file copies from earlier automatic lookups get the same treatment
    for fn in g["files"]:
        fe = data.cache.get(fn)
        if data.is_found(fe) and _refreshable_file_entry(fe):
            s2, o2 = data.merge_refresh(fe, new, title, year)
            if s2 is not None:
                data.cache[fn] = s2
            outcomes.append(o2)
    data.save_cache()

    changed = [fn for fn in g["files"] if _shown(fn) != before[fn]]
    flagged_ambiguous = any(data.resolve(fn)["ambiguous"] is not None for fn in g["files"])
    unmatched = all(not data.resolve(fn)["entry"] for fn in g["files"])
    with _lock:
        if changed or "updated" in outcomes:
            _job["updated"] += 1
        if flagged_ambiguous:
            _job["ambiguous"] += 1
        elif unmatched:
            _job["still_unmatched"] += 1
        for fn in set(changed) | (set(g["files"]) if flagged_ambiguous else set()):
            _seq[0] += 1
            _changes.append((_seq[0], fn))
        del _changes[:-5000]
    if changed or flagged_ambiguous:
        cb = _on_change[0]
        if cb:
            cb()
