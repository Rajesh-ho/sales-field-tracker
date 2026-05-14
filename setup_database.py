import sqlite3

# Connect to (or create) the database file
conn = sqlite3.connect('sales_tracker.db')
cursor = conn.cursor()

# ── Table 1: Executives ─────────────────────────────────
cursor.execute('''
    CREATE TABLE IF NOT EXISTS executives (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        phone       TEXT,
        email       TEXT,
        region      TEXT,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

# ── Table 2: Daily Visits ───────────────────────────────
cursor.execute('''
    CREATE TABLE IF NOT EXISTS visits (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        executive_id    INTEGER NOT NULL,
        client_name     TEXT    NOT NULL,
        visit_date      DATE    NOT NULL,
        meeting_notes   TEXT,
        outcome         TEXT,
        FOREIGN KEY (executive_id) REFERENCES executives(id)
    )
''')

# ── Table 3: GPS Location Snapshots ────────────────────
cursor.execute('''
    CREATE TABLE IF NOT EXISTS locations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        executive_id    INTEGER NOT NULL,
        latitude        REAL    NOT NULL,
        longitude       REAL    NOT NULL,
        recorded_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (executive_id) REFERENCES executives(id)
    )
''')

conn.commit()
conn.close()
print('Database created successfully!')
