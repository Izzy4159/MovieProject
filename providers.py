"""
Metadata providers: OMDb (primary) and the anime fallbacks AniList → Kitsu → Jikan.

Every provider call goes through Provider.request(), which applies
- a 3 s connect / 8 s read timeout,
- a per-provider rate limit (requests are serialised per provider),
- a circuit breaker: 2 consecutive connection failures → the provider is
  skipped for 10 minutes, with ONE log line,
- 429 handling that honours Retry-After.

Search functions return a list of candidates (an empty list is a definitive
"not found") or raise ProviderError when the answer is unknown (network
trouble, HTTP 5xx, rate/daily limits). Callers must never treat a
ProviderError as "not found".
"""
import html
import re
import threading
import time
import unicodedata
from difflib import SequenceMatcher

import requests

TIMEOUT          = (3, 8)     # (connect, read) seconds
BREAKER_FAILURES = 2
BREAKER_SECONDS  = 600

ACCEPT_SCORE = 0.75           # below this a result is rejected (stored as not-found)
LOW_CONF     = 0.85           # below this a match is shown in the Needs Fix panel

USER_AGENT = "MovieProject/1.0 (personal poster library)"


class ProviderError(Exception):
    """The provider could not give a definitive answer."""


class Provider:
    def __init__(self, name: str, min_interval: float = 0.0):
        self.name          = name
        self.session       = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._lock         = threading.Lock()     # one request at a time → rate limit
        self._min_interval = min_interval
        self._last         = 0.0
        self._fails        = 0
        self._open_until   = 0.0
        self.calls         = 0                    # requests made this session (for logs)

    def available(self) -> bool:
        return time.monotonic() >= self._open_until

    def trip(self, seconds: float, message: str):
        """Skip this provider for `seconds`, logging one line."""
        self._open_until = max(self._open_until, time.monotonic() + seconds)
        self._fails = 0
        print(f"[{self.name}] {message}", flush=True)

    def request(self, method: str, url: str, **kw) -> requests.Response:
        for attempt in (0, 1):
            if not self.available():
                raise ProviderError(f"{self.name} skipped")
            with self._lock:
                wait = self._last + self._min_interval - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self.calls += 1
                try:
                    resp = self.session.request(method, url, timeout=TIMEOUT, **kw)
                except (requests.ConnectionError, requests.Timeout) as e:
                    self._last = time.monotonic()
                    self._fails += 1
                    if self._fails >= BREAKER_FAILURES:
                        self.trip(BREAKER_SECONDS, f"unreachable, skipping for {BREAKER_SECONDS // 60} min")
                    raise ProviderError(f"{self.name}: {type(e).__name__}") from None
                self._last  = time.monotonic()
                self._fails = 0

            if resp.status_code == 429:
                delay = _retry_after(resp)
                if attempt == 0 and delay <= 15:
                    time.sleep(delay)
                    continue
                self.trip(delay, f"rate limited (HTTP 429), pausing for {delay:.0f} s")
                raise ProviderError(f"{self.name}: HTTP 429")
            if resp.status_code >= 500:
                raise ProviderError(f"{self.name}: HTTP {resp.status_code}")
            return resp
        raise ProviderError(f"{self.name}: HTTP 429")


def _retry_after(resp) -> float:
    try:
        return max(1.0, float(resp.headers.get("Retry-After", "")))
    except ValueError:
        return 60.0


OMDB    = Provider("OMDb",    min_interval=0.15)
ANILIST = Provider("AniList", min_interval=60 / 25)   # degraded to 30/min upstream — stay at 25
KITSU   = Provider("Kitsu",   min_interval=1.0)
JIKAN   = Provider("Jikan",   min_interval=1.0)


