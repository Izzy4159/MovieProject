#Only Run when New Posters are Added into the Folder -------------------------

import os
import subprocess

input_folder = "posters"

for filename in os.listdir(input_folder):
    if filename.lower().endswith((".jpg", ".jpeg", ".png")):
        base = os.path.splitext(filename)[0]
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(input_folder, base + ".webp")

        # Avoid re-converting
        if not os.path.exists(output_path):
            print(f"Converting: {filename} → {base}.webp")
            subprocess.run(["cwebp", "-q", "80", input_path, "-o", output_path])
