# Movie Poster Explorer

A personal web project to display and explore my favorite movies and series with a clean, Steam-inspired dark UI.
Every poster is handpicked, converted to `.webp`, and laid out in a responsive grid with lightbox previews, live metadata from APIs, and a full suite of personal tracking and organization tools.

---

## Features

### Library & Grid
- **Responsive Poster Grid** — paginated (50 per page), smooth hover animations, left-aligned with no last-row stretching
- **Adjustable Poster Size** — slider in the nav bar (100–300 px) with `−` / `+` buttons; persists across sessions via localStorage
- **A–Z order** — posters are sorted by display title with the same rules as Big Picture: case-insensitive, a leading *The / A / An* ignored (*The Dark Knight* sorts under D), punctuation stripped, natural number order (*2 Fast 2 Furious* before *10 Cloverfield Lane*, *Part 2* before *Part 10*), titles starting with a number first; ties by year, then filename
- **Status Filters** — filter the grid by All / Watched / Want to Watch / Unwatched
- **Dark / Light Mode** toggle
- **Multiple posters per movie are intentional** — alternate, international and variant posters (`1917 (2019).webp`, `1917 (2019) (2).webp`, …) are each their own poster with their own watch status, rating and collection. Nothing is ever merged or deleted; see *Stack Duplicates* for a tidier view

