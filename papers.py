"""Past papers: fetch from the archive, attempt, mark with Jev, log mistakes."""
import json
import os
import uuid

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

import papersource
from models import Attempt, Mistake, Paper, Subject, db
from tagging import grade_answer

papers = Blueprint("papers", __name__)


def _paper_folder():
    folder = os.path.join(current_app.static_folder, "papers")
    os.makedirs(folder, exist_ok=True)
    return folder


def _upload(field, allowed):
    file = request.files.get(field)
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        abort(400)
    stored = "%s.%s" % (uuid.uuid4().hex, ext)
    file.save(os.path.join(_paper_folder(), stored))
    return "/static/papers/" + stored


def _stored_path(paper):
    """'/static/papers/x.pdf' -> absolute path, so Flask can serve it."""
    if not paper:
        return None
    name = os.path.basename(paper)
    return paper if os.path.isabs(paper) else os.path.join(_paper_folder(), name)


def _public(path):
    """Absolute path -> the /static URL the browser can open."""
    if not path:
        return None
    name = os.path.basename(path)
    return "/static/papers/" + name


def _split(paper, questions):
    marks = [q.get("marks") or 1 for q in questions]
    if marks and sum(marks) > 0:
        return marks
    even = round(paper.total_marks / max(1, paper.question_count), 2)
    return [even] * paper.question_count


@papers.route("/papers")
@login_required
def index():
    rows = (Paper.query.filter_by(user_id=current_user.id)
            .order_by(Paper.created_at.desc()).all())
    subjects = (Subject.query.filter_by(user_id=current_user.id)
                .order_by(Subject.name).all())
    attempts = (Attempt.query.filter_by(user_id=current_user.id)
                .order_by(Attempt.graded_at.desc()).all())
    attempts = {a.paper_id: a for a in attempts}
    codes = {s.id: papersource.code_for(s.name) for s in subjects}
    return render_template("papers/index.html", papers=rows, subjects=subjects,
                           attempts=attempts, codes=codes)


@papers.route("/papers/fetch", methods=["POST"])
@login_required
def fetch():
    """Download a paper + mark scheme, read it, save it. No uploads needed."""
    subject = Subject.query.filter_by(
        id=request.form.get("subject_id", type=int),
        user_id=current_user.id).first()
    if subject is None:
        abort(400)
    code = papersource.code_for(subject.name, request.form.get("code") or "")
    year = request.form.get("year", type=int) or 2023
    component = (request.form.get("component") or "").strip()
    session = (request.form.get("session") or "a").strip().lower()[:1]

    try:
        built = papersource.build_paper(
            code=code, session=session, year=year, component=component,
            folder=_paper_folder(),
            key=current_app.config.get("JEV_API_KEY", ""),
        )
    except papersource.FetchError as error:
        flash(str(error), "warning")
        return redirect(url_for("papers.index"))
    except Exception as error:                 # network/parse surprises
        flash("Could not fetch that paper: %s" % error, "warning")
        return redirect(url_for("papers.index"))

    paper = Paper(
        user_id=current_user.id,
        subject_id=subject.id,
        title=built["title"],
        session=papersource.SESSIONS.get(built["session"], ""),
        paper_number=built["component"],
        question_count=len(built["questions"]),
        total_marks=built["total_marks"],
        mark_split=",".join(str(q["marks"]) for q in built["questions"]),
        questions=json.dumps(built["questions"]),
        paper_path=_public(built["paper_path"]),
        scheme_path=_public(built["scheme_path"]),
        scheme_text=built["scheme_text"],
    )
    db.session.add(paper)
    db.session.commit()
    flash("Fetched %s with %d questions." % (paper.title, paper.question_count), "success")
    return redirect(url_for("papers.detail", paper_id=paper.id))


