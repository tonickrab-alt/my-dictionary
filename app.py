import os
import sqlite3
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'krian_dictionary_secret_super_safe'

# ==========================================
# 1. ระบบฐานข้อมูล (Database) & ประวัติ (Audit)
# ==========================================
def get_db_connection():
    conn = sqlite3.connect('opendict.db')
    conn.row_factory = sqlite3.Row
    return conn

def log_action(username, action):
    conn = get_db_connection()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute('INSERT INTO audit_logs (username, action, timestamp) VALUES (?, ?, ?)', 
                 (username, action, timestamp))
    conn.commit()
    conn.close()

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT, bio TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT, meaning TEXT, first_letter TEXT, 
        nominated_by TEXT, likes INTEGER DEFAULT 0, dislikes INTEGER DEFAULT 0, status TEXT DEFAULT 'normal'
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER, username TEXT, comment TEXT, created_at TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER, username TEXT, vote_type TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, action TEXT, timestamp TEXT
    )''')
    
    # สร้างแอดมินอัตโนมัติ
    admin = conn.execute("SELECT * FROM users WHERE username='Admin'").fetchone()
    if not admin:
        hashed = generate_password_hash('113333555555')
        conn.execute("INSERT INTO users (username, password, role, bio) VALUES (?, ?, ?, ?)",
                     ('Admin', hashed, 'admin', 'ผู้คุมกฎสูงสุดแห่งพจนานุเกรียน!'))
    
    conn.commit()
    conn.close()

# ==========================================
# 2. โครงสร้างหน้าเว็บ (HTML Templates) - ธีมสว่าง ฟอนต์ Prompt
# ==========================================
base_html = '''
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>พจนานุเกรียน</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- นำเข้าฟอนต์ Prompt -->
    <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { background-color: #f4f7f6; color: #2c3e50; font-family: 'Prompt', sans-serif; }
        
        /* แถบ Navbar ไล่สีสนุกๆ */
        .navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 12px 0; }
        .navbar-brand { color: #fff !important; font-size: 1.6rem; font-weight: 700; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); }
        
        /* การ์ดต่างๆ (ทำให้มีมิติและสะอาดตา) */
        .card { background-color: #fff; border: none; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); transition: all 0.3s ease; }
        .card:hover { box-shadow: 0 12px 25px rgba(0,0,0,0.1); transform: translateY(-4px); }
        .hover-card { cursor: pointer; }
        
        /* สีตัวอักษรและปุ่ม */
        .text-primary { color: #667eea !important; }
        .btn-primary { background-color: #667eea; border-color: #667eea; color: #fff; }
        .btn-primary:hover { background-color: #764ba2; border-color: #764ba2; }
        
        /* เอฟเฟกต์การกดปุ่ม (Active & Hover) */
        .btn { border-radius: 10px; font-weight: 500; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.15); }
        .btn:active { transform: scale(0.92); box-shadow: 0 2px 5px rgba(0,0,0,0.1); } /* ปุ่มจะบุ๋มลงตอนกด */
        
        a { transition: all 0.2s; }
        a.btn:active { transform: scale(0.92); }
        
        /* ช่องใส่เหรียญตรา */
        .badge-slot { width: 45px; height: 45px; background: #e9ecef; border-radius: 50%; display: inline-block; margin: 5px; border: 2px dashed #ced4da; }
        
        /* เอฟเฟกต์ไฟกะพริบมุมขวาบน (ปรับให้เข้ากับธีมสว่าง) */
        .day-indicator {
            background: rgba(255,255,255,0.2); border-radius: 20px; padding: 6px 16px; margin-left: auto;
            color: #fff; font-weight: 600; border: 1px solid rgba(255,255,255,0.5); backdrop-filter: blur(5px);
            box-shadow: 0 0 10px rgba(255,255,255,0.3); animation: pulseWhite 2s infinite; font-size: 0.95rem;
        }
        @keyframes pulseWhite { 0% { box-shadow: 0 0 5px rgba(255,255,255,0.3); } 50% { box-shadow: 0 0 15px rgba(255,255,255,0.8); } 100% { box-shadow: 0 0 5px rgba(255,255,255,0.3); } }
        
        /* โหมดวันอาทิตย์ (สีแดงโดดเด่น) */
        .sunday-mode { color: #fff !important; background-color: #ff4757 !important; border-color: #ff4757 !important; animation: pulseRed 2s infinite !important;}
        @keyframes pulseRed { 0% { box-shadow: 0 0 5px rgba(255, 71, 87, 0.5); } 50% { box-shadow: 0 0 20px rgba(255, 71, 87, 0.9); } 100% { box-shadow: 0 0 5px rgba(255, 71, 87, 0.5); } }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg sticky-top shadow-sm">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('home') }}">🤡 พจนานุเกรียน</a>
            
            <!-- ป้ายบอกวันสุดเก๋ -->
            <div id="dayDisplay" class="day-indicator d-none d-lg-block me-3">กำลังเชื่อมต่อ...</div>

            <div class="d-flex align-items-center">
                {% if session.get('username') %}
                    <a href="{{ url_for('profile', username=session['username']) }}" class="text-white text-decoration-none me-3 fw-medium" style="transition: transform 0.2s;">
                        <span onmousedown="this.style.transform='scale(0.9)'" onmouseup="this.style.transform='scale(1)'">👾 {{ session['username'] }}</span>
                    </a>
                    <a href="{{ url_for('wotw') }}" class="btn btn-warning btn-sm me-2 fw-bold text-dark">🏆 ศัพท์ประจำสัปดาห์</a>
                    <a href="{{ url_for('nominate') }}" class="btn btn-light btn-sm me-2 text-primary fw-bold">+ บัญญัติศัพท์</a>
                    {% if session.get('role') == 'admin' %}
                        <a href="{{ url_for('admin_panel') }}" class="btn btn-danger btn-sm me-2 fw-bold">⚙️ Admin</a>
                    {% endif %}
                    <a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm fw-bold border-2">ออก</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="container mt-4 mb-5" style="max-width: 900px;">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show shadow-sm fw-bold border-0" style="border-radius: 12px;">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <!-- CONTENT_PLACEHOLDER -->
        
    </div>

    <script>
        const days = ['วันอาทิตย์', 'วันจันทร์', 'วันอังคาร', 'วันพุธ', 'วันพฤหัสบดี', 'วันศุกร์', 'วันเสาร์'];
        const today = new Date().getDay();
        const el = document.getElementById('dayDisplay');
        if(today === 0) {
            el.classList.add('sunday-mode');
            el.innerText = '🚨 วันอาทิตย์: ประกาศผลศัพท์แห่งสัปดาห์! (งดบัญญัติ)';
        } else {
            el.innerText = '✨ วันนี้: ' + days[today];
        }
    </script>
</body>
</html>
'''

auth_html = '''
<div class="card mx-auto mt-5 border-0 shadow-lg" style="max-width: 420px; border-radius: 20px;">
    <div class="card-body p-5">
        <h2 class="text-center mb-4 fw-bold text-primary">{{ title }}</h2>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label fw-medium text-secondary">ชื่อผู้ใช้ (Username)</label>
                <input type="text" class="form-control form-control-lg bg-light border-0" name="username" style="border-radius: 10px;" required>
            </div>
            <div class="mb-4">
                <label class="form-label fw-medium text-secondary">รหัสผ่าน (Password)</label>
                <input type="password" class="form-control form-control-lg bg-light border-0" name="password" style="border-radius: 10px;" required>
            </div>
            <button type="submit" class="btn btn-primary w-100 py-3 fw-bold fs-5 shadow-sm">{{ btn_text }}</button>
        </form>
        <div class="text-center mt-4">
            <a href="{{ alt_link }}" class="text-secondary text-decoration-none fw-medium hover-effect">{{ alt_text }}</a>
        </div>
    </div>
</div>
<style>.hover-effect:hover { color: #667eea !important; }</style>
'''

home_html = '''
<div class="text-center mb-5">
    <h1 class="display-4 fw-bold text-primary">พจนานุเกรียน</h1>
    <p class="text-secondary fs-5">พื้นที่บัญญัติศัพท์ไร้สาระของมวลมนุษยชาติ</p>
</div>

<!-- หมวดหมู่ตัวอักษร -->
<div class="card p-4 mb-5 shadow-sm text-center">
    <div>
        {% for letter in "กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ" %}
            <a href="?letter={{ letter }}" class="btn btn-sm btn-light m-1 text-secondary border">{{ letter }}</a>
        {% endfor %}
    </div>
    <hr class="text-muted opacity-25">
    <div>
        {% for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" %}
            <a href="?letter={{ letter }}" class="btn btn-sm btn-light m-1 text-secondary border">{{ letter }}</a>
        {% endfor %}
        <a href="{{ url_for('home') }}" class="btn btn-sm btn-dark m-1 px-3">ดูทั้งหมด</a>
    </div>
</div>

<div class="row">
    {% for word in words %}
    <div class="col-md-6 mb-4">
        <div class="card h-100 shadow-sm hover-card">
            <div class="card-body p-4" onclick="window.location='{{ url_for('view_word', word_id=word.id) }}'">
                <h3 class="fw-bold mb-3"><a href="{{ url_for('view_word', word_id=word.id) }}" class="text-primary text-decoration-none">{{ word.word }}</a></h3>
                <p class="text-dark fs-5 text-truncate" style="max-height: 3rem; white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">{{ word.meaning }}</p>
            </div>
            <div class="card-footer bg-transparent border-top-0 px-4 pb-4 pt-0 d-flex justify-content-between align-items-center">
                <small class="text-muted">โดย: <a href="{{ url_for('profile', username=word.nominated_by) }}" class="text-decoration-none fw-bold">{{ word.nominated_by }}</a></small>
                <div class="bg-light px-3 py-1 rounded-pill border">
                    <span class="text-success fw-bold me-2">👍 {{ word.likes }}</span>
                    <span class="text-danger fw-bold">👎 {{ word.dislikes }}</span>
                </div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="text-center py-5 w-100">
        <div class="display-1 mb-3 opacity-25">👻</div>
        <p class="text-secondary fs-4">ยังไม่มีศัพท์เกรียนๆ ในหมวดนี้</p>
    </div>
    {% endfor %}
</div>
'''

word_detail_html = '''
<div class="card shadow-sm border-0 mb-4 overflow-hidden">
    <div class="bg-light p-5 border-bottom">
        <div class="d-flex justify-content-between align-items-start">
            <h1 class="display-3 fw-bold text-primary mb-0">{{ word.word }}</h1>
            <a href="{{ url_for('report_word', word_id=word.id) }}" class="btn btn-outline-danger btn-sm rounded-pill fw-bold" onclick="return confirm('แจ้งแอดมินลบคำนี้?')">🚩 Report</a>
        </div>
    </div>
    <div class="card-body p-5">
        <p class="fs-3 text-dark lh-base">{{ word.meaning }}</p>
        <div class="mt-5 p-4 rounded-4 bg-light border d-flex flex-column flex-md-row justify-content-between align-items-center gap-3">
            <span class="text-secondary fs-5">ผู้บัญญัติ: <a href="{{ url_for('profile', username=word.nominated_by) }}" class="text-primary text-decoration-none fw-bold">{{ word.nominated_by }}</a></span>
            <div class="d-flex gap-2">
                {% if is_sunday %}
                    <span class="badge bg-danger fs-5 p-3 rounded-pill shadow-sm">🚨 วันอาทิตย์ งดโหวตนะจ๊ะ!</span>
                {% else %}
                    <a href="{{ url_for('vote_word', word_id=word.id, type='like') }}" class="btn btn-success btn-lg px-4 fw-bold shadow-sm rounded-pill">👍 ยอดเยี่ยม ({{ word.likes }})</a>
                    <a href="{{ url_for('vote_word', word_id=word.id, type='dislike') }}" class="btn btn-danger btn-lg px-4 fw-bold shadow-sm rounded-pill">👎 อิหยังวะ ({{ word.dislikes }})</a>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<div class="card shadow-sm border-0">
    <div class="card-body p-5">
        <h3 class="fw-bold mb-4 text-dark">💬 ลานประลองคอมเมนต์</h3>
        <form method="POST" action="{{ url_for('add_comment', word_id=word.id) }}" class="mb-5">
            <div class="input-group input-group-lg shadow-sm" style="border-radius: 15px; overflow: hidden;">
                <input type="text" class="form-control border-0 bg-light px-4" name="comment" placeholder="พิมพ์ด่า หรือ อวย ได้ที่นี่..." required>
                <button class="btn btn-primary px-5 fw-bold" type="submit">ส่งความคิดเห็น</button>
            </div>
        </form>
        
        <div class="d-flex flex-column gap-3">
            {% for c in comments %}
            <div class="bg-light p-4 rounded-4 border-0">
                <div class="d-flex align-items-center mb-2">
                    <strong class="fs-5"><a href="{{ url_for('profile', username=c.username) }}" class="text-primary text-decoration-none">{{ c.username }}</a></strong> 
                    <small class="text-muted ms-3">{{ c.created_at }}</small>
                </div>
                <p class="mb-0 text-dark fs-5">{{ c.comment }}</p>
            </div>
            {% else %}
            <div class="text-center py-4 bg-light rounded-4">
                <span class="fs-1 opacity-50">🦗</span>
                <p class="text-muted mt-2 fs-5">ยังเงียบกริบ... มาประเดิมคอมเมนต์แรกกันหน่อย!</p>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
'''

profile_html = '''
<div class="card shadow-lg border-0 mx-auto overflow-hidden" style="max-width: 650px; border-radius: 20px;">
    <div class="bg-primary p-5 text-center" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;">
        <div class="mb-3">
            <span class="display-1 bg-white rounded-circle p-3 shadow" style="width: 120px; height: 120px; display: inline-block; line-height: 85px;">👾</span>
        </div>
        <h1 class="fw-bold text-white mb-2">{{ user.username }}</h1>
        <span class="badge bg-white text-primary px-3 py-2 fs-6 rounded-pill shadow-sm">คลาส: {{ user.role|upper }}</span>
    </div>
    
    <div class="card-body p-5">
        <div class="bg-light p-4 rounded-4 mb-5 border">
            <h4 class="fw-bold text-dark mb-3">📝 แนะนำตัวเกรียนๆ</h4>
            <p class="text-secondary fs-5 fst-italic">"{{ user.bio if user.bio else 'ยังไม่ได้ใส่คำคมบาดจิต...' }}"</p>
            {% if session.get('username') == user.username %}
                <hr class="opacity-25 my-4">
                <form method="POST">
                    <textarea class="form-control bg-white border-light mb-3" name="bio" rows="2" placeholder="เปลี่ยนคำแนะนำตัวของคุณ..." style="border-radius: 10px;">{{ user.bio }}</textarea>
                    <button type="submit" class="btn btn-outline-primary w-100 fw-bold py-2 rounded-pill">💾 บันทึกการตั้งค่า</button>
                </form>
            {% endif %}
        </div>

        <div class="text-center">
            <h5 class="fw-bold text-dark mb-4">🏅 เหรียญตราเกียรติยศ <span class="badge bg-warning text-dark ms-2">Coming Soon</span></h5>
            <div class="d-flex justify-content-center flex-wrap gap-2">
                <div class="badge-slot shadow-sm"></div> <div class="badge-slot shadow-sm"></div>
                <div class="badge-slot shadow-sm"></div> <div class="badge-slot shadow-sm"></div>
                <div class="badge-slot shadow-sm"></div>
            </div>
            <p class="text-muted small mt-3">พื้นที่สำหรับสะสมตราประทับในอนาคต</p>
        </div>
    </div>
</div>
'''

add_word_html = '''
<div class="card shadow-lg mx-auto border-0" style="max-width: 600px; border-radius: 20px;">
    <div class="card-body p-5">
        <div class="text-center mb-5">
            <span class="display-4">✍️</span>
            <h2 class="fw-bold mt-3 text-primary">บัญญัติศัพท์ไร้สาระ</h2>
            <p class="text-muted">ฝากฝีปากไว้ให้โลกรู้จำ!</p>
        </div>
        <form method="POST">
            <div class="mb-4">
                <label class="form-label fw-bold text-dark fs-5">คำศัพท์</label>
                <input type="text" class="form-control form-control-lg bg-light border-0 px-4" name="word" placeholder="พิมพ์คำศัพท์..." style="border-radius: 12px;" required>
            </div>
            <div class="mb-5">
                <label class="form-label fw-bold text-dark fs-5">ความหมาย (แปลให้มนุษย์เข้าใจ)</label>
                <textarea class="form-control bg-light border-0 p-4" name="meaning" rows="5" placeholder="อธิบายมาเลย..." style="border-radius: 12px;" required></textarea>
            </div>
            <button type="submit" class="btn btn-primary w-100 py-3 fw-bold fs-4 shadow rounded-pill">🚀 จารึกคำศัพท์!</button>
        </form>
    </div>
</div>
'''

wotw_html = '''
<div class="text-center mb-5">
    <h1 class="display-3 fw-bold text-warning" style="text-shadow: 2px 2px 4px rgba(0,0,0,0.1);">🏆 ศัพท์เก๋ประจำสัปดาห์</h1>
    {% if is_sunday %}
        <div class="alert alert-danger mt-4 border-0 shadow-sm mx-auto" style="max-width: 600px; border-radius: 15px;">
            <h3 class="fw-bold text-danger mb-0 py-2">🚨 วันนี้วันอาทิตย์! ประกาศผลผู้ชนะแล้ว! 🚨</h3>
        </div>
    {% else %}
        <p class="fs-4 text-secondary mt-3">โหวตดันศัพท์ที่ใช่ (ระบบจะตัดสินผู้ชนะในวันอาทิตย์)</p>
    {% endif %}
</div>

<div class="row justify-content-center">
    {% for word in words %}
    <div class="col-md-8 mb-4">
        <div class="card shadow-sm hover-card {% if loop.index == 1 and is_sunday %}border border-warning border-4{% else %}border-0{% endif %}">
            <div class="card-body text-center p-5">
                {% if loop.index == 1 and is_sunday %}
                    <div class="bg-warning text-dark fw-bold d-inline-block px-4 py-2 rounded-pill mb-4 fs-5 shadow-sm">👑 เดอะเบสท์แห่งสัปดาห์ 👑</div>
                {% endif %}
                <h1 class="fw-bold text-primary display-4 mb-4">{{ word.word }}</h1>
                <p class="fs-4 text-dark bg-light p-4 rounded-4">{{ word.meaning }}</p>
                <div class="mt-4 d-flex justify-content-center align-items-center gap-4">
                    <span class="fs-3 fw-bold text-success bg-success bg-opacity-10 px-4 py-2 rounded-pill">👍 {{ word.likes }} โหวต</span>
                    <a href="{{ url_for('view_word', word_id=word.id) }}" class="btn btn-primary btn-lg rounded-pill px-4 shadow-sm">เข้าไปดูคอมเมนต์</a>
                </div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="text-center py-5">
        <span class="display-1 opacity-25">🏆</span>
        <p class="text-secondary fs-4 mt-3">ยังไม่มีใครส่งเข้าประกวดสัปดาห์นี้</p>
    </div>
    {% endfor %}
</div>
'''

admin_html = '''
<div class="d-flex align-items-center mb-4">
    <span class="display-4 me-3">⚙️</span>
    <h1 class="fw-bold text-danger mb-0">แผงควบคุม (ห้องเชือด)</h1>
</div>

<div class="card shadow-sm border-0 mb-5 overflow-hidden">
    <div class="card-header bg-danger text-white fw-bold py-3 fs-5">🚩 บัญชีดำ (คำที่ถูก Report)</div>
    <div class="card-body p-0">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr><th class="ps-4">คำศัพท์</th><th>ผู้บัญญัติ</th><th class="text-end pe-4">จัดการ</th></tr>
            </thead>
            <tbody>
            {% for w in reported %}
            <tr>
                <td class="ps-4"><a href="{{ url_for('view_word', word_id=w.id) }}" class="text-danger fw-bold text-decoration-none fs-5">{{ w.word }}</a></td>
                <td><span class="badge bg-secondary">{{ w.nominated_by }}</span></td>
                <td class="text-end pe-4">
                    <a href="{{ url_for('admin_action', action='clear', word_id=w.id) }}" class="btn btn-sm btn-success fw-bold rounded-pill px-3">บริสุทธิ์ (ยกเลิก)</a>
                    <a href="{{ url_for('admin_action', action='delete', word_id=w.id) }}" class="btn btn-sm btn-outline-danger fw-bold rounded-pill px-3 ms-1" onclick="return confirm('ลบถาวร แน่ใจนะแอด?')">ลบทิ้ง</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="3" class="text-center text-muted py-5 fs-5">ความสงบสุขบังเกิด ไม่มีคำโดนรีพอร์ต</td></tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div class="card shadow-sm border-0 overflow-hidden">
    <div class="card-header bg-dark text-white fw-bold py-3 fs-5">👁️ ระบบสอดส่อง (Audit Logs)</div>
    <div class="card-body p-0" style="max-height: 500px; overflow-y: auto;">
        <table class="table table-striped align-middle mb-0">
            <thead class="table-light sticky-top">
                <tr><th class="ps-4">เวลา</th><th>ผู้ใช้</th><th>สิ่งที่ทำลงไป</th></tr>
            </thead>
            <tbody>
            {% for log in logs %}
            <tr>
                <td class="text-muted ps-4 small">{{ log.timestamp }}</td>
                <td><span class="text-primary fw-bold">{{ log.username }}</span></td>
                <td>{{ log.action }}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
</div>
'''

# ==========================================
# 3. Logic & Routes
# ==========================================
def render_page(template_string, **kwargs):
    full_template = base_html.replace('<!-- CONTENT_PLACEHOLDER -->', template_string)
    return render_template_string(full_template, **kwargs)

def is_sunday():
    return datetime.now().weekday() == 6  # 0=Mon, ..., 6=Sun

@app.before_request
def require_login():
    allowed = ['login', 'signup', 'static']
    if request.endpoint not in allowed and 'username' not in session:
        flash('ไม่พบบัญชีนี้ครับ รบกวน login ก่อนนะครับ', 'danger')
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if not user:
            flash('ไม่พบบัญชีนี้ครับ รบกวน login ก่อนนะครับ', 'danger')
        elif not check_password_hash(user['password'], password):
            flash('ขออภัยด้วยครับ username หรือ รหัสผ่านของคุณไม่ถูกต้อง', 'danger')
        else:
            session['username'] = user['username']
            session['role'] = user['role']
            log_action(username, 'เข้าสู่ระบบแล้ว')
            return redirect(url_for('home'))
            
    return render_page(auth_html, title='ประตูสู่ความเกรียน (Login)', btn_text='เข้าสู่ระบบ', 
                       alt_link=url_for('signup'), alt_text='หน้าใหม่หรอ? ไป Sign up สิ (สมัครสมาชิก)')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password, role, bio) VALUES (?, ?, ?, ?)', 
                         (username, hashed_pw, 'user', ''))
            conn.commit()
            log_action(username, 'จุติบัญชีใหม่บนพจนานุเกรียน')
            flash('สร้างบัญชีสำเร็จ! ลองเข้าสู่ระบบดูสิ', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('ช้าไปต๋อย! Username นี้มีคนจองแล้ว', 'warning')
        finally:
            conn.close()
    return render_page(auth_html, title='ลงทะเบียนคนเกรียน (Sign Up)', btn_text='สร้างบัญชี', 
                       alt_link=url_for('login'), alt_text='มีของอยู่แล้ว? กลับไปเข้าสู่ระบบ (Login)')

@app.route('/logout')
def logout():
    log_action(session.get('username', 'Ghost'), 'ออกจากระบบไปเผชิญโลกความจริง')
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    letter = request.args.get('letter')
    conn = get_db_connection()
    if letter:
        words = conn.execute("SELECT * FROM words WHERE first_letter = ? ORDER BY id DESC", (letter.upper(),)).fetchall()
    else:
        words = conn.execute("SELECT * FROM words ORDER BY id DESC").fetchall()
    conn.close()
    return render_page(home_html, words=words)

@app.route('/word/<int:word_id>')
def view_word(word_id):
    conn = get_db_connection()
    word = conn.execute('SELECT * FROM words WHERE id = ?', (word_id,)).fetchone()
    comments = conn.execute('SELECT * FROM comments WHERE word_id = ? ORDER BY id DESC', (word_id,)).fetchall()
    conn.close()
    if not word: return redirect(url_for('home'))
    return render_page(word_detail_html, word=word, comments=comments, is_sunday=is_sunday())

@app.route('/nominate', methods=['GET', 'POST'])
def nominate():
    if is_sunday():
        flash('วันอาทิตย์ศักดิ์สิทธิ์! ระบบปิดรับคำศัพท์และปิดโหวตเพื่อประกาศผลนะจ๊ะ', 'danger')
        return redirect(url_for('wotw'))
        
    if request.method == 'POST':
        word_text = request.form['word']
        meaning = request.form['meaning']
        first_letter = word_text[0].upper() if word_text else ''
        
        conn = get_db_connection()
        conn.execute('INSERT INTO words (word, meaning, first_letter, nominated_by) VALUES (?, ?, ?, ?)',
                     (word_text, meaning, first_letter, session['username']))
        conn.commit()
        conn.close()
        log_action(session['username'], f'บัญญัติคำว่า: {word_text}')
        flash('จารึกคำศัพท์ลงพจนานุเกรียนเรียบร้อย!', 'success')
        return redirect(url_for('home'))
    return render_page(add_word_html)

@app.route('/vote/<int:word_id>/<type>')
def vote_word(word_id, type):
    if is_sunday():
        flash('วันอาทิตย์งดลงคะแนนเสียง!', 'danger')
        return redirect(url_for('view_word', word_id=word_id))
        
    username = session['username']
    conn = get_db_connection()
    exist_vote = conn.execute('SELECT * FROM votes WHERE word_id = ? AND username = ?', (word_id, username)).fetchone()
    if exist_vote:
        flash('คุณลงคะแนนให้คำนี้ไปแล้ว เปลี่ยนใจไม่ได้หรอกนะ!', 'warning')
    else:
        conn.execute('INSERT INTO votes (word_id, username, vote_type) VALUES (?, ?, ?)', (word_id, username, type))
        if type == 'like':
            conn.execute('UPDATE words SET likes = likes + 1 WHERE id = ?', (word_id,))
            log_action(username, f'ปา Like ใส่คำศัพท์ ID:{word_id}')
        elif type == 'dislike':
            conn.execute('UPDATE words SET dislikes = dislikes + 1 WHERE id = ?', (word_id,))
            log_action(username, f'แจก Dislike ให้คำศัพท์ ID:{word_id}')
        conn.commit()
        flash('บันทึกคะแนนโหวตเรียบร้อย!', 'success')
    conn.close()
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/comment/<int:word_id>', methods=['POST'])
def add_comment(word_id):
    comment_text = request.form['comment']
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_db_connection()
    conn.execute('INSERT INTO comments (word_id, username, comment, created_at) VALUES (?, ?, ?, ?)',
                 (word_id, session['username'], comment_text, timestamp))
    conn.commit()
    conn.close()
    log_action(session['username'], f'พ่นคอมเมนต์ในคำศัพท์ ID:{word_id}')
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/profile/<username>', methods=['GET', 'POST'])
def profile(username):
    conn = get_db_connection()
    if request.method == 'POST' and session.get('username') == username:
        conn.execute('UPDATE users SET bio = ? WHERE username = ?', (request.form['bio'], username))
        conn.commit()
        log_action(username, 'เปลี่ยนคำแนะนำตัวใหม่')
        flash('อัปเดตโปรไฟล์เรียบร้อย', 'success')
        
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if not user: return redirect(url_for('home'))
    return render_page(profile_html, user=user)

@app.route('/wotw')
def wotw():
    conn = get_db_connection()
    top_words = conn.execute('SELECT * FROM words ORDER BY likes DESC LIMIT 5').fetchall()
    conn.close()
    return render_page(wotw_html, words=top_words, is_sunday=is_sunday())

@app.route('/report/<int:word_id>')
def report_word(word_id):
    conn = get_db_connection()
    conn.execute("UPDATE words SET status='reported' WHERE id=?", (word_id,))
    conn.commit()
    conn.close()
    log_action(session['username'], f'แหกปาก Report คำศัพท์ ID:{word_id}')
    flash('รายงานไปถึงหูแอดมินแล้ว!', 'info')
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin':
        flash('เห้ย! นี่มันห้องลับของแอดมิน ออกไปเลย!', 'danger')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    reported = conn.execute("SELECT * FROM words WHERE status='reported'").fetchall()
    logs = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return render_page(admin_html, reported=reported, logs=logs)

@app.route('/admin/action/<action>/<int:word_id>')
def admin_action(action, word_id):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    conn = get_db_connection()
    if action == 'clear':
        conn.execute("UPDATE words SET status='normal' WHERE id=?", (word_id,))
        log_action('Admin', f'ปลดคำร้องเรียนคำศัพท์ ID:{word_id}')
    elif action == 'delete':
        conn.execute("DELETE FROM words WHERE id=?", (word_id,))
        conn.execute("DELETE FROM comments WHERE word_id=?", (word_id,))
        conn.execute("DELETE FROM votes WHERE word_id=?", (word_id,))
        log_action('Admin', f'ใช้พลังเทพเจ้าลบคำศัพท์ ID:{word_id} ทิ้งจากโลก')
    conn.commit()
    conn.close()
    flash('ระบบลงทัณฑ์เรียบร้อย!', 'success')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
