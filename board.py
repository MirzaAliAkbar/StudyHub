import os
import uuid
from datetime import date
from flask import Blueprint, render_template, request, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, Subject, Deadline, Note, BoardItem

board = Blueprint("board", __name__)

SUBJECT_COLORS = {
    "math": "#8181cf",
    "physics": "#f472b6",
    "chem": "#34d399",
    "bio": "#fbbf24",
    "econ": "#a78bfa",
    "business": "#22d3ee",
    "Computer": "#94a3b8",
    "english": "#f87171",
    "account": "#facc15",
}

GAP = 28
COL_W = 320

UPLOAD_TYPES = {
    "image": {"png", "jpg", "jpeg", "gif", "webp", "bmp", "avif"},
    "video": {"mp4", "webm", "ogv", "mov", "m4v"},
    "audio": {"mp3", "wav", "ogg", "m4a"},
    "pdf": {"pdf"},
    "file": {"text", "md", "csv", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "zip", "rtf"},
}

NOTE_COLORS = {"#f6e7a8", "#f7c6cf", "#bfe8cb", "#c2dcf7", "#dfcdf5"}

def get_color(name):
    key = name.lower()
    for needle, color in SUBJECT_COLORS.items():
        if needle in key:
            return color
    return "#6366f1"

def place(obj, default_x, default_y):
    x = obj.x if obj.x is not None else default_x
    y = obj.y if obj.y is not None else default_y
    return x, y


@board.route("/board")
@login_required
def index():
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    items = BoardItem.query.filter_by(user_id=current_user.id).all()
    today = date.today()

    subject_nodes = []

    for i, subject in enumerate(subjects):
        col_x = 80 + i * COL_W
        color = get_color(subject.name)
        sx, sy = place(subject, col_x, 80)

        exam_rows, paper_rows = [], []
        for deadline in subject.deadlines:
            days = (deadline.exam_date - today).days
            meta = deadline.exam_date.strftime("%d %b")
            meta += " . past" if days < 0 else f" . {days}d left"
            row = {"title": deadline.title, "meta": meta}
            if "paper" in (deadline.type or "").lower():
                paper_rows.append(row)
            else:
                exam_rows.append(row)

        note_rows = [{
            "title": note.filename, 
            "meta": note.created_at.strftime("%d %b") if note.created_at else "",
        } for note in subject.notes]

        groups = []
        group = []

        for key, label, rows in (
            ("deadlines", "Deadlines", exam_rows),
            ("notes", "Notes", note_rows),
            ("papers", "Past papers", paper_rows),
        ):
            if rows:
                groups.append({"key": key, "label": label, "rows": rows})

        subject_nodes.append({
            "subject": subject,
            "x": sx,
            "y": sy,
            "color": color,
            "groups": groups,
            "count": len(exam_rows) + len(note_rows) + len(paper_rows),
        })

    return render_template("board/index.html", subject_nodes=subject_nodes, items=items)

@board.route("/board/node/<kind>/<int:node_id>", methods=["POST"])
@login_required
def move_node(kind, node_id):
    payload = request.get_json(silent=True) or {}
    try:
        x = float(payload["x"])
        y = float(payload["y"])
    except (KeyError, TypeError, ValueError):
        abort(400)

    model = {"subject": Subject,  "deadline": Deadline, "note": Note}.get(kind)
    if model is None:
        abort(404)

    node = model.query.filter_by(id=node_id, user_id=current_user.id).first_or_404()
    node.x, node.y = x, y

    if hasattr(node, "w"):
        w, h = payload.get("w"), payload.get("h")
        if w is not None and h is not None:
            node.w = max(180.0, float(w))
            node.h = max(96.0, float(h))
    if hasattr(node, "s"):
        s = payload.get("s")
        if s is not None:
            node.s = min(3.0, max(0.4, float(s)))

    db.session.commit()
    return {"ok": True}

@board.route("/board/item", methods=["POST"])
@login_required

def tag_item(item):
    """Sort one board item into a subject. Never raises, never blocks saving."""
    subjects = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.name).all()
    guess = classify(
        {"title": item.title, "content": item.content, "kind": item.kind},
        [{"id": s.id, "name": s.name} for s in subjects],
        url=current_app.config.get("JEV_API_URL", ""),
        key=current_app.config.get("JEV_API_KEY", ""),
        model=current_app.config.get("JEV_MODEL", "jev-latest"),
        minimum=float(current_app.config.get("AUTO_TAG_MIN", 0.45)),
    )
    item.subject_id = guess["subject_id"]
    item.tag_confidence = guess["confidence"] if guess["subject_id"] else None
    item.auto_tagged = bool(guess["subject_id"])
    db.session.commit()
    return guess

