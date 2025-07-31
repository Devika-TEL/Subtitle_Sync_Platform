import sqlite3

def init_db():
    """
    Initializes the subtitle_sync_platform.db database using schema.sql.
    """
    conn = sqlite3.connect('subtitle_sync_platform.db')
    cursor = conn.cursor()
    with open("schema.sql", "r") as f:
        sql_script = f.read()
    cursor.executescript(sql_script)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
