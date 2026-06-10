import io
import re
import tempfile
from typing import List, Dict, Any

import cv2
import numpy as np
import pandas as pd
import pytesseract
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image
from rapidfuzz import fuzz


app = FastAPI(title="AI-Powered Alcohol Label Verification App")

STANDARD_WARNING_PARTS = [
    "GOVERNMENT WARNING",
    "according to the surgeon general",
    "women should not drink alcoholic beverages during pregnancy",
    "risk of birth defects",
    "consumption of alcoholic beverages impairs your ability",
    "drive a car or operate machinery",
    "may cause health problems",
]


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.upper()
    text = re.sub(r"[^A-Z0-9.%/ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def preprocess_image(image_bytes: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(image)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)


def extract_text(image_bytes: bytes) -> str:
    processed = preprocess_image(image_bytes)
    return pytesseract.image_to_string(processed)


def find_abv_values(text: str) -> List[str]:
    pattern = r"(\d{1,3}(?:\.\d+)?)\s*%?\s*(?:ALC|ALCOHOL)?\.?\s*/?\s*(?:VOL|VOLUME)?"
    values = []
    for match in re.findall(pattern, text.upper()):
        try:
            val = float(match)
            if 0 < val <= 100:
                values.append(str(val).rstrip("0").rstrip("."))
        except ValueError:
            pass
    return sorted(set(values))


def check_field(field_name: str, expected: str, ocr_text: str, threshold: int = 80) -> Dict[str, Any]:
    if not expected or not expected.strip():
        return {
            "field": field_name,
            "expected": "",
            "status": "Not Provided",
            "score": "",
            "note": "No application value was provided for this field.",
        }

    normalized_expected = normalize_text(expected)
    normalized_ocr = normalize_text(ocr_text)

    if normalized_expected in normalized_ocr:
        return {
            "field": field_name,
            "expected": expected,
            "status": "Pass",
            "score": 100,
            "note": "Exact or normalized text was found on the label.",
        }

    score = fuzz.partial_ratio(normalized_expected, normalized_ocr)
    if score >= threshold:
        status = "Review"
        note = "Close match found. Human review recommended because wording may differ."
    else:
        status = "Fail"
        note = "Expected value was not found clearly on the label."

    return {
        "field": field_name,
        "expected": expected,
        "status": status,
        "score": round(score, 1),
        "note": note,
    }


def check_abv(expected: str, ocr_text: str) -> Dict[str, Any]:
    if not expected or not expected.strip():
        return {
            "field": "Alcohol Content",
            "expected": "",
            "status": "Not Provided",
            "score": "",
            "note": "No alcohol content was provided.",
        }

    expected_numbers = re.findall(r"\d{1,3}(?:\.\d+)?", expected)
    found_numbers = find_abv_values(ocr_text)

    for number in expected_numbers:
        try:
            expected_float = float(number)
            for found in found_numbers:
                if abs(float(found) - expected_float) < 0.2:
                    return {
                        "field": "Alcohol Content",
                        "expected": expected,
                        "status": "Pass",
                        "score": 100,
                        "note": f"Alcohol value appears to match. Found {found} on label.",
                    }
        except ValueError:
            pass

    return check_field("Alcohol Content", expected, ocr_text, threshold=75)


def check_government_warning(ocr_text: str) -> Dict[str, Any]:
    lower_text = (ocr_text or "").lower()
    hits = sum(1 for part in STANDARD_WARNING_PARTS if part.lower() in lower_text)
    score = round((hits / len(STANDARD_WARNING_PARTS)) * 100, 1)

    if hits >= 6:
        status = "Pass"
        note = "Most required government warning wording appears to be present."
    elif hits >= 3:
        status = "Review"
        note = "Some required warning wording was detected, but human review is recommended."
    else:
        status = "Fail"
        note = "The required government warning was not detected clearly."

    return {
        "field": "Government Health Warning",
        "expected": "Standard required warning statement",
        "status": status,
        "score": score,
        "note": note,
    }


def overall_status(results: List[Dict[str, Any]]) -> str:
    statuses = [r["status"] for r in results]
    if "Fail" in statuses:
        return "Needs Review / Possible Rejection"
    if "Review" in statuses:
        return "Needs Human Review"
    return "Likely Pass"


def verify_label(
    image_bytes: bytes,
    brand_name: str,
    class_type: str,
    alcohol_content: str,
    net_contents: str,
    name_address: str,
    country_origin: str,
) -> Dict[str, Any]:
    ocr_text = extract_text(image_bytes)

    results = [
        check_field("Brand Name", brand_name, ocr_text),
        check_field("Class/Type", class_type, ocr_text),
        check_abv(alcohol_content, ocr_text),
        check_field("Net Contents", net_contents, ocr_text),
        check_field("Name and Address", name_address, ocr_text, threshold=70),
        check_field("Country of Origin", country_origin, ocr_text, threshold=75),
        check_government_warning(ocr_text),
    ]

    return {
        "overall_status": overall_status(results),
        "ocr_text": ocr_text,
        "results": results,
    }


def render_results(result: Dict[str, Any]) -> str:
    rows = ""
    for r in result["results"]:
        rows += f"""
        <tr>
            <td>{r["field"]}</td>
            <td>{r["expected"]}</td>
            <td><strong>{r["status"]}</strong></td>
            <td>{r["score"]}</td>
            <td>{r["note"]}</td>
        </tr>
        """

    return f"""
    <h2>Overall Result: {result["overall_status"]}</h2>
    <table>
        <tr>
            <th>Field</th>
            <th>Expected/Application Value</th>
            <th>Status</th>
            <th>Score</th>
            <th>Notes</th>
        </tr>
        {rows}
    </table>
    <h3>Extracted OCR Text</h3>
    <pre>{result["ocr_text"]}</pre>
    """


BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AI-Powered Alcohol Label Verification</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 30px; background: #f7f7f7; }
        .container { background: white; padding: 25px; border-radius: 10px; max-width: 1100px; margin: auto; }
        input, button { width: 100%; padding: 10px; margin: 7px 0 15px 0; }
        button { background: #174ea6; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; background: white; }
        th, td { border: 1px solid #ccc; padding: 9px; text-align: left; }
        th { background: #e8eef8; }
        pre { background: #111; color: #eee; padding: 15px; overflow-x: auto; white-space: pre-wrap; }
        .note { background: #fff8d5; padding: 12px; border-left: 4px solid #d4a600; margin-bottom: 20px; }
        .nav { margin-bottom: 20px; }
        .nav a { margin-right: 15px; }
    </style>
</head>
<body>
<div class="container">
    <div class="nav">
        <a href="/">Single Label Review</a>
        <a href="/batch">Batch Upload</a>
    </div>
    {content}
</div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    content = """
    <h1>AI-Powered Alcohol Label Verification App</h1>
    <p class="note">
    Upload a label image and enter the application values. The app extracts text with OCR,
    compares key fields, checks for the government warning, and gives a pass/review/fail result.
    </p>
    <form action="/verify" enctype="multipart/form-data" method="post">
        <label>Label Image</label>
        <input name="file" type="file" accept="image/*" required>

        <label>Brand Name</label>
        <input name="brand_name" value="OLD TOM DISTILLERY">

        <label>Class/Type</label>
        <input name="class_type" value="Kentucky Straight Bourbon Whiskey">

        <label>Alcohol Content</label>
        <input name="alcohol_content" value="45% Alc./Vol. (90 Proof)">

        <label>Net Contents</label>
        <input name="net_contents" value="750 mL">

        <label>Name and Address</label>
        <input name="name_address" value="Bottled by Old Tom Distillery, Louisville, KY">

        <label>Country of Origin</label>
        <input name="country_origin" value="United States">

        <button type="submit">Verify Label</button>
    </form>
    """
    return BASE_HTML.replace("{content}", content)


@app.post("/verify", response_class=HTMLResponse)
async def verify(
    file: UploadFile = File(...),
    brand_name: str = Form(""),
    class_type: str = Form(""),
    alcohol_content: str = Form(""),
    net_contents: str = Form(""),
    name_address: str = Form(""),
    country_origin: str = Form(""),
):
    image_bytes = await file.read()
    result = verify_label(
        image_bytes,
        brand_name,
        class_type,
        alcohol_content,
        net_contents,
        name_address,
        country_origin,
    )
    content = "<h1>Verification Results</h1>" + render_results(result) + '<p><a href="/">Review another label</a></p>'
    return BASE_HTML.replace("{content}", content)


@app.get("/batch", response_class=HTMLResponse)
def batch_page():
    content = """
    <h1>Batch Label Review</h1>
    <p class="note">
    Upload multiple label images. For prototype purposes, the same application fields are applied to each file.
    This supports the stakeholder request for reviewing large groups of labels faster.
    </p>
    <form action="/batch_verify" enctype="multipart/form-data" method="post">
        <label>Label Images</label>
        <input name="files" type="file" accept="image/*" multiple required>

        <label>Brand Name</label>
        <input name="brand_name" value="OLD TOM DISTILLERY">

        <label>Class/Type</label>
        <input name="class_type" value="Kentucky Straight Bourbon Whiskey">

        <label>Alcohol Content</label>
        <input name="alcohol_content" value="45% Alc./Vol. (90 Proof)">

        <label>Net Contents</label>
        <input name="net_contents" value="750 mL">

        <label>Name and Address</label>
        <input name="name_address" value="Bottled by Old Tom Distillery, Louisville, KY">

        <label>Country of Origin</label>
        <input name="country_origin" value="United States">

        <button type="submit">Run Batch Verification</button>
    </form>
    """
    return BASE_HTML.replace("{content}", content)


@app.post("/batch_verify", response_class=HTMLResponse)
async def batch_verify(
    files: List[UploadFile] = File(...),
    brand_name: str = Form(""),
    class_type: str = Form(""),
    alcohol_content: str = Form(""),
    net_contents: str = Form(""),
    name_address: str = Form(""),
    country_origin: str = Form(""),
):
    summary_rows = ""

    for file in files:
        image_bytes = await file.read()
        result = verify_label(
            image_bytes,
            brand_name,
            class_type,
            alcohol_content,
            net_contents,
            name_address,
            country_origin,
        )
        field_summary = ", ".join([f'{r["field"]}: {r["status"]}' for r in result["results"]])
        summary_rows += f"""
        <tr>
            <td>{file.filename}</td>
            <td><strong>{result["overall_status"]}</strong></td>
            <td>{field_summary}</td>
        </tr>
        """

    content = f"""
    <h1>Batch Verification Results</h1>
    <table>
        <tr>
            <th>File</th>
            <th>Overall Status</th>
            <th>Field Summary</th>
        </tr>
        {summary_rows}
    </table>
    <p><a href="/batch">Run another batch</a></p>
    """
    return BASE_HTML.replace("{content}", content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860)