# ── Title matching ────────────────────────────────────────────────────────────
# Only used to SCORE results against the filename title. API queries are sent
# as the cleaned title (plus the spelling variants from query_variants()).

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}
_WORD_NUM = {w: i for i, w in enumerate(_ONES)} | _TENS
_ROMAN = {"ii": 2, "iii": 3, "iv": 4, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "xi": 11,
          "xii": 12, "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18,
          "xix": 19, "xx": 20}
_ARTICLES = {"the", "a", "an"}


def _tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"['’`]", "", s)
    # Keep non-Latin letters: "NARUTO -ナルト- 疾風伝" must not collapse to "naruto"
    return re.sub(r"[\W_]+", " ", s).split()


def _numeric_tokens(tokens: list[str], single_letters: bool = True) -> list[str]:
    """Number words and roman numerals → digits.

    "mortal kombat two" / "ii" → "2" · "one hundred twenty seven" → "127" ·
    "two thousand and one" → "2001" · "blade runner twenty forty nine" → "2049"
    """
    out, words = [], []                 # words[i]: out[i] came from number words
    cur = None

    def flush():
        nonlocal cur
        if cur is None:
            return
        # Spoken years: "twenty forty nine" → 2049, "nineteen eighty four" → 1984
        if words and words[-1] and 10 <= int(out[-1]) <= 99 and 10 <= cur <= 99:
            out[-1] = str(int(out[-1]) * 100 + cur)
        else:
            out.append(str(cur))
            words.append(True)
        cur = None

    for i, t in enumerate(tokens):
        if t == "hundred" and cur is not None and cur < 10:
            cur *= 100
            continue
        if t == "thousand" and cur is not None and cur < 1000:
            cur *= 1000
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if t == "and" and cur is not None and cur >= 100 and cur % 100 == 0 and nxt in _WORD_NUM:
            continue
        v = _WORD_NUM.get(t)
        if v is not None:
            round_hundreds = cur is not None and cur >= 100 and cur % 100 == 0
            tens_only      = cur is not None and cur % 100 >= 20 and cur % 10 == 0
            if cur is None:
                cur = v
            elif round_hundreds or (tens_only and 0 < v < 10):
                cur += v
            else:
                flush()
                cur = v
            continue
        flush()
        if t in _ROMAN:
            out.append(str(_ROMAN[t]))
        elif single_letters and t in ("v", "x") and i == len(tokens) - 1 and i > 0:   # "Rocky V", not "X-Men"
            out.append("5" if t == "v" else "10")
        else:
            out.append(t)
        words.append(False)
    flush()
    return out


def match_form(s: str) -> str:
    toks = _numeric_tokens(_tokens(s))
    if len(toks) > 1 and toks[0] in _ARTICLES:
        toks = toks[1:]
    return " ".join(toks)


def title_similarity(a: str, b: str) -> float:
    fa, fb = match_form(a), match_form(b)
    if not fa or not fb:
        return 0.0
    spaced  = SequenceMatcher(None, fa, fb).ratio()
    compact = SequenceMatcher(None, fa.replace(" ", ""), fb.replace(" ", "")).ratio()
    return max(spaced, compact)


def year_range(year) -> tuple[int | None, int | None]:
    """'2013–2023' → (2013, 2023); '2013–' → (2013, this year); '1999' → (1999, 1999)."""
    yrs = [int(y) for y in re.findall(r"(?:18|19|20)\d\d", str(year or ""))]
    if not yrs:
        return None, None
    start = yrs[0]
    if len(yrs) > 1:
        return start, yrs[1]
    if re.search(r"\d{4}\s*[–-]\s*$", str(year)):
        return start, time.localtime().tm_year
    return start, start


_GENERIC_SUFFIX = re.compile(r"\s*[:\-–]\s*(?:the )?movie\s*$", re.I)


MAIN_TITLE_SCORE = 0.78  # query == the part before "Title: Subtitle" → accepted, but flagged for review


def _numbers(form: str) -> set[str]:
    return {t for t in form.split() if t.isdigit()}


