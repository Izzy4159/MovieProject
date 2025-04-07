import os
import http.server
import socketserver
import webbrowser
from omdb_fetcher import get_movie_info
import time

PORT = 8000

# NEW: Function to clean poster filenames for better API matches
def clean_title(raw_name):
    """
    Clean poster file names to make better title guesses for OMDb.
    Removes things like 'ver2', 'xlg', 'poster', etc.
    """
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
        # 🎯 Use cleaned-up title for better OMDb matching
        title_guess = clean_title(os.path.splitext(poster)[0])
        print(f"[DEBUG] Fetching metadata for: {title_guess}")

        movie_info = get_movie_info(title_guess)
        page = i // items_per_page + 1  # 50 items per page

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
            <img loading="lazy" src="posters/{poster}" alt="{poster}" onclick="openLightbox('posters/{poster}', this)">
        </div>
        '''

    print(f"[DEBUG] Took {time.time() - start_time:.2f}s to generate grid items")
    return grid_items

def generate_html():
    with open("templates/index.html", "r", encoding="utf-8") as file:
        template = file.read()
    return template.replace("{grid_items}", generate_grid_items())

class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            html = generate_html()
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            super().do_GET()

def start_server():
    os.chdir(os.path.dirname(__file__))
    with socketserver.TCPServer(("0.0.0.0", PORT), MyRequestHandler) as httpd:
        print(f"Serving at http://localhost:{PORT}")
        webbrowser.open(f"http://localhost:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    start_server()
