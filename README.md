# Movie Poster Explorer

A personal web project to display and explore my favorite movies and series with a clean, modern UI.
Every poster is handpicked, converted to `.webp`, and laid out in a responsive grid with lightbox previews and metadata pulled from live APIs.

---

## Features

- **Responsive Poster Grid** — paginated (50 per page), with smooth hover animations
- **Lightbox View** — click any poster to see title, year, IMDB rating, and plot
- **Dark / Light Mode** toggle
- **Search** to filter posters by title
- **Multi-API Metadata Lookup**
  - **OMDb API** — movies, TV shows, and series
  - **Jikan API** — anime titles via MyAnimeList
- **Smart Fuzzy Matching** — poster filenames are parsed and matched intelligently using `difflib`
- **Year-aware Filename Parsing** — filenames like `Alien (1979).webp` are parsed for better API accuracy
- **Local Metadata Cache** (`omdb_cache.json`) — avoids redundant API calls on repeat loads
- **Trickle Backfill** — fetches metadata for up to 8 uncached posters per page load in the background
- **Auto-close Watchdog** — Flask server shuts itself down when the browser tab is closed
- **Flask-Compress** — gzip/brotli compression for faster asset delivery (optional)

---

## Tech Stack

| Technology | Purpose |
|---|---|
| `Python` + `Flask` | Backend server, routing, API integration, caching |
| `HTML5` + `Jinja2` | Page structure and template rendering |
| `CSS3` | Responsive grid, animations, dark/light mode |
| `JavaScript` | Lightbox, pagination, search, heartbeat ping |
| `OMDb API` | Movie/TV metadata (title, year, rating, plot) |
| `Jikan API` | Anime metadata from MyAnimeList |
| `difflib` | Fuzzy title matching between filenames and API results |
| `Pillow` | Image conversion to `.webp` |
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
├── routes.py                # Blueprint: grid generation, poster serving, backfill
├── data.py                  # OMDb + Jikan API lookup, filename parsing, cache
├── build_cache.py           # CLI: prebuild metadata cache for all posters
├── rename_and_cache.py      # CLI: clean filenames + add (YYYY), rebuild cache
├── convert_to_webp.py       # CLI: batch convert JPG/PNG posters to .webp
├── omdb_cache.json          # Cached API responses (auto-updated)
├── requirements.txt         # Python dependencies
├── README.md                # Project documentation (this file)
├── project_structure.txt    # Snapshot of full folder structure
│
├── posters/                 # Poster collection (.webp) — named "Title (YYYY).webp"
│   ├── Alien (1979).webp
│   ├── Dune Part Two (2024).webp
│   └── … (hundreds more)
│
├── static/
│   ├── style.css            # Grid, animations, dark/light mode
│   └── script.js            # Lightbox, pagination, search, heartbeat
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
- Poster collection is a personal curation — the goal is style and favorite picks, not completeness.
- Poster filenames follow the `Title (YYYY).webp` convention for accurate API matching.
