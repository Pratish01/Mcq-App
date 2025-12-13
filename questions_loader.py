import os
import json
from app import app, db, Question


DATA_DIR = "data"

FILES = [
    ("Big data", "Medium", "Stats_med.json"),
    # Add more subjects & levels if needed
]


def ensure_file(path):
    """Create file if missing"""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4)
        print(f"📁 Created new file: {path}")


def load_questions():
    with app.app_context():
        total_loaded = 0

        for subject, level, filename in FILES:
            path = os.path.join(DATA_DIR, filename)

            ensure_file(path)

            with open(path, "r", encoding="utf-8") as f:
                questions = json.load(f)

            added_count = 0

            for i, q in enumerate(questions, start=1):

                # Avoid duplicates (auto-number)
                existing = Question.query.filter_by(
                    subject=subject,
                    level=level,
                    number=i
                ).first()

                if existing:
                    continue

                new_question = Question(
                    subject=subject,
                    level=level,
                    number=i,
                    question_text=q.get("question_text", ""),
                    option_a=q.get("option_a", ""),
                    option_b=q.get("option_b", ""),
                    option_c=q.get("option_c", ""),
                    option_d=q.get("option_d", ""),
                    correct_option=q.get("correct_option", "A"),
                    explanation=q.get("explanation", "")
                )

                db.session.add(new_question)
                added_count += 1
                total_loaded += 1

            db.session.commit()
            print(f"✔ Loaded {added_count} → {subject} - {level} ({filename})")

        print(f"🎯 TOTAL LOADED: {total_loaded} questions into database!")


if __name__ == "__main__":
    load_questions()
