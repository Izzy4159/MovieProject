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

### Poster Management
- **Drag-and-Drop Upload** — "+ Add Poster" opens a modal; drop or browse any jpg/png/webp; non-webp images are auto-converted via Pillow and saved as `.webp`
- **Inline Title Rename** — pencil icon on card hover; renames the file on disk and migrates all associated metadata, watch status, rating, and collection in one step
- **Delete Poster** — remove a poster from the lightbox; deletes the file and cleans up all associated state

### Lightbox
- **Full Metadata View** — title, year, IMDb rating, plot
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
- **Auto-close Watchdog** — Flask server shuts itself down when the browser tab is closed
- **Flask-Compress** — gzip/brotli compression for faster asset delivery (optional)

---

## Tech Stack

| Technology | Purpose |
|---|---|
| `Python` + `Flask` | Backend server, routing, API integration, caching |
| `HTML5` + `Jinja2` | Page structure and template rendering |
| `CSS3` | Responsive grid, animations, dark/light mode, custom properties |
| `JavaScript` | Lightbox, pagination, search, upload, collections, group view |
| `OMDb API` | Movie/TV metadata (title, year, rating, plot) |
| `Jikan API` | Anime metadata from MyAnimeList |
| `difflib` | Fuzzy title matching between filenames and API results |
| `Pillow` | Image conversion to `.webp` on upload |
| `Flask-Compress` | Optional gzip/brotli compression |
| `Git` / `GitHub` | Version control |

---

## Live Version

[https://movieproject-gr3a.onrender.com](https://movieproject-gr3a.onrender.com)

---

## Project Structure

```
MovieProject/
├── main.py                  # Flask app entry point + browser watchdog
├── routes.py                # Blueprint: grid, routes, backfill, all API endpoints
├── data.py                  # OMDb + Jikan API lookup, filename parsing, cache
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
│   └── … (hundreds more)
│
├── static/
│   ├── style.css            # Grid, lightbox, animations, dark/light mode, group view
│   └── script.js            # All client-side logic
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
# Close the browser tab to shut down the server
```

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

### `convert_to_webp.py` — Convert images to .webp

Converts `.jpg` / `.png` posters to `.webp` (quality 95, max 4K) and deletes originals.

```bash
python convert_to_webp.py
python convert_to_webp.py posters/     # specify a folder
```

---

## Notes

- No `.venv` is included — create your own locally.
- `omdb_cache.json` is committed so the live site has metadata ready without API calls on first load.
- `watched.json`, `personal_ratings.json`, and `collections.json` are local state files — not committed.
- Poster collection is a personal curation — the goal is style and favorite picks, not completeness.
- Poster filenames follow the `Title (YYYY).webp` convention for accurate API matching. Variant suffixes like `(2)`, `xlg`, and `ver2` are automatically stripped by the filename parser so duplicates share a single cache entry.
