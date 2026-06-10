from src.verification import verify_label


def test_matching_label_passes_core_fields():
    application = {
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "bottler_address": "Bottled by Old Tom Distillery, Louisville, KY",
        "country_of_origin": "United States",
    }
    ocr_text = """
    OLD TOM DISTILLERY
    Kentucky Straight Bourbon Whiskey
    45% Alc./Vol. (90 Proof)
    Net Contents: 750 mL
    Bottled by Old Tom Distillery, Louisville, KY
    Country of Origin: United States
    GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
    """
    result = verify_label(application, ocr_text)
    assert result["overall_status"] == "PASS"


def test_missing_warning_fails():
    application = {"brand_name": "OLD TOM DISTILLERY"}
    result = verify_label(application, "OLD TOM DISTILLERY 45% Alc./Vol. 750 mL")
    assert result["overall_status"] == "FAIL"
    warning = [check for check in result["checks"] if check["field"] == "government_warning"][0]
    assert warning["status"] == "FAIL"