def create_item():
    payload = request.get_json(silent=True) or {}
    kind = payload.get("kind")
    if kind not in ("note", "text", "link"):
        abort(400)

    title = (payload.get("title") or "").strip()[:120]
    content = (payload.get("content") or "").strip()
    if not content:
        abort(400)
    if len(content) > 4000:
        content = content[:4000]

    if kind == "link" and not content.startswith(("http://", "https://")):
        abort(400)

    try:
        x = float(payload.get("x", 0))
        y = float(payload.get("y", 0))
    except (TypeError, ValueError):
        abort(400)

    try:
        s = min(3.0, max(0.4, float(payload.get("s") or 1.0)))
    except (TypeError, ValueError):
        s = 1.0
    color = payload.get("color")
    if kind != "note":
        color = None
    elif color not in NOTE_COLORS:
        color = "#f6e7a8"

    item = BoardItem(kind=kind, title=title, content=content, x=x, y=y, s=s, color=color, user_id=current_user.id)



    db.session.add(item)
    db.session.commit()
    guess = tag_item(item)
    return {"tag": guess, "id": item.id, "kind": item.kind, "title": item.title, "content": item.content, "x": item.x, "y": item.y, "s": item.s, "color": item.color,}


@board.route("/board/item/<int:item_id>", methods=["POST"])
@login_required
def move_item(item_id):
    payload = request.get_json(silent=True) or {}
    item = BoardItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    try:
        item.x = float(payload["x"])
        item.y = float(payload["y"])
    except (KeyError, TypeError,ValueError):
        abort(400)
    if payload.get("s") is not None:
        item.s = min(3.0, max(0.4, float(payload["s"])))
    db.session.commit()
    return {"ok": True}

@board.route("/board/item/<int:item_id>/duplicate", methods=["POST"])
@login_required
def duplicate_item(item_id):
    src = BoardItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    copy = BoardItem(
        kind=src.kind, title=src.title, content=src.content, x=(src.x or 0.0) + 28, y=(src.y or 0.0) + 28, s=src.s or 1.0, user_id=current_user.id,
    )
    db.session.add(copy)
    db.session.commit()
    return {
        "id": copy.id, "kind": copy.kind, "title": copy.title,
        "content": copy.content, "x": copy.x, "y": copy.y, "s": copy.s,
    }


@board.route("/board/item/<int:item_id>/edit", methods=["POST"])
@login_required
def edit_item(item_id):
    payload = request.get_json(silent=True) or {}
    item = BoardItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    if item.kind not in ("note", "text"):
        abort(400)

    content = (payload.get("content") or "").strip()
    if not content:
        abort(400)
    item.content = content[:4000]
    if "title" in payload and item.kind == "note":
        item.title = (payload.get("title") or "").strip()[:120]
    db.session.commit()
    return {"ok": True, "content": item.content, "title": item.title}

@board.route("/board/item/<int:item_id>/color", methods=["POST"])
@login_required
def set_item_color(item_id):
    payload = request.get_json(silent=True) or {}
    item = BoardItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    if item.kind != "note":
        abort(400)
    color = (payload.get("color") or "").strip().lower()
    if color not in NOTE_COLORS:
        abort(400)
    item.color = color
    db.session.commit()
    return {"ok": True, "color": item.color}

@board.route("/board/item/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    item = BoardItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return {"ok": True}

def set_item_tag(item_id):
    payload = request.get_json(silent=True) or {}
    item = BoardItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    subject_id = payload.get("subject_id")
    if subject_id in (None, "", 0):
        item.subject_id = None
    else:
        subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
        if subject is None:
            abort(400)
        item.subject_id = subject.id
    item.auto_tagged = False
    item.tag_confidence = None
    db.session.commit()
    return {"ok": True, "subject_id": item.subject_id}
@board.route("/board/item/<int:item_id>/retag", methods=["POST"])
@login_required
def retag_item(item_id):
    item = BoardItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    return {"ok": True, "tag": tag_item(item)}

@board.route("/board/autosort", methods=["POST"])
@login_required
def autosort_board():
    items = (BoardItem.query.filter_by(user_id=current_user.id, subject_id=None).order_by(BoardItem.id).limit(40).all())
    sorted_rows, errors = [], 0
    for item in items:
        guess = tag_item(item)
        if guess["subject_id"]:
            sorted_rows.append({
                "id": item.id, "subject_id": item.subject_id,
                "subject_name": guess["subject_name"], "confidence": guess["confidence"],
            })
        elif guess["error"]:
            errors += 1
    return {"ok": True, "sorted": sorted_rows, "untouched": len(items) - len(sorted_rows), "errors": errors}

@board.route("/board/upload", methods=["POST"])
@login_required

def upload_file():
    file = request.files.get("file")
    if not file or not file.filename:
        abort(400)

    raw = file.filename
    name = secure_filename(raw) or "file"
    ext = raw.rsplit(".", 1)[-1].lower() if "." in raw else ""
    kind = next((k for k, exts in UPLOAD_TYPES.items() if ext in exts), None)
    if kind is None:
        abort(400)

    folder = os.path.join(current_app.static_folder, "uploads")
    os.makedirs(folder, exist_ok=True)
    stored = "%s.%s" % (uuid.uuid4().hex, ext)
    file.save(os.path.join(folder, stored))

    try:
        x = float(request.form.get("x", 0))
        y = float(request.form.get("y", 0))
    except (TypeError, ValueError):
        x, y = 0.0, 0.0

    item = BoardItem(kind=kind, title=raw[:120], content="/static/uploads/" + stored, x=x, y=y, s=1.0, user_id=current_user.id)
    db.session.add(item)
    db.session.commit()
    return {"id": item.id, "kind": item.kind, "title": item.title, "content": item.content, "x": item.x, "y": item.y, "s": item.s}