def _title_score(query_title: str, cand: str) -> float:
    sim = title_similarity(query_title, cand)
    q, c = match_form(query_title), match_form(cand)
    # Sequel / season numbers must agree: "Season 1" is not "Judgement of Fury"
    if _numbers(q) != _numbers(c):
        sim *= 0.8
    # "Avatar Aang" vs "Avatar Aang: The Last Airbender"
    main = re.split(r"\s*[:–]\s+|\s+-\s+", cand, maxsplit=1)[0]
    if main != cand and title_similarity(query_title, main) >= 0.95:
        sim = max(sim, MAIN_TITLE_SCORE)
    return sim


def score_match(query_title: str, query_year, cand_titles, cand_year) -> float:
    """difflib similarity against every title variant, adjusted for the year.
    Exact year +0.05; ±1 year (or inside a series' run) neutral; otherwise ×0.7."""
    titles = [t for t in cand_titles if t]
    titles += [_GENERIC_SUFFIX.sub("", t) for t in titles if _GENERIC_SUFFIX.search(t)]
    sim = max((_title_score(query_title, t) for t in titles), default=0.0)
    qy, _ = year_range(query_year)
    cy, cend = year_range(cand_year)
    if qy and cy:
        if qy == cy:
            sim = min(1.0, sim + 0.05)
        elif abs(qy - cy) <= 1 or cy <= qy <= (cend or cy):
            pass
        else:
            sim *= 0.7
    return round(sim, 3)


# ── Query variants ────────────────────────────────────────────────────────────

# Joined / split spellings that title databases hyphenate
_HYPHEN_FIXES = [
    (r"\bspider ?man\b",   "spider-man"),
    (r"\bspider ?verse\b", "spider-verse"),
    (r"\bspider ?woman\b", "spider-woman"),
    (r"\bx ?men\b",        "x-men"),
    (r"\bant ?man\b",      "ant-man"),
]
_NUM_TO_ROMAN = {2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}


def query_variants(title: str) -> list[str]:
    """The cleaned title first, then hyphenated / numeric / roman-numeral spellings.

    "mortal kombat two"       → ["mortal kombat two", "mortal kombat 2", "mortal kombat II"]
    "spiderman brand new day" → ["spiderman brand new day", "spider-man brand new day"]
    """
    base = " ".join(str(title or "").split())
    hyph = base
    for pat, rep in _HYPHEN_FIXES:
        hyph = re.sub(pat, rep, hyph, flags=re.I)

    out = []
    for t in (base, hyph):
        nums  = _numeric_tokens([w.lower() for w in t.split()], single_letters=False)
        cands = [t, " ".join(nums)]
        if len(nums) > 1 and nums[-1].isdigit() and int(nums[-1]) in _NUM_TO_ROMAN:
            cands.append(" ".join(nums[:-1] + [_NUM_TO_ROMAN[int(nums[-1])]]))
        # "cowboys and aliens" → "Cowboys & Aliens"
        cands += [re.sub(r"\band\b", "&", c, flags=re.I) for c in cands if re.search(r"\w and \w", c, re.I)]
        for c in cands:
            if c and c.lower() not in (o.lower() for o in out):
                out.append(c)
    return out


def split_trailing_year(title: str) -> tuple[str, str] | None:
    """'american hustle 2013' → ('american hustle', '2013'). Not for titles that
    are a number ('2012') or future years ('Blade Runner 2049')."""
    m = re.match(r"^(.*\S)\s+((?:19|20)\d\d)$", str(title or "").strip())
    if m and int(m.group(2)) <= time.localtime().tm_year + 2:
        return m.group(1), m.group(2)
    return None


# ── Ratings ───────────────────────────────────────────────────────────────────

RATING_LABELS = {"imdb": "IMDb", "anilist": "AniList", "kitsu": "Kitsu", "jikan": "MAL"}
PROVIDER_LABELS = {"omdb": "OMDb", "anilist": "AniList", "kitsu": "Kitsu", "jikan": "Jikan"}


