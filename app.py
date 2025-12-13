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
    correct_option = db.Column(db.String(1), nullable=False)
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
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("User already exists!", "danger")
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created! Login now.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username_or_email']
        password = request.form['password']

        user = User.query.filter(
            (User.username == username_or_email) |
            (User.email == username_or_email)
        ).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))

        flash("Invalid credentials!", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

# =======================
# Dashboard
# =======================
@app.route('/')
@login_required
def dashboard():
    user_id = session['user_id']

    attempts = QuizAttempt.query.filter_by(user_id=user_id)\
        .order_by(QuizAttempt.created_at.desc()).all()

    # Build subject -> levels mapping
    subject_levels = {}
    rows = db.session.query(Question.subject, Question.level).distinct().all()

    for subject, level in rows:
        subject_levels.setdefault(subject, []).append(level)

    return render_template(
        'dashboard.html',
        attempts=attempts,
        subject_levels=subject_levels
    )

# =======================
# Quiz (NO REPEAT MCQs)
# =======================
@app.route('/quiz', methods=['GET', 'POST'])
@login_required
def quiz():
    user_id = session['user_id']

    if request.method == 'GET':
        subject = request.args.get('subject')
        level = request.args.get('level')
        limit = request.args.get('limit', type=int, default=10)
        mode = request.args.get('mode', 'new')  # new | all

        base_query = Question.query.filter(
            Question.subject == subject,
            Question.level == level
        ).order_by(Question.number)

        # 🔹 MODE 1: ONLY NEW QUESTIONS
        if mode == 'new':
            attempted_qids = (
                db.session.query(QuizAnswer.question_id)
                .join(QuizAttempt)
                .filter(QuizAttempt.user_id == user_id)
                .subquery()
            )

            base_query = base_query.filter(
                ~Question.id.in_(attempted_qids)
            )

        # 🔹 MODE 2: ALL QUESTIONS (no filtering)
        questions = base_query.limit(limit).all() if limit > 0 else base_query.all()

        if not questions:
            flash(
                "No questions available for this selection.",
                "info"
            )
            return redirect(url_for('dashboard'))

        return render_template(
            'quiz.html',
            questions=questions,
            subject=subject,
            level=level,
            mode=mode
        )

    # ---------------- POST (Evaluation) ----------------

    subject = request.form['subject']
    level = request.form['level']
    question_ids = request.form['question_ids'].split(',')

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
        chosen = request.form.get(f"q_{qid}")
        is_correct = chosen == q.correct_option

        if is_correct:
            score += 1

        db.session.add(QuizAnswer(
            attempt_id=attempt.id,
            question_id=q.id,
            chosen_option=chosen,
            is_correct=is_correct
        ))

        results.append({
            "question": q,
            "chosen": chosen,
            "is_correct": is_correct
        })

    attempt.score = score
    db.session.commit()

    return render_template(
        'result.html',
        score=score,
        total=total,
        results=results,
        subject=subject,
        level=level
    )

# =======================
# Reset Progress
# =======================
@app.route('/reset-progress')
@login_required
def reset_progress():
    user_id = session['user_id']

    # Step 1: get attempt IDs for this user
    attempt_ids = (
        db.session.query(QuizAttempt.id)
        .filter(QuizAttempt.user_id == user_id)
        .subquery()
    )

    # Step 2: delete answers linked to those attempts
    QuizAnswer.query.filter(
        QuizAnswer.attempt_id.in_(attempt_ids)
    ).delete(synchronize_session=False)

    # Step 3: delete attempts
    QuizAttempt.query.filter_by(user_id=user_id).delete()

    db.session.commit()

    flash("Your quiz progress has been reset successfully.", "success")
    return redirect(url_for('dashboard'))


# =======================
# Run App
# =======================

if __name__ == '__main__':
    app.run(debug=True)
