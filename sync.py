#!/usr/bin/env python3
"""
Entheogenous Portfolio — Media Sync & Optimization
Handles high-res photos, 1080x2400 mobile wallpapers, and motion loops.
Generates responsive thumbnails, updates index.html, and deploys to GitHub Pages.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

PORTFOLIO_DIR = Path(__file__).resolve().parent
PHOTOS_DIR = PORTFOLIO_DIR / "photos"
MOBILE_DIR = PHOTOS_DIR / "Mobile"
MOBILE_FULL_DIR = MOBILE_DIR / "full"
MOBILE_THUMBS_DIR = MOBILE_DIR / "thumbs"
PHOTO_THUMBS_DIR = PHOTOS_DIR / "thumbs"
MOTIONS_DIR = PORTFOLIO_DIR / "motions"
INDEX_FILE = PORTFOLIO_DIR / "index.html"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}


def parse_filename(file_path: Path):
    """Extract clean title and year from filename or metadata."""
    stem = file_path.stem
    year = None
    
    # Check if starts with a 4-digit year like "2026_" or "2025-"
    start_year_match = re.match(r"^(\d{4})[_\-\s]+(.*)", stem)
    if start_year_match:
        year = start_year_match.group(1)
        clean = start_year_match.group(2)
    else:
        # Check if ends with a 4-digit year like "_2026"
        end_year_match = re.search(r"[_\-\s](\d{4})$", stem)
        if end_year_match:
            year = end_year_match.group(1)
            clean = stem[:end_year_match.start()]
        else:
            # Check MandelBrowser_YYMMDD pattern
            mb_match = re.match(r"MandelBrowser_(\d{2})(\d{2})(\d{2})", stem)
            if mb_match:
                year = f"20{mb_match.group(1)}"
                clean = stem
            else:
                clean = re.sub(r"^[\d\s_\-]+", "", stem)
                mtime = file_path.stat().st_mtime
                year = str(datetime.fromtimestamp(mtime).year)
    
    title = re.sub(r"[_\-]+", " ", clean).strip().title()
    if not title or title.startswith("Mandelbrowser"):
        title = "Untitled"
    return title, year


def optimize_photo_thumb(orig_path: Path) -> Path:
    """Generate a responsive 1200px thumbnail for photos."""
    PHOTO_THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    thumb_path = PHOTO_THUMBS_DIR / f"{orig_path.stem}_thumb.jpg"
    if thumb_path.exists() and thumb_path.stat().st_mtime >= orig_path.stat().st_mtime:
        return thumb_path
    
    cmd = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", "-Z", "1200", str(orig_path), "--out", str(thumb_path)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return thumb_path


def process_mobile_wallpapers():
    """Convert raw Mobile PNGs to web JPEGs and thumbnails."""
    if not MOBILE_DIR.exists():
        return []
    
    MOBILE_FULL_DIR.mkdir(parents=True, exist_ok=True)
    MOBILE_THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Collect all PNGs or JPGs in Mobile directory (excluding full and thumbs subdirs)
    raw_files = [
        p for p in sorted(MOBILE_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and not p.name.startswith(".")
    ]
    
    if not raw_files:
        return []
    
    print(f"Checking web optimization for {len(raw_files)} mobile wallpapers...")
    
    def convert_single(p):
        name = p.stem
        full_out = MOBILE_FULL_DIR / f"{name}.jpg"
        thumb_out = MOBILE_THUMBS_DIR / f"{name}_thumb.jpg"
        
        # 1. Full-res Web JPEG (crisp 88% quality)
        if not full_out.exists() or full_out.stat().st_mtime < p.stat().st_mtime:
            cmd1 = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "88", str(p), "--out", str(full_out)]
            subprocess.run(cmd1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
        # 2. Thumbnail (height/width max 700px, 80% quality)
        if not thumb_out.exists() or thumb_out.stat().st_mtime < p.stat().st_mtime:
            cmd2 = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", "-Z", "700", str(full_out), "--out", str(thumb_out)]
            subprocess.run(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
        return full_out, thumb_out, p
    
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(convert_single, raw_files))
        
    return results


def build_gallery():
    print("=" * 60)
    print(" Entheogenous Portfolio — Media Sync")
    print("=" * 60)
    
    # 1. Collect standalone photos (outside Mobile)
    photos = []
    if PHOTOS_DIR.exists():
        for p in sorted(PHOTOS_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and not p.name.startswith("."):
                photos.append(p)
                
    # 2. Collect motions
    motions = []
    if MOTIONS_DIR.exists():
        for m in sorted(MOTIONS_DIR.iterdir()):
            if m.is_file() and m.suffix.lower() in VIDEO_EXTENSIONS and not m.name.startswith("."):
                motions.append(m)
                
    # 3. Collect mobile wallpapers
    wallpapers = process_mobile_wallpapers()
    
    print(f"Found: {len(photos)} standalone photos, {len(wallpapers)} wallpapers, {len(motions)} motions.")
    
    if not photos and not motions and not wallpapers:
        print("No media files found.")
        return False
    
    items_html = []
    
    # Sort wallpapers by filename descending (newest first)
    wallpapers.sort(key=lambda x: x[2].name, reverse=True)
    
    # Process Wallpapers
    for idx, (full_path, thumb_path, orig_path) in enumerate(wallpapers, 1):
        num_str = f"{len(wallpapers) - idx + 1:03d}"
        title = f"Fractal Wallpaper #{num_str}"
        year = "2022"
        
        # Check if square or portrait
        ratio_attr = ""
        try:
            res = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(thumb_path)], capture_output=True, text=True)
            w_match = re.search(r"pixelWidth:\s*(\d+)", res.stdout)
            h_match = re.search(r"pixelHeight:\s*(\d+)", res.stdout)
            if w_match and h_match:
                w = int(w_match.group(1))
                h = int(h_match.group(1))
                if abs(w - h) < 50:
                    ratio_attr = ' data-ratio="square"'
        except Exception:
            pass
            
        rel_thumb = thumb_path.relative_to(PORTFOLIO_DIR).as_posix()
        rel_full = full_path.relative_to(PORTFOLIO_DIR).as_posix()
        
        card = f"""    <!-- WALLPAPER: {title} -->
    <div class="gallery__item" data-category="wallpapers"{ratio_attr}>
      <img src="{rel_thumb}" data-full="{rel_full}" alt="{title}" loading="lazy">
      <div class="item-info">
        <div class="item-info__title">{title}</div>
        <div class="item-info__date">{year}</div>
      </div>
    </div>"""
        items_html.append(card)
        
    # Process Motions
    for m in motions:
        title, year = parse_filename(m)
        rel_video = m.relative_to(PORTFOLIO_DIR).as_posix()
        card = f"""    <!-- MOTION: {title} -->
    <div class="gallery__item" data-category="motions">
      <video src="{rel_video}" preload="metadata" muted playsinline loop></video>
      <div class="play-icon"><svg viewBox="0 0 24 24"><polygon points="8,5 20,12 8,19"/></svg></div>
      <div class="item-info">
        <div class="item-info__title">{title}</div>
        <div class="item-info__date">{year}</div>
      </div>
    </div>"""
        items_html.append(card)
        
    # Process Standalone Photos (if any)
    for p in photos:
        title, year = parse_filename(p)
        thumb_path = optimize_photo_thumb(p)
        rel_thumb = thumb_path.relative_to(PORTFOLIO_DIR).as_posix()
        rel_full = p.relative_to(PORTFOLIO_DIR).as_posix()
        card = f"""    <!-- PHOTO: {title} -->
    <div class="gallery__item" data-category="photos">
      <img src="{rel_thumb}" data-full="{rel_full}" alt="{title}" loading="lazy">
      <div class="item-info">
        <div class="item-info__title">{title}</div>
        <div class="item-info__date">{year}</div>
      </div>
    </div>"""
        items_html.append(card)
        
    # Inject into index.html
    html_content = INDEX_FILE.read_text(encoding="utf-8")
    start_tag = "<!-- GALLERY_ITEMS_START -->"
    end_tag = "<!-- GALLERY_ITEMS_END -->"
    
    if start_tag not in html_content or end_tag not in html_content:
        print("Warning: Could not locate gallery markers in index.html.")
        return False

    pattern = rf"({re.escape(start_tag)})(.*?)({re.escape(end_tag)})"
    replacement = f"\\1\n" + "\n\n".join(items_html) + f"\n    \\3"
    new_html = re.sub(pattern, replacement, html_content, flags=re.DOTALL)
    
    if new_html != html_content:
        INDEX_FILE.write_text(new_html, encoding="utf-8")
        print(f"Updated index.html with {len(items_html)} media items.")
    else:
        print("index.html gallery is already up to date.")
    return True


def git_deploy():
    print("\nDeploying to GitHub Pages...")
    try:
        subprocess.run(["git", "add", "."], cwd=PORTFOLIO_DIR, check=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=PORTFOLIO_DIR, capture_output=True, text=True)
        if not status.stdout.strip():
            print("No new changes to commit.")
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git", "commit", "-m", f"update: sync 206 wallpapers and motions ({timestamp})"], cwd=PORTFOLIO_DIR, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=PORTFOLIO_DIR, check=True)
        print("\nSuccessfully pushed to GitHub!")
        print("Live site will update in ~30 seconds at:")
        print("👉 https://mjavadz.github.io/entheogenous/")
    except Exception as e:
        print(f"Git deploy failed: {e}")


if __name__ == "__main__":
    should_deploy = "--no-deploy" not in sys.argv
    has_changes = build_gallery()
    if has_changes and should_deploy:
        git_deploy()
    print("\nDone!")