def make_rating(value, scale: int, source: str) -> dict | None:
    try:
        v = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    v = round(v, 2)
    return {"value": int(v) if v == int(v) else v, "scale": scale, "source": source}


def rating_norm(r) -> float | None:
    """0–100 for sorting/filtering mixed sources."""
    if not isinstance(r, dict) or r.get("value") is None:
        return None
    return round(float(r["value"]) * 100.0 / float(r.get("scale") or 10), 2)


def rating_label(r) -> str:
    if not isinstance(r, dict) or r.get("value") is None:
        return ""
    return f"{RATING_LABELS.get(r.get('source'), r.get('source', ''))} {r['value']}/{r.get('scale', 10)}"


# ── Text clean-up ─────────────────────────────────────────────────────────────

def clean_plot(text) -> str | None:
    if not text:
        return None
    t = html.unescape(re.sub(r"<br\s*/?>", "\n", str(text), flags=re.I))
    t = re.sub(r"<[^>]+>", "", t)
    # Trailing "(Source: Crunchyroll)" / "[Written by MAL Rewrite]" credit lines
    t = re.sub(r"\s*[\(\[]\s*(?:source|written by)\b[^\)\]]*[\)\]]\s*$", "", t.strip(), flags=re.I)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t or None


def _year_str(y) -> str:
    return str(y) if y else "N/A"


# ── OMDb ──────────────────────────────────────────────────────────────────────

_OMDB_URL = "https://www.omdbapi.com/"
_OMDB_TYPES = ("movie", "series")   # skip "game" / "episode" results


def _omdb_get(params: dict, api_key: str) -> dict:
    if not api_key:
        raise ProviderError("OMDb: no API key")
    resp = OMDB.request("GET", _OMDB_URL, params={**params, "apikey": api_key})
    if resp.status_code != 200:
        raise ProviderError(f"OMDb: HTTP {resp.status_code}")
    data = resp.json()
    if data.get("Response") == "True":
        return data
    err = str(data.get("Error") or "")
    low = err.lower()
    if "not found" in low or "too many results" in low or "incorrect imdb id" in low:
        return {}                                  # definitive: nothing for this query
    if "limit" in low:
        OMDB.trip(3600, "daily request limit reached, skipping for 60 min")
    elif "api key" in low:
        OMDB.trip(BREAKER_SECONDS, f"{err} — check OMDB_API_KEY; skipping for 10 min")
    raise ProviderError(f"OMDb: {err or 'unknown error'}")


def _omdb_entry(d: dict) -> dict:
    return {
        "title":  d.get("Title"),
        "year":   d.get("Year") or "N/A",
        "rating": make_rating(d.get("imdbRating"), 10, "imdb"),
        "plot":   d.get("Plot") if d.get("Plot") not in (None, "", "N/A") else None,
        "source": "omdb",
        "id":     d.get("imdbID"),
        "type":   d.get("Type"),
        "poster": d.get("Poster") if str(d.get("Poster", "")).startswith("http") else None,
    }


def omdb_by_id(imdb_id: str, api_key: str) -> dict | None:
    d = _omdb_get({"i": imdb_id, "plot": "short"}, api_key)
    return _omdb_entry(d) if d else None


