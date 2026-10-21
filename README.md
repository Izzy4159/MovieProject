# Movie Poster Explorer

A personal web project to display and explore my favorite movies and series with a clean, Steam-inspired dark UI.
Every poster is handpicked, converted to `.webp`, and laid out in a responsive grid with lightbox previews, live metadata from APIs, and a full suite of personal tracking and organization tools.

---

## Features

### Library & Grid
- **Responsive Poster Grid** — paginated (50 per page), smooth hover animations, left-aligned with no last-row stretching
- **Adjustable Poster Size** — slider in the nav bar (100–300 px) with `−` / `+` buttons; persists across sessions via localStorage
- **Search** — filter posters by title in real time
- **Status Filters** — filter the grid by All / Watched / Want to Watch / Unwatched
- **Dark / Light Mode** toggle

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

### Mobile & Installable App
- **Phone layout** — under 700 px the grid becomes fluid (the size slider sets the minimum column width), every touch target is at least 44 px, and hover-only controls are revealed for touch
- **Collapsible nav** — below ~1350 px (where the full toolbar no longer fits) the nav shrinks to brand + search + a ☰ menu holding filters, size, Group View, Recently Added, upload and theme
- **Bottom-sheet lightbox** — on phones the lightbox slides up from the bottom; **swipe left/right** on the poster to move between posters, **swipe down** to close
- **Installable (PWA)** — web app manifest + service worker (caches static assets only), so the site can be added to a phone home screen and opens full-screen (`display: standalone`)

### Poster Management
- **Drag-and-Drop Upload** — "+ Add Poster" opens a modal; drop or browse any jpg/png/webp; non-webp images are auto-converted via Pillow and saved as `.webp`
- **Inline Title Rename** — pencil icon on card hover; renames the file on disk and migrates all associated metadata, watch status, rating, and collection in one step
- **Delete Poster** — trash icon on card hover, or the "Delete poster" button in the lightbox; deletes the file, its thumbnail, and all associated state

### Lightbox
- **Full Metadata View** — title, year, IMDb rating, plot
- **Previous / Next** — `←` / `→` keys, the ‹ › buttons on the poster, or swipe on touch screens; steps through posters matching the current search + filter (or the open collection in Group View)
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
- **Strict Filename Parsing** — only `(19xx)`/`(20xx)` parentheticals count as years; variant tags like `(2)`, `xlg`, `ver2` are stripped so duplicate filenames share one cache entry
- **Local Metadata Cache** (`omdb_cache.json`) — avoids redundant API calls; auto-updated on backfill
- **Background Backfill** — up to 8 uncached posters fetched from OMDb per page load in a daemon thread; never blocks page delivery
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
| `JavaScript` | Lightbox, pagination, search, upload, collections, group view, theater mode |
| View Transitions / Fullscreen / Gamepad APIs | Theater mode morph, fullscreen, controller input |
| `OMDb API` | Movie/TV metadata (title, year, rating, plot) |
| `Jikan API` | Anime metadata from MyAnimeList |
| `difflib` | Fuzzy title matching between filenames and API results |
| `Pillow` | `.webp` conversion on upload, grid thumbnails |
| Web App Manifest + Service Worker | Installable PWA, static-asset caching |
| `Flask-Compress` | Optional gzip/brotli compression |
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
├── omdb_cache.json          # Cached API responses (auto-updated)
├── watched.json             # Per-poster watch status ("watched" / "want_to_watch")
├── personal_ratings.json    # Per-poster personal star ratings (1–5)
├── collections.json         # Per-poster group/collection assignments
├── requirements.txt         # Python dependencies
├── README.md                # Project documentation (this file)
│
├── posters/                 # Poster collection (.webp) — named "Title (YYYY).webp"
│   ├── Alien (1979).webp
│   ├── Dune Part Two (2024).webp
│   ├── … (hundreds more)
│   └── thumbs/              # Generated 400px grid thumbnails (git-ignored)
│
├── static/
│   ├── style.css            # Grid, lightbox, theater, animations, dark/light mode, group view, mobile
│   ├── script.js            # All client-side logic
│   ├── sw.js                # Service worker (served at /sw.js; caches /static/* only)
│   ├── manifest.webmanifest # PWA manifest (served at /manifest.webmanifest)
│   └── icons/               # App icons (192, 512, maskable, apple-touch)
│
├── templates/
│   └── index.html           # Jinja2 template — injects poster grid
│
└── __pycache__/             # Python bytecode cache
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
pip install flask-compress Pillow   # optional extras

# 4. Run the app
python main.py
# Opens http://127.0.0.1:5000 automatically
# Stops itself after 30 minutes unless you pass --no-watchdog
```

### Command-line flags

| Flag | Env var | Default | Effect |
|---|---|---|---|
| `--host HOST` | `HOST` | `127.0.0.1` (`0.0.0.0` on Render) | Interface to bind. Use `0.0.0.0` for LAN / phone access |
| `--port PORT` | `PORT` | `5000` | Port to listen on |
| `--no-watchdog` | `WATCHDOG=0` | watchdog on | Don't auto-shutdown after 30 minutes |
| `--no-browser` | `OPEN_BROWSER=0` | browser opens | Don't open a browser tab on startup |

On Render (detected via the `RENDER` env var Render sets) the watchdog and browser auto-open are always off and the host defaults to `0.0.0.0`.

### Open it on your phone (same Wi-Fi)

```bash
python main.py --host 0.0.0.0 --no-watchdog
# Starting Movie Poster Grid → http://127.0.0.1:5000/
# On your phone (same Wi-Fi) → http://192.168.1.23:5000/
```

1. Run with `--host 0.0.0.0` — the startup log prints your computer's LAN address.
2. Open that address on your phone. If it doesn't load, allow Python through the Windows Defender Firewall for **Private** networks (Windows usually prompts the first time).
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

Thumbnails are created on demand, but you can build them all up front (e.g. after a bulk import) so the first page load is instant.

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
- `posters/thumbs/` is generated and git-ignored; it's rebuilt automatically wherever the app runs.
- `omdb_cache.json` is committed so the live site has metadata ready without API calls on first load.
- `watched.json`, `personal_ratings.json`, and `collections.json` are local state files — not committed.
- Poster collection is a personal curation — the goal is style and favorite picks, not completeness.
- Poster filenames follow the `Title (YYYY).webp` convention for accurate API matching. Variant suffixes like `(2)`, `xlg`, and `ver2` are automatically stripped by the filename parser so duplicates share a single cache entry.
