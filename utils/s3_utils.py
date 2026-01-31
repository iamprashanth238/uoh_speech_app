import boto3
import os
from config import Config

class S3Manager:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.S3_REGION
        )
        self.bucket_name = Config.S3_BUCKET_NAME

    def upload_file(self, file_path, s3_key):
        """Uploads a file from local path to S3."""
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            return True
        except Exception as e:
            print(f"❌ S3 Error uploading file {file_path} to {s3_key}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def upload_fileobj(self, file_obj, s3_key):
        """Uploads a file object (like a Flask file storage object) to S3."""
        try:
            self.s3_client.upload_fileobj(file_obj, self.bucket_name, s3_key)
            return True
        except Exception as e:
            print(f"Error uploading file object to {s3_key}: {e}")
            return False

    def upload_string(self, content, s3_key):
        """Uploads a string content to S3."""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content.encode("utf-8"),
                ContentType="text/plain; charset=utf-8"
            )
            return True
        except Exception as e:
            print(f"Error uploading string to {s3_key}: {e}")
            return False
            
    def list_files(self, prefix):
        """List files in a given prefix."""
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' in response:
                return [f['Key'] for f in response['Contents']]
            return []
        except Exception as e:
            print(f"Error listing files in {prefix}: {e}")
            return []

    def export_db_to_csv(self, db_path, s3_key, query="SELECT * FROM prompts"):
        """Reads a SQLite DB and exports query results to S3 as CSV."""
        import sqlite3
        import pandas as pd
        
        if not os.path.exists(db_path):
            return False
            
        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            csv_buffer = df.to_csv(index=False)
            return self.upload_string(csv_buffer, s3_key)
        except Exception as e:
            print(f"Error exporting DB {db_path} to {s3_key}: {e}")
            return False

    def count_files(self, prefix):
        """Counts the number of objects with a given prefix."""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            count = 0
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    count += len(page['Contents'])
            return count
        except Exception as e:
            print(f"❌ S3 Error counting files with prefix '{prefix}': {e}")
            import traceback
            traceback.print_exc()
            return 0

    def read_file(self, s3_key):
        """Reads a file from S3 and returns its content as a string."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response['Body'].read().decode('utf-8')
        except Exception as e:
            print(f"❌ S3 Error reading file {s3_key}: {e}")
            return None

    def move_file(self, source_key, dest_key):
        """Moves a file from source_key to dest_key (Copy + Delete)."""
        try:
            # Copy
            copy_source = {'Bucket': self.bucket_name, 'Key': source_key}
            self.s3_client.copy_object(CopySource=copy_source, Bucket=self.bucket_name, Key=dest_key)
            # Delete
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=source_key)
            return True
        except Exception as e:
            print(f"Error moving file {source_key} to {dest_key}: {e}")
            return False

    def get_all_file_keys(self, prefix):
        """Returns a list of all file keys in a prefix, EXCLUDING sub-folders (inprogress/used)."""
        keys = []
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        # Filter out 'inprogress/' and 'used/' if they are sub-folders of this prefix
                        # Logic: If the key contains the prefix + "inprogress/" or "used/", skip it.
                        if "inprogress/" in key or "used/" in key:
                            continue
                        # Also ensure it's not the directory itself (if created empty)
                        if key.endswith('/'):
                            continue
                        keys.append(key)
            return keys
        except Exception as e:
            print(f"Error listing all files in {prefix}: {e}")
            return []

    def check_file_exists(self, key):
        """Checks if a file exists in S3 without downloading it."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except:
            return False

    def get_random_file_from_prefix(self, prefix, lock=False):
        """
        Pick a random text file from the prefix.
        Ensures the prompt is NOT in the 'used/' folder (Duplicate Check).
        Default is False (as per simplified lifecycle).
        Returns: (new_key, content)
        """
        import random
        keys = self.get_all_file_keys(prefix)
        # Filter for text files only
        txt_keys = [k for k in keys if k.lower().endswith('.txt')]
        
        if not txt_keys:
            return None, None
            
        # Try to find a unique unsed prompt
        for _ in range(20): # Try 20 times to find a non-duplicate
            selected_key = random.choice(txt_keys)
            
            # Construct the theoretical 'used' key
            # prefix: "prompts/standard/"
            # selected_key: "prompts/standard/UOH_123.txt"
            filename = os.path.basename(selected_key)
            
            # Determine correct used folder based on prefix
            if "tribal" in prefix:
                 used_prefix = Config.S3_PROMPTS_TRIBAL_USED
            else:
                 used_prefix = Config.S3_PROMPTS_STANDARD_USED
                 
            used_key = used_prefix + filename
            
            # CHECK: If this file is already in the used folder?
            if self.check_file_exists(used_key):
                print(f"⚠️ Prompt {filename} is marked as USED (Duplicate found). Skipping...")
                # Optional: self.delete_file(selected_key) ?
                # For now, just skip.
                # Remove from local list so we don't pick it again in this loop
                if selected_key in txt_keys:
                    txt_keys.remove(selected_key)
                if not txt_keys:
                    return None, None
                continue
            
            # Found a unique one!
            content = self.read_file(selected_key)
            return selected_key, content
            
        return None, None
