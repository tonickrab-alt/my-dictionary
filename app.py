import os
import sqlite3
from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_key_v2'

# --- ระบบฐานข้อมูล ---
def get_db_connection():
    conn = sqlite3.connect('opendict.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # ตารางผู้ใช้งาน
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    # ตารางคำศัพท์
    conn.execute('''
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            meaning TEXT NOT NULL,
            status TEXT NOT NULL,
            nominated_by TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- โครงสร้างหน้าเว็บ (Templates) ---
base_html = '''
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>พจนานุกรมเสรี</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        body { background-color: #f0f2f5; font-family: 'Sarabun', sans-serif; }
        .navbar { background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); }
        .card { border: none; border-radius: 15px; }
        .btn-primary { border-radius: 10px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold" href="{{ url_for('home') }}">📚 OPENDICT</a>
            <div class="d-flex">
                {% if session.get('username') %}
                    <a href="{{ url_for('nominate') }}" class="btn btn-light btn-sm me-2">เพิ่มคำ</a>
                    {% if session.get('role') == 'admin' %}
                        <a href="{{ url_for('admin_panel') }}" class="btn btn-warning btn-sm me-2">แผงควบคุม</a>
                    {% endif %}
                    <a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">ออก</a>
                {% else %}
                    <a href="{{ url_for('login') }}" class="btn btn-outline-light btn-sm me-2">เข้าสู่ระบบ</a>
                    <a href="{{ url_for('signup') }}" class="btn btn-success btn-sm">สมัครสมาชิก</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <div class="container mt-4" style="max-width: 800px;">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
</body>
</html>
'''

home_html = '''
{% extends "base" %}
{% block content %}
<div class="text-center mb-5">
    <h1 class="display-5 fw-bold text-dark">พจนานุกรมเปิดเสรี</h1>
    <p class="text-muted">แหล่งรวบรวมคำศัพท์ที่ทุกคนช่วยกันสร้าง</p>
</div>
<div class="row">
    {% for word in words %}
    <div class="col-md-12 mb-3">
        <div class="card shadow-sm">
            <div class="card-body p-4">
                <h3 class="text-primary fw-bold">{{ word.word }}</h3>
                <p class="fs-5 text-dark">{{ word.meaning }}</p>
                <hr>
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-secondary">โดย: {{ word.nominated_by }}</small>
                    <span class="badge bg-info text-dark">อนุมัติแล้ว</span>
                </div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="text-center py-5">
        <p class="text-muted fs-4">ยังไม่มีคำศัพท์ที่ผ่านการอนุมัติ</p>
    </div>
    {% endfor %}
</div>
{% endblock %}
'''

signup_html = '''
{% extends "base" %}
{% block content %}
<div class="card shadow mx-auto" style="max-width: 450px;">
    <div class="card-body p-5">
        <h2 class="text-center mb-4 fw-bold">สมัครสมาชิก</h2>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label">ชื่อผู้ใช้</label>
                <input type="text" class="form-control" name="username" required>
            </div>
            <div class="mb-4">
                <label class="form-label">รหัสผ่าน</label>
                <input type="password" class="form-control" name="password" required>
            </div>
            <button type="submit" class="btn btn-success w-100 py-2 fw-bold">ลงทะเบียน</button>
        </form>
    </div>
</div>
{% endblock %}
'''

login_html = '''
{% extends "base" %}
{% block content %}
<div class="card shadow mx-auto" style="max-width: 450px;">
    <div class="card-body p-5">
        <h2 class="text-center mb-4 fw-bold">เข้าสู่ระบบ</h2>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label">ชื่อผู้ใช้</label>
                <input type="text" class="form-control" name="username" required>
            </div>
            <div class="mb-4">
                <label class="form-label">รหัสผ่าน</label>
                <input type="password" class="form-control" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary w-100 py-2 fw-bold">ล็อกอิน</button>
        </form>
    </div>
</div>
{% endblock %}
'''

nominate_html = '''
{% extends "base" %}
{% block content %}
<div class="card shadow p-4">
    <h2 class="mb-4 fw-bold">เสนอคำศัพท์ใหม่</h2>
    <form method="POST">
        <div class="mb-3">
            <label class="form-label fw-bold">คำศัพท์</label>
            <input type="text" class="form-control" name="word" placeholder="ระบุคำศัพท์..." required>
        </div>
        <div class="mb-4">
            <label class="form-label fw-bold">ความหมาย</label>
            <textarea class="form-control" name="meaning" rows="4" placeholder="อธิบายความหมาย..." required></textarea>
        </div>
        <button type="submit" class="btn btn-primary px-4 py-2">ส่งให้แอดมินพิจารณา</button>
    </nav>
</div>
{% endblock %}
'''

admin_html = '''
{% extends "base" %}
{% block content %}
<h2 class="mb-4 fw-bold">🛡️ แผงควบคุมผู้ดูแลระบบ</h2>
<div class="card shadow">
    <div class="card-header bg-white fw-bold py-3">คำศัพท์ที่รอการตรวจสอบ</div>
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th>คำศัพท์</th>
                    <th>ความหมาย</th>
                    <th>โดย</th>
                    <th class="text-center">จัดการ</th>
                </tr>
            </thead>
            <tbody>
                {% for word in pending_words %}
                <tr>
                    <td class="fw-bold text-primary">{{ word.word }}</td>
                    <td>{{ word.meaning }}</td>
                    <td>{{ word.nominated_by }}</td>
                    <td class="text-center">
                        <a href="{{ url_for('approve_word', word_id=word.id) }}" class="btn btn-success btn-sm">อนุมัติ</a>
                        <a href="{{ url_for('reject_word', word_id=word.id) }}" class="btn btn-danger btn-sm">ทิ้ง</a>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="4" class="text-center py-4 text-muted">ไม่มีคำศัพท์ที่รอการตรวจสอบในขณะนี้</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
'''

# --- ระบบ Logic ---
def render_page(template_string, **kwargs):
    full_template = template_string.replace('{% extends "base" %}', base_html)
    return render_template_string(full_template, **kwargs)

@app.route('/')
def home():
    conn = get_db_connection()
    words = conn.execute("SELECT * FROM words WHERE status='approved' ORDER BY id DESC").fetchall()
    conn.close()
    return render_page(home_html, words=words)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        conn = get_db_connection()
        try:
            count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            role = 'admin' if count == 0 else 'user'
            conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, hashed_pw, role))
            conn.commit()
            flash('สมัครสมาชิกสำเร็จ! กรุณาล็อกอิน', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('ชื่อผู้ใช้นี้ถูกใช้งานไปแล้ว', 'danger')
        finally:
            conn.close()
    return render_page(signup_html)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'สวัสดีคุณ {username} ยินดีต้อนรับกลับมา!', 'success')
            return redirect(url_for('home'))
        flash('ชื่อผู้ใช้หรือรหัสผ่านผิดพลาด', 'danger')
    return render_page(login_html)

@app.route('/logout')
def logout():
    session.clear()
    flash('ออกจากระบบแล้ว', 'info')
    return redirect(url_for('home'))

@app.route('/nominate', methods=['GET', 'POST'])
def nominate():
    if not session.get('username'):
        flash('โปรดเข้าสู่ระบบก่อน', 'warning')
        return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO words (word, meaning, status, nominated_by) VALUES (?, ?, ?, ?)',
                     (request.form['word'], request.form['meaning'], 'pending', session['username']))
        conn.commit()
        conn.close()
        flash('ส่งคำศัพท์เรียบร้อย! รอแอดมินตรวจสอบนะ', 'success')
        return redirect(url_for('home'))
    return render_page(nominate_html)

@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin':
        flash('สิทธิ์ไม่เพียงพอ', 'danger')
        return redirect(url_for('home'))
    conn = get_db_connection()
    pending = conn.execute("SELECT * FROM words WHERE status='pending'").fetchall()
    conn.close()
    return render_page(admin_html, pending_words=pending)

@app.route('/admin/approve/<int:word_id>')
def approve_word(word_id):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    conn = get_db_connection()
    conn.execute("UPDATE words SET status='approved' WHERE id=?", (word_id,))
    conn.commit()
    conn.close()
    flash('อนุมัติเรียบร้อย', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/reject/<int:word_id>')
def reject_word(word_id):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    conn = get_db_connection()
    conn.execute("DELETE FROM words WHERE id=?", (word_id,))
    conn.commit()
    conn.close()
    flash('ลบคำศัพท์ที่ถูกปฏิเสธแล้ว', 'info')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
