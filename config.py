import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = 'your-secret-key-here'  # Change this to a secure random key
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')    
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    DB_PATH = "prompts.db"
    TRIBAL_DB_PATH = "telugu_tribe.db"
    
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    S3_REGION = os.getenv('S3_REGION', 'ap-south-1') # Default to a common region or update as needed

    # S3 Prefixes (Folders)
    S3_AUDIO_PREFIX = "audio/standard/"
    S3_TRANSCRIPTION_PREFIX = "transcription/standard/"
    S3_TRIBAL_AUDIO_PREFIX = "audio/tribal/"
    S3_TRIBAL_TRANSCRIPTION_PREFIX = "transcription/tribal/"
    
    # Updated Prompt Prefixes
    S3_PROMPTS_STANDARD_PREFIX = "prompts/standard/"
    S3_PROMPTS_STANDARD_USED = "prompts/standard/used/"
    
    S3_PROMPTS_TRIBAL_PREFIX = "prompts/tribal/"
    S3_PROMPTS_TRIBAL_USED = "prompts/tribal/used/"
    
    S3_METADATA_PREFIX = "metadata/"
    
    
    
    # Upload Directories (Required for main_routes.py)
    # Upload Directories (Required for main_routes.py)
    # Using temp directory to allow writes on Serverless (Vercel) /tmp
    import tempfile
    BASE_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), 'uoh_speech_uploads')
    
    UPLOAD_AUDIO_DIR = os.path.join(BASE_UPLOAD_DIR, "audio")
    UPLOAD_TRANSCRIPTION_DIR = os.path.join(BASE_UPLOAD_DIR, "transcription")
    TRIBAL_AUDIO_DIR = os.path.join(BASE_UPLOAD_DIR, "tribe-audio")
    TRIBAL_TRANSCRIPTION_DIR = os.path.join(BASE_UPLOAD_DIR, "tribe-transcription")
    
    # Restoring missing configs to prevent system crash (AttributeErrors)
    S3_PROMPTS_STANDARD_INPROGRESS = "prompts/standard/inprogress/"
    S3_PROMPTS_TRIBAL_INPROGRESS = "prompts/tribal/inprogress/"

    # Email Configuration (Required for utils/email_utils.py)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    try:
        MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    except ValueError:
        MAIL_PORT = 587
    MAIL_USE_TLS = str(os.getenv('MAIL_USE_TLS', 'true')).lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@uoh-speech.com')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
