"""Fetch a CAIE past paper + mark scheme, extract the questions, done.

No uploads, no typing question counts: give a syllabus code and a component
and this returns the paper split into questions with marks and the matching
mark-scheme rows.

Text layer first (pdftotext); for scanned/image-only papers it falls back to
page images read by a vision model.
"""
import base64
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

PDF_URL = ("https://pastpapers.papacambridge.com/directories/CAIE/"
           "CAIE-pastpapers/upload/%s.pdf")
CHAT_URL = "https://ai.hackclub.com/proxy/v1/chat/completions"
VISION_MODEL = "nvidia/nemotron-3.5-super-vl:free"

SESSIONS = {"s": "May/June", "w": "October/November", "m": "February/March"}

# syllabus code by subject name (lowercase, loose match)
CODES = {
    "mathematics": "9709", "maths": "9709", "further mathematics": "9231",
    "physics": "9702", "chemistry": "9701", "biology": "9700",
    "computer science": "9618", "economics": "9708", "business": "9609",
    "accounting": "9706", "psychology": "9990", "sociology": "9699",
    "english language": "9093", "english literature": "9695",
    "history": "9489", "geography": "9696", "law": "9084",
    "information technology": "9626", "art & design": "9479",
    "thinking skills": "9694", "global perspectives": "9239",
}

SKIP_LINE = re.compile(
    r"(© UCLES|\[Turn over|^\s*\d{1,2}\s*$|^\s*DC \(|BLANK PAGE|Blank page|"
    r"^\s*\d{1,2}/\d{1,2}/[A-Z]/[A-Z]/\d{2}|^[.\s]+$|^\s*@|Permission to reproduce)"
)


class FetchError(Exception):
    """Raised when the paper cannot be downloaded or understood."""


# ---------------------------------------------------------------- download
def candidate_names(code, session, year, component):
    yy = "%02d" % (int(year) % 100)
    stem = "%s_%s%s" % (code, session, yy)
    return ["%s_qp_%s" % (stem, component), "%s_ms_%s" % (stem, component)]


def download(name, folder, timeout=60):
    """Save one PDF into folder and return its path, or None if it is not there."""
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, name + ".pdf")
    if os.path.exists(target) and os.path.getsize(target) > 20000:
        return target
    url = PDF_URL % name
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 StudyHub"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return None
    if not data.startswith(b"%PDF"):
        return None
    with open(target, "wb") as handle:
        handle.write(data)
    return target


def find_session(code, year, component, folder, order=("s", "w", "m")):
    """Try each session until a question paper turns up."""
    for session in order:
        qp_name, ms_name = candidate_names(code, session, year, component)
        qp = download(qp_name, folder)
        if qp:
            return session, qp, download(ms_name, folder)
    return None, None, None


