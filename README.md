# TruthLens — Fake News Detector

A small full-stack fake-news screening tool with a responsive web UI and Flask API. It performs transparent, rule-based checks for source reputation, sensational/clickbait language, and a small set of known false-claim patterns.

> **Important:** This is a screening/triage tool, not an AI fact checker. A high score does not prove that an article is true, and an unknown source is not automatically false.

## Features
- Responsive frontend dashboard
- Flask JSON API
- URL/domain normalization
- Local source reputation list
- Sensational and clickbait language detection
- Known-claim pattern matching
- Deterministic scoring (no random results)
- Input validation and useful error responses
- `/api/health` health check

## Run locally

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## API
`POST /api/analyze`

```json
{"text":"Article text goes here...","source":"https://www.reuters.com/example"}
```

`GET /api/health` returns `{ "status": "ok" }`.

## What was fixed
The original page generated a random credibility score and performed all checks in browser-only JavaScript. It also searched for source names by substring, which could incorrectly treat arbitrary text as a trusted source. The new version uses deterministic scoring, proper hostname parsing, a backend API, validation, a clean UI, and an explicit uncertainty disclaimer.

## Future upgrades
For real fact verification, add reputable fact-checking/news APIs and show citations for external claims. A machine-learning model can be added later with documented training data, calibration, false-positive rate, and explainability.

## Validation and tests

The API requires a JSON object with a string `text` (20–20,000 characters) and an optional string `source` (HTTP(S) URL or domain, at most 2,048 characters). Malformed JSON, incorrect types, invalid source domains and oversized requests return JSON errors instead of server exceptions. Request bodies are limited to 128 KiB.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions checks Python 3.10 and 3.12. Tests cover deterministic results, validation, source-domain spoofing, punctuation detection and contextual uncertainty. The old standalone HTML entry now directs users to the working Flask interface.

Scores are heuristic points out of 100, not a probability that an article is true. Known-claim wording can appear in quotations or rebuttals; the tool explicitly asks for contextual review. It does not retrieve or verify facts from external sources.

To run this app alongside the traffic detector, use a different port:

```bash
python -m flask --app app run --host 127.0.0.1 --port 5002
```
