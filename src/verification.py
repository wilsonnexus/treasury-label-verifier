"""Core verification logic for the Treasury/TTB alcohol label prototype.

The goal is not to replace a compliance agent. The goal is to quickly flag
routine mismatches between application data and label artwork so agents can
review faster.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

STANDARD_GOVERNMENT_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

FIELD_THRESHOLDS = {
    "brand_name": 84,
    "class_type": 78,
    "alcohol_content": 90,
    "net_contents": 90,
    "bottler_address": 72,
    "country_of_origin": 82,
}


@dataclass
class CheckResult:
    field: str
    expected: str
    found: str
    status: str
    score: float
    notes: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def normalize_text(text: str) -> str:
    """Normalize text for OCR/fuzzy matching without losing important words."""
    if not text:
        return ""
    text = text.upper()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"[^A-Z0-9%./'&()\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_text(text))


def status_from_score(score: float, threshold: int) -> str:
    if score >= threshold:
        return "PASS"
    if score >= max(60, threshold - 15):
        return "REVIEW"
    return "FAIL"


def extract_abv_values(text: str) -> List[str]:
    """Find ABV-like values from OCR text."""
    normalized = normalize_text(text)
    patterns = [
        r"\b(\d{1,2}(?:\.\d{1,2})?)\s*%\s*(?:ALC|ALCOHOL)?\s*/?\s*(?:VOL|VOLUME)?\b",
        r"\b(\d{1,3}(?:\.\d{1,2})?)\s*PROOF\b",
    ]
    values: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, normalized):
            values.append(match.group(0).strip())
    return values


def extract_net_contents_values(text: str) -> List[str]:
    normalized = normalize_text(text)
    values: List[str] = []
    for match in re.finditer(r"\b\d+(?:\.\d+)?\s*(?:ML|MILLILITER|MILLILITERS|L|LITER|LITERS|OZ|FL OZ)\b", normalized):
        values.append(match.group(0).strip())
    return values


def best_fuzzy_match(expected: str, ocr_text: str) -> Tuple[str, float]:
    """Return best approximate match using full text and token scoring.

    OCR often does not preserve line breaks or punctuation, so we score against
    the full OCR output instead of trying to locate exact spans.
    """
    expected_norm = normalize_text(expected)
    text_norm = normalize_text(ocr_text)
    if not expected_norm or not text_norm:
        return "", 0.0

    score = float(max(
        fuzz.partial_ratio(expected_norm, text_norm),
        fuzz.token_set_ratio(expected_norm, text_norm),
        fuzz.token_sort_ratio(expected_norm, text_norm),
    ))
    return expected_norm if score >= 60 else "Not confidently found", score


def verify_numeric_field(field_name: str, expected: str, ocr_text: str) -> CheckResult:
    expected_norm = normalize_text(expected)
    candidates = extract_abv_values(ocr_text) if field_name == "alcohol_content" else extract_net_contents_values(ocr_text)

    if not expected_norm:
        return CheckResult(field_name, expected, "Not provided", "SKIPPED", 0.0, "No application value was provided for this field.")

    if candidates:
        best_candidate = max(candidates, key=lambda c: fuzz.ratio(compact(expected_norm), compact(c)))
        score = float(fuzz.ratio(compact(expected_norm), compact(best_candidate)))
        threshold = FIELD_THRESHOLDS[field_name]
        status = status_from_score(score, threshold)
        notes = "Numeric value was compared against OCR-extracted candidates."
        return CheckResult(field_name, expected, best_candidate, status, score, notes)

    found, score = best_fuzzy_match(expected_norm, ocr_text)
    threshold = FIELD_THRESHOLDS[field_name]
    return CheckResult(field_name, expected, found, status_from_score(score, threshold), score, "No clean numeric candidate was extracted, so fuzzy matching was used.")


def verify_text_field(field_name: str, label: str, expected: str, ocr_text: str) -> CheckResult:
    if not expected.strip():
        return CheckResult(label, expected, "Not provided", "SKIPPED", 0.0, "No application value was provided for this field.")
    found, score = best_fuzzy_match(expected, ocr_text)
    threshold = FIELD_THRESHOLDS.get(field_name, 80)
    status = status_from_score(score, threshold)
    notes = "Fuzzy matching allows harmless formatting differences such as case, spacing, or punctuation."
    return CheckResult(label, expected, found, status, score, notes)


def verify_government_warning(ocr_text: str) -> CheckResult:
    text_norm = normalize_text(ocr_text)
    warning_norm = normalize_text(STANDARD_GOVERNMENT_WARNING)

    if "GOVERNMENT WARNING" not in text_norm:
        return CheckResult(
            "government_warning",
            STANDARD_GOVERNMENT_WARNING,
            "Not found",
            "FAIL",
            0.0,
            "The required GOVERNMENT WARNING heading was not detected.",
        )

    score = float(max(
        fuzz.partial_ratio(warning_norm, text_norm),
        fuzz.token_set_ratio(warning_norm, text_norm),
    ))

    if score >= 92:
        status = "PASS"
        notes = "Required warning text appears to be present. Visual formatting such as bold text should still be reviewed by an agent."
    elif score >= 75:
        status = "REVIEW"
        notes = "Warning heading was found, but the wording may differ or OCR confidence may be low. Agent review recommended."
    else:
        status = "FAIL"
        notes = "Warning heading was found, but the full required warning text was not confidently detected."

    return CheckResult("government_warning", STANDARD_GOVERNMENT_WARNING, "Detected near warning text", status, score, notes)


def verify_label(application: Dict[str, str], ocr_text: str) -> Dict[str, object]:
    """Verify one OCR text result against application fields."""
    checks: List[CheckResult] = []
    checks.append(verify_text_field("brand_name", "brand_name", application.get("brand_name", ""), ocr_text))
    checks.append(verify_text_field("class_type", "class_type", application.get("class_type", ""), ocr_text))
    checks.append(verify_numeric_field("alcohol_content", application.get("alcohol_content", ""), ocr_text))
    checks.append(verify_numeric_field("net_contents", application.get("net_contents", ""), ocr_text))
    checks.append(verify_text_field("bottler_address", "bottler_address", application.get("bottler_address", ""), ocr_text))
    checks.append(verify_text_field("country_of_origin", "country_of_origin", application.get("country_of_origin", ""), ocr_text))
    checks.append(verify_government_warning(ocr_text))

    counted = [c for c in checks if c.status != "SKIPPED"]
    fail_count = sum(1 for c in counted if c.status == "FAIL")
    review_count = sum(1 for c in counted if c.status == "REVIEW")
    pass_count = sum(1 for c in counted if c.status == "PASS")

    if fail_count > 0:
        overall = "FAIL"
    elif review_count > 0:
        overall = "REVIEW"
    else:
        overall = "PASS"

    if counted:
        confidence = round(sum(c.score for c in counted) / len(counted), 1)
    else:
        confidence = 0.0

    return {
        "overall_status": overall,
        "confidence": confidence,
        "pass_count": pass_count,
        "review_count": review_count,
        "fail_count": fail_count,
        "checks": [c.to_dict() for c in checks],
        "ocr_text": ocr_text,
    }
