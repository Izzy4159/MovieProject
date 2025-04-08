import os
import time
from flask import Blueprint, send_from_directory
from omdb_fetcher import get_movie_info

main_bp = Blueprint("main", __name__)

def clean_title(raw_name):
    ignore_words = {"ver", "xlg", "poster", "final", "intl", "cover"}
    parts = raw_name.replace("_", " ").split()
    cleaned = [word for word in parts if not any(word.lower().startswith(ig) for ig in ignore_words)]
    return " ".join(cleaned).strip()

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
        movie_info = get_movie_info(title_guess)
        page = i // items_per_page + 1

        # Convert original poster filename to .webp
        base_name = os.path.splitext(poster)[0]
        webp_filename = base_name + ".webp"

        if movie_info:
            data_attrs = f'''
                data-title="{movie_info['title']}"
                data-year="{movie_info['year']}"
                data-rating="{movie_info['rating']}"
                data-plot="{movie_info['plot']}"
            '''
        else:
            data_attrs = f'''
                data-title="{title_guess}"
                data-year="N/A"
                data-rating="N/A"
                data-plot="No plot available"
            '''

        grid_items += f'''
        <div class="grid-item page-{page}" style="display: none;" {data_attrs.strip()}>
            <img loading="lazy" src="/posters/{webp_filename}" alt="{base_name}" onclick="openLightbox('/posters/{webp_filename}', this)">
        </div>
        '''

    print(f"[DEBUG] Took {time.time() - start_time:.2f}s to generate grid items")
    return grid_items

from flask import render_template
@main_bp.route("/")
def index():
    grid_html = generate_grid_items()
    return render_template("index.html", grid_items=grid_html)

@main_bp.route("/posters/<path:filename>")
def poster(filename):
    return send_from_directory("posters", filename)
