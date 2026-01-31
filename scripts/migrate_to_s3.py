import os
import json
import sqlite3
import pandas as pd
from config import Config
from utils.s3_utils import S3Manager

def migrate_files(s3):
    """Uploads all files from local upload directories to S3."""
    directories = [
        (Config.UPLOAD_AUDIO_DIR, Config.S3_AUDIO_PREFIX),
        (Config.UPLOAD_TRANSCRIPTION_DIR, Config.S3_TRANSCRIPTION_PREFIX),
        (Config.TRIBAL_AUDIO_DIR, Config.S3_TRIBAL_AUDIO_PREFIX),
        (Config.TRIBAL_TRANSCRIPTION_DIR, Config.S3_TRIBAL_TRANSCRIPTION_PREFIX)
    ]

    total_uploaded = 0
    errors = 0

    print("🚀 Starting File Migration...")

    for local_dir, s3_prefix in directories:
        if not os.path.exists(local_dir):
            print(f"⚠️ Directory not found: {local_dir}, skipping.")
            continue

        print(f"📂 Processing {local_dir} -> {s3_prefix}...")
        
        for filename in os.listdir(local_dir):
            file_path = os.path.join(local_dir, filename)
            
            # Skip directories
            if not os.path.isfile(file_path):
                continue
                
            s3_key = f"{s3_prefix}{filename}"
            
            print(f"   ⬆️ Uploading {filename}...", end="\r")
            if s3.upload_file(file_path, s3_key):
                total_uploaded += 1
            else:
                errors += 1
                print(f"   ❌ Failed to upload {filename}")
        
        print(f"✅ Finished {local_dir}")

    print(f"\n✨ File Migration Complete. Uploaded: {total_uploaded}, Errors: {errors}")

def export_prompts(s3):
    """Exports all prompts from SQLite databases to S3."""
    print("\n🚀 Starting Prompt Database Export...")
    
    dbs = [
        ("Standard Dictionary", Config.DB_PATH, "all_standard_prompts.csv"),
        ("Tribal Dictionary", Config.TRIBAL_DB_PATH, "all_tribal_prompts.csv")
    ]

    for name, db_path, export_filename in dbs:
        if not os.path.exists(db_path):
            print(f"⚠️ Database not found: {db_path}, skipping.")
            continue

        try:
            conn = sqlite3.connect(db_path)
            query = "SELECT * FROM prompts"
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            # Save to CSV string
            csv_buffer = df.to_csv(index=False)
            
            # Upload to S3
            s3_key = f"{Config.S3_METADATA_PREFIX}{export_filename}"
            if s3.upload_string(csv_buffer, s3_key):
                print(f"✅ Exported {name} ({len(df)} rows) to s3://{s3.bucket_name}/{s3_key}")
            else:
                print(f"❌ Failed to export {name}")

        except Exception as e:
            print(f"❌ Error exporting {name}: {e}")

if __name__ == "__main__":
    if not Config.AWS_ACCESS_KEY_ID or not Config.S3_BUCKET_NAME:
        print("❌ Error: AWS credentials not found in .env")
        exit(1)

    s3_manager = S3Manager()
    
    migrate_files(s3_manager)
    export_prompts(s3_manager)