def omdb_lookup(title: str, year, api_key: str) -> tuple[dict | None, dict | None]:
    """Best accepted OMDb match → (entry, None), or (None, best_rejected_guess).
    Order: exact title with year → without year → search + difflib, for each
    spelling variant. Raises ProviderError if any request failed."""
    variants = query_variants(title)
    seen, best = set(), None

    def consider(entry, score):
        nonlocal best
        if best is None or score > best[1]:
            best = (entry, score)

    # 1–2. Exact title (t=), with the year first
    for y in ([year, None] if year else [None]):
        for v in variants:
            params = {"t": v, "plot": "short", **({"y": y} if y else {})}
            d = _omdb_get(params, api_key)
            if not d or d.get("Type") not in _OMDB_TYPES or d.get("imdbID") in seen:
                continue
            seen.add(d.get("imdbID"))
            entry = _omdb_entry(d)
            score = score_match(title, year, [entry["title"]], entry["year"])
            consider(entry, score)
            if score >= ACCEPT_SCORE and (not year or score >= 0.9):
                entry["confidence"] = score
                return entry, None

    if best and best[1] >= ACCEPT_SCORE:
        best[0]["confidence"] = best[1]
        return best[0], None

    # 3. Search (s=) + difflib over every result
    results = {}
    for v in variants[:2]:
        for y in ([year, None] if year else [None]):
            d = _omdb_get({"s": v, **({"y": y} if y else {})}, api_key)
            for r in (d.get("Search") or []):
                if r.get("Type") in _OMDB_TYPES:
                    results.setdefault(r.get("imdbID"), r)
    def pick():
        scored = sorted(((score_match(title, year, [r.get("Title")], r.get("Year")), r)
                         for r in results.values()), key=lambda x: -x[0])
        return scored[0] if scored else (0.0, None)

    score, r = pick()
    # 4. Search on the title's first words: OMDb search is word-based, so a
    #    filename that lost its apostrophes ("sorcerers stone", "dead mans
    #    chest") or uses another spelling only matches on a shorter prefix
    if score < ACCEPT_SCORE:
        words = variants[1 if len(variants) > 1 else 0].split()
        for n in (4, 3, 2):
            if 2 <= n < len(words):
                d = _omdb_get({"s": " ".join(words[:n])}, api_key)
                for res in (d.get("Search") or []):
                    if res.get("Type") in _OMDB_TYPES:
                        results.setdefault(res.get("imdbID"), res)
                score, r = pick()
                if score >= ACCEPT_SCORE:
                    break

    if r is not None:
        if score >= ACCEPT_SCORE:
            full = omdb_by_id(r["imdbID"], api_key)
            if full:
                full["confidence"] = score
                return full, None
        if not best or score > best[1]:
            best = ({"title": r.get("Title"), "year": r.get("Year"), "source": "omdb",
                     "id": r.get("imdbID")}, score)
    return None, _guess(best)


AMBIGUOUS_TITLE = 0.95     # "same title" for remakes / reboots
DOMINANT_VOTES  = 20       # one candidate with 20× the IMDb votes of the next is the obvious one


def _votes(d: dict) -> int:
    try:
        return int(str(d.get("imdbVotes") or "0").replace(",", ""))
    except ValueError:
        return 0


