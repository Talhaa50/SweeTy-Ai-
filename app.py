from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timezone, timedelta
import uuid
import os
import json
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


# -------------------- JSON STORAGE --------------------
def get_chat_file_path(session_id):
    chat_dir = os.path.join(os.path.dirname(__file__), 'chat_data')
    os.makedirs(chat_dir, exist_ok=True)
    return os.path.join(chat_dir, f'{session_id}.json')

def save_message_to_json(session_id, role, content):
    file_path = get_chat_file_path(session_id)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {'messages': [], 'conversations': []}

    data['messages'].append({
        'role': role,
        'content': content,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_conversation_to_json(session_id, user_message, ai_response):
    file_path = get_chat_file_path(session_id)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {'messages': [], 'conversations': []}

    data['conversations'].append({
        'user_message': user_message,
        'ai_response': ai_response,
        'timestamp': datetime.now(timezone.utc).isoformat() 
    })

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_chat_history_from_json(session_id, limit=10):
    file_path = get_chat_file_path(session_id)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        messages = data.get('messages', [])
        return messages[-limit:] if len(messages) > limit else messages
    except:
        return []

def get_conversation_history_from_json(session_id, limit=20):
    file_path = get_chat_file_path(session_id)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        conversations = data.get('conversations', [])
        return conversations[-limit:] if len(conversations) > limit else conversations
    except:
        return []

def clear_chat_json(session_id):
    file_path = get_chat_file_path(session_id)
    if os.path.exists(file_path):
        os.remove(file_path)


# -------------------- SESSION HELPERS --------------------
def get_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]

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

        if user and user.password == password:  # direct raw comparison
            session['user_id'] = user.id
            session['username'] = user.username

            # -------------------- EMAIL FEATURE --------------------
            try:
                send_login_email(user.email)
            except Exception as e:
                print(f"⚠️ Email could not be sent: {e}")
            # -------------------------------------------------------

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
            password=password   # raw storage
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

        session_id = get_session_id()
        save_message_to_json(session_id, "user", user_message)

        messages = get_chat_history_from_json(session_id, limit=10)
        ai_reply = ai_integration.get_response(messages)

        save_message_to_json(session_id, "assistant", ai_reply)
        save_conversation_to_json(session_id, user_message, ai_reply)

        return jsonify({"response": ai_reply})

    except Exception as e:
        print(f"Error in /chat route: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/history", methods=["GET"])
def history():
    try:
        session_id = get_session_id()
        conversations = get_conversation_history_from_json(session_id, limit=20)
        return jsonify({"conversations": conversations})
    except Exception as e:
        print(f"Error in /history route: {e}")
        return jsonify({"conversations": []})

@app.route("/new-session", methods=["POST"])
def new_session():
    try:
        session_id = get_session_id()
        clear_chat_json(session_id)
        session.pop("session_id", None)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error in /new-session route: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/reset", methods=["POST"])
def reset():
    try:
        session_id = get_session_id()
        clear_chat_json(session_id)
        return jsonify({"message": "Chat reset successfully"})
    except Exception as e:
        print(f"Error in /reset route: {e}")
        return jsonify({"error": "Failed to reset chat"}), 500
    

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
