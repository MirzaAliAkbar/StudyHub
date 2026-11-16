"""Auto-sorting of board items into subjects, and marking of past-paper answers.
"""
import json
import re
import time
import urllib.error
import urllib.request

UNSORTED = "unsorted"

TOPICS = {
    "math": "algebra calculus integration differentiation matrix vector trigonometry "
            "probability statistics function graph quadratic sequence logarithm binomial "
            "equation geometry circle triangle sine cosine tangent",
    "phys": "force newton velocity acceleration momentum energy wave circuit voltage current "
            "resistance magnetic electromagnetic quantum photon nucleus capacitor pressure "
            "thermodynamics oscillation refraction",
    "chem": "mole atom ion bond acid base oxidation reduction organic alkane alkene enthalpy "
            "equilibrium electrode titration periodic solution reaction",
    "bio": "cell photosynthesis chloroplast enzyme dna rna protein gene mitosis meiosis "
           "respiration diffusion osmosis plant tissue hormone kidney neuron",
    "econ": "demand supply elasticity inflation gdp unemployment market price monopoly fiscal "
            "monetary tariff subsidy",
    "business": "marketing stakeholder cashflow breakeven profit business plan operations "
                "recruitment motivation",
    "computer": "algorithm array list loop variable function class object recursion complexity "
                "binary boolean compiler database network protocol",
    "english": "essay poem language literature character theme narrative",
    "account": "ledger debit credit trial balance depreciation journal balance sheet",
}


def _post(url, key, body, timeout):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "StudyHub",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _text(item):
    """Only real text is sent. File URLs, image paths and PDF links are dropped."""
    parts = [item.get("title") or ""]
    if item.get("kind") in ("note", "text", "link"):
        parts.append(item.get("content") or "")
    return re.sub(r"\s+", " ", " ".join(parts)).strip()[:2000]


def _number(value):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0.0
    if n > 1.0:  # a model may answer 82 instead of 0.82
        n = n / 100.0
    return max(0.0, min(1.0, n))


def _hint(name):
    key = next((k for k in TOPICS if k in name.lower()), None)
    if key:
        return name + " topics: " + TOPICS[key]
    return name + " (only if the material is clearly part of this subject)"


def _ask(url, key, body, timeout, retries=1):
    """POST with one retry on 429/5xx. Returns (payload, error_string)."""
    attempt = 0
    while True:
        try:
            return _post(url, key, body, timeout), None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            if exc.code in (429, 500, 502, 503, 529) and attempt < retries:
                attempt += 1
                time.sleep(0.8 * attempt)
                continue
            return None, "HTTP %s: %s" % (exc.code, detail)
        except Exception as exc:
            if attempt < retries:
                attempt += 1
                time.sleep(0.5 * attempt)
                continue
            return None, "%s: %s" % (type(exc).__name__, exc)


def _keyword_scores(text, subjects):
    words = set(re.findall(r"[a-z]{3,}", text.lower()))
    scores = {}
    for subject in subjects:
        key = next((k for k in TOPICS if k in subject["name"].lower()), None)
        if not key:
            continue
        topics = TOPICS[key].split()
        hits = sum(1 for t in topics if t in words)
        named = subject["name"].lower() in text.lower()
        if hits or named:
            scores[subject["id"]] = (0.18 * hits) + (0.3 if named else 0.0)
    total = sum(scores.values())
    if not total:
        return {}
    return {sid: round(min(0.6, s / total), 4) for sid, s in scores.items()}


