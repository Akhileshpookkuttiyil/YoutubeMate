"""
YouTubeMate Branding Assets Generator
Creates high-resolution PNG and multi-resolution Windows ICO (16, 32, 48, 64, 128, 256 px).
Designed with a clean, geometric, dark-themed desktop software identity
incorporating a download arrow, local storage tray, and subtle video play concept.
"""

import os
from PIL import Image, ImageDraw


def create_base_icon(size=1024):
    """Renders the master YouTubeMate brand icon at high resolution."""
    # 1. Canvas with transparency
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = size * 0.05
    rect_box = [pad, pad, size - pad, size - pad]
    radius = size * 0.22

    # Squircle background - sleek dark slate / charcoal
    bg_color = (20, 24, 33, 255)       # #141821
    border_color = (45, 53, 72, 255)   # #2D3548
    border_width = int(size * 0.02)

    draw.rounded_rectangle(rect_box, radius=radius, fill=bg_color, outline=border_color, width=border_width)

    # Subtle inner accent glow / header pill
    glow_box = [pad + border_width, pad + border_width, size - pad - border_width, pad + size * 0.14]
    draw.rounded_rectangle(glow_box, radius=radius * 0.6, fill=(30, 36, 50, 160))

    # Center coordinates
    cx = size / 2.0
    cy = size / 2.0

    # Dimensions for download arrow + play glyph + tray
    # Arrow Stem & Head
    # Color palette:
    # Accent Blue: (59, 130, 246) #3B82F6
    # Deep Accent: (37, 99, 235) #2563EB
    # Video Crimson/Coral Accent: (239, 68, 68) #EF4444
    # Crisp Light: (248, 250, 252) #F8FAFC

    stem_width = size * 0.17
    stem_top = size * 0.22
    stem_bottom = size * 0.44

    # Draw Upper Arrow Stem
    stem_rect = [cx - stem_width / 2.0, stem_top, cx + stem_width / 2.0, stem_bottom]
    draw.rounded_rectangle(stem_rect, radius=size * 0.035, fill=(59, 130, 246, 255))

    # Draw Arrow Head (Chevron / Inverted Triangle)
    arrow_head_top = size * 0.40
    arrow_head_tip = size * 0.64
    arrow_wing_width = size * 0.58

    head_points = [
        (cx - arrow_wing_width / 2.0, arrow_head_top),  # Left wing
        (cx + arrow_wing_width / 2.0, arrow_head_top),  # Right wing
        (cx, arrow_head_tip),                           # Bottom center point
    ]
    draw.polygon(head_points, fill=(59, 130, 246, 255))

    # Center Play Symbol (Video concept embedded into the download arrow)
    # A crisp, stylized play triangle pointing right, in bold contrasting white
    play_cx = cx + (size * 0.01)
    play_cy = size * 0.45
    play_r = size * 0.11

    # Right-pointing triangle
    p1 = (play_cx - play_r * 0.8, play_cy - play_r * 0.95)
    p2 = (play_cx - play_r * 0.8, play_cy + play_r * 0.95)
    p3 = (play_cx + play_r * 1.1, play_cy)
    draw.polygon([p1, p2, p3], fill=(255, 255, 255, 255))

    # Bottom Tray (Bracket representing local media storage / completed download)
    tray_y = size * 0.74
    tray_height = size * 0.075
    tray_width = size * 0.62
    tray_left = cx - tray_width / 2.0
    tray_right = cx + tray_width / 2.0
    tray_lip = size * 0.10

    # Draw bottom bar
    bar_box = [tray_left, tray_y - tray_height / 2.0, tray_right, tray_y + tray_height / 2.0]
    draw.rounded_rectangle(bar_box, radius=tray_height / 2.0, fill=(241, 245, 249, 255))

    # Draw left and right upright lips of the tray
    lip_w = tray_height
    left_lip = [tray_left, tray_y - tray_lip, tray_left + lip_w, tray_y + tray_height / 2.0]
    right_lip = [tray_right - lip_w, tray_y - tray_lip, tray_right, tray_y + tray_height / 2.0]
    draw.rounded_rectangle(left_lip, radius=lip_w / 2.0, fill=(241, 245, 249, 255))
    draw.rounded_rectangle(right_lip, radius=lip_w / 2.0, fill=(241, 245, 249, 255))

    # Subtle bottom accent dot / indicator (Coral Red dot indicating YouTube/Video media)
    dot_cy = size * 0.74
    dot_r = size * 0.025
    draw.ellipse([cx - dot_r, dot_cy - dot_r, cx + dot_r, dot_cy + dot_r], fill=(239, 68, 68, 255))

    return img


def generate_all_icon_assets(output_dir="assets"):
    os.makedirs(output_dir, exist_ok=True)
    master = create_base_icon(1024)

    # Standard Windows icon sizes
    sizes = [16, 32, 48, 64, 128, 256]
    ico_images = []

    for s in sizes:
        resized = master.resize((s, s), Image.Resampling.LANCZOS)
        ico_images.append(resized)
        png_path = os.path.join(output_dir, f"icon_{s}.png")
        resized.save(png_path, "PNG", optimize=True)
        print(f"Generated {png_path} ({s}x{s})")

    # High-resolution primary PNG (512x512)
    png_512 = master.resize((512, 512), Image.Resampling.LANCZOS)
    primary_png = os.path.join(output_dir, "icon.png")
    png_512.save(primary_png, "PNG", optimize=True)
    print(f"Generated primary PNG {primary_png} (512x512)")

    # Windows multi-resolution ICO file with 16, 32, 48, 64, 128, 256 px
    ico_path = os.path.join(output_dir, "icon.ico")
    master.save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes]
    )
    print(f"Generated multi-resolution ICO {ico_path} with sizes: {sizes}")


if __name__ == "__main__":
    generate_all_icon_assets()
