import os
import http.server
import socketserver
import webbrowser

PORT = 8000

# Generate HTML dynamically
def generate_html():
    posters_path = "posters"
    poster_files = sorted(
        [f for f in os.listdir(posters_path) if f.endswith((".jpg", ".jpeg", ".png"))],
        key=str.lower
    )

    # Placeholder sizes for demo; replace with actual sizes if available
    poster_sizes = {
        poster: {"width": 200, "height": 300} for poster in poster_files
    }

    # Create grid items for all poster files
    grid_items = "".join(
        f"""
        <div class="grid-item" data-title="{poster.lower()}" data-size="{poster_sizes[poster]['width'] * poster_sizes[poster]['height']}">
            <img src="{posters_path}/{poster}" alt="{poster}" onclick="openLightbox('{posters_path}/{poster}')">
        </div>
        """
        for poster in poster_files
    )

    # Return full HTML
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Movie Poster Grid</title>
        <style>
            @font-face {{
                font-family: 'FiraSansCondensed';
                src: url('fonts/FiraSansCondensed-Black.ttf') format('truetype');
            }}
            body {{
                font-family: 'FiraSansCondensed', sans-serif;
                text-align: center;
                background-color: #4f4f4f; /* Dark mode background */
                margin: 0;
                padding: 20px;
                color: #ffffff; /* Dark mode text color */
                transition: background-color 0.3s, color 0.3s;
            }}
            body.light-mode {{
                background-color: #ffffff; /* Light mode background */
                color: #000000; /* Light mode text color */
            }}
            h1 {{
                font-family: 'FiraSansCondensed', sans-serif;
                font-size: 48px;
                color: #007bff;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.7);
                margin-bottom: 20px;
            }}
            .search-bar {{
                margin: 20px auto;
                padding: 10px;
                font-size: 16px;
                width: 80%;
                border: 2px solid #007bff;
                border-radius: 5px;
                outline: none;
            }}
            .grid-container {{
                display: flex;
                flex-wrap: wrap;
                justify-content: center;
                gap: 20px;
                padding: 10px;
            }}
            body.list-view .grid-container {{
                display: block; /* Change layout to block for list view */
            }}
            .grid-item {{
                width: 200px;
                flex-shrink: 0;
                transition: transform 0.3s ease;
            }}
            body.list-view .grid-item {{
                display: flex;
                align-items: center;
                margin-bottom: 10px;
            }}
            body.list-view .grid-item img {{
                width: 100px;
                margin-right: 10px;
            }}
            .grid-item:hover {{
                transform: scale(1.3);
            }}
            .grid-item img {{
                width: 100%;
                height: auto;
                object-fit: contain;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            }}
            .dark-mode-toggle {{
                position: fixed;
                width: 40px;
                height: 40px;
                cursor: pointer;
                background-size: contain;
                border: none;
                outline: none;
                transition: transform 0.2s ease;
            }}
            .dark-mode-toggle {{
                top: 20px;
                right: 20px;
                background: url('moon-icon.png') no-repeat center center;
            }}
            .dark-mode-toggle:hover{{
                transform: scale(1.2); /* Slightly enlarge the icon on hover */
            }}
            /* Lightbox CSS */
            #lightbox {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 9999;
            }}
            #lightbox.hidden {{
                display: none;
            }}
            #lightbox img {{
                max-width: 90%;
                max-height: 90%;
            }}
            #closeLightbox {{
                position: absolute;
                top: 20px;
                right: 20px;
                font-size: 24px;
                color: white;
                background: transparent;
                border: none;
                cursor: pointer;
            }}
        </style>
        <script>
            function toggleDarkMode() {{
                const body = document.body;
                body.classList.toggle('light-mode');
                const mode = body.classList.contains('light-mode') ? 'light' : 'dark';
                localStorage.setItem('theme', mode);
                document.getElementById('darkModeLabel').textContent = mode === 'dark' ? 'Dark Mode' : 'Light Mode';
            }}

            function openLightbox(imageSrc) {{
                const lightbox = document.getElementById('lightbox');
                const lightboxImage = document.getElementById('lightboxImage');
                lightboxImage.src = imageSrc;
                lightbox.classList.remove('hidden');
            }}

            function closeLightbox() {{
                const lightbox = document.getElementById('lightbox');
                const lightboxImage = document.getElementById('lightboxImage');
                lightbox.classList.add('hidden');
                lightboxImage.src = ''; // Clear the image
            }}

            document.addEventListener("DOMContentLoaded", function() {{
                const savedTheme = localStorage.getItem('theme');
                if (savedTheme === 'light') {{
                    document.body.classList.add('light-mode');
                }}

                const searchBar = document.getElementById('searchBar');
                const gridItems = document.querySelectorAll('.grid-item');

                searchBar.addEventListener('input', function() {{
                    const searchTerm = searchBar.value.toLowerCase();
                    gridItems.forEach(item => {{
                        const title = item.getAttribute('data-title');
                        if (title.includes(searchTerm)) {{
                            item.style.display = 'block';
                        }} else {{
                            item.style.display = 'none';
                        }}
                    }});
                }});
            }});
        </script>
    </head>
    <body>
        <div class="dark-mode-toggle">
            <label id="darkModeLabel" for="darkModeSwitch">Dark Mode</label>
            <input type="checkbox" id="darkModeSwitch" onchange="toggleDarkMode()">
        </div>
        <h1>Movie Posters</h1>
        <input type="text" id="searchBar" class="search-bar" placeholder="Search...">
        <div class="grid-container">
            {grid_items}
        </div>
        <div id="lightbox" class="hidden">
            <img id="lightboxImage" src="" alt="Lightbox Image">
            <button id="closeLightbox" onclick="closeLightbox()">Close</button>
        </div>
    </body>
    </html>
    """

# Define the HTTP request handler
class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            # Generate and serve the dynamic HTML
            html_content = generate_html()
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        else:
            # Serve other files as usual
            super().do_GET()

# Start the server
def start_server():
    os.chdir(os.path.dirname(__file__))  # Ensure the working directory is correct
    handler = MyRequestHandler
    with socketserver.TCPServer(("0.0.0.0", PORT), handler) as httpd:
        print(f"Serving at http://localhost:{PORT}")
        webbrowser.open(f"http://localhost:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    start_server()
