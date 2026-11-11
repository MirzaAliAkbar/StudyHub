from datetime import date, timedelta
from app import create_app
from models import db, User, Subject, Deadline

app = create_app()

with app.app_context():
    db.create_all()

    if User.query.filter_by(username="demo").first():
        print("Demo account already exists - log in with demo / demo1234")
    else: 
        user = User(username='demo')
        user.set_password("demo1234")
        db.session.add(user)
        db.session.flush()

        today = date.today()
        plan = {
            "Mathermatics": [("P1 mock", 12, "paper"), ("P3 mock", 40, "paper")],
            "Physics": [("Paper 4 revision", 21, "exam")],
            "Chemistry": [("Paper 2 past papers", 33, "paper")],
            "Computer Science": [("Porject deadline", 55, "assignment")],
        }

        for name, items in plan.items():
            subject = Subject(name=name, user_id=user.id)
            db.session.add(subject)
            db.session.flush()
            for title, days, kind in items:
                db.session.add(Deadline(
                    title=title, subject_id=subject.id, user_id=user.id, type=kind, exam_date=today + timedelta(days=days),
                ))
        db.session.commit()
        print("Seeded demo data - log in with demo / demo1234")