def omdb_ambiguity(title: str, api_key: str) -> dict:
    """
    For a title WITHOUT a year: are there several strong same-title matches
    from different years (Resident Evil 2002 / 2026)?

    {"status": "clear"}                                    one title, nothing to decide
    {"status": "dominant", "entry": {...}}                 one is overwhelmingly the famous one
    {"status": "ambiguous", "candidates": [{title, year, imdbID, poster, type, rating, votes}]}
    """
    results = {}
    for v in query_variants(title)[:2]:
        d = _omdb_get({"s": v}, api_key)
        for r in (d.get("Search") or []):
            if (r.get("Type") in _OMDB_TYPES and r.get("imdbID")
                    and score_match(title, None, [r.get("Title")], None) >= AMBIGUOUS_TITLE):
                results.setdefault(r["imdbID"], r)
        if d.get("Search"):          # one search is enough when it returned anything
            break
    # Search ranks by popularity, so a brand-new remake (no votes yet) is buried
    # under the older title: ask for this year's titles explicitly
    this_year = time.localtime().tm_year
    d = _omdb_get({"s": query_variants(title)[0], "y": this_year}, api_key)
    for r in (d.get("Search") or []):
        if (r.get("Type") in _OMDB_TYPES and r.get("imdbID")
                and score_match(title, None, [r.get("Title")], None) >= AMBIGUOUS_TITLE):
            results.setdefault(r["imdbID"], r)
    years = sorted({year_range(r.get("Year"))[0] for r in results.values()} - {None})
    if len(results) < 2 or not years or years[-1] - years[0] < 2:
        return {"status": "clear"}

    cands = []
    for r in list(results.values())[:4]:
        full = _omdb_get({"i": r["imdbID"], "plot": "short"}, api_key)
        if full:
            e = _omdb_entry(full)
            e["votes"] = _votes(full)
            cands.append(e)
    cands.sort(key=lambda e: -e["votes"])
    if len(cands) < 2:
        return {"status": "clear"}
    top, second = cands[0], cands[1]
    # A new release has few votes yet, so votes can't rule it out: if any other
    # candidate is from this year or last year, let the user decide
    recent = any((year_range(c["year"])[0] or 0) >= this_year - 1 for c in cands[1:])
    if not recent and top["votes"] >= DOMINANT_VOTES * max(second["votes"], 1):
        return {"status": "dominant", "entry": top}
    return {"status": "ambiguous", "candidates": [
        {"title": c["title"], "year": c["year"], "imdbID": c["id"], "poster": c.get("poster"),
         "type": c.get("type"), "rating": c.get("rating"), "votes": c["votes"]} for c in cands]}


def omdb_search(query: str, year, api_key: str) -> list[dict]:
    """Fix-panel search: candidates for a free-text query."""
    results = {}
    for v in query_variants(query)[:2]:
        d = _omdb_get({"s": v, **({"y": year} if year else {})}, api_key)
        for r in (d.get("Search") or []):
            if r.get("Type") in _OMDB_TYPES:
                results.setdefault(r.get("imdbID"), r)
    if not results:   # s= can miss exact titles that t= finds
        d = _omdb_get({"t": query, **({"y": year} if year else {})}, api_key)
        if d and d.get("Type") in _OMDB_TYPES:
            results[d["imdbID"]] = {"Title": d.get("Title"), "Year": d.get("Year"),
                                    "imdbID": d.get("imdbID"), "Type": d.get("Type"),
                                    "Poster": d.get("Poster")}
    return [{"title": r.get("Title"), "year": r.get("Year"), "source": "omdb",
             "id": r.get("imdbID"), "type": r.get("Type"),
             "poster": r.get("Poster") if str(r.get("Poster", "")).startswith("http") else None,
             "score": score_match(query, year, [r.get("Title")], r.get("Year"))}
            for r in results.values()]


# ── AniList ───────────────────────────────────────────────────────────────────

_ANILIST_URL = "https://graphql.anilist.co"
_ANILIST_FIELDS = """
  id title { romaji english native } synonyms seasonYear startDate { year }
  averageScore meanScore description(asHtml: false) format coverImage { extraLarge }
"""
_ANILIST_SEARCH = ("query ($q: String, $year: Int) { Page(perPage: 5) { "
                   "media(search: $q, type: ANIME, seasonYear: $year) {" + _ANILIST_FIELDS + "} } }")
_ANILIST_BY_ID = "query ($id: Int) { Media(id: $id, type: ANIME) {" + _ANILIST_FIELDS + "} }"


def _anilist_post(query: str, variables: dict) -> dict:
    resp = ANILIST.request("POST", _ANILIST_URL, json={"query": query, "variables": variables},
                           headers={"Accept": "application/json"})
    if resp.status_code == 404:
        return {}
    if resp.status_code != 200:
        raise ProviderError(f"AniList: HTTP {resp.status_code}")
    return resp.json().get("data") or {}


def _anilist_titles(m: dict) -> list[str]:
    t = m.get("title") or {}
    return [x for x in (t.get("english"), t.get("romaji"), t.get("native")) if x]


