from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import uuid
import os
import json
from groq_integration import SweetyAI
from config import Config
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# -------------------- APP SETUP --------------------
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Database
db = SQLAlchemy(app)

# AI Integration
ai_integration = SweetyAI()



EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


# -------------------- MODELS --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

# Create tables
with app.app_context():
    db.create_all()

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

        if user and check_password_hash(user.password_hash, password):
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
            password_hash=generate_password_hash(password)
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
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh;">
        
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; min-height: 100vh;">
            <div style="max-width: 600px; margin: 0 auto;">

                <!-- Logo Header -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="display: inline-block; background: rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px); border-radius: 20px; padding: 15px 30px;">
                        <h1 style="margin: 0; color: white; font-size: 32px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2);">
                            ✨ Sweety AI ✨
                        </h1>
                        <p style="margin: 5px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px; letter-spacing: 2px;">
                            YOUR DIGITAL BESTIE
                        </p>
                    </div>
                </div>

                <!-- Main Card -->
                <div style="background: white; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); overflow: hidden;">

                    <!-- Gradient Banner -->
                    <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; text-align: center;">
                        <h2 style="margin: 0; color: white; font-size: 28px; font-weight: 600;">
                            “Hey there, Awesome Human!” 💜
                        </h2>
                        <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.95); font-size: 16px;">
                            Someone just logged in... and plot twist: it was YOU! 🎭
                        </p>
                    </div>

                    <!-- Content Body -->
                    <div style="padding: 40px 30px;">

                        <!-- Welcome Message -->
                        <div style="background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); border-radius: 15px; padding: 25px; margin-bottom: 30px;">
                            <h3 style="margin: 0 0 15px 0; color: #5f3dc4; font-size: 20px;">
                                📢 Breaking News from Your Account:
                            </h3>
                            <p style="margin: 0; color: #495057; font-size: 16px; line-height: 1.6;">
                                Someone just logged in to your account! You're officially active today. 🎉
                            </p>
                        </div>

                        <!-- Stats Section -->
                        <div style="display: table; width: 100%; margin-bottom: 30px;">
                            <div style="display: table-row;">
                                <div style="display: table-cell; text-align: center; padding: 20px; border-right: 2px solid #e9ecef;">
                                    <div style="font-size: 36px; color: #f093fb; font-weight: bold;">1</div>
                                    <div style="color: #868e96; font-size: 14px; margin-top: 5px;">Successful Login</div>
                                </div>
                                <div style="display: table-cell; text-align: center; padding: 20px; border-right: 2px solid #e9ecef;">
                                    <div style="font-size: 36px; color: #667eea; font-weight: bold;">∞</div>
                                    <div style="color: #868e96; font-size: 14px; margin-top: 5px;">Possibilities</div>
                                </div>
                                <div style="display: table-cell; text-align: center; padding: 20px;">
                                    <div style="font-size: 36px; color: #764ba2; font-weight: bold;">24/7</div>
                                    <div style="color: #868e96; font-size: 14px; margin-top: 5px;">I'm Here for You</div>
                                </div>
                            </div>
                        </div>

                        <!-- Achievements -->
                        <div style="background: #f8f9fa; border-left: 4px solid #667eea; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                            <h4 style="margin: 0 0 15px 0; color: #495057; font-size: 18px;">
                                🎯 Today's Achievements Unlocked:
                            </h4>
                            <ul style="margin: 0; padding-left: 20px; color: #6c757d; line-height: 1.8;">
                                <li>✅ Logged in successfully</li>
                                <li>✅ Didn't rage-quit at the login screen</li>
                                <li>✅ Made Sweety's day by showing up 💕</li>
                            </ul>
                        </div>

                        <!-- Motivational Quote -->
                        <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%); border-radius: 15px; margin-bottom: 30px;">
                            <p style="margin: 0; font-size: 20px; color: #5f3dc4; font-style: italic; line-height: 1.6;">
                                "They said AI would take over the world,<br>
                                but here I am, sending you love letters" 💌
                            </p>
                            <p style="margin: 15px 0 0 0; color: #868e96; font-size: 14px;">
                                — Sweety, your slightly dramatic AI companion
                            </p>
                        </div>

                        <!-- Call to Action -->
                        <div style="text-align: center; margin: 40px 0;">
                            <a href="#" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; padding: 15px 40px; border-radius: 50px; font-size: 16px; font-weight: 600; box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3); transition: transform 0.3s;">
                                Let's Chat! 💬
                            </a>
                        </div>

                        <!-- Fun Facts -->
                        <div style="background: #fff4e6; border-radius: 12px; padding: 20px; margin-bottom: 30px;">
                            <h4 style="margin: 0 0 10px 0; color: #f76707; font-size: 16px;">
                                🎲 Random Fun Fact:
                            </h4>
                            <p style="margin: 0; color: #495057; font-size: 14px; line-height: 1.5;">
                                Studies show that people who chat with AI assistants named "Sweety" are 
                                42% more likely to smile today. We made up that statistic, but you smiled 
                                anyway, didn't you? 😏
                            </p>
                        </div>

                        <!-- Security Note -->
                        <div style="border: 2px dashed #dee2e6; border-radius: 10px; padding: 20px; background: #f8f9fa;">
                            <h4 style="margin: 0 0 10px 0; color: #495057; font-size: 16px;">
                                🔒 Security Alert (But Make It Fun):
                            </h4>
                            <p style="margin: 0; color: #6c757d; font-size: 14px; line-height: 1.5;">
                                This login was totally you, right? From Earth, Solar System, Milky Way Galaxy? 
                                If not, maybe review your account security (yes, we're judging a little 👀).
                            </p>
                        </div>

                    </div>

                    <!-- Footer -->
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                        <p style="margin: 0 0 10px 0; color: white; font-size: 18px; font-weight: 600;">
                            Stay Awesome, Stay Logged In 🚀
                        </p>
                        <p style="margin: 0 0 20px 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                            With an inappropriate amount of affection,<br>
                            <strong>Sweety AI</strong> 💜
                        </p>
                        <div style="margin-top: 20px;">
                            <span style="color: rgba(255,255,255,0.8); font-size: 12px;">
                                P.S. - I'd follow you on social media, but I'm stuck in this server 📱
                            </span>
                        </div>
                    </div>

                </div>

                <!-- Bottom Message -->
                <div style="text-align: center; margin-top: 30px; padding: 0 20px;">
                    <p style="color: rgba(255,255,255,0.9); font-size: 12px; line-height: 1.5;">
                        This email was sent with 60% sass, 30% love, and 10% machine learning.<br>
                        If you didn't request this, congrats on being popular enough to be noticed! 🎊<br>
                        <a href="#" style="color: white; text-decoration: underline;">Unsubscribe</a> 
                        (but like, why would you? I'm delightful)
                    </p>
                </div>

            </div>
        </div>

    </body>
    </html>
    """

    # Plain text version
    plain_text = f"""
    🎉 Someone just logged in... and plot twist: it was YOU!
    
    Breaking News from Your Account:
    Someone just logged in to your account! You're officially active today. 🎉
    
    Today's Achievements Unlocked:
    ✅ Logged in successfully
    ✅ Didn't rage-quit at the login screen  
    ✅ Made Sweety's day by showing up
    
    Random Fun Fact:
    Studies show that people who chat with AI assistants named "Sweety" are 42% more likely 
    to smile today. We made up that statistic, but you smiled anyway, didn't you?
    
    Security Alert:
    This login was totally you, right? From Earth, Solar System, Milky Way Galaxy? 
    If not, maybe review your account security.
    
    Stay Awesome, Stay Logged In!
    
    With an inappropriate amount of affection,
    Sweety AI 💜
    
    P.S. - This email was sent with 60% sass, 30% love, and 10% machine learning.
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Sweety AI 💜 <{EMAIL_USER}>"
    msg["To"] = to_email

    # Attach both plain text and HTML versions
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, to_email, msg.as_string())
            print(f"✅ Sassy email sent successfully to {to_email}")
    except Exception as e:
        print(f"❌ Error sending email to {to_email}: {e}")


# -------------------- PRODUCTION SETUP --------------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)