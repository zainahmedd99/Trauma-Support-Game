from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_bcrypt import Bcrypt
from functools import wraps
from datetime import datetime
from db import get_conn
from config import SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY
bcrypt = Bcrypt(app)

# -------- Helpers --------

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

LEVELS = ['low', 'medium', 'high']
T_LIMIT = {'low': 60, 'medium': 45, 'high': 30}  # seconds
Q_COUNT = {'low': 5, 'medium': 6, 'high': 7}     # questions per level

# -------- Auth --------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('Username & password required', 'danger')
            return redirect(url_for('register'))
        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        conn = get_conn(); cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users(username, password_hash) VALUES(%s,%s)", (username, pw_hash))
            conn.commit()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash('Username already taken', 'danger')
        finally:
            cur.close(); conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE username=%s", (username,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row and bcrypt.check_password_hash(row[1], password):
            session['user_id'] = row[0]
            session['username'] = username
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------- Dashboard --------
@app.route('/')
@login_required
def dashboard():
    user_id = session['user_id']
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id, code, name, COALESCE(description,'') FROM games ORDER BY id")
    games = cur.fetchall()
    # Fetch best total score per game for this user
    cur.execute(
        """
        SELECT g.code, MAX(p.total_score)
        FROM plays p
        JOIN games g ON g.id = p.game_id
        WHERE p.user_id = %s AND p.status='completed'
        GROUP BY g.code
        """, (user_id,)
    )
    best = {code: score for code, score in cur.fetchall()}
    cur.close(); conn.close()
    return render_template('dashboard.html', games=games, best=best)

# -------- Start a new play --------
@app.route('/game/<code>/start')
@login_required
def start_game(code):
    user_id = session['user_id']
    # Create a new play for this game
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id FROM games WHERE code=%s", (code,))
    g = cur.fetchone()
    if not g:
        cur.close(); conn.close()
        flash('Game not found', 'danger')
        return redirect(url_for('dashboard'))
    game_id = g[0]
    cur.execute("INSERT INTO plays(user_id, game_id, status) VALUES(%s,%s,'active')", (user_id, game_id))
    play_id = cur.lastrowid
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('play_level', code=code, level='low', play_id=play_id))

# -------- Play a specific level (GET displays game UI) --------
@app.route('/game/<code>/<level>')
@login_required
def play_level(code, level):
    if level not in LEVELS:
        flash('Invalid level', 'danger'); return redirect(url_for('dashboard'))
    play_id = request.args.get('play_id', type=int)
    if not play_id:
        flash('Start the game properly.', 'warning'); return redirect(url_for('dashboard'))

    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id FROM games WHERE code=%s", (code,))
    game = cur.fetchone()
    if not game:
        cur.close(); conn.close(); flash('Game not found', 'danger'); return redirect(url_for('dashboard'))
    game_id = game[0]

    # Validate play belongs to user and game
    cur.execute("SELECT user_id, game_id, status FROM plays WHERE id=%s", (play_id,))
    p = cur.fetchone()
    if not p or p[0] != session['user_id'] or p[1] != game_id:
        cur.close(); conn.close(); flash('Invalid play session', 'danger'); return redirect(url_for('dashboard'))
    if p[2] != 'active':
        cur.close(); conn.close(); flash('Play already finished', 'info'); return redirect(url_for('dashboard'))

    # Enforce level gating
    idx = LEVELS.index(level)
    if idx > 0:
        prev_level = LEVELS[idx-1]
        cur.execute("SELECT completed_at FROM play_levels WHERE play_id=%s AND level=%s", (play_id, prev_level))
        ok = cur.fetchone()
        if not ok or not ok[0]:
            cur.close(); conn.close(); flash('Finish previous level first.', 'warning');
            return redirect(url_for('play_level', code=code, level=prev_level, play_id=play_id))

    # Create level row if not exists (start timestamp)
    cur.execute("SELECT id FROM play_levels WHERE play_id=%s AND level=%s", (play_id, level))
    pl = cur.fetchone()
    if not pl:
        cur.execute("INSERT INTO play_levels(play_id, level) VALUES(%s,%s)", (play_id, level))
        conn.commit()
    cur.close(); conn.close()

    # Pick template by game code
    if code == 'emoji':
        tmpl = 'game_emoji.html'
    elif code == 'geo':
        tmpl = 'game_geo.html'
    else:
        tmpl = 'game_math.html'

    return render_template(
        tmpl,
        play_id=play_id,
        code=code,
        level=level,
        time_limit=T_LIMIT[level],
        q_count=Q_COUNT[level]
    )

