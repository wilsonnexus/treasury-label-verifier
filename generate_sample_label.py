"""Generate sample alcohol label images for local testing.

These synthetic labels are only for testing the prototype.
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages "
    "during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs "
    "your ability to drive a car or operate machinery, and may cause health problems."
)


def get_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int):
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def create_label(path: str, warning_text: str = WARNING, brand: str = "OLD TOM DISTILLERY"):
    img = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(img)
    title_font = get_font(58, bold=True)
    heading_font = get_font(34, bold=True)
    body_font = get_font(28)
    small_font = get_font(22)

    draw.rectangle((60, 60, 940, 1340), outline="black", width=6)
    draw.text((110, 120), brand, fill="black", font=title_font)
    draw.line((110, 200, 890, 200), fill="black", width=3)

    lines = [
        ("Kentucky Straight Bourbon Whiskey", heading_font),
        ("45% Alc./Vol. (90 Proof)", body_font),
        ("Net Contents: 750 mL", body_font),
        ("Bottled by Old Tom Distillery, Louisville, KY", small_font),
        ("Country of Origin: United States", small_font),
    ]
    y = 280
    for text, font in lines:
        draw.text((110, y), text, fill="black", font=font)
        y += 70

    draw.rectangle((100, 830, 900, 1240), outline="black", width=3)
    y = 865
    for line in wrap_text(draw, warning_text, small_font, 730):
        draw.text((135, y), line, fill="black", font=small_font)
        y += 36

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


if __name__ == "__main__":
    create_label("samples/sample_pass.png")
    create_label(
        "samples/sample_review_bad_warning.png",
        warning_text="Government Warning: Alcohol may be harmful during pregnancy and may impair driving.",
    )
    create_label("samples/sample_mismatch_brand.png", brand="OLD TON DISTILLERY")
    print("Created sample labels in samples/")