@papers.route("/papers/new", methods=["POST"])
@login_required
def create():
    subject = Subject.query.filter_by(
        id=request.form.get("subject_id", type=int),
        user_id=current_user.id).first()
    if subject is None:
        abort(400)
    title = (request.form.get("title") or "").strip()[:120]
    if not title:
        abort(400)
    paper = Paper(
        user_id=current_user.id,
        subject_id=subject.id,
        title=title,
        session=(request.form.get("session") or "").strip()[:40],
        paper_number=(request.form.get("paper_number") or "").strip()[:10],
        question_count=max(1, min(30, request.form.get("question_count", type=int) or 1)),
        total_marks=max(1, min(200, request.form.get("total_marks", type=int) or 1)),
        mark_split=(request.form.get("mark_split") or "").strip()[:400],
        paper_path=_upload("paper_file", {"pdf"}),
        scheme_path=_upload("scheme_file", {"pdf"}),
        scheme_text=(request.form.get("scheme_text") or "").strip()[:20000],
        questions="[]",
    )
    db.session.add(paper)
    db.session.commit()
    flash("Paper added.", "success")
    return redirect(url_for("papers.detail", paper_id=paper.id))


def _questions(paper):
    try:
        rows = json.loads(paper.questions or "[]")
    except ValueError:
        rows = []
    if rows:
        return rows
    return [{"n": n, "text": "Question %d" % n, "marks": None, "scheme": ""}
            for n in range(1, paper.question_count + 1)]


@papers.route("/papers/<int:paper_id>")
@login_required
def detail(paper_id):
    paper = Paper.query.filter_by(id=paper_id, user_id=current_user.id).first_or_404()
    attempt = (Attempt.query.filter_by(paper_id=paper.id, user_id=current_user.id)
               .order_by(Attempt.id.desc()).first())
    mistakes = (Mistake.query.filter_by(paper_id=paper.id, user_id=current_user.id)
                .order_by(Mistake.question_no).all())
    return render_template("papers/detail.html", paper=paper, attempt=attempt,
                           mistakes=mistakes, questions=_questions(paper))


@papers.route("/papers/<int:paper_id>/attempt", methods=["POST"])
@login_required
def attempt(paper_id):
    paper = Paper.query.filter_by(id=paper_id, user_id=current_user.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    answers = payload.get("answers") or {}
    questions = _questions(paper)
    split = _split(paper, questions)

    marks, awarded, missing = [], 0.0, []
    for question in questions:
        n = int(question["n"])
        answer = str(answers.get(str(n)) or "").strip()
        max_marks = split[n - 1] if n - 1 < len(split) else 1
        if not answer:
            marks.append({"q": n, "awarded": 0, "max": max_marks,
                          "reason": "no answer", "error": None})
            missing.append(n)
            continue
        result = grade_answer(
            question=str(question.get("text") or "Question %d" % n)[:2000],
            answer=answer,
            scheme=(question.get("scheme") or paper.scheme_text
                    or "No mark scheme supplied."),
            max_marks=max_marks,
            url=current_app.config.get("JEV_API_URL", ""),
            key=current_app.config.get("JEV_API_KEY", ""),
            model=current_app.config.get("JEV_MODEL", "jev-latest"),
        )
        marks.append({"q": n, "awarded": result["awarded"], "max": max_marks,
                      "reason": result["reason"], "error": result["error"]})
        awarded += result["awarded"]

    record = Attempt(
        paper_id=paper.id,
        user_id=current_user.id,
        answers=json.dumps(answers),
        marks=json.dumps(marks),
        score=round(awarded, 2),
        total=paper.total_marks,
        graded_at=db.func.now(),
    )
    db.session.add(record)
    db.session.flush()

    for row in marks:
        if row["awarded"] < row["max"]:
            db.session.add(Mistake(
                user_id=current_user.id,
                paper_id=paper.id,
                subject_id=paper.subject_id,
                question_no=row["q"],
                note=row["reason"][:400],
            ))
    db.session.commit()
    return {
        "ok": True,
        "attempt_id": record.id,
        "score": record.score,
        "total": record.total,
        "percent": round(100 * record.score / max(1, paper.total_marks), 1),
        "missing": missing,
        "marks": marks,
    }


@papers.route("/papers/mistakes")
@login_required
def mistakes():
    rows = (Mistake.query.filter_by(user_id=current_user.id)
            .order_by(Mistake.created_at.desc()).limit(200).all())
    return render_template("papers/mistakes.html", mistakes=rows)