# -------- Submit level results --------
@app.route('/submit/<code>/<level>', methods=['POST'])
@login_required
def submit_level(code, level):
    play_id = int(request.form['play_id'])
    score = int(request.form['score'])
    duration = int(request.form['duration_seconds'])

    conn = get_conn(); cur = conn.cursor()
    # Update level
    cur.execute(
        """
        UPDATE play_levels
        SET score=%s, duration_seconds=%s, completed_at=NOW()
        WHERE play_id=%s AND level=%s
        """,
        (score, duration, play_id, level)
    )
    conn.commit()

    # If final level, sum totals and close play
    if level == 'high':
        cur.execute("SELECT SUM(score) FROM play_levels WHERE play_id=%s", (play_id,))
        total = cur.fetchone()[0] or 0
        cur.execute("UPDATE plays SET total_score=%s, status='completed', completed_at=NOW() WHERE id=%s", (total, play_id))
        conn.commit()
        cur.close(); conn.close()
        return redirect(url_for('result', play_id=play_id))

    # Otherwise go to next level
    next_level = LEVELS[LEVELS.index(level)+1]
    cur.close(); conn.close()
    return redirect(url_for('play_level', code=code, level=next_level, play_id=play_id))

# -------- Result page (Game Over card) --------
@app.route('/result/<int:play_id>')
@login_required
def result(play_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
    """
    SELECT p.id, g.code, g.name, p.total_score, p.started_at, p.completed_at, p.user_id
    FROM plays p JOIN games g ON g.id = p.game_id
    WHERE p.id=%s AND p.user_id=%s
    """,
    (play_id, session['user_id'])
)
    meta = cur.fetchone()

    if not meta:
        cur.close(); conn.close();
        flash('Result not found', 'danger'); return redirect(url_for('dashboard'))

    cur.execute(
        "SELECT level, score, duration_seconds, started_at, completed_at FROM play_levels WHERE play_id=%s ORDER BY FIELD(level,'low','medium','high')",
        (play_id,)
    )
    levels = cur.fetchall()
    cur.close(); conn.close()
    return render_template('result.html', meta=meta, levels=levels)

# -------- History dashboard with charts --------
@app.route('/history')
@login_required
def history():
    user_id = session['user_id']
    conn = get_conn(); cur = conn.cursor()

    # Fetch per-level scores with date
    cur.execute(
        """
        SELECT g.code, g.name, pl.level, pl.completed_at, pl.score
        FROM play_levels pl
        JOIN plays p ON p.id = pl.play_id
        JOIN games g ON g.id = p.game_id
        WHERE p.user_id=%s AND p.status='completed' AND pl.completed_at IS NOT NULL
        ORDER BY pl.completed_at ASC
        """,
        (user_id,)
    )
    rows = cur.fetchall()
    cur.close(); conn.close()

    # Build labels (dates) and datasets per game+level
    labels = []
    by_game_level = {}
    for code, name, level, completed_at, score in rows:
        dstr = completed_at.strftime('%Y-%m-%d %H:%M') if hasattr(completed_at, 'strftime') else str(completed_at)
        labels.append(dstr)
        key = f"{name} ({level.capitalize()})"
        ds = by_game_level.setdefault(key, {})
        ds[dstr] = ds.get(dstr, 0) + int(score or 0)

    labels = sorted(set(labels))

    datasets = []
    for key, points in by_game_level.items():
        data = [points.get(lbl, 0) for lbl in labels]
        datasets.append({'label': key, 'data': data})

    # 🔹 Pass rows too
    return render_template("history.html", labels=labels, datasets=datasets, rows=rows)

if __name__ == '__main__':
    app.run(debug=True)
