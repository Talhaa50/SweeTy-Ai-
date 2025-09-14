from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Local imports
from groq_integration import SweetyAI
from config import Config

# -------------------- APP SETUP --------------------
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Database
db = SQLAlchemy(app)

# AI Integration
ai_integration = SweetyAI()

# Email credentials
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


# -------------------- MODELS --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)  # raw password storage
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

# Create tables safely
with app.app_context():
    try:
        db.create_all()
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"⚠️ Database initialization error: {e}")


# -------------------- SESSION HELPERS --------------------
def is_logged_in():
    return 'user_id' in session

def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


# -------------------- AUTH ROUTES --------------------
@app.route("/login")
def login_page():
    if is_logged_in():
        return redirect(url_for('index'))
    return render_template("login.html")

@app.route("/signup")
def signup_page():
    if is_logged_in():
        return redirect(url_for('index'))
    return render_template("signup.html")

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.password == password:
            session['user_id'] = user.id
            session['username'] = user.username
            
            
            return jsonify({"success": True, "username": user.username})
        else:
            return jsonify({"error": "Invalid username or password"}), 401

    except Exception as e:
        print(f"Error in login: {e}")
        return jsonify({"error": "Login failed"}), 500

@app.route("/api/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not all([username, email, password]):
            return jsonify({"error": "All fields are required"}), 400

        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username already exists"}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already exists"}), 400

        user = User(
            username=username,
            email=email,
            password=password
        )
        db.session.add(user)
        db.session.commit()

        return jsonify({"success": True, "username": user.username})

    except Exception as e:
        print(f"Error in signup: {e}")
        db.session.rollback()
        return jsonify({"error": "Signup failed"}), 500

@app.route("/api/user-status", methods=["GET"])
def user_status():
    try:
        if is_logged_in():
            user = get_current_user()
            if user:
                return jsonify({
                    "logged_in": True,
                    "username": user.username,
                    "user_id": user.id
                })
        return jsonify({"logged_in": False})
    except Exception as e:
        print(f"Error in user-status: {e}")
        return jsonify({"logged_in": False})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index'))


# -------------------- MAIN ROUTES --------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_message = request.json.get("message", "").strip()
        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400

        # ephemeral chat: store in session only until browser closes
        session_messages = session.get("messages", [])
        session_messages.append({"role": "user", "content": user_message})

        ai_reply = ai_integration.get_response(session_messages)
        session_messages.append({"role": "assistant", "content": ai_reply})

        session["messages"] = session_messages

        return jsonify({"response": ai_reply})

    except Exception as e:
        print(f"Error in /chat route: {e}")
        return jsonify({"error": "Internal server error"}), 500


# -------------------- OTHER ROUTES --------------------
@app.route("/voice/transcribe", methods=["POST"])
def transcribe_voice():
    return jsonify({"text": "Voice transcription not implemented yet"})

@app.route("/settings")
def settings():
    if not is_logged_in():
        return redirect(url_for('login_page'))
    user = get_current_user()
    return render_template("settings.html", user=user)


# ------------------ EMAIL FUNCTION ------------------
def send_login_email(to_email):
    subject = "🎉 Alert: Someone Logged In!"
    body = f"""
    Hello,

    A login was just detected on your SweetyAI account:
    
    - Email: {to_email}
    - Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

    If this was you, ignore this message.
    If not, please reset your password immediately.

    Regards,
    SweetyAI Security Team
    """

    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())
            print(f"📧 Login alert sent to {to_email}")
    except Exception as e:
        print(f"⚠️ Email sending failed: {e}")


# -------------------- PRODUCTION SETUP --------------------
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
