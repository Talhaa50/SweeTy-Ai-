import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'fallback-secret-key-change-in-production'
    
    # Database
    instance_dir = os.path.join(basedir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    'sqlite:///' + os.path.join(instance_dir, 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # OpenAI API
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')
    
    # Optional voice settings
    ENABLE_VOICE = os.environ.get('ENABLE_VOICE', 'False').lower() == 'true'
    ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
    ELEVENLABS_VOICE_ID = os.environ.get('ELEVENLABS_VOICE_ID')