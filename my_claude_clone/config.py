import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-claude-clone-change-me')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///claude_clone.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # AI Providers
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
    GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID', '')
    
    AI_PROVIDER = os.getenv('AI_PROVIDER', 'mock')  # anthropic, openrouter, groq, mock
    AI_MODEL = os.getenv('AI_MODEL', 'claude-3-5-sonnet-20241022')
    
    # App
    APP_NAME = "Claude Clone"
