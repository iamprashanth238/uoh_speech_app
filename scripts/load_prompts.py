import pandas as pd
import sqlite3

CSV_PATH = "Tribal-Telugu-Text.xlsx"
DB_PATH = "tribal-text.db"

df = pd.read_excel(CSV_PATH)

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

# Add the in_progress_since column if it doesn't exist (for existing databases)
try:
    cur.execute("ALTER TABLE prompts ADD COLUMN in_progress_since TIMESTAMP")
except sqlite3.OperationalError:
    # Column already exists
    pass

for index, row in df.iterrows():
    try:
        cur.execute(
            "INSERT INTO prompts (language, text, status) VALUES (?, ?, ?)",
            (row["language"], row["text"].strip(), row["status"])
        )
    except sqlite3.IntegrityError:
        pass  # duplicate text, ignore

conn.commit()
conn.close()

print("✅ Prompts loaded into SQLite")
