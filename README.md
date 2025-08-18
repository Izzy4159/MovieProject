# 🎬 Movie Poster Explorer

Welcome to **Movie Poster Explorer**, A personal web project to display and explore my favorite movies and series with a **clean, modern UI**.  
Unlike other poster sites, the focus here is on **style + curation**: every poster is handpicked, converted to `.webp`, and laid out in a responsive grid with lightbox previews.

---

## 🌟 Features

- 🖼️ **Display of High-Resolution Movie Posters**  
  A collection of beautifully curated movie posters displayed in a grid layout, converted to `.webp` format for performance.

- 🔍 **Interactive Preview with Metadata**  
  Hover or click on posters to view movie metadata like title, rating, year, and plot.

- 🔁 **Fuzzy Matching & Multi-API Lookup**  
  Poster filenames are cleaned and matched intelligently using:
  - 🎬 **OMDb API** (for mainstream movies and series)
  - 📺 **Jikan API** (for anime titles via MyAnimeList)

- ⚙️ **Flask Backend with Caching**  
  Metadata is fetched dynamically and cached locally (`omdb_cache.json`) to speed up repeat loads and reduce API usage.

- 🌐 **Deployed on Render**  
  This project is live on the web using Render’s free hosting tier.

- 📱 **Responsive Design**  
  Clean layout built with HTML/CSS and mobile-first design in mind.

---

## ✨ Goal

The goal is to create a **beautiful, unique website** for browsing movie/anime posters that I like — not just a database clone.  
It emphasizes:

- 🎨 **Minimal + clean UI** (no clutter, smooth hover effects, and responsive design).  
- 🖼️ **High-quality poster images** with lightbox previews.  
- ⚡ **Metadata support** from APIs (OMDb + Jikan for anime).  
- 📱 **Mobile-friendly browsing** with pagination & search.  

---

## 🧰 Tech Stack

| Technology        | Purpose                                                        |
|-------------------|----------------------------------------------------------------|
| `Python` + `Flask`| Backend server, routing, caching, and API integration          |
| `HTML5`           | Page structure                                                 |
| `CSS3`            | Styling, responsive layout, animations, and dark/light mode    |
| `JavaScript`      | Lightbox, pagination, search, and interactivity                |
| `OMDb API`        | Fetches movie/TV metadata (title, year, rating, plot)          |
| `Jikan API`       | Fetches anime metadata from MyAnimeList                        |
| `difflib`         | Fuzzy matching between poster filenames and API results        |
| `Flask-Compress`  | Enables gzip/br compression for faster static file delivery    |
| `Render` / `Railway` / `Heroku` | Deployment platforms for hosting the project     |
| `Git` / `GitHub`  | Version control and project collaboration                      |

---

## 🚀 Live Version (Hosted on Render)

👉 [https://movieproject-gr3a.onrender.com](https://movieproject-gr3a.onrender.com)

---

## 📸 UI Features
 - Poster Grid – responsive, with hover animations.
 - Lightbox View – click a poster to see title, year, rating, and plot.
 - Dark/Light Mode toggle.
 - Pagination + Search to navigate large collections.

---

## 📝 Notes
 - No .venv is included in this repo (create your own local venv if needed).
 - Poster collection is personal curation → this site is about style + favorite movies rather than completeness.
 - .webp conversion via convert_to_webp.py keeps loading fast.

---

## 🗂️ Project Structure

```plaintext
MovieProject/
├── .DS_Store
├── .gitignore
├── convert_to_webp.py        # Utility to batch convert images to .webp
├── data.py                   # Fetch metadata (OMDb/Jikan) + caching
├── main.py                   # Flask app entry point
├── omdb_cache.json           # Cached API responses
├── project_structure.txt     # Snapshot of full folder structure
├── README.md                 # Project documentation (this file)
├── requirements.txt          # Python dependencies
├── routes.py                 # Routing + poster grid rendering
│
├── .idea/                    # PyCharm project files
│   └── inspectionProfiles/   # Code style/inspection settings
│
├── posters/                  # 🎨 Main poster collection (.webp)
│   ├── A Silent Voice.webp
│   ├── alien_xlg.webp
│   ├── avatar_the_way_of_water_xlg.webp
│   ├── breaking_bad_ver11_xlg.webp
│   ├── … (hundreds more posters)
│
├── static/                   # Frontend assets
│   ├── script.js             # Interactivity (pagination, dark mode, lightbox)
│   └── style.css             # CSS styles (grid, animations, clean UI)
│
├── templates/                # Jinja2 templates
│   └── index.html            # Injects posters + metadata into grid
│
├── TerminalBehavior/         # VSCode terminal settings
│   ├── terminal.integrated.copyOnSelection
│   └── terminal.integrated.rightClickBehavior
│
└── __pycache__/              # Python cache files
    ├── data.cpython-312.pyc
    ├── omdb_fetcher.cpython-312.pyc
    └── routes.cpython-312.pyc