# -------------------------------------------------------------------- text
def pdf_text(path):
    """Text layer, or '' when the PDF is just scanned images."""
    try:
        out = subprocess.run(["pdftotext", "-layout", path, "-"],
                             capture_output=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else ""


def ocr_page(path, page, key, model=VISION_MODEL, timeout=120):
    """Render one page and read it with a vision model."""
    tmp = tempfile.mkdtemp(prefix="studyhub-ocr-")
    prefix = os.path.join(tmp, "page")
    try:
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-f", str(page),
                        "-l", str(page), path, prefix],
                       capture_output=True, timeout=120, check=True)
        files = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
        if not files:
            return ""
        encoded = base64.b64encode(open(os.path.join(tmp, files[0]), "rb").read()).decode()
    except (OSError, subprocess.SubprocessError):
        return ""
    finally:
        for name in os.listdir(tmp):
            try:
                os.remove(os.path.join(tmp, name))
            except OSError:
                pass
        os.rmdir(tmp)

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text":
                "Transcribe this exam paper page exactly. Keep question numbers "
                "at the start of lines and keep [n] mark values. Return JSON "
                '{"text": "..."} and nothing else.'},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}},
        ]}],
    }).encode()
    request = urllib.request.Request(CHAT_URL, data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            content = payload["choices"][0]["message"]["content"]
            return _json_text(content)
        except urllib.error.HTTPError as error:
            if error.code in (429, 500, 502, 503) and attempt == 0:
                time.sleep(3)
                continue
            return ""
        except (urllib.error.URLError, OSError, KeyError, ValueError):
            if attempt == 0:
                time.sleep(2)
                continue
            return ""
    return ""


def _json_text(content):
    match = re.search(r"\{.*\}", content or "", re.S)
    if match:
        try:
            return json.loads(match.group(0)).get("text", "") or ""
        except ValueError:
            pass
    return content or ""


def read_pdf(path, key, max_pages=32):
    """Text for the whole PDF: free text layer, else OCR page by page."""
    text = pdf_text(path)
    if len(text.strip()) > 500:
        return text
    try:
        pages = int(re.search(r"Pages:\s+(\d+)",
                              subprocess.run(["pdfinfo", path], capture_output=True,
                                             timeout=30).stdout.decode("utf-8", "replace")
                              ).group(1))
    except (OSError, subprocess.SubprocessError, AttributeError, ValueError):
        pages = 12
    chunks = []
    for page in range(1, min(pages, max_pages) + 1):
        chunk = ocr_page(path, page, key)
        if chunk:
            chunks.append(chunk)
        else:
            break
    return "\n".join(chunks)


# ------------------------------------------------------------------ parsing
def _clean(block):
    lines = []
    for line in block.splitlines():
        if "\f" in line:
            line = line.split("\f")[-1]
        if not line.strip() or SKIP_LINE.search(line):
            continue
        line = re.sub(r"[.\u2026]{4,}", " ", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def parse_questions(text):
    """Split paper text into [{n, text, marks}] by walking question numbers in order."""
    blocks, current = [], 0
    for line in text.replace("\r", "").splitlines():
        match = re.match(r"^(\d{1,2})\s+(\S.*)$", line)
        if match and int(match.group(1)) == current + 1:
            current = int(match.group(1))
            blocks.append([])
        if current and blocks:
            blocks[-1].append(line)
    questions = []
    for index, block in enumerate(blocks):
        raw = "\n".join(block)
        total = re.search(r"\[Total:\s*(\d+)\]", raw)
        parts = [int(x) for x in re.findall(r"\[(\d{1,2})\]\s*$", raw, re.M)]
        questions.append({
            "n": index + 1,
            "text": _clean(raw)[:1500],
            "marks": int(total.group(1)) if total else (sum(parts) or 1),
        })
    return questions


def parse_scheme(text):
    """{question number: mark-scheme text for that question}."""
    rows, current = {}, None
    for line in text.replace("\r", "").splitlines():
        if "\f" in line:
            line = line.split("\f")[-1]
        match = (re.match(r"^\s{1,6}(\d{1,2})\s*\(([a-z])\)", line)
                 or re.match(r"^\s{1,6}(\d{1,2})\s*$", line))
        if match:
            current = int(match.group(1))
            rows.setdefault(current, [])
        if current and line.strip() and not re.match(r"^\s*Page \d+ of", line):
            rows[current].append(re.sub(r"\s{2,}", " ", line).strip())
    return {key: "\n".join(value)[:2500] for key, value in rows.items()}


# -------------------------------------------------------------------- build
def build_paper(code, session, year, component, folder, key, sessions=("s", "w", "m")):
    """Download, read and split one paper. Raises FetchError with a plain reason."""
    code = (code or "").strip()
    if not re.match(r"^\d{4}$", code):
        raise FetchError("Syllabus code must be 4 digits, e.g. 9702.")
    session = (session or "s").strip().lower()[:1]
    if session not in SESSIONS and session != "a":
        session = "s"
    component = str(component or "").strip()
    if not re.match(r"^\d{1,2}$", component):
        raise FetchError("Component must be digits, e.g. 42 or 12.")

    if session == "a":  # any session of that year
        used, qp_path, ms_path = find_session(code, year, component, folder, sessions)
    else:
        qp_name, ms_name = candidate_names(code, session, year, component)
        qp_path = download(qp_name, folder)
        ms_path = download(ms_name, folder) if qp_path else None
        used = session
    if not qp_path:
        raise FetchError("No paper %s/%s/%s on the archive. Check the code, year and component."
                         % (code, year, component))

    paper_text = read_pdf(qp_path, key)
    questions = parse_questions(paper_text)
    if len(questions) < 2:
        raise FetchError("Could not read the questions in that paper (empty or unreadable text).")

    scheme_rows = {}
    if ms_path:
        scheme_rows = parse_scheme(read_pdf(ms_path, key))

    for question in questions:
        question["scheme"] = scheme_rows.get(question["n"], "")[:1500]

    return {
        "code": code,
        "session": used,
        "year": int(year),
        "component": component,
        "title": "%s/%s %s %s" % (code, component, SESSIONS.get(used, used.upper()), year),
        "questions": questions,
        "total_marks": sum(q["marks"] for q in questions),
        "paper_path": qp_path,
        "scheme_path": ms_path,
        "scheme_text": "\n".join(scheme_rows.get(q["n"], "") for q in questions)[:20000],
    }


def code_for(subject_name, explicit=""):
    if explicit:
        return explicit.strip()
    name = (subject_name or "").lower()
    for label, code in CODES.items():
        if label in name:
            return code
    return ""
