from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime  # Correct import

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-to-a-secure-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# =======================
# Database Models
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
# Login Required Decorator
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
# Create Tables (1 Time)
# =======================

with app.app_context():
    db.create_all()



# with app.app_context():
#     Question.query.filter_by(subject="Python", level="Medium").delete()
#     db.session.commit()



# =======================
# Auth Routes
# =======================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        if not username or not email or not password:
            flash("All fields required!", "danger")
            return redirect(url_for('register'))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists!", "danger")
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()
        flash("Registration successful! Login now.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username_or_email'].strip()
        password = request.form['password']

        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash("Login Successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username/email or password.", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out!", "info")
    return redirect(url_for('login'))


# =======================
# Dashboard
# =======================

@app.route('/')
@login_required
def dashboard():
    user_id = session['user_id']
    attempts = QuizAttempt.query.filter_by(user_id=user_id).order_by(QuizAttempt.created_at.desc()).all()

    subjects = [row[0] for row in db.session.query(Question.subject).distinct().all()]
    levels = [row[0] for row in db.session.query(Question.level).distinct().all()]

    return render_template(
        'dashboard.html',
        attempts=attempts,
        subjects=subjects,
        levels=levels
    )


# =======================
# Quiz
# =======================
@app.route('/quiz', methods=['GET', 'POST'])
@login_required
def quiz():
    if request.method == 'GET':
        subject = request.args.get('subject')
        level = request.args.get('level')
        limit = request.args.get('limit', type=int, default=0)

        query = Question.query.filter_by(
            subject=subject,
            level=level
        ).order_by(Question.number)

        if limit > 0:
            questions = query.limit(limit).all()
        else:
            questions = query.all()

        if not questions:
            flash("No questions found for this subject & level.", "warning")
            return redirect(url_for('dashboard'))

        return render_template('quiz.html', questions=questions, subject=subject, level=level)

    # POST → evaluate answers
    subject = request.form['subject']
    level = request.form['level']
    question_ids = request.form['question_ids'].split(',')
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
        chosen = request.form.get(f"q_{qid}")
        is_correct = (chosen == q.correct_option)

        if is_correct:
            score += 1

        qa = QuizAnswer(
            attempt_id=attempt.id,
            question_id=q.id,
            chosen_option=chosen if chosen else None,
            is_correct=is_correct
        )
        db.session.add(qa)

        results.append({
            "question": q,
            "chosen": chosen,
            "is_correct": is_correct
        })

    attempt.score = score
    db.session.commit()

    return render_template(
        'result.html',
        subject=subject,
        level=level,
        score=score,
        total=total,
        results=results
    )



# =======================
# Run App
# =======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
