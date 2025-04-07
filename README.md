# 🎬 Movie Poster Explorer

Welcome to **Movie Poster Explorer**, a web-based project that allows users to visually browse high-quality movie posters in an interactive and user-friendly layout. This is a fun and creative project that showcases classic and modern movie posters, organized neatly with preview functionality.

---

## 🌟 Features

- 🖼️ **Display of High-Resolution Movie Posters**  
  A collection of beautifully curated movie posters displayed in a grid layout.

- 🔍 **Interactive Preview**  
  Click on posters to view movie metadata (title, rating, year, plot).  
  *(Fetched dynamically from the OMDb API)*

- 📱 **Responsive Design**  
  Clean layout built with HTML/CSS and mobile-first design in mind.

- ⚙️ **Flask Backend**  
  Python/Flask used to generate dynamic HTML using Jinja templates.

---

## 🧰 Tech Stack

| Technology | Purpose |
|------------|---------|
| `Python` + `Flask` | Backend server to serve posters and metadata |
| `HTML5`    | Page structure |
| `CSS3`     | Styling and responsive layout |
| `JavaScript` | Lightbox and interactivity |
| `OMDb API` | Pulls movie data like title, rating, and plot |
| `Git` / `GitHub` | Version control and project tracking |
| `Render`   | Deploys the live version (cloud hosting) |

---

## 🚀 Live Version (Hosted on Render)

👉 [https://movieproject-gr3a.onrender.com](https://movieproject-gr3a.onrender.com)

---

## 🗂️ Project Structure

```plaintext
MovieProject/
├── posters/               # Movie poster images
├── templates/
│   └── index.html         # Main HTML template with injected grid items
├── styles.css             # Custom styles
├── main.py                # Flask app entry point
├── omdb_fetcher.py        # OMDb API logic + JSON caching
├── requirements.txt       # Python dependencies
└── README.md              # This file


