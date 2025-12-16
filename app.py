from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

# =======================
# App Config
# =======================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =======================
# Models
# =======================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    attempts = db.relationship('QuizAttempt', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(20), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(10), nullable=False)
    explanation = db.Column(db.Text)


class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(20), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    answers = db.relationship('QuizAnswer', backref='attempt', lazy=True)


class QuizAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempt.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    chosen_option = db.Column(db.String(1))
    is_correct = db.Column(db.Boolean, default=False)

# =======================
# Login Required
# =======================

# from app import app, db, Question

# with app.app_context():
#     Question.query.filter_by(subject="Linux", level="Easy").delete()
#     db.session.commit()

print("✅ Linux Easy questions deleted")



def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login first.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

# =======================
# DB Init
# =======================

with app.app_context():
    db.create_all()

# =======================
# Auth Routes
# =======================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User(
            username=request.form['username'].strip(),
            email=request.form['email'].strip()
        )
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        flash("Account created!", "success")
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter(
            (User.username == request.form['username_or_email']) |
            (User.email == request.form['username_or_email'])
        ).first()

        if user and user.check_password(request.form['password']):
            session['user_id'] = user.id
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))

        flash("Invalid credentials", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =======================
# Dashboard
# =======================

@app.route('/')
@login_required
def dashboard():
    user_id = session['user_id']

    attempts = QuizAttempt.query.filter_by(
        user_id=user_id
    ).order_by(QuizAttempt.created_at.desc()).all()

    subject_levels = {}
    rows = db.session.query(Question.subject, Question.level).distinct().all()

    for s, l in rows:
        subject_levels.setdefault(s, []).append(l)

    return render_template(
        'dashboard.html',
        attempts=attempts,
        subject_levels=subject_levels
    )

# =======================
# Quiz
@app.route('/quiz', methods=['GET', 'POST'])
@login_required
def quiz():

    # ===================== GET =====================
    if request.method == 'GET':
        subject = request.args.get('subject')
        level = request.args.get('level')
        limit = request.args.get('limit', type=int, default=0)

        user_id = session['user_id']

        # all solved question ids for this user
        solved_ids = (
            db.session.query(QuizAnswer.question_id)
            .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
            .filter(QuizAttempt.user_id == user_id)
            .distinct()
            .all()
        )
        solved_ids = [qid for (qid,) in solved_ids]

        query = Question.query.filter_by(subject=subject, level=level)

        if solved_ids:
            query = query.filter(~Question.id.in_(solved_ids))

        questions = query.limit(limit).all() if limit else query.all()

        if not questions:
            flash("🎉 You have solved all available questions!", "success")
            return redirect(url_for('dashboard'))

        return render_template(
            'quiz.html',
            questions=questions,
            subject=subject,
            level=level
        )

    # ===================== POST =====================
    subject = request.form.get('subject')
    level = request.form.get('level')
    qid_string = request.form.get('question_ids')

    # 🔴 SAFETY CHECK
    if not qid_string:
        flash("Invalid quiz submission.", "danger")
        return redirect(url_for('dashboard'))

    question_ids = qid_string.split(',')

    user_id = session['user_id']
    score = 0
    total = len(question_ids)

    attempt = QuizAttempt(
        user_id=user_id,
        subject=subject,
        level=level,
        score=0,
        total_questions=total
    )
    db.session.add(attempt)
    db.session.commit()

    results = []

    for qid in question_ids:
        q = Question.query.get(int(qid))
        if not q:
            continue

        chosen = request.form.get(f"q_{qid}")
        if not chosen:
            continue

        correct = q.correct_option.strip().upper()[0]
        is_correct = chosen.upper() == correct

        if is_correct:
            score += 1

        db.session.add(
            QuizAnswer(
                attempt_id=attempt.id,
                question_id=q.id,
                chosen_option=chosen,
                is_correct=is_correct
            )
        )

        results.append({
            "question": q,
            "chosen": chosen,
            "is_correct": is_correct
        })

    attempt.score = score
    db.session.commit()

    # 🔴 SAFETY CHECK
    if not results:
        flash("No answers were submitted.", "warning")
        return redirect(url_for('dashboard'))

    return render_template(
        'result.html',
        subject=subject,
        level=level,
        score=score,
        total=total,
        results=results
    )


# =======================
# Reset Progress
# =======================

@app.route('/reset-progress')
@login_required
def reset_progress():
    user_id = session['user_id']

    attempt_ids = db.session.query(QuizAttempt.id)\
        .filter_by(user_id=user_id).subquery()

    QuizAnswer.query.filter(
        QuizAnswer.attempt_id.in_(attempt_ids)
    ).delete(synchronize_session=False)

    QuizAttempt.query.filter_by(user_id=user_id).delete()
    db.session.commit()

    flash("Progress reset!", "success")
    return redirect(url_for('dashboard'))

# =======================
# Run
# =======================

if __name__ == '__main__':
    app.run(debug=True)
