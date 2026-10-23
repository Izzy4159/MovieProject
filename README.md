# Movie Poster Explorer

A personal web project to display and explore my favorite movies and series with a clean, Steam-inspired dark UI.
Every poster is handpicked, converted to `.webp`, and laid out in a responsive grid with lightbox previews, live metadata from APIs, and a full suite of personal tracking and organization tools.

---

## Features

### Library & Grid
- **Responsive Poster Grid** — paginated (50 per page), smooth hover animations, left-aligned with no last-row stretching
- **Adjustable Poster Size** — slider in the nav bar (100–300 px) with `−` / `+` buttons; persists across sessions via localStorage
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
- **Rows** — Recently Added, Want to Watch, Watched, Top Rated (your personal stars), then one row per collection. Built from the same data the grid uses, so nothing extra is fetched except the Recently Added list
- **Focus** — the focused poster scales up with a glow; the page background crossfades to a heavily blurred, darkened copy of it, and its title, year, IMDb rating, your rating, watch status and plot fade in beside it
- **Controls**

  | Action | Keyboard | Gamepad | Touch / mouse |
  |---|---|---|---|
  | Move | `←` `↑` `↓` `→` or `W` `A` `S` `D` | D-pad or left stick | Swipe rows / hover, mouse wheel |
  | Open lightbox | `Enter` | **A** | Tap a focused card / click |
  | Back (close lightbox, then exit) | `Esc` | **B** | ✕ Exit button |
  | Toggle theater | `B` | **Start** | 📺 nav button |

  Inside the lightbox, `←` / `→` (or the D-pad) step through the current row. In fullscreen, Chrome/Edge use the Keyboard Lock API so `Esc` closes the lightbox first instead of dropping out of fullscreen.
- **Smooth** — with keyboard, mouse or gamepad the rows move with GPU `transform`s; on touch they switch to native scrolling with `scroll-snap`. Only the focused poster and its immediate neighbours have their full-size images preloaded

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
- **Full Metadata View** — title, year, IMDb rating, plot
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
- **Multi-API Metadata Lookup**
  - **OMDb API** — movies, TV shows, and series (title, year, IMDb rating, plot)
  - **Jikan API** — anime titles via MyAnimeList as a fallback
- **Smart Fuzzy Matching** — filenames are parsed and matched using `difflib` with year-aware logic
- **Strict Filename Parsing**
  - Only a `(19xx)` / `(20xx)` parenthetical counts as the year — `1917 (2019)` → *1917*, 2019. A title that *is* a number (`1917`, `1984`, `2012`, `2046`) is never taken as the year
  - Variant tags — `(2)`, `(3)`, `xlg`, `ver2`, `v2`, `poster`, `intl`, `#4` — are stripped from the **displayed** title as well as the cache key, so `1917 (3).webp` shows as *1917*. Tags are matched as whole words only, so titles like *Vertigo* are safe
- **Local Metadata Cache** (`omdb_cache.json`) — avoids redundant API calls; auto-updated on backfill. One shared in-memory copy is written by both the lookup code and the routes, so background results are never overwritten
- **Background Backfill** — up to 8 uncached posters fetched from OMDb per page load in a daemon thread (one batch at a time); never blocks page delivery. Uploaded posters that were cached with a raw filename title and no year are looked up again automatically
- **In-Memory Grid Cache** — grid HTML is cached in memory and keyed by folder + cache file mtimes; subsequent requests return instantly with no disk I/O
- **Grid Thumbnails** — the grid loads ~400 px `.webp` thumbnails (quality 80, ~10× smaller than the originals) from `posters/thumbs/`; they're generated lazily on first request and on upload, regenerated on rename, and removed on delete. The lightbox always loads the full-size poster
- **Lazy, layout-stable images** — `loading="lazy"`, `decoding="async"`, explicit `width`/`height`, and `content-visibility: auto` on cards so off-screen posters cost nothing
- **Compositor-only animation** — only `transform` and `opacity` are animated; everything honours `prefers-reduced-motion`
- **Auto-shutdown Watchdog** — when run locally, the server stops itself 30 minutes after startup; disable with `--no-watchdog` / `WATCHDOG=0` (always off on Render)
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
| `OMDb API` | Movie/TV metadata (title, year, rating, plot) |
| `Jikan API` | Anime metadata from MyAnimeList |
| `difflib` | Fuzzy title matching between filenames and API results |
| `Pillow` | `.webp` conversion on upload, grid thumbnails, dominant-colour extraction |
| Web App Manifest + Service Worker | Installable PWA, static-asset caching |
| `Flask-Compress` | Optional gzip/brotli compression |
| `python-dotenv` | Loads `OMDB_API_KEY` from a local `.env` file |
| `Git` / `GitHub` | Version control |

---

## Live Version

