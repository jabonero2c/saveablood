from flask import Flask, render_template, request, redirect, session, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os


class Config:
    SECRET_KEY = os.urandom(24)
    SQLALCHEMY_DATABASE_URI = "sqlite:///saveablood.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)


# --- Database Models ---

class BloodBank(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    location = db.Column(db.String(100), nullable=False)

    # Simple inventory tracking by blood type (unit count)
    A_pos = db.Column(db.Integer, default=10)
    B_pos = db.Column(db.Integer, default=10)
    O_pos = db.Column(db.Integer, default=10)
    AB_pos = db.Column(db.Integer, default=10)
    A_neg = db.Column(db.Integer, default=10)
    B_neg = db.Column(db.Integer, default=10)
    O_neg = db.Column(db.Integer, default=10)
    AB_neg = db.Column(db.Integer, default=10)

    # Relationships
    posts = db.relationship('BloodPost', backref='blood_bank', lazy=True)
    requests = db.relationship('BloodRequest', backref='target_bank', lazy=True)

    def get_inventory(self):
        """Returns inventory as a dictionary."""
        return {
            "A+": self.A_pos, "B+": self.B_pos, "O+": self.O_pos, "AB+": self.AB_pos,
            "A-": self.A_neg, "B-": self.B_neg, "O-": self.O_neg, "AB-": self.AB_neg,
        }

    def update_inventory(self, blood_type, operation='donate'):
        """Updates inventory based on donation or request."""
        type_map = {
            'A+': 'A_pos', 'B+': 'B_pos', 'O+': 'O_pos', 'AB+': 'AB_pos',
            'A-': 'A_neg', 'B-': 'B_neg', 'O-': 'O_neg', 'AB-': 'AB_neg',
        }
        col_name = type_map.get(blood_type)
        if not col_name:
            return False

        current_value = getattr(self, col_name)

        if operation == 'donate':
            setattr(self, col_name, current_value + 1)
            db.session.commit()
            return True
        elif operation == 'request' and current_value > 0:
            setattr(self, col_name, current_value - 1)
            db.session.commit()
            return True  # Request fulfilled

        return False  # Request could not be fulfilled (inventory too low)


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
    blood_bank_id = db.Column(db.Integer, db.ForeignKey('blood_bank.id'), nullable=True)  # Where the blood went


class BloodRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blood_type_needed = db.Column(db.String(3), nullable=False)
    location_needed = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blood_bank_id = db.Column(db.Integer, db.ForeignKey('blood_bank.id'), nullable=False)  # Which bank is targeted
    is_fulfilled = db.Column(db.Boolean, default=False)


# --- Routes ---

@app.route('/')
def home():
    """Public home page (with flash animation)."""
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
    """User dashboard - redirects based on role."""
    if 'username' not in session:
        return redirect(url_for('index'))

    user = User.query.filter_by(username=session['username']).first()

    if user.role == 'donor':
        # Donor specific data
        posts = BloodPost.query.filter_by(user_id=user.id).order_by(BloodPost.id.desc()).all()
        # Suggest banks nearby for donation
        banks_nearby = BloodBank.query.filter_by(location=user.location).all()
        all_banks = BloodBank.query.all()
        return render_template('donor_dashboard.html', user=user, posts=posts, banks_nearby=banks_nearby,
                               all_banks=all_banks)

    elif user.role == 'recipient':
        # Recipient specific data
        requests = BloodRequest.query.filter_by(user_id=user.id).order_by(BloodRequest.id.desc()).all()
        return render_template('recipient_dashboard.html', user=user, requests=requests)

    # Should not happen
    return "Unknown role or profile error.", 400


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


@app.route('/post_donation', methods=['POST'])
def post_donation():
    """Donor action: Post a donation to a specific blood bank."""
    if 'username' not in session:
        return redirect(url_for('index'))

    user = User.query.filter_by(username=session['username']).first()
    if user.role != 'donor':
        return redirect(url_for('dashboard'))

    blood_bank_id = request.form.get('blood_bank_id')
    content = request.form['content']

    bank = BloodBank.query.get(blood_bank_id)
    if not bank:
        # Bank not found (shouldn't happen with proper form)
        return redirect(url_for('dashboard'))

    # 1. Update Blood Bank Inventory (Donation = +1 unit)
    bank.update_inventory(user.blood_type, operation='donate')

    # 2. Record the donation post
    new_post = BloodPost(content=f"Donated {user.blood_type} unit to {bank.name}: {content}",
                         user_id=user.id,
                         blood_bank_id=blood_bank_id)
    db.session.add(new_post)
    db.session.commit()

    return redirect(url_for('dashboard'))


@app.route('/blood_banks')
def blood_banks():
    """Recipient page: List all available blood banks."""
    if 'username' not in session:
        return redirect(url_for('index'))

    user = User.query.filter_by(username=session['username']).first()
    if user.role != 'recipient':
        # Donors can also browse banks if needed, but primary feature for recipient
        return redirect(url_for('dashboard'))

    all_banks = BloodBank.query.all()
    return render_template('blood_banks.html', user=user, all_banks=all_banks)


@app.route('/blood_bank_inventory/<int:bank_id>')
def blood_bank_inventory(bank_id):
    """Recipient page: View detailed inventory of a single blood bank."""
    if 'username' not in session:
        return redirect(url_for('index'))

    user = User.query.filter_by(username=session['username']).first()
    if user.role != 'recipient':
        # Deny access if not a recipient
        return redirect(url_for('dashboard'))

    bank = BloodBank.query.get_or_404(bank_id)
    inventory = bank.get_inventory()

    # Blood types relevant to the current user (e.g. if they need O+, show who can give it)
    blood_types = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]

    return render_template('blood_bank_inventory.html', user=user, bank=bank, inventory=inventory,
                           blood_types=blood_types)


@app.route('/request_blood', methods=['POST'])
def request_blood():
    """Recipient action: Request blood from a specific bank."""
    if 'username' not in session:
        return redirect(url_for('index'))

    user = User.query.filter_by(username=session['username']).first()
    if user.role != 'recipient':
        return redirect(url_for('dashboard'))

    blood_type_needed = request.form['blood_type_needed']
    blood_bank_id = request.form['blood_bank_id']

    bank = BloodBank.query.get(blood_bank_id)

    # 1. Check and Update Blood Bank Inventory (Request = -1 unit if available)
    is_fulfilled = False
    if bank:
        is_fulfilled = bank.update_inventory(blood_type_needed, operation='request')

    # 2. Record the request
    new_request = BloodRequest(blood_type_needed=blood_type_needed,
                               location_needed=bank.location if bank else "Unknown",
                               user_id=user.id,
                               blood_bank_id=blood_bank_id,
                               is_fulfilled=is_fulfilled)
    db.session.add(new_request)
    db.session.commit()

    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Initialize Blood Banks if none exist for demonstration purposes
        if not BloodBank.query.first():
            print("Initializing Blood Banks...")
            db.session.add(BloodBank(name='Central City Blood Center', location='New York', O_neg=3, A_pos=50))
            db.session.add(
                BloodBank(name='Metropolitan General Hospital Bank', location='New York', B_pos=20, A_neg=20))
            db.session.add(BloodBank(name='Dallas Community Bank', location='Dallas', O_pos=100, AB_neg=1))
            db.session.add(
                BloodBank(name='San Diego LifeSource', location='San Diego', A_pos=10, B_pos=10, O_pos=10, AB_pos=10,
                          A_neg=10, B_neg=10, O_neg=10, AB_neg=10))
            db.session.commit()
    app.run(debug=True)