def _anilist_entry(m: dict) -> dict:
    t = m.get("title") or {}
    year = m.get("seasonYear") or (m.get("startDate") or {}).get("year")
    score = m.get("averageScore") or m.get("meanScore")
    return {
        "title":  t.get("english") or t.get("romaji") or t.get("native"),
        "year":   _year_str(year),
        "rating": make_rating(score, 100, "anilist"),
        "plot":   clean_plot(m.get("description")),
        "source": "anilist",
        "id":     str(m.get("id")),
        "type":   m.get("format"),
        "poster": (m.get("coverImage") or {}).get("extraLarge"),
        "_titles": _anilist_titles(m),
        "_alt":    [x for x in (m.get("synonyms") or []) if x],
    }


def anilist_search(query: str, year=None) -> list[dict]:
    y, _ = year_range(year)
    media = (_anilist_post(_ANILIST_SEARCH, {"q": query, "year": y}).get("Page") or {}).get("media") or []
    entries = [_anilist_entry(m) for m in media]
    # The season year is often off for films / later seasons: retry without it
    # unless the year-filtered search already produced a good match
    if y and not any(score_match(query, year, e["_titles"] + e["_alt"], e["year"]) >= ACCEPT_SCORE for e in entries):
        media = (_anilist_post(_ANILIST_SEARCH, {"q": query, "year": None}).get("Page") or {}).get("media") or []
        ids = {e["id"] for e in entries}
        entries += [e for e in map(_anilist_entry, media) if e["id"] not in ids]
    return entries


def anilist_by_id(aid) -> dict | None:
    m = _anilist_post(_ANILIST_BY_ID, {"id": int(aid)}).get("Media")
    return _anilist_entry(m) if m else None


# ── Kitsu ─────────────────────────────────────────────────────────────────────

_KITSU_URL = "https://kitsu.io/api/edge/anime"
_KITSU_HEADERS = {"Accept": "application/vnd.api+json"}


def _kitsu_get(url: str, params: dict | None = None) -> dict:
    resp = KITSU.request("GET", url, params=params, headers=_KITSU_HEADERS)
    if resp.status_code == 404:
        return {}
    if resp.status_code != 200:
        raise ProviderError(f"Kitsu: HTTP {resp.status_code}")
    return resp.json()


def _kitsu_titles(a: dict) -> list[str]:
    t = a.get("titles") or {}
    return [x for x in (t.get("en"), t.get("en_us"), t.get("en_jp"), a.get("canonicalTitle")) if x]


def _kitsu_entry(item: dict) -> dict:
    a = item.get("attributes") or {}
    t = a.get("titles") or {}
    return {
        "title":  t.get("en") or t.get("en_us") or a.get("canonicalTitle") or t.get("en_jp"),
        "year":   _year_str((a.get("startDate") or "")[:4]),
        "rating": make_rating(a.get("averageRating"), 100, "kitsu"),
        "plot":   clean_plot(a.get("synopsis")),
        "source": "kitsu",
        "id":     str(item.get("id")),
        "type":   a.get("subtype"),
        "poster": (a.get("posterImage") or {}).get("medium") or (a.get("posterImage") or {}).get("original"),
        "_titles": _kitsu_titles(a),
        "_alt":    [x for x in (a.get("abbreviatedTitles") or []) if x],
    }


def kitsu_search(query: str, year=None) -> list[dict]:
    data = _kitsu_get(_KITSU_URL, {"filter[text]": query, "page[limit]": 5})
    return [_kitsu_entry(i) for i in data.get("data") or []]


def kitsu_by_id(kid) -> dict | None:
    kid = str(kid).strip()
    if kid.isdigit():
        d = _kitsu_get(f"{_KITSU_URL}/{kid}").get("data")
        return _kitsu_entry(d) if d else None
    items = _kitsu_get(_KITSU_URL, {"filter[slug]": kid}).get("data") or []
    return _kitsu_entry(items[0]) if items else None


# ── Jikan (MyAnimeList) ───────────────────────────────────────────────────────

