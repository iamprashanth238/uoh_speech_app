import sqlite3
from datetime import datetime, timedelta
from flask import session
from config import Config

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_db_path_for_user():
    user_info = session.get("user_info", {})
    state = user_info.get("state", "")
    if state in ["TS-Tribal", "AP-Tribal"]:
        return Config.TRIBAL_DB_PATH
    return Config.DB_PATH

def reset_old_in_progress_prompts(db_path):
    try:
        conn = get_db_connection(db_path)
        cur = conn.cursor()
        
        # Reset prompts that have been in_progress for more than 30 minutes
        cutoff_time = datetime.now() - timedelta(minutes=30)
        cur.execute("""
            UPDATE prompts 
            SET status = 'unused', in_progress_since = NULL 
            WHERE status = 'in_progress' AND in_progress_since < ?
        """, (cutoff_time,))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error resetting prompts in {db_path}: {e}")

def get_next_prompt():
    current_db_path = get_db_path_for_user()
    reset_old_in_progress_prompts(current_db_path)

    conn = get_db_connection(current_db_path)
    cur = conn.cursor()

    try:
        cur.execute("BEGIN IMMEDIATE")

        cur.execute("""
            SELECT id, text FROM prompts
            WHERE status = 'unused'
            LIMIT 1
        """)
        row = cur.fetchone()

        if row is None:
            conn.commit()
            conn.close()
            return None

        cur.execute("""
            UPDATE prompts
            SET status = 'in_progress', in_progress_since = ?
            WHERE id = ?
        """, (datetime.now(), row["id"]))

        conn.commit()
        conn.close()

        return dict(row)
    except Exception:
        if conn:
            conn.close()
        return None

def mark_prompt_as_used(prompt_id):
    current_db_path = get_db_path_for_user()
    conn = get_db_connection(current_db_path)
    conn.execute(
        "UPDATE prompts SET status='used', in_progress_since=NULL WHERE id=?",
        (prompt_id,)
    )
    conn.commit()
    conn.commit()
    conn.close()

def get_prompt_text(prompt_id):
    current_db_path = get_db_path_for_user()
    conn = get_db_connection(current_db_path)
    cur = conn.cursor()
    cur.execute("SELECT text FROM prompts WHERE id = ?", (prompt_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["text"]
    return None

def add_new_prompt(language, text, db_type='standard'):
    target_db = Config.TRIBAL_DB_PATH if db_type == 'tribal' else Config.DB_PATH
    conn = get_db_connection(target_db)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO prompts (language, text, status) VALUES (?, ?, ?)",
            (language, text, "unused")
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return new_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def get_prompt_stats(db_type='standard'):
    target_db = Config.TRIBAL_DB_PATH if db_type == 'tribal' else Config.DB_PATH
    conn = get_db_connection(target_db)
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM prompts GROUP BY status")
    stats = dict(cur.fetchall())
    conn.close()
    return stats

def bulk_add_prompts(prompts_list, db_type='standard'):
    """
    Adds multiple prompts to the database.
    prompts_list: list of tuples (language, text)
    db_type: 'standard' or 'tribal'
    Returns: number of prompts added
    """
    target_db = Config.TRIBAL_DB_PATH if db_type == 'tribal' else Config.DB_PATH
    conn = get_db_connection(target_db)
    cur = conn.cursor()
    added_count = 0
    try:
        # We need IDs to upload to S3 individually.
        # Since sqlite3 executemany doesn't return IDs easily, we will loop.
        # It is slower but ensures we get the IDs for our S3 requirement.
        added_prompts = []
        
        for lang, text in prompts_list:
            try:
                cur.execute(
                    "INSERT INTO prompts (language, text, status) VALUES (?, ?, 'unused')",
                    (lang, text)
                )
                if cur.rowcount > 0:
                    added_prompts.append((cur.lastrowid, text))
            except sqlite3.IntegrityError:
                continue # Duplicate

        conn.commit()
        added_count = len(added_prompts)
        
    except Exception as e:
        print(f"Error in bulk add: {e}")
        added_prompts = []
        added_count = 0
    finally:
        conn.close()
        
    return added_count, added_prompts
def create_recordings_table(db_path):
    """Creates the recordings table if it doesn't exist."""
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE NOT NULL,
            age INTEGER,
            gender TEXT,
            location TEXT,
            state TEXT,
            prompt_text TEXT,
            audio_path TEXT,
            is_tribal INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
    except Exception as e:
        print(f"Error creating recordings table in {db_path}: {e}")
    finally:
        conn.close()

def add_recording_metadata(uid, user_info, audio_path, prompt_text, is_tribal):
    """
    Saves recording metadata to both databases to ensure consistency.
    We save to both because the admin dashboard might check either, 
    and it provides a fallback.
    """
    for db_path in [Config.DB_PATH, Config.TRIBAL_DB_PATH]:
        conn = get_db_connection(db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO recordings (uid, age, gender, location, state, prompt_text, audio_path, is_tribal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                user_info.get('age'),
                user_info.get('gender'),
                user_info.get('location'),
                user_info.get('state'),
                prompt_text,
                audio_path,
                1 if is_tribal else 0
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            # Already exists, skip
            pass
        except Exception as e:
            print(f"Error saving recording metadata to {db_path}: {e}")
        finally:
            conn.close()

def get_total_recordings_count():
    """Returns the total number of recordings across both databases (handles duplicates via UID)."""
    # Simply count from one DB as we are mirroring them now for simplicity of query
    # or better, fetch from one and assume they are synced. 
    # To be safest, we could count unique UIDs if we were merging, 
    # but mirroring to both is easier for now.
    conn = get_db_connection(Config.DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM recordings")
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_all_recordings():
    """Fetches all recordings from the database for the metadata view."""
    conn = get_db_connection(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM recordings ORDER BY timestamp DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]
