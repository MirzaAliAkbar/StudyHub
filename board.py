from datetime import date
from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
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

COL_W = 320
GAP = 24
SUBJECT_H = 120
DEADLINE_H = 132
NOTE_H = 104

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

    subject__nodes, deadline_nodes, note_nodes = [], [], []
    board_data = {}

    for i, subject in enumerate(subjects):
        col_x = 80 + i * COL_W
        color = get_color(subject.name)

        sx, sy = place(subject, col_x, 80)
        subject_nodes.append({
            "subject": subject, "x": sx, "y":sy, "color": color,
        })

        y = sy + SUBJECT_H + GAP
        for deadline in subject.deadlines:
            dx, dy = place(deadline, col_x, y)
            deadline_nodes.append({
                "deadline": deadline, "x": dx, "y": dy, "color": color,
                "days": (deadline.exam_date - today).days,
            })
            y += DEADLINE_H + GAP

        for note in subject.notes:
            nx, ny = place(note, col_x, y)
            note_nodes.append({"note": note, "x": nx, "y":ny, "color": color})
            y += NOTE_H + GAP

        rows = []
        for note in subject.notes:
            rows.append({
                "group": "notes",
                "title": note.filename,
                "meta" : note.created_at.strftime("%d %b") if note.created_at else "",
            })
        for deadline in subject.deadlines:
            is_paper = "paper" in (deadline.type or "").lower()
            rows.append({
                "group": "papers" if is_paper else "deadlines",
                "title": deadline.title,
                "meta": deadline.exam_data.strftime("%d %b"),
            })

        board_data[str(subject.id)] = {
            "name": subject.name,
            "color": color,
            "items": rows,
        }

    return render_template("board/index.html", subject_nodes=subject_nodes, deadline_nodes=deadline_nodes, note_nodes=note_nodes, items=items, board_data=board_data,)


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

    if hasattr(node,"w"):
        w, h = payload.get("w"), payload.get("h")
        if w is not None and h is not None:
            node.w = max(180.0, float(w))
            node.h = max(96.0, float(h))

    db.session.commit()
    return {"ok": True}

@board.route("/board/item", methods=["POST"])
@login_required
def create_item():
    payload = request.get_json(silent=True) or {}
    kind = payload.get("kind")
    if kind not in ("note", "text", "image", "link"):
        abort(400)

    content = (payload.get("content") or "").strip()
    if not content:
        abort(400)

    if len(content) > 2000:
        content = content[:2000]

    if kind in ("image", "link") and not content.starswith(("http://", "https://")):
        abort(400)

    try:
        x = float(payload.get("x", 0))
        y = float(payload.get("y", 0))
    except (TypeError, ValueError):
        abort(400)

    item = BoardItem(kind=kind, content=content, x=x, y=y, user_id=current_user.id)
    db.session.add(item)
    db.session.commit()
    return {"id": item.id, "kind": item.kind, "content": item.content, "x": item.x, "y": item.y}

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
    db.session.commit()
    return {"ok": True}

@board.route("/board/item/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    item = BoardItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return {"ok": True}