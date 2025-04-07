import os
import time
from flask import Flask, render_template_string, send_from_directory
from omdb_fetcher import get_movie_info

app = Flask(__name__, static_folder='posters')

# Function to clean file names
def clean_title(raw_name):
    ignore_words = {"ver", "xlg", "poster", "final", "intl", "cover"}
    parts = raw_name.replace("_", " ").split()
    cleaned = [word for word in parts if not any(word.lower().startswith(ig) for ig in ignore_words)]
    return " ".join(cleaned).strip()

# 🖼️ Generate poster grid
def generate_grid_items():
    start_time = time.time()
    posters_path = "posters"
    poster_files = sorted(
        [f for f in os.listdir(posters_path) if f.endswith((".jpg", ".jpeg", ".png"))],
        key=str.lower
    )

    items_per_page = 50
    grid_items = ""

    for i, poster in enumerate(poster_files):
        title_guess = clean_title(os.path.splitext(poster)[0])
        print(f"[DEBUG] Fetching metadata for: {title_guess}")

        movie_info = get_movie_info(title_guess)
        page = i // items_per_page + 1

        if movie_info:
            data_attrs = f'''
                data-title="{movie_info['title']}"
                data-year="{movie_info['year']}"
                data-rating="{movie_info['rating']}"
                data-plot="{movie_info['plot']}"
            '''
        else:
            print(f"[WARN] No metadata found for: {title_guess}")
            data_attrs = f'''
                data-title="{title_guess}"
                data-year="N/A"
                data-rating="N/A"
                data-plot="No plot available"
            '''

        grid_items += f'''
        <div class="grid-item page-{page}" style="display: none;" {data_attrs.strip()}>
            <img loading="lazy" src="/posters/{poster}" alt="{poster}" onclick="openLightbox('/posters/{poster}', this)">
        </div>
        '''

    print(f"[DEBUG] Took {time.time() - start_time:.2f}s to generate grid items")
    return grid_items

@app.route("/")
def index():
    with open("templates/index.html", "r", encoding="utf-8") as file:
        template = file.read()
    return render_template_string(template.replace("{grid_items}", generate_grid_items()))

@app.route("/posters/<path:filename>")
def poster(filename):
    return send_from_directory("posters", filename)

# 🔥 Needed for Render deployment
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
