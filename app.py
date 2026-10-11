from __future__ import annotations

import re
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 128 * 1024

TRUSTED_SOURCES = {
    "reuters.com": 95,
    "bbc.com": 92,
    "apnews.com": 92,
    "npr.org": 88,
    "theguardian.com": 85,
    "nytimes.com": 85,
    "factcheck.org": 90,
    "politifact.com": 88,
}

SENSATIONAL_PATTERNS = [
    r"\bshocking\b", r"\bunbelievable\b", r"\byou won't believe\b",
    r"\bmind[- ]blowing\b", r"\bbreaking!{3,}", r"\b100% proven\b",
    r"\bsecret the media won't tell you\b", r"\bmust share\b",
]

FALSE_CLAIM_PATTERNS = [
    r"5g\s+spreads\s+covid",
    r"the\s+earth\s+is\s+flat",
    r"vaccines?\s+(cause|causes)\s+autism",
]

CLICKBAIT_PATTERNS = [r"\bclick here\b", r"\bshare this\b", r"\bthey don't want you to know\b"]


def normalize_domain(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if '://' in value and not re.match(r'^https?://', value, re.I):
        return None
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    try:
        parsed = urlparse(value)
        if parsed.username or parsed.password:
            return None
        _ = parsed.port
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower().rstrip('.')
    except (ValueError, UnicodeError):
        return None
    if host.startswith("www."):
        host = host[4:]
    labels = host.split('.')
    if len(labels) < 2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels):
        return None
    return host if len(host) <= 253 else None


def source_analysis(source: str | None) -> dict:
    domain = normalize_domain(source or "")
    if not domain:
        return {"domain": None, "label": "Not provided", "score": 50}

    if domain in TRUSTED_SOURCES:
        return {"domain": domain, "label": "Known reputable source", "score": TRUSTED_SOURCES[domain]}

    for trusted, score in TRUSTED_SOURCES.items():
        if domain.endswith("." + trusted):
            return {"domain": domain, "label": "Subdomain of a known source", "score": max(score - 5, 0)}

    return {"domain": domain, "label": "Unknown / not in local source list", "score": 50}


def matches(patterns: list[str], text: str) -> list[str]:
    return [p for p in patterns if re.search(p, text, re.I)]


def analyze(text: str, source: str | None = None) -> dict:
    clean = re.sub(r"\s+", " ", text.strip())
    src = source_analysis(source)
    sensational = matches(SENSATIONAL_PATTERNS, clean)
    clickbait = matches(CLICKBAIT_PATTERNS, clean)
    false_claims = matches(FALSE_CLAIM_PATTERNS, clean)

    exclamations = clean.count("!")
    uppercase_words = re.findall(r"\b[A-Z]{4,}\b", clean)
    language_penalty = min(len(sensational) * 7 + len(clickbait) * 5 + exclamations * 1.5 + len(uppercase_words) * 1, 30)

    score = round(max(0, min(100, src["score"] - language_penalty - (25 if false_claims else 0))))
    if false_claims:
        verdict = "Known-claim wording detected — review context"
        confidence = "Low"
    elif score >= 75:
        verdict = "Higher credibility — verify before sharing"
        confidence = "Moderate"
    elif score >= 50:
        verdict = "Unverified — further verification recommended"
        confidence = "Low"
    else:
        verdict = "Potential misinformation signals detected"
        confidence = "Moderate"

    return {
        "score": score,
        "verdict": verdict,
        "confidence": confidence,
        "source": src,
        "language": {
            "sensational_count": len(sensational),
            "clickbait_count": len(clickbait),
            "exclamation_count": exclamations,
            "flagged": bool(sensational or clickbait or exclamations > 2),
        },
        "fact_check": {
            "known_false_claim_pattern": bool(false_claims),
            "status": "Known-claim wording found; quotation, negation and context require manual verification" if false_claims else "No built-in known-claim pattern matched",
        },
        "disclaimer": "This is a heuristic screening tool, not proof that an article is true or false. Check primary sources and independent fact-checkers before relying on a result.",
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/analyze")
def api_analyze():
    if not request.is_json:
        return jsonify(error='Send a JSON object with Content-Type: application/json.'), 415
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Request body must be a valid JSON object.'), 400
    if not isinstance(data.get('text'), str) or not isinstance(data.get('source', ''), str):
        return jsonify(error='text and source must be strings.'), 400
    text = data['text'].strip()
    source = data.get('source', '').strip()
    if len(source) > 2048 or (source and normalize_domain(source) is None):
        return jsonify(error='Enter a valid HTTP(S) source URL or domain (up to 2,048 characters).'), 400
    if len(text) < 20:
        return jsonify({"error": "Enter at least 20 characters of article text."}), 400
    if len(text) > 20000:
        return jsonify({"error": "Article text is limited to 20,000 characters."}), 413
    return jsonify(analyze(text, source))


@app.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return jsonify(error='Request body is limited to 128 KiB.'), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
