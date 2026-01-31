import pandas as pd
import sqlite3
import os

CSV_PATH = "Tribal-Telugu-Text.xlsx"
DB_PATH = "telugu_tribe.db"

def load_tribal_prompts():
    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: {CSV_PATH} not found.")
        return

    try:
        df = pd.read_excel(CSV_PATH)
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS prompts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      language TEXT NOT NULL,
      text TEXT UNIQUE NOT NULL,
      status TEXT DEFAULT 'unused',
      in_progress_since TIMESTAMP
    )
    """)

    # Add columns if they don't exist (loading generic logic just in case, though it is a new DB)
    try:
        cur.execute("ALTER TABLE prompts ADD COLUMN in_progress_since TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    count = 0
    for index, row in df.iterrows():
        try:
            # Excel column is 'Tribal-Telugu-Text' based on inspection
            text = row.get("Tribal-Telugu-Text", "").strip()
            # Default to te-tribal as language is likely not in this sheet
            language = row.get("language", "te-tribal")
            status = row.get("status", "unused")
            
            if text:
                cur.execute(
                    "INSERT INTO prompts (language, text, status) VALUES (?, ?, ?)",
                    (language, text, status)
                )
                count += 1
        except sqlite3.IntegrityError:
            pass  # duplicate text, ignore

    conn.commit()
    conn.close()

    print(f"✅ Loaded {count} tribal prompts into {DB_PATH}")

if __name__ == "__main__":
    load_tribal_prompts()
