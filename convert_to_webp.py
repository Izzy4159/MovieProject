#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from pathlib import Path

from PIL import Image

# ----------------- CONFIG -----------------
INPUT_DIR = Path("posters")     # change if needed
QUALITY = 95                    # webp quality (0-100, 95 = near-lossless)
MAX_DIM = 3840                  # max width/height (≈ 4K)
RECURSIVE = True                # walk subfolders
DELETE_ORIGINALS = True         # delete source after successful convert
OVERWRITE_WEBP = False          # re-create even if .webp exists
# ------------------------------------------

VALID_EXTS = {".jpg", ".jpeg", ".png"}

def resize_if_needed(img: Image.Image) -> Image.Image:
    """Resize image to fit within MAX_DIM (keep aspect ratio)."""
    w, h = img.size
    if max(w, h) <= MAX_DIM:
        return img  # no resizing
    scale = MAX_DIM / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)

def convert_with_pillow(src: Path, dst: Path, quality: int) -> bool:
    try:
        with Image.open(src) as im:
            # Convert to RGB/ RGBA if needed
            if im.mode in ("P", "LA"):
                im = im.convert("RGBA")
            else:
                im = im.convert("RGB")

            # Resize if bigger than 4K
            im = resize_if_needed(im)

            im.save(dst, "WEBP", quality=quality, method=6)
        return True
    except Exception as e:
        print(f"❌ Pillow convert failed for {src.name}: {e}")
        return False

def iter_files(root: Path):
    if RECURSIVE:
        yield from (p for p in root.rglob("*") if p.is_file())
    else:
        yield from (p for p in root.iterdir() if p.is_file())

def main():
    total = converted = skipped = deleted = failed = 0

    for src in iter_files(INPUT_DIR):
        if src.suffix.lower() not in VALID_EXTS:
            continue
        total += 1
        dst = src.with_suffix(".webp")

        if dst.exists() and not OVERWRITE_WEBP:
            print(f"🟡 Skipping (exists): {dst.name}")
            if DELETE_ORIGINALS:
                src.unlink()
            skipped += 1
            continue

        print(f"Converting {src.name} → {dst.name}")
        ok = convert_with_pillow(src, dst, QUALITY)

        if ok:
            converted += 1
            if DELETE_ORIGINALS:
                src.unlink()
                deleted += 1
                print(f"✅ Converted & deleted {src.name}")
        else:
            failed += 1

    print("\nSUMMARY")
    print(f"Total: {total}, Converted: {converted}, Skipped: {skipped}, Deleted: {deleted}, Failed: {failed}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        INPUT_DIR = Path(sys.argv[1])
    main()
