"""OCR utilities for uploaded label images."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
import pytesseract
from PIL import Image


def preprocess_image(image_path: str | Path) -> np.ndarray:
    """Improve OCR on common label images.

    This keeps preprocessing simple and fast so it can meet the stakeholder goal
    of returning results quickly. It handles basic grayscale conversion,
    resizing, denoising, and thresholding.
    """
    path = str(image_path)
    image = cv2.imread(path)
    if image is None:
        pil_image = Image.open(path).convert("RGB")
        image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    height, width = gray.shape[:2]
    longest_side = max(height, width)
    if longest_side < 1400:
        scale = 1400 / longest_side
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    thresholded = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    return thresholded


def extract_text(image_path: str | Path) -> Tuple[str, float]:
    """Extract text from an image and return text plus runtime seconds."""
    started = time.perf_counter()
    processed = preprocess_image(image_path)
    config = "--oem 3 --psm 6"
    text = pytesseract.image_to_string(processed, config=config)
    elapsed = time.perf_counter() - started
    return text.strip(), elapsed