_JIKAN_URL = "https://api.jikan.moe/v4/anime"


def _jikan_get(url: str, params: dict | None = None) -> dict:
    resp = JIKAN.request("GET", url, params=params, headers={"Accept": "application/json"})
    if resp.status_code == 404:
        return {}
    if resp.status_code != 200:
        raise ProviderError(f"Jikan: HTTP {resp.status_code}")
    return resp.json()


def _jikan_entry(a: dict) -> dict:
    year = a.get("year") or str((a.get("aired") or {}).get("from") or "")[:4] or None
    titles = [a.get("title_english"), a.get("title"),
              *[t.get("title") for t in (a.get("titles") or []) if t.get("type") != "Synonym"]]
    alt = [*(a.get("title_synonyms") or []),
           *[t.get("title") for t in (a.get("titles") or []) if t.get("type") == "Synonym"]]
    return {
        "title":  a.get("title_english") or a.get("title"),
        "year":   _year_str(year),
        "rating": make_rating(a.get("score"), 10, "jikan"),
        "plot":   clean_plot(a.get("synopsis")),
        "source": "jikan",
        "id":     str(a.get("mal_id")),
        "type":   a.get("type"),
        "poster": ((a.get("images") or {}).get("jpg") or {}).get("image_url"),
        "_titles": [t for t in titles if t],
        "_alt":    [t for t in alt if t],
    }


def jikan_search(query: str, year=None) -> list[dict]:
    data = _jikan_get(_JIKAN_URL, {"q": query, "limit": 5, "sfw": "true"})
    return [_jikan_entry(a) for a in data.get("data") or []]


def jikan_by_id(mal_id) -> dict | None:
    d = _jikan_get(f"{_JIKAN_URL}/{int(mal_id)}").get("data")
    return _jikan_entry(d) if d else None


# ── Anime fallback chain ──────────────────────────────────────────────────────

ANIME_PROVIDERS = [("anilist", ANILIST, anilist_search),
                   ("kitsu",   KITSU,   kitsu_search),
                   ("jikan",   JIKAN,   jikan_search)]


SYNONYM_WEIGHT = 0.95   # a match on a synonym only must not beat a main-title match


def score_candidates(title: str, year, cands: list[dict]) -> list[dict]:
    """Attach `score` to each candidate (never trusting API order), best first."""
    for c in cands:
        main = score_match(title, year, c.get("_titles") or [c.get("title")], c.get("year"))
        alt  = score_match(title, year, c.get("_alt") or [], c.get("year")) * SYNONYM_WEIGHT
        c["score"] = round(max(main, alt), 3)
    return sorted(cands, key=lambda c: -c["score"])


def anime_lookup(title: str, year) -> tuple[dict | None, dict | None, bool]:
    """Try AniList → Kitsu → Jikan. Returns (entry, best_rejected_guess, definitive)
    where `definitive` is True when at least one provider answered."""
    best, definitive = None, False
    for _name, prov, search in ANIME_PROVIDERS:
        if not prov.available():
            continue
        try:
            cands = score_candidates(title, year, search(title, year))
        except ProviderError:
            continue
        definitive = True
        if cands and cands[0]["score"] >= ACCEPT_SCORE:
            entry = dict(cands[0])
            entry["confidence"] = entry.pop("score")
            entry.pop("_titles", None)
            entry.pop("_alt", None)
            return entry, None, True
        if cands and (best is None or cands[0]["score"] > best[1]):
            best = (cands[0], cands[0]["score"])
    return None, _guess(best), definitive


def _guess(best) -> dict | None:
    if not best:
        return None
    e, score = best
    return {"title": e.get("title"), "year": e.get("year"), "source": e.get("source"),
            "id": e.get("id"), "confidence": score}


BY_ID = {"omdb": omdb_by_id, "anilist": anilist_by_id, "kitsu": kitsu_by_id, "jikan": jikan_by_id}
