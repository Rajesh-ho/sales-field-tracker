from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime

# Create the Flask app (the web server)
app = Flask(__name__)
CORS(app)  # Allow the HTML page to talk to this server

DB_FILE = 'sales_tracker.db'

# Auto-create database tables if they don't exist
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS executives (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            phone       TEXT,
            email       TEXT,
            region      TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            executive_id    INTEGER NOT NULL,
            client_name     TEXT NOT NULL,
            visit_date      DATE NOT NULL,
            meeting_notes   TEXT,
            outcome         TEXT,
            FOREIGN KEY (executive_id) REFERENCES executives(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            executive_id    INTEGER NOT NULL,
            latitude        REAL NOT NULL,
            longitude       REAL NOT NULL,
            recorded_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (executive_id) REFERENCES executives(id)
        )
    ''')
    conn.commit()
    conn.close()

# Run this when server starts
init_db()

# ── Helper: connect to the database ─────────────────────
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Return results as dicts
    return conn

# ── Helper: validate required fields ────────────────────
def require_fields(data, fields):
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return {'error': f'Missing fields: {missing}'}, 400
    return None


# ════════════════════════════════════════════════════════
#  EXECUTIVES ENDPOINTS
# ════════════════════════════════════════════════════════

# GET /api/executives  →  List all executives
@app.route('/api/executives', methods=['GET'])
def list_executives():
    db = get_db()
    rows = db.execute('SELECT * FROM executives ORDER BY name').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# POST /api/executives  →  Add a new executive
@app.route('/api/executives', methods=['POST'])
def add_executive():
    data = request.json or {}
    err = require_fields(data, ['name', 'region'])
    if err: return jsonify(err[0]), err[1]
    db = get_db()
    db.execute(
        'INSERT INTO executives (name, phone, email, region) VALUES (?,?,?,?)',
        (data['name'], data.get('phone',''), data.get('email',''), data['region'])
    )
    db.commit()
    db.close()
    return jsonify({'message': 'Executive added successfully!'}), 201

# DELETE /api/executives/<id>  →  Remove an executive
@app.route('/api/executives/<int:exec_id>', methods=['DELETE'])
def delete_executive(exec_id):
    db = get_db()
    db.execute('DELETE FROM executives WHERE id = ?', (exec_id,))
    db.commit()
    db.close()
    return jsonify({'message': 'Executive removed!'})


# ════════════════════════════════════════════════════════
#  VISITS ENDPOINTS
# ════════════════════════════════════════════════════════

# GET /api/visits?executive_id=1  →  List visits for one exec
@app.route('/api/visits', methods=['GET'])
def list_visits():
    exec_id = request.args.get('executive_id')
    db = get_db()
    if exec_id:
        rows = db.execute(
            'SELECT * FROM visits WHERE executive_id=? ORDER BY visit_date DESC',
            (exec_id,)
        ).fetchall()
    else:
        rows = db.execute('SELECT * FROM visits ORDER BY visit_date DESC').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# POST /api/visits  →  Log a new visit
@app.route('/api/visits', methods=['POST'])
def log_visit():
    data = request.json or {}
    err = require_fields(data, ['executive_id', 'client_name', 'visit_date'])
    if err: return jsonify(err[0]), err[1]
    db = get_db()
    db.execute(
        '''INSERT INTO visits
           (executive_id, client_name, visit_date, meeting_notes, outcome)
           VALUES (?, ?, ?, ?, ?)''',
        (data['executive_id'], data['client_name'], data['visit_date'],
         data.get('meeting_notes',''), data.get('outcome',''))
    )
    db.commit()
    db.close()
    return jsonify({'message': 'Visit logged!'}), 201


# ════════════════════════════════════════════════════════
#  LOCATION ENDPOINTS
# ════════════════════════════════════════════════════════

# POST /api/location  →  Save a GPS coordinate snapshot
@app.route('/api/location', methods=['POST'])
def save_location():
    data = request.json or {}
    err = require_fields(data, ['executive_id', 'latitude', 'longitude'])
    if err: return jsonify(err[0]), err[1]
    db = get_db()
    db.execute(
        'INSERT INTO locations (executive_id, latitude, longitude) VALUES (?,?,?)',
        (data['executive_id'], data['latitude'], data['longitude'])
    )
    db.commit()
    db.close()
    return jsonify({'message': 'Location saved!'})

# GET /api/locations/latest  →  Latest location for all execs
@app.route('/api/locations/latest', methods=['GET'])
def latest_locations():
    db = get_db()
    rows = db.execute('''
        SELECT e.id, e.name, e.region,
               l.latitude, l.longitude, l.recorded_at
        FROM executives e
        LEFT JOIN (
            SELECT executive_id, latitude, longitude, recorded_at,
                   ROW_NUMBER() OVER (PARTITION BY executive_id ORDER BY recorded_at DESC) rn
            FROM locations
        ) l ON e.id = l.executive_id AND l.rn = 1
    ''').fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


# ════════════════════════════════════════════════════════
#  REPORTS ENDPOINTS
# ════════════════════════════════════════════════════════

# GET /api/reports/daily/<exec_id>  →  Today's visits WITH locations
@app.route('/api/reports/daily/<int:exec_id>')
def daily_report(exec_id):
    today = datetime.date.today().isoformat()
    db = get_db()
    exec_row = db.execute(
        'SELECT * FROM executives WHERE id=?', (exec_id,)
    ).fetchone()

    # Get visits WITH nearest location at time of visit
    visits = db.execute('''
        SELECT v.*,
               l.latitude,
               l.longitude,
               l.recorded_at as location_time
        FROM visits v
        LEFT JOIN locations l ON l.executive_id = v.executive_id
            AND date(l.recorded_at) = v.visit_date
        WHERE v.executive_id = ?
        AND v.visit_date = ?
        GROUP BY v.id
    ''', (exec_id, today)).fetchall()

    db.close()
    return jsonify({
        'executive': dict(exec_row) if exec_row else None,
        'date': today,
        'total_visits': len(visits),
        'visits': [dict(v) for v in visits],
    })


# GET /api/reports/weekly/<exec_id>  →  Last 7 days WITH locations
@app.route('/api/reports/weekly/<int:exec_id>')
def weekly_report(exec_id):
    today = datetime.date.today()
    week_ago = (today - datetime.timedelta(days=7)).isoformat()
    db = get_db()
    exec_row = db.execute(
        'SELECT * FROM executives WHERE id=?', (exec_id,)
    ).fetchone()

    # Get visits WITH nearest location at time of visit
    visits = db.execute('''
        SELECT v.*,
               l.latitude,
               l.longitude,
               l.recorded_at as location_time
        FROM visits v
        LEFT JOIN locations l ON l.executive_id = v.executive_id
            AND date(l.recorded_at) = v.visit_date
        WHERE v.executive_id = ?
        AND v.visit_date >= ?
        GROUP BY v.id
    ''', (exec_id, week_ago)).fetchall()

    db.close()
    return jsonify({
        'executive': dict(exec_row) if exec_row else None,
        'period': f'{week_ago} to {today.isoformat()}',
        'total_visits': len(visits),
        'visits': [dict(v) for v in visits],
    })

# GET /api/locations/missing  →  Who hasn't shared location today?
@app.route('/api/locations/missing')
def missing_locations():
    today = datetime.date.today().isoformat()
    db = get_db()
    rows = db.execute('''
        SELECT e.id, e.name, e.region, e.phone
        FROM executives e
        WHERE e.id NOT IN (
            SELECT DISTINCT executive_id
            FROM locations
            WHERE date(recorded_at) = ?
        )
    ''', (today,)).fetchall()
    db.close()
    return jsonify({
        'date': today,
        'missing_count': len(rows),
        'executives': [dict(r) for r in rows]
    })


# ════════════════════════════════════════════════════════
#  START THE SERVER
# ════════════════════════════════════════════════════════
import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'Server running on port {port}')
    app.run(debug=False, host='0.0.0.0', port=port)

