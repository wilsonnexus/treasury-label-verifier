---
title: Treasury Label Verifier
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# AI-Powered Alcohol Label Verification App

This is a Python prototype for the Treasury take-home assessment. It helps compliance agents compare alcohol label artwork against application fields using OCR, fuzzy matching, and rule-based validation.

The app is intentionally designed as a standalone proof of concept. It does not integrate with COLA and does not store uploaded files permanently.

## Features

- Upload a single alcohol label image and verify it against application fields
- Batch upload multiple labels for faster review during peak submissions
- OCR text extraction using Tesseract
- Fuzzy matching for reasonable formatting differences, such as capitalization and punctuation
- Specific validation for:
  - Brand name
  - Class/type designation
  - Alcohol content
  - Net contents
  - Bottler/producer name and address
  - Country of origin
  - Government Health Warning Statement
- PASS / REVIEW / FAIL results for each field
- Downloadable JSON report
- Dockerized deployment for easy hosting

## Why this approach

The stakeholder notes emphasized speed, simplicity, batch processing, and avoiding fragile external cloud API dependencies. For that reason, this prototype uses local OCR and deterministic validation logic instead of requiring a paid LLM or external ML endpoint.

This design is also explainable: agents can see what text was extracted, what was expected, what matched, and why something was flagged.

## Tools used

- Python
- FastAPI for the web interface
- Tesseract OCR through pytesseract
- OpenCV for image preprocessing
- RapidFuzz for fuzzy matching
- pandas for result tables
- Docker for deployability

## Assumptions

- The prototype checks whether required text appears on the label, but a human agent still makes the final compliance decision.
- OCR quality depends on image quality. Blurry, curved, low-resolution, or glared labels may require human review.
- The app checks warning text but cannot reliably verify visual formatting such as bold text or exact font size.
- For this prototype, uploads are processed at runtime and are not persisted after the session.

## Government warning text used

`GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.`

## Local setup without Docker

Install Tesseract first.

### macOS

```bash
brew install tesseract
```

### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

### Windows

Install Tesseract from the official UB Mannheim Windows installer, then make sure `tesseract.exe` is on your PATH.

Then run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python generate_sample_label.py
python app.py
```

Open the local URL shown in the terminal.

## Local setup with Docker

```bash
docker build -t treasury-label-verifier .
docker run -p 7860:7860 treasury-label-verifier
```

Then open:

```text
http://localhost:7860
```

## Run tests

```bash
pytest
```

## Deployment option: Hugging Face Spaces Docker

1. Create a free Hugging Face account.
2. Click **New Space**.
3. Choose:
   - Space name: `treasury-label-verifier`
   - SDK: `Docker`
   - Visibility: Public or Private depending on what the assessment allows
4. Push this repository to the Space.
5. Hugging Face will build the Dockerfile and provide a deployed URL.

Example deployment commands:

```bash
git init
git add .
git commit -m "Initial Treasury label verification prototype"
git branch -M main
git remote add origin https://huggingface.co/spaces/YOUR_USERNAME/treasury-label-verifier
git push -u origin main
```

Your deployed application URL will look like:

```text
https://YOUR_USERNAME-treasury-label-verifier.hf.space
```

## Suggested demo values

Use the generated `samples/sample_pass.png` image with these form values:

- Brand Name: `OLD TOM DISTILLERY`
- Class/Type: `Kentucky Straight Bourbon Whiskey`
- Alcohol Content: `45% Alc./Vol. (90 Proof)`
- Net Contents: `750 mL`
- Name and Address: `Bottled by Old Tom Distillery, Louisville, KY`
- Country of Origin: `United States`

## Trade-offs and limitations

I prioritized a complete, working core application over adding heavier features that may not work reliably in a take-home review environment. The main trade-off is that this version does not use an external LLM or paid vision API. That makes it easier to deploy, test, and explain, but it also means the app relies on OCR quality.

Future improvements could include:

- Confidence scores from OCR word boxes
- Better image deskewing and glare correction
- Separate front/back label support
- Field-level bounding boxes showing where the app found each match
- Integration with COLA application data
- A human feedback loop to improve thresholds over time

