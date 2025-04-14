import os
import subprocess

input_folder = "posters"

for filename in os.listdir(input_folder):
    file_path = os.path.join(input_folder, filename)
    name, ext = os.path.splitext(filename)
    ext = ext.lower()

    # Convert only if it's a jpg/jpeg/png and webp doesn't already exist
    if ext in (".jpg", ".jpeg", ".png"):
        webp_path = os.path.join(input_folder, name + ".webp")

        if not os.path.exists(webp_path):
            print(f"Converting: {filename} → {name}.webp")
            result = subprocess.run(["cwebp", "-q", "80", file_path, "-o", webp_path])

            if result.returncode == 0:
                print(f"✅ Converted and now deleting original: {filename}")
                os.remove(file_path)
            else:
                print(f"❌ Failed to convert: {filename}")
        else:
            print(f"🟡 Skipping {filename} — .webp already exists")
            os.remove(file_path)  # Still remove the original even if webp already exists

    else:
        # Do nothing for .webp or other formats
        continue
