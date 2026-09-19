#!/usr/bin/env python3
"""
Entheogenous Portfolio Sync Script
Automatically optimizes images, generates thumbnails, updates index.html,
and deploys to GitHub Pages in one step.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

PORTFOLIO_DIR = Path(__file__).resolve().parent
PHOTOS_DIR = PORTFOLIO_DIR / "photos"
THUMBS_DIR = PHOTOS_DIR / "thumbs"
MOTIONS_DIR = PORTFOLIO_DIR / "motions"
INDEX_FILE = PORTFOLIO_DIR / "index.html"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}


def parse_filename(filename: str, file_path: Path):
    """Extract clean title and year from filename or file metadata."""
    stem = file_path.stem
    # Remove leading numbering like "01_", "02 - "
    clean = re.sub(r"^[\d\s_\-]+", "", stem)
    
    # Try to extract 4-digit year at end (e.g. "_2024" or "-2024")
    year_match = re.search(r"[_\-\s](\d{4})$", clean)
    if year_match:
        year = year_match.group(1)
        clean = clean[:year_match.start()]
    else:
        mtime = file_path.stat().st_mtime
        year = str(datetime.fromtimestamp(mtime).year)
    
    # Replace underscores/hyphens with spaces
    title = re.sub(r"[_\-]+", " ", clean).strip().title()
    if not title:
        title = "Untitled"
    return title, year


def optimize_thumbnail(orig_path: Path) -> Path:
    """Generate a responsive 1200px thumbnail using macOS native sips."""
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    thumb_path = THUMBS_DIR / f"{orig_path.stem}_thumb.jpg"
    
    # Skip if thumbnail exists and is newer than source
    if thumb_path.exists() and thumb_path.stat().st_mtime >= orig_path.stat().st_mtime:
        return thumb_path
    
    print(f"  Optimizing thumbnail: {orig_path.name} -> {thumb_path.name}...")
    try:
        cmd = [
            "sips",
            "-s", "format", "jpeg",
            "-s", "formatOptions", "85",
            "-Z", "1200",
            str(orig_path),
            "--out", str(thumb_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return thumb_path
    except Exception as e:
        print(f"  Warning: sips optimization failed for {orig_path.name}: {e}")
        return orig_path


def build_gallery():
    print("=" * 60)
    print(" Entheogenous Portfolio — Media Sync")
    print("=" * 60)
    
    # 1. Collect photos
    photos = []
    if PHOTOS_DIR.exists():
        for p in sorted(PHOTOS_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
                photos.append(p)
    
    # 2. Collect motions
    motions = []
    if MOTIONS_DIR.exists():
        for m in sorted(MOTIONS_DIR.iterdir()):
            if m.is_file() and m.suffix.lower() in VIDEO_EXTENSIONS:
                motions.append(m)
    
    print(f"Found: {len(photos)} photos, {len(motions)} motions.")
    
    if not photos and not motions:
        print("No media files found in photos/ or motions/.")
        print("Drop your fractal images into photos/ and video clips into motions/.")
        print("Existing placeholders in index.html will remain untouched.")
        return False
    
    # Generate HTML blocks
    items_html = []
    
    # Combine photos and motions (interleaving motions every few photos for magazine feel)
    media_items = []
    for p in photos:
        media_items.append(("photo", p))
    for m in motions:
        media_items.append(("motion", m))
    
    # Order by modification date descending (newest first)
    media_items.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)
    
    for kind, file_path in media_items:
        title, year = parse_filename(file_path.name, file_path)
        
        if kind == "photo":
            thumb_path = optimize_thumbnail(file_path)
            rel_thumb = thumb_path.relative_to(PORTFOLIO_DIR).as_posix()
            rel_full = file_path.relative_to(PORTFOLIO_DIR).as_posix()
            
            card = f"""    <!-- PHOTO: {title} -->
    <div class="gallery__item" data-category="photos">
      <img src="{rel_thumb}" data-full="{rel_full}" alt="{title}" loading="lazy">
      <div class="item-info">
        <div class="item-info__title">{title}</div>
        <div class="item-info__date">{year}</div>
      </div>
    </div>"""
            items_html.append(card)
            
        elif kind == "motion":
            rel_video = file_path.relative_to(PORTFOLIO_DIR).as_posix()
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
    
    # 3. Inject into index.html
    html_content = INDEX_FILE.read_text(encoding="utf-8")
    start_tag = "<!-- GALLERY_ITEMS_START -->"
    end_tag = "<!-- GALLERY_ITEMS_END -->"
    
    pattern = rf"({re.escape(start_tag)})(.*?)({re.escape(end_tag)})"
    replacement = f"\\1\n" + "\n\n".join(items_html) + f"\n    \\3"
    
    new_html = re.sub(pattern, replacement, html_content, flags=re.DOTALL)
    if new_html == html_content:
        print("Warning: Could not locate gallery markers in index.html.")
        return False
    
    INDEX_FILE.write_text(new_html, encoding="utf-8")
    print("Updated index.html with new media items.")
    return True


def git_deploy():
    print("\nDeploying to GitHub Pages...")
    try:
        subprocess.run(["git", "add", "."], cwd=PORTFOLIO_DIR, check=True)
        # Check if there are changes
        status = subprocess.run(["git", "status", "--porcelain"], cwd=PORTFOLIO_DIR, capture_output=True, text=True)
        if not status.stdout.strip():
            print("No new changes to commit.")
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git", "commit", "-m", f"update: sync media ({timestamp})"], cwd=PORTFOLIO_DIR, check=True)
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