### Smart Search
- **Forgiving matching** — case, accents and punctuation are ignored, and a leading *The / A / An* doesn't matter (`dark knight` → *The Dark Knight*); `&` and `and` are interchangeable
- **Numbers ↔ words** — `ten` and `10` both find *10 Cloverfield Lane*, `twelve angry men` finds *12 Angry Men*, `blade runner 2049` finds a file named *blade runner twenty forty nine*
- **Roman numerals ↔ digits** — `star wars episode 3` finds *Episode III* (standalone numerals only, so *X-Men* isn't "10 Men")
- **Spacing-insensitive** — `clover field` → *Cloverfield*, `spiderman` / `spider man` → *Spider-Man*
- **Any word order** — every word you type just has to appear in the title; numeric titles like `1917`, `1984`, `2012` match as typed
- **Ranked results** — exact title, then titles starting with your query, then all-words matches, then typo-tolerant fuzzy matches
- **"Did you mean?"** — when nothing (or only fuzzy matches) turns up, up to three clickable suggestions appear above the grid (`intersteller` → *Interstellar*)
- Works in the normal grid, Group View, Stacked mode and with every status filter; input is debounced (~120 ms)

### Stack Duplicates
- **Stack / Show All toggle** in the nav — Stacked mode collapses every poster of the same movie (same title + year, i.e. the same metadata cache key) into one card; Show All restores every poster file. The choice is remembered (localStorage)
- **Stacked card** — shows the stack cover (the first poster alphabetically unless you've picked one), a **×N** count badge and an offset "pile" edge; it shows ✓ if *any* variant is watched and ♥ if any is Want to Watch. Single-poster movies look like normal cards
- **Expand inline** — click a stack to fan its variants out in a row below it (*Poster 2 of 4*, with a **Collapse** button); click a variant to open it in the lightbox. On phones the expanded row scrolls sideways
- **Pagination counts stacks**, so Stacked mode has fewer pages. Search, status filters and Recently Added work in both modes — a stack matches if any of its variants does
- **With Group View** — both toggles can be on at once; collections then show one card per movie inside them
- **Animated switch** — cards fly into their pile (or back out of it) when you toggle, using FLIP animations with the Web Animations API; off with reduced motion

### Recently Added
- **Recently Added Dropdown** — nav bar button reveals the 12 most recently modified posters, fetched live from the filesystem on every open so newly uploaded or manually added posters always appear at the top

### Theater Mode (Big Picture style)
- **Enter / exit** — the 📺 button in the nav, the **`B`** key, or **Start** on a gamepad. Goes fullscreen on enter (where the browser allows it) and leaves fullscreen on exit
- **Morphing transition** — uses the View Transitions API so the grid morphs into the rows (and the first poster morphs into its card when it's on screen); browsers without the API, or with reduced motion on, just switch instantly
- **Rows** — Recently Added, Want to Watch, Watched, Top Rated (your personal stars), one row per collection, then **Library** (every poster; one card per movie in Stacked mode). Built from the same data the grid uses, so nothing extra is fetched except the Recently Added list
- **Sorting** — A–Z by default (same rules as the grid). Every row except Recently Added (always newest first) follows the sort control in the top bar: **A–Z, Z–A, Year (newest), Year (oldest), Rating (high → low)** (normalised to 0–100 so IMDb x/10 and AniList/Kitsu x/100 sort together) and **Recently added**. `O` or gamepad **Y** cycles it (`S` stays "down" for WASD); the menu works with the arrow keys. A changed sort is remembered (localStorage); **Reset to A–Z** returns to the default
- **Focus** — the focused poster scales up with a glow; the page background crossfades to a heavily blurred, darkened copy of it, and its title, year, rating (with its source, e.g. *AniList 80/100*), your rating, watch status and plot fade in beside it
- **Controls**

  | Action | Keyboard | Gamepad | Touch / mouse |
  |---|---|---|---|
  | Move | `←` `↑` `↓` `→` or `W` `A` `S` `D` | D-pad or left stick | Swipe rows / hover, mouse wheel |
  | Open lightbox | `Enter` | **A** | Tap a focused card / click |
  | Cycle sort | `O` | **Y** | Sort button (top bar) |
  | Back (close lightbox, then exit) | `Esc` | **B** | ✕ Exit button |
  | Toggle theater | `B` | **Start** | 📺 nav button |

  Inside the lightbox, `←` / `→` (or the D-pad) step through the current row. In fullscreen, Chrome/Edge use the Keyboard Lock API so `Esc` closes the lightbox first instead of dropping out of fullscreen.
- **Smooth** — with keyboard, mouse or gamepad the rows move with GPU `transform`s; on touch they switch to native scrolling with `scroll-snap`. Only the focused poster and its immediate neighbours have their full-size images preloaded

### Needs Fix (metadata review)
- **⚠ nav button with a live count** of poster files without a solid match (the badge hides at 0). Opens a slide-in drawer on desktop, a full-screen sheet on phones
- **Checked per poster file**, not per stack: no match / not found, match confidence below 85%, missing year, rating or plot, and **Mismatched stacks** — posters that stack together but resolved to different titles or IDs, or where some matched and some didn't (grouped, with a *Mismatch* tag)
- **Tabs** — All · Not Found · Low Confidence · Missing Fields · Mismatched Stacks · Ignored. Each row shows the thumbnail (click → lightbox), filename, display title, and what it matched (title, year, provider, confidence) — or the closest rejected guess with a one-click **Use this**
- **Fix match** — inline search prefilled with the cleaned filename title; pick **Auto / OMDb / AniList / Kitsu** and choose from the top 5 (poster, title, year, type, rating). You can also paste an IMDb ID (`tt1234567`), an AniList, Kitsu or MyAnimeList URL, or `anilist:123`
- **Never renames files** — a fix is stored as a manual override in `metadata_overrides.json` (`{"<poster file>": {"source", "id"}}`). Overrides always win over auto-matching and are never retried, overwritten or flagged again. Optional **Also set display title**; **Apply to all posters in this stack** (on by default — untick it when variants are intentionally different, e.g. different seasons)
- **Ignore** marks a poster as intentionally unmatched (fan art, custom posters); un-ignore it from the **Ignored** tab
- Fixed rows animate out and the badge, grid cards and an open lightbox update without a reload. Rename and delete migrate / clean up overrides like they do watch status and ratings

### Fun Extras
- **"What should I watch?"** — the 🎲 *Pick for me* button spins a slot-machine reel through your Want to Watch posters, decelerates, lands on a random pick (glowing in that poster's colour), then opens its lightbox. If Want to Watch is empty it picks from your unwatched posters instead. `Esc` cancels
- **Poster colours** — each poster's dominant colour is extracted with Pillow when its thumbnail is built and cached in `posters/thumbs/colors.json`; it drives the grid hover glow, the theater focus glow, and the theater backdrop tint
- **3D tilt** — posters tilt subtly toward the cursor on hover (mouse/trackpad only; off for touch and reduced motion)
- **Stats page** (`/stats`, 📊 in the nav) — total posters and unique titles, watched count and percentage, Want to Watch count, average personal rating, posters by decade, your rating distribution, and the largest collections; every chart has a hover tooltip and a "Show as table" view

### Mobile & Installable App
- **Phone layout** — under 700 px the grid becomes fluid (the size slider sets the minimum column width), every touch target is at least 44 px, and hover-only controls are revealed for touch
- **Collapsible nav** — below ~1450 px (where the full toolbar no longer fits) the nav shrinks to brand + search + a ☰ menu holding filters, size, Group View, Stack, Recently Added, upload and theme
- **Bottom-sheet lightbox** — on phones the lightbox slides up from the bottom; **swipe left/right** on the poster to move between posters, **swipe down** to close
- **Installable (PWA)** — web app manifest + service worker (caches static assets only), so the site can be added to a phone home screen and opens full-screen (`display: standalone`)

### Poster Management
- **Drag-and-Drop Upload** — "+ Add Poster" opens a modal; drop or browse any jpg/png/webp; non-webp images are auto-converted via Pillow and saved as `.webp`
- **Inline Title Rename** — pencil icon on card hover; renames the file on disk and migrates all associated metadata, watch status, rating, and collection in one step
- **Delete Poster** — trash icon on card hover, or the "Delete poster" button in the lightbox; deletes the file, its thumbnail, and all associated state

### Lightbox
- **Full Metadata View** — title, year, rating on its native scale with its source (*IMDb 7.8/10*, *AniList 80/100*, *Kitsu 84.07/100*, *MAL 8.1/10*), plot, and a small *Metadata: OMDb / AniList / Kitsu / Jikan* line
- **Fits its content** — the dialog wraps the poster (sized from its real aspect ratio) and the sidebar exactly, up to 95% × 92% of the screen
- **Previous / Next** — `←` / `→` keys, the ‹ › buttons on the poster, or swipe on touch screens; steps through posters matching the current search + filter in ranked order (or the open collection in Group View). In Stacked mode it cycles through the current movie's variants first, then moves on to the next movie
- **Variant info** — for movies with several posters the sidebar shows *Poster 2 of 4* and a **Set as stack cover** button (saved to `stack_covers.json`)
- **Inline Metadata Editing** — edit title, year, and plot directly in the lightbox without leaving the page
- **Watched / Want to Watch** — two toggle buttons; marks a poster with a green ✓ badge (watched) or amber ♥ badge (want to watch); filters in the nav bar reflect the status immediately
- **Personal Star Rating** — 1–5 star rating stored locally per poster
- **Collection Assignment** — combo box with live filtering of existing groups; type a new name and press Enter to create a group on the fly; or browse and click existing groups
- **Appearance Customization** — gear icon opens a panel to change the sidebar font family, font size, text color, and background tint; settings persist via localStorage

### Collections & Group View
- **Movie Collections** — assign any poster to a named group via the lightbox combo box
- **Group View** — toggle in the nav bar; hides individual posters and shows one blurred proxy card per collection with a name overlay and poster count badge; click any proxy card to expand its posters inline

### Metadata & Performance
- **Multi-API Metadata Lookup** — **OMDb → AniList → Kitsu → Jikan**
  - **OMDb** — movies and series: exact title with the year, then without, then search + `difflib` best match, for each spelling variant (`spiderman` → *Spider-Man*, `xmen` → *X-Men*, `antman` → *Ant-Man*, `two` → `2` → `II`, `and` → `&`, a year left in the title, and a shorter word-prefix search for titles that lost their apostrophes)
  - **AniList** (GraphQL), then **Kitsu**, then **Jikan** (MyAnimeList) — anime fallbacks, tried only after OMDb gives a *definitive* not-found, never after an OMDb network error
- **One lookup per movie** — every variant poster of a movie shares one metadata cache key, so 10 alternate posters trigger one lookup; an in-flight lock means concurrent threads never query the same title, and no title is queried twice in one session
- **Negative cache** — a title nobody can match is stored as `{"not_found": true, "checked": …}` and not retried for 7 days (unless `build_cache.py --force`, Link Metadata, or a Needs Fix fix)
- **Circuit breakers** — every provider has a 3 s connect / 8 s read timeout and its own rate limit (AniList 25/min, Kitsu 1/s, Jikan 1/s); two consecutive connection failures skip that provider for 10 minutes with a single log line (`[Jikan] unreachable, skipping for 10 min`); HTTP 429 honours `Retry-After`
- **Smart Fuzzy Matching** — every result is scored with `difflib` against all of its titles (English, romaji, native, synonyms), never trusting API order; the year counts (exact year boosts, ±1 year or inside a series' run allowed). Below ~0.75 a result is rejected and stored as not-found instead of attaching the wrong show. The confidence and the provider's ID (imdbID / AniList id / Kitsu id) are saved with each match
- **Native rating scales** — ratings are stored as `{"value", "scale", "source"}`: IMDb x/10, AniList x/100 (`averageScore`, else `meanScore`), Kitsu x/100 (two decimals), Jikan/MAL x/10. Anything that sorts by rating normalises to 0–100; the display always shows the native value
- **Strict Filename Parsing**
  - Only a `(19xx)` / `(20xx)` parenthetical counts as the year — `1917 (2019)` → *1917*, 2019. A title that *is* a number (`1917`, `1984`, `2012`, `2046`) is never taken as the year
  - Variant tags — `(2)`, `(3)`, `xlg`, `ver2`, `v2`, `poster`, `intl`, `#4` — are stripped from the **displayed** title as well as the cache key, so `1917 (3).webp` shows as *1917*. Tags are matched as whole words only, so titles like *Vertigo* are safe
- **Local Metadata Cache** (`omdb_cache.json`) — avoids redundant API calls; auto-updated on backfill. One shared in-memory copy is written by both the lookup code and the routes, so background results are never overwritten
- **Background Backfill** — every movie still missing metadata is looked up in a daemon thread after a page load; never blocks page delivery. Uploaded posters that were cached with a raw filename title are looked up again automatically
- **In-Memory Grid Cache** — grid HTML is cached in memory and keyed by folder + cache file mtimes; subsequent requests return instantly with no disk I/O
- **Grid Thumbnails** — the grid loads ~400 px `.webp` thumbnails (quality 80, ~10× smaller than the originals) from `posters/thumbs/`; they're generated lazily on first request and on upload, regenerated on rename, and removed on delete. The lightbox always loads the full-size poster
- **Lazy, layout-stable images** — `loading="lazy"`, `decoding="async"`, explicit `width`/`height`, and `content-visibility: auto` on cards so off-screen posters cost nothing
- **Compositor-only animation** — only `transform` and `opacity` are animated; everything honours `prefers-reduced-motion`
- **Auto-shutdown Watchdog** — when run locally, every open tab checks in every 15 s and says goodbye on close; the server stops ~10 s after its last tab closes (3 min if a tab just goes quiet, e.g. throttled in the background; 30 min if no tab ever connects), so the silent launcher never leaves an orphan `python.exe`. Disable with `--no-watchdog` / `WATCHDOG=0` (always off on Render)
- **Flask-Compress** — gzip/brotli compression for faster asset delivery (optional)

---

## Tech Stack

| Technology | Purpose |
|---|---|
| `Python` + `Flask` | Backend server, routing, API integration, caching |
| `HTML5` + `Jinja2` | Page structure and template rendering |
| `CSS3` | Responsive grid, animations, dark/light mode, custom properties |
| `JavaScript` | Lightbox, pagination, smart search, upload, collections, group view, stacking, theater mode |
| View Transitions / Fullscreen / Gamepad / Keyboard Lock APIs | Theater mode morph, fullscreen, controller input, `Esc` handling in fullscreen |
| Web Animations API | Stack / unstack FLIP animations, pick-for-me reel |
| `OMDb API` | Movie/TV metadata (title, year, IMDb rating, plot) |
| `AniList GraphQL API` | Anime metadata, first anime fallback |
| `Kitsu API` (JSON:API) | Anime metadata, second anime fallback |
| `Jikan API` | Anime metadata from MyAnimeList, last fallback |
| `requests` | HTTP with per-provider timeouts, rate limits and circuit breakers |
| `difflib` | Fuzzy title matching between filenames and API results |
| `Pillow` | `.webp` conversion on upload, grid thumbnails, dominant-colour extraction |
| Web App Manifest + Service Worker | Installable PWA, static-asset caching |
| `Flask-Compress` | Optional gzip/brotli compression |
| `python-dotenv` | Loads `OMDB_API_KEY` from a local `.env` file |
| Batch / VBScript / PowerShell | One-click Windows launcher and Desktop / Start Menu shortcuts |
| `Git` / `GitHub` | Version control |

---

## Live Version

[https://movieproject-gr3a.onrender.com](https://movieproject-gr3a.onrender.com)

---

## Project Structure

```
MovieProject/
├── main.py                  # Flask app entry point, CLI flags, tab-close watchdog
├── routes.py                # Blueprint: grid, routes, backfill, Needs Fix, all API endpoints
├── data.py                  # Filename parsing, metadata cache, overrides, lookup orchestration
├── providers.py             # OMDb / AniList / Kitsu / Jikan clients, circuit breakers, matching, ratings
├── thumbs.py                # Grid thumbnail generation (also a CLI pre-builder)
├── build_cache.py           # CLI: prebuild metadata cache for all posters
├── rename_and_cache.py      # CLI: clean filenames + add (YYYY), rebuild cache
├── convert_to_webp.py       # CLI: batch convert JPG/PNG posters to .webp
├── backfill_poster_ids.py   # CLI: record stable OMDb/Jikan IDs per poster
├── omdb_cache.json          # Cached API responses (auto-updated, committed)
├── poster_ids.json          # Stable filename → OMDb/Jikan ID map (committed)
├── metadata_overrides.json  # Needs Fix links, display titles, ignores (committed)
├── poster_zoom.json         # Per-poster lightbox zoom         (local-only, git-ignored)
├── watched.json             # Per-poster watch status          (local-only, git-ignored)
├── personal_ratings.json    # Per-poster star ratings (1–5)    (local-only, git-ignored)
├── collections.json         # Per-poster collection names      (local-only, git-ignored)
├── stack_covers.json        # Chosen cover per stacked movie   (local-only, git-ignored)
├── .env                     # OMDB_API_KEY=…                   (local-only, git-ignored)
├── .env.example             # Template for .env
├── requirements.txt         # Python dependencies
├── README.md                # Project documentation (this file)
├── Launch MovieProject.bat          # One-click launcher (Windows)
├── Launch MovieProject (silent).vbs # Same, without a console window
├── create_shortcut.ps1              # Desktop + Start Menu shortcuts
├── server.log               # Silent launcher's server log     (local-only, git-ignored)
├── .vscode/launch.json      # F5 runs main.py with the .venv interpreter
│
├── posters/                 # Poster collection (.webp) — named "Title (YYYY).webp"
│   ├── Alien (1979).webp
│   ├── Dune Part Two (2024).webp
│   ├── … (hundreds more)
│   └── thumbs/              # Generated 400px grid thumbnails + colors.json (local-only, git-ignored)
│
├── static/
│   ├── style.css            # Grid, lightbox, theater, animations, dark/light mode, group view, mobile
│   ├── script.js            # All client-side logic (smart search, stacking, lightbox, theater, …)
│   ├── heartbeat.js         # Tab heartbeat for the watchdog
│   ├── sw.js                # Service worker (served at /sw.js; caches /static/* only)
│   ├── manifest.webmanifest # PWA manifest (served at /manifest.webmanifest)
│   ├── icon.ico             # Windows shortcut icon (16–256 px)
│   └── icons/               # App icons (192, 512, maskable, apple-touch)
│
├── templates/
│   ├── index.html           # Jinja2 template — injects poster grid
│   └── stats.html           # Library stats page (/stats)
```

---

## Quick Launch (Windows)

One-time setup, from the project folder:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\create_shortcut.ps1
```

- **Desktop / Start Menu** — `create_shortcut.ps1` adds a **Movie Poster Explorer** shortcut (with the app icon) to both. It runs the silent launcher, so no console window appears
- **Pin to taskbar** — right-click the Desktop shortcut (Windows 11: *Show more options*) → **Pin to taskbar**
- **Double-click** `Launch MovieProject.bat` for the same with a console window showing the server log (the silent `.vbs` writes it to `server.log` instead)
- The launcher starts `main.py` from `.venv`, waits until the server actually answers, then opens `http://127.0.0.1:5000`. If the app is already running it just opens the browser. If `.venv` is missing it tells you how to create it
- Close the last browser tab and the server stops by itself ~10 s later
- **VS Code** — press **F5**: `.vscode/launch.json` runs `main.py` with the `.venv` interpreter (a second configuration adds `--host 0.0.0.0 --no-watchdog` for phone access)

---

## Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/izzy4159/MovieProject.git
cd MovieProject

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
pip install flask-compress          # optional extra

# 4. Add your OMDb API key (free: https://www.omdbapi.com/apikey.aspx)
copy .env.example .env              # Windows   (cp .env.example .env on macOS / Linux)
# then edit .env:  OMDB_API_KEY=your_key
# (or set it in the environment instead: set OMDB_API_KEY=your_key)

# 5. Run the app
python main.py
# Opens http://127.0.0.1:5000 automatically
# Stops itself when the last browser tab closes unless you pass --no-watchdog
python main.py --no-watchdog        # keep it running
```

Without `OMDB_API_KEY` the app still runs (and prints a warning), but new posters won't get OMDb metadata.

### Command-line flags

| Flag | Env var | Default | Effect |
|---|---|---|---|
| `--host HOST` | `HOST` | `127.0.0.1` (`0.0.0.0` on Render) | Interface to bind. Use `0.0.0.0` for LAN / phone access |
| `--port PORT` | `PORT` | `5000` | Port to listen on |
| `--no-watchdog` | `WATCHDOG=0` | watchdog on | Keep running after the last browser tab closes |
| `--no-browser` | `OPEN_BROWSER=0` | browser opens | Don't open a browser tab on startup |

On Render (detected via the `RENDER` env var Render sets) the watchdog and browser auto-open are always off and the host defaults to `0.0.0.0`.

### View on your phone (same Wi-Fi)

```bash
python main.py --host 0.0.0.0 --no-watchdog
# Starting Movie Poster Grid → http://127.0.0.1:5000/
# On your phone (same Wi-Fi) → http://192.168.1.23:5000/
```

1. Run with `--host 0.0.0.0` (listen on your network, not just this PC) and `--no-watchdog` (phones pause background tabs, which would otherwise let the server stop).
2. Find your PC's IP: the startup log prints it, or run `ipconfig` and use the **IPv4 Address** of your Wi-Fi/Ethernet adapter (e.g. `192.168.1.23`).
3. On the phone, connected to the **same Wi-Fi**, open `http://<PC-IP>:5000`.
4. If it doesn't load, allow Python through the Windows Defender Firewall for **Private** networks (Windows usually prompts the first time; otherwise *Windows Security → Firewall & network protection → Allow an app through firewall*).
5. **Add to Home Screen** — on iPhone: Share → *Add to Home Screen*; it opens full-screen with no browser bar.
   On Android/Chrome, the full "Install app" prompt and service worker need HTTPS, so over plain `http://` on the LAN Chrome only adds a shortcut. The live Render site (HTTPS) installs as a full PWA.

---

## Utility Scripts

### `build_cache.py` — Pre-build metadata cache

Looks up every movie that has no metadata yet (one lookup per movie, OMDb → AniList → Kitsu → Jikan) before the app runs.
Useful after adding a large batch of new posters. Titles cached as not-found are skipped for 7 days; Needs Fix overrides are never touched.

```bash
python build_cache.py                  # look up everything still missing
python build_cache.py --force          # re-query every movie, including not-found titles
python build_cache.py --limit 20       # test on the first 20 movies
```

### `rename_and_cache.py` — Clean filenames and add year tags

Renames poster files to the standard `Title (YYYY).webp` format and updates the cache.

```bash
python rename_and_cache.py             # process all posters
python rename_and_cache.py --limit 10  # test on first 10
python rename_and_cache.py --sleep 1.2 # slower rate
```

### `thumbs.py` — Pre-build grid thumbnails

Thumbnails (and their dominant colours) are created on demand, but you can build them all up front (e.g. after a bulk import) so the first page load is instant.

```bash
python thumbs.py           # build missing / out-of-date thumbs
python thumbs.py --force   # rebuild everything
```

### `convert_to_webp.py` — Convert images to .webp

Converts `.jpg` / `.png` posters to `.webp` (quality 95, max 4K) and deletes originals.

```bash
python convert_to_webp.py
python convert_to_webp.py posters/     # specify a folder
```

---

## Notes

- No `.venv` is included — create your own locally.
- The OMDb key is never committed: it lives in `.env` (git-ignored) or the `OMDB_API_KEY` environment variable. On Render, set `OMDB_API_KEY` under the service's **Environment** settings.
- **The Render live site is effectively read-only.** Render's filesystem is ephemeral, so uploads, renames, deletes, ratings, watch status, collections, stack covers and Needs Fix fixes made there are lost on the next deploy or restart. Curate locally, then commit and push.
- `posters/thumbs/` is generated and git-ignored; it's rebuilt automatically wherever the app runs.
- `omdb_cache.json` is committed so the live site has metadata ready without API calls on first load.
- `watched.json`, `personal_ratings.json`, `collections.json` and `stack_covers.json` are local state files — not committed.
- `metadata_overrides.json` **is** committed: it's curation data (which record each poster is), so the live site gets your Needs Fix fixes.
- Poster collection is a personal curation — the goal is style and favorite picks, not completeness.
- Poster filenames follow the `Title (YYYY).webp` convention for accurate API matching. Variant suffixes like `(2)`, `xlg`, and `ver2` are stripped by the filename parser, so alternate posters of one movie share a cache entry (and a stack) while staying separate files.
