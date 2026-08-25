from __future__ import annotations

import re
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

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
    r"\bmind[- ]blowing\b", r"\bbreaking!!!+\b", r"\b100% proven\b",
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
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    try:
        host = (urlparse(value).hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


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
        verdict = "Likely false claim detected"
        confidence = "High"
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
            "status": "Matched a built-in known-claim pattern" if false_claims else "No built-in known-claim pattern matched",
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
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    source = str(data.get("source", "")).strip()
    if len(text) < 20:
        return jsonify({"error": "Enter at least 20 characters of article text."}), 400
    if len(text) > 20000:
        return jsonify({"error": "Article text is limited to 20,000 characters."}), 413
    return jsonify(analyze(text, source))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
