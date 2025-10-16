from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

# -------------------------------------
# Configuration
# -------------------------------------
class Config:
    SECRET_KEY = os.urandom(24)
    SQLALCHEMY_DATABASE_URI = "sqlite:///saveablood.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


# -------------------------------------
# Flask Initialization
# -------------------------------------
app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)


# -------------------------------------
# Database Models
# -------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    blood_type = db.Column(db.String(3), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # donor or recipient

    blood_posts = db.relationship('BloodPost', backref='author', lazy=True)
    blood_requests = db.relationship('BloodRequest', backref='requester', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class BloodPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class BloodRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blood_type_needed = db.Column(db.String(3), nullable=False)
    location_needed = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


# -------------------------------------
# Routes
# -------------------------------------
@app.route('/')
def home():
    """First page (public home with flash animation)."""
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')


@app.route('/index')
def index():
    """Login/Register page."""
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """User dashboard."""
    if 'username' not in session:
        return redirect(url_for('index'))

    user = User.query.filter_by(username=session['username']).first()
    posts = BloodPost.query.all()
    requests = BloodRequest.query.filter_by(location_needed=user.location).all()
    return render_template('dashboard.html', username=user.username, posts=posts, requests=requests)


@app.route('/login', methods=['POST'])
def login():
    """Handle login."""
    username = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        session['username'] = username
        return redirect(url_for('dashboard'))
    return render_template('index.html', error="Invalid username or password.")


@app.route('/register', methods=['POST'])
def register():
    """Handle registration."""
    username = request.form['new_username']
    password = request.form['new_password']
    blood_type = request.form['blood_type']
    location = request.form['location']
    role = request.form['role']

    if User.query.filter_by(username=username).first():
        return render_template('index.html', error="Username already exists.")

    new_user = User(username=username, blood_type=blood_type, location=location, role=role)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    session['username'] = username
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    """Log out and return to home page."""
    session.pop('username', None)
    return redirect(url_for('home'))


@app.route('/post_blood', methods=['POST'])
def post_blood():
    """Post a donation."""
    if 'username' not in session:
        return redirect(url_for('index'))

    content = request.form['content']
    user = User.query.filter_by(username=session['username']).first()
    new_post = BloodPost(content=content, user_id=user.id)
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/request_blood', methods=['POST'])
def request_blood():
    """Request blood."""
    if 'username' not in session:
        return redirect(url_for('index'))

    blood_type_needed = request.form['blood_type_needed']
    location_needed = request.form['location_needed']
    user = User.query.filter_by(username=session['username']).first()
    new_request = BloodRequest(blood_type_needed=blood_type_needed,
                               location_needed=location_needed,
                               user_id=user.id)
    db.session.add(new_request)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/search', methods=['GET', 'POST'])
def search():
    """Search for donors."""
    if 'username' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        blood_type = request.form['blood_type']
        location = request.form['location']
        donors = User.query.filter_by(blood_type=blood_type, location=location, role='donor').all()
        return render_template('search_results.html', donors=donors)
    return render_template('search_results.html')


# -------------------------------------
# Run App
# -------------------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
