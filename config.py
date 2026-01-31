import os
import tempfile
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')    
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
    
    # Use absolute paths for SQLite databases
    DB_PATH = os.path.join(BASE_DIR, "prompts.db")
    TRIBAL_DB_PATH = os.path.join(BASE_DIR, "telugu_tribe.db")
    
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    
    # Prioritize S3_REGION to avoid collision with Vercel's default AWS_REGION (e.g., iad1)
    _raw_region = os.getenv('S3_REGION', os.getenv('AWS_REGION', 'eu-north-1'))
    if _raw_region and ' ' in _raw_region:
        # Extract the last part which is usually the region code like 'eu-north-1'
        S3_REGION = _raw_region.split()[-1].strip()
    else:
        S3_REGION = _raw_region


    # S3 Prefixes (Folders)
    S3_AUDIO_PREFIX = "audio/standard/"
    S3_TRANSCRIPTION_PREFIX = "transcription/standard/"
    S3_TRIBAL_AUDIO_PREFIX = "audio/tribal/"
    S3_TRIBAL_TRANSCRIPTION_PREFIX = "transcription/tribal/"
    
    # Updated Prompt Prefixes
    S3_PROMPTS_STANDARD_PREFIX = "prompts/standard/"
    S3_PROMPTS_STANDARD_USED = "prompts/standard/used/"
    S3_PROMPTS_STANDARD_ENGLISH_PREFIX = "prompts/en-transcription-std/"
    S3_PROMPTS_STANDARD_ENGLISH_USED = "prompts/en-transcription-std/used/"
    
    S3_PROMPTS_TRIBAL_PREFIX = "prompts/tribal/"
    S3_PROMPTS_TRIBAL_USED = "prompts/tribal/used/"
    S3_PROMPTS_TRIBAL_ENGLISH_PREFIX = "prompts/en-transcription-tribal/"
    S3_PROMPTS_TRIBAL_ENGLISH_USED = "prompts/en-transcription-tribal/used/"
    
    S3_METADATA_PREFIX = "metadata/"
    
    # Upload Directories (Required for main_routes.py)
    # Using temp directory to allow writes on Serverless (Vercel) /tmp
    BASE_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), 'uoh_speech_uploads')
    
    UPLOAD_AUDIO_DIR = os.path.join(BASE_UPLOAD_DIR, "audio")
    UPLOAD_TRANSCRIPTION_DIR = os.path.join(BASE_UPLOAD_DIR, "transcription")
    TRIBAL_AUDIO_DIR = os.path.join(BASE_UPLOAD_DIR, "tribe-audio")
    TRIBAL_TRANSCRIPTION_DIR = os.path.join(BASE_UPLOAD_DIR, "tribe-transcription")
    
    # Restoring missing configs to prevent system crash (AttributeErrors)
    S3_PROMPTS_STANDARD_INPROGRESS = "prompts/standard/inprogress/"
    S3_PROMPTS_TRIBAL_INPROGRESS = "prompts/tribal/inprogress/"
    S3_PROMPTS_STANDARD_ENGLISH_INPROGRESS = "prompts/en-transcription-std/inprogress/"
    S3_PROMPTS_TRIBAL_ENGLISH_INPROGRESS = "prompts/en-transcription-tribal/inprogress/"

    # Email Configuration (Required for utils/email_utils.py)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    try:
        MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    except (ValueError, TypeError):
        MAIL_PORT = 587
    MAIL_USE_TLS = str(os.getenv('MAIL_USE_TLS', 'true')).lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@uoh-speech.com')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')

