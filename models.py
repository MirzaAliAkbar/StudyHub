from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash,check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    subjects = db.relationship("Subject", backref="user", cascade="all, delete-orphan")
    deadlines = db.relationship("Deadline", backref="user", cascade="all, delete-orphan")
    notes = db.relationship("Note", backref="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Subject(db.Model):
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_subject_user_name"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    x = db.Column(db.Float)
    y = db.Column(db.Float)
    w = db.Column(db.Float)
    h = db.Column(db.Float)
    s = db.Column(db.Float, default=1.0)

    deadlines = db.relationship(
        "Deadline", backref="subject", cascade="all, delete-orphan", order_by="Deadline.exam_date",
    )
    notes = db.relationship(
        "Note", backref="subject", cascade="all, delete-orphan", order_by="Note.created_at",
    )



class Deadline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject_id = db.Column(db.Integer,  db.ForeignKey("subject.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(40), default="exam")
    x = db.Column(db.Float)
    y = db.Column(db.Float)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    text = db.Column(db.Text, default="")
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    x = db.Column(db.Float)
    y = db.Column(db.Float)

class BoardItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    kind = db.Column(db.String(16), nullable=False)
    content = db.Column(db.String(500))
    title = db.Column(db.Text)
    x = db.Column(db.Float)
    y = db.Column(db.Float)
    s = db.Column(db.Float, default=1.0)
    color = db.Column(db.String(7), default="#f6e7a8")

    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True)
    auto_tagged = db.Column(db.Boolean, default=False, nullable=False)
    tag_confidence = db.Column(db.Float)
    subject = db.relationship("Subject")

class Paper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    session = db.Column(db.String(40), default="")
    paper_number = db.Column(db.String(10), default="")
    question_count = db.Column(db.Integer, default=1)
    total_marks = db.Column(db.Integer,default=1)
    mark_split = db.Column(db.Text, default="")
    paper_path = db.Column(db.String(500))
    scheme_path = db.Column(db.String(500))
    scheme_text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subject = db.relationship("Subject")
    attempts = db.relationship("Attempt", backref="paper", cascade="all, delete-orphan")

class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("paper.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    answers = db.Column(db.Text, default="{}")
    marks = db.Column(db.Text, default="[]")
    score = db.Column(db.Float, default=0.0)
    graded_at = db.Column(db.DateTime, default=datetime.utcnow)

class Mistake(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    paper_id = db.Column(db.Integer, db.ForeignKey("paper.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    question_no = db.Column(db.Integer, nullable=False)
    topic = db.Column(db.String(80), default="")
    note = db.Column(db.String(400), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)