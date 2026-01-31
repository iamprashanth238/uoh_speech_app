import sqlite3

conn = sqlite3.connect("prompts.db")
cur = conn.cursor()

for row in cur.execute("SELECT status, COUNT(*) FROM prompts GROUP BY status"):
    print(row)

conn.close()