def classify(item, subjects, url, key, model, minimum=0.45, timeout=20):
    """Return {subject_id, subject_name, confidence, probabilities, source, error}."""
    result = {
        "subject_id": None, "subject_name": None, "confidence": 0.0,
        "probabilities": {}, "source": "none", "error": None,
    }
    subjects = list(subjects)
    text = _text(item)
    if not subjects:
        result["error"] = "no subjects yet"
        return result
    if not text:
        result["error"] = "nothing to read"
        return result

    if url and key:
        criteria = {s["name"]: _hint(s["name"]) for s in subjects}
        body = {
            "model": model,
            "state": text,
            "questions": {
                "subject": {
                    "type": "choice",
                    "instructions": (
                        "Which school subject does this material belong to? Judge by the "
                        "topics it actually mentions, not by its file name."
                    ),
                    "criteria": criteria,
                }
            },
        }
        payload, error = _ask(url, key, body, timeout)
        if error:
            result["error"] = error
        else:
            answer = ((payload or {}).get("answers") or {}).get("subject") or {}
            probabilities = answer.get("probabilities") or {}
            by_name = {s["name"].lower(): s for s in subjects}
            picked = by_name.get(str(answer.get("choice") or "").strip().lower())
            clean = {}
            for name, value in probabilities.items():
                hit = by_name.get(str(name).strip().lower())
                if hit:
                    clean[hit["id"]] = _number(value)
            if clean:
                result["source"] = "jev"
                result["probabilities"] = {
                    next(s["name"] for s in subjects if s["id"] == sid): round(v, 4)
                    for sid, v in sorted(clean.items(), key=lambda kv: -kv[1])
                }
                best_id, best_p = max(clean.items(), key=lambda kv: kv[1])
                confidence = _number(answer.get("confidence"))
                confidence = max(confidence, best_p)
                result["confidence"] = round(confidence, 4)
                if not picked and best_p >= minimum:
                    picked = next(s for s in subjects if s["id"] == best_id)
                if picked and best_p >= minimum:
                    result["subject_id"] = picked["id"]
                    result["subject_name"] = picked["name"]
                return result
            result["error"] = "Jev returned no usable subject: " + json.dumps(answer)[:160]

    scores = _keyword_scores(text, subjects)
    result["source"] = "keyword"
    if scores:
        sid, score = max(scores.items(), key=lambda kv: kv[1])
        result["confidence"] = round(score, 4)
        result["probabilities"] = {
            next(s["name"] for s in subjects if s["id"] == k): round(v, 4)
            for k, v in sorted(scores.items(), key=lambda kv: -kv[1])
        }
        if score >= minimum:
            result["subject_id"] = sid
            result["subject_name"] = next(s["name"] for s in subjects if s["id"] == sid)
    return result


def grade_answer(question, answer, scheme, max_marks, url, key, model, timeout=40):
    """Mark one free-text answer against a mark scheme excerpt. Never raises.

    Marks are read as the expected value of Jev's probability distribution, so
    an answer that is 60% likely to be worth 4 and 37% likely to be worth 3
    scores 3.6 rather than pretending to be certain.
    """
    top = max(1, int(round(float(max_marks))))
    result = {"awarded": 0.0, "max": float(max_marks), "reason": "", "error": None}
    if not (url and key):
        result["error"] = "no AI key configured"
        result["reason"] = "not marked"
        return result
    if not (answer or "").strip():
        result["reason"] = "blank answer"
        return result

    criteria = {}
    for n in range(top + 1):
        criteria[str(n)] = "%d out of %d marks. %s" % (
            n, top,
            "Nothing creditworthy." if n == 0
            else ("Fully correct and complete." if n == top
                  else "Partially correct: correct method or some required points."),
        )
    body = {
        "model": model,
        "state": (
            "Mark scheme:\n" + (scheme or "No scheme provided.")[:5000] +
            "\n\nQuestion:\n" + (question or "Question")[:1000] +
            "\n\nStudent answer:\n" + answer[:3000]
        ),
        "questions": {
            "marks": {
                "type": "choice",
                "instructions": "Award marks strictly against the mark scheme. "
                                "Unsupported or missing working earns nothing.",
                "criteria": criteria,
            }
        },
    }
    payload, error = _ask(url, key, body, timeout, retries=0)
    if error:
        result["error"] = error
        return result

    answer_map = ((payload or {}).get("answers") or {}).get("marks") or {}
    probabilities = answer_map.get("probabilities") or {}
    total = 0.0
    expected = 0.0
    best, best_p = 0, 0.0
    for mark, probability in probabilities.items():
        try:
            value = float(mark)
        except ValueError:
            continue
        p = _number(probability)
        total += p
        expected += value * p
        if p > best_p:
            best, best_p = int(round(value)), p
    if total <= 0:
        result["error"] = "Jev returned no marks: " + json.dumps(answer_map)[:160]
        return result
    result["awarded"] = round(max(0.0, min(float(max_marks), expected / total)), 2)
    result["reason"] = "most likely %d/%d (%.0f%%); expected %.1f" % (
        best, top, best_p * 100, result["awarded"])
    return result