[https://movieproject-gr3a.onrender.com](https://movieproject-gr3a.onrender.com)

---

## Project Structure

```
MovieProject/
├── main.py                  # Flask app entry point, CLI flags, shutdown watchdog
├── routes.py                # Blueprint: grid, routes, backfill, all API endpoints
├── data.py                  # OMDb + Jikan API lookup, filename parsing, cache
├── thumbs.py                # Grid thumbnail generation (also a CLI pre-builder)
├── build_cache.py           # CLI: prebuild metadata cache for all posters
├── rename_and_cache.py      # CLI: clean filenames + add (YYYY), rebuild cache
├── convert_to_webp.py       # CLI: batch convert JPG/PNG posters to .webp
├── backfill_poster_ids.py   # CLI: record stable OMDb/Jikan IDs per poster
├── omdb_cache.json          # Cached API responses (auto-updated, committed)
├── poster_ids.json          # Stable filename → OMDb/Jikan ID map (committed)
├── poster_zoom.json         # Per-poster lightbox zoom (committed)
├── watched.json             # Per-poster watch status          (local-only, git-ignored)
├── personal_ratings.json    # Per-poster star ratings (1–5)    (local-only, git-ignored)
├── collections.json         # Per-poster collection names      (local-only, git-ignored)
├── stack_covers.json        # Chosen cover per stacked movie   (local-only, git-ignored)
├── .env                     # OMDB_API_KEY=…                   (local-only, git-ignored)
├── .env.example             # Template for .env
├── requirements.txt         # Python dependencies
├── README.md                # Project documentation (this file)
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
│   ├── sw.js                # Service worker (served at /sw.js; caches /static/* only)
│   ├── manifest.webmanifest # PWA manifest (served at /manifest.webmanifest)
│   └── icons/               # App icons (192, 512, maskable, apple-touch)
│
├── templates/
│   ├── index.html           # Jinja2 template — injects poster grid
│   └── stats.html           # Library stats page (/stats)
```

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
# Stops itself after 30 minutes unless you pass --no-watchdog
python main.py --no-watchdog        # keep it running
```

Without `OMDB_API_KEY` the app still runs (and prints a warning), but new posters won't get OMDb metadata.

### Command-line flags

| Flag | Env var | Default | Effect |
|---|---|---|---|
| `--host HOST` | `HOST` | `127.0.0.1` (`0.0.0.0` on Render) | Interface to bind. Use `0.0.0.0` for LAN / phone access |
| `--port PORT` | `PORT` | `5000` | Port to listen on |
| `--no-watchdog` | `WATCHDOG=0` | watchdog on | Don't auto-shutdown after 30 minutes |
| `--no-browser` | `OPEN_BROWSER=0` | browser opens | Don't open a browser tab on startup |

On Render (detected via the `RENDER` env var Render sets) the watchdog and browser auto-open are always off and the host defaults to `0.0.0.0`.

### View on your phone (same Wi-Fi)

```bash
python main.py --host 0.0.0.0 --no-watchdog
# Starting Movie Poster Grid → http://127.0.0.1:5000/
# On your phone (same Wi-Fi) → http://192.168.1.23:5000/
```

1. Run with `--host 0.0.0.0` (listen on your network, not just this PC) and `--no-watchdog` (don't stop after 30 minutes).
2. Find your PC's IP: the startup log prints it, or run `ipconfig` and use the **IPv4 Address** of your Wi-Fi/Ethernet adapter (e.g. `192.168.1.23`).
3. On the phone, connected to the **same Wi-Fi**, open `http://<PC-IP>:5000`.
4. If it doesn't load, allow Python through the Windows Defender Firewall for **Private** networks (Windows usually prompts the first time; otherwise *Windows Security → Firewall & network protection → Allow an app through firewall*).
3. **Add to Home Screen** — on iPhone: Share → *Add to Home Screen*; it opens full-screen with no browser bar.
   On Android/Chrome, the full "Install app" prompt and service worker need HTTPS, so over plain `http://` on the LAN Chrome only adds a shortcut. The live Render site (HTTPS) installs as a full PWA.

---

## Utility Scripts

### `build_cache.py` — Pre-build metadata cache

Scans every poster and fetches metadata from OMDb/Jikan before the app runs.
Useful after adding a large batch of new posters.

```bash
python build_cache.py                  # fetch all missing entries
python build_cache.py --force          # re-fetch everything
python build_cache.py --limit 20       # test on first 20 posters
python build_cache.py --sleep 1.2      # slower rate to avoid API limits
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
- **The Render live site is effectively read-only.** Render's filesystem is ephemeral, so uploads, renames, deletes, ratings, watch status, collections and stack covers made there are lost on the next deploy or restart. Curate locally, then commit and push.
- `posters/thumbs/` is generated and git-ignored; it's rebuilt automatically wherever the app runs.
- `omdb_cache.json` is committed so the live site has metadata ready without API calls on first load.
- `watched.json`, `personal_ratings.json`, `collections.json` and `stack_covers.json` are local state files — not committed.
- Poster collection is a personal curation — the goal is style and favorite picks, not completeness.
- Poster filenames follow the `Title (YYYY).webp` convention for accurate API matching. Variant suffixes like `(2)`, `xlg`, and `ver2` are stripped by the filename parser, so alternate posters of one movie share a cache entry (and a stack) while staying separate files.
