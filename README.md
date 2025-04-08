# 🎬 Movie Poster Explorer

Welcome to **Movie Poster Explorer**, a web-based project that allows users to visually browse high-quality movie posters in an interactive and user-friendly layout. This is a fun and creative project that showcases classic and modern movie posters, organized neatly with preview functionality.

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

## 🧰 Tech Stack

| Technology     | Purpose                                               |
|----------------|-------------------------------------------------------|
| `Python` + `Flask` | Backend server to serve posters and metadata     |
| `HTML5`        | Page structure                                        |
| `CSS3`         | Styling and responsive layout                         |
| `JavaScript`   | Lightbox, pagination, and interactivity               |
| `OMDb API`     | Pulls movie/TV data like title, rating, and plot      |
| `Jikan API`    | Pulls anime metadata from MyAnimeList                |
| `difflib`      | Used for fuzzy title matching with search results     |
| `Render`       | Cloud deployment platform                             |
| `Git` / `GitHub` | Version control and collaboration                  |

---

## 🚀 Live Version (Hosted on Render)

👉 [https://movieproject-gr3a.onrender.com](https://movieproject-gr3a.onrender.com)

---

## 🗂️ Project Structure

```plaintext
MovieProject/
├── main.py                   # Flask entry point (runs the app)
├── data.py                   # OMDb + Jikan API integration with caching and fuzzy matching
├── routes.py                 # Poster grid logic + file cleaning + HTML generation
├── omdb_cache.json           # Cached metadata from API calls
├── posters/                  # Movie poster images (converted to .webp format)
├── static/                   # Static files served by Flask                
│   ├── style.css             # CSS stylesheet
│   └── script.js             # JavaScript for dark mode, pagination, lightbox
├── templates/
│   └── index.html            # HTML template that injects `grid_items`
├── requirements.txt          # Python dependencies for Flask + requests
└── README.md                 # Project overview and documentation
