import os
import sqlite3
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'ultimate_dictionary_secret'

# ==========================================
# 1. ระบบฐานข้อมูลและ Audit Log
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
    # ตารางผู้ใช้ (เพิ่ม bio)
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT, bio TEXT
    )''')
    # ตารางคำศัพท์ (เพิ่ม like, dislike, status การ report)
    conn.execute('''CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT, meaning TEXT, first_letter TEXT, 
        nominated_by TEXT, likes INTEGER DEFAULT 0, dislikes INTEGER DEFAULT 0, status TEXT DEFAULT 'normal'
    )''')
    # ตารางคอมเมนต์
    conn.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER, username TEXT, comment TEXT, created_at TEXT
    )''')
    # ตารางเก็บประวัติการโหวต (กันโหวตซ้ำ)
    conn.execute('''CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER, username TEXT, vote_type TEXT
    )''')
    # ตาราง Audit Log
    conn.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, action TEXT, timestamp TEXT
    )''')
    
    # สร้างไอดี Admin อัตโนมัติตามโจทย์
    admin_exist = conn.execute("SELECT * FROM users WHERE username='Admin'").fetchone()
    if not admin_exist:
        hashed = generate_password_hash('113333555555')
        conn.execute("INSERT INTO users (username, password, role, bio) VALUES (?, ?, ?, ?)",
                     ('Admin', hashed, 'admin', 'ผู้คุมกฎแห่งพจนานุกรม'))
    
    conn.commit()
    conn.close()

# ==========================================
# 2. HTML Templates (UI สวยงาม)
# ==========================================
base_html = '''
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>พจนานุกรมเสรี Ultimate</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        body { background-color: #f4f7f6; font-family: 'Sarabun', sans-serif; }
        .navbar { background: linear-gradient(90deg, #141E30 0%, #243B55 100%); }
        .card { border: none; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .badge-slot { width: 40px; height: 40px; background: #e9ecef; border-radius: 50%; display: inline-block; margin: 2px; border: 2px dashed #ccc; }
        
        /* เอฟเฟกต์วันมุมขวาบน */
        .day-indicator {
            background: rgba(255,255,255,0.1); border-radius: 20px; padding: 5px 15px;
            color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc;
            box-shadow: 0 0 10px #00ffcc; animation: pulseGlow 2s infinite;
        }
        @keyframes pulseGlow {
            0% { box-shadow: 0 0 5px #00ffcc; }
            50% { box-shadow: 0 0 20px #00ffcc; }
            100% { box-shadow: 0 0 5px #00ffcc; }
        }
        .sunday-alert { color: #ff3366 !important; border-color: #ff3366 !important; box-shadow: 0 0 10px #ff3366 !important; animation: pulseRed 2s infinite !important;}
        @keyframes pulseRed { 0% { box-shadow: 0 0 5px #ff3366; } 50% { box-shadow: 0 0 20px #ff3366; } 100% { box-shadow: 0 0 5px #ff3366; } }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark sticky-top">
        <div class="container">
            <a class="navbar-brand fw-bold" href="{{ url_for('home') }}">📚 OPENDICT</a>
            
            <!-- ป้ายบอกวันมุมขวาบน -->
            <div id="dayDisplay" class="day-indicator d-none d-lg-block mx-auto">กำลังโหลด...</div>

            <div class="d-flex align-items-center">
                {% if session.get('username') %}
                    <a href="{{ url_for('profile', username=session['username']) }}" class="text-white text-decoration-none me-3">
                        👤 {{ session['username'] }}
                    </a>
                    <a href="{{ url_for('wotw') }}" class="btn btn-outline-info btn-sm me-2">🏆 ศัพท์ประจำสัปดาห์</a>
                    <a href="{{ url_for('nominate') }}" class="btn btn-light btn-sm me-2">+ เพิ่มคำ</a>
                    {% if session.get('role') == 'admin' %}
                        <a href="{{ url_for('admin_panel') }}" class="btn btn-warning btn-sm me-2">🛡️ Admin</a>
                    {% endif %}
                    <a href="{{ url_for('logout') }}" class="btn btn-danger btn-sm">ออก</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="container mt-4 mb-5" style="max-width: 900px;">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show shadow-sm">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <!-- CONTENT_PLACEHOLDER -->
        
    </div>

    <script>
        // Script เปลี่ยนสีป้ายบอกวัน
        const days = ['วันอาทิตย์', 'วันจันทร์', 'วันอังคาร', 'วันพุธ', 'วันพฤหัสบดี', 'วันศุกร์', 'วันเสาร์'];
        const today = new Date().getDay();
        const el = document.getElementById('dayDisplay');
        el.innerText = '✨ วันนี้: ' + days[today];
        if(today === 0) {
            el.classList.add('sunday-alert');
            el.innerText = '🏆 วันอาทิตย์: ประกาศผลศัพท์แห่งสัปดาห์!';
        }
    </script>
</body>
</html>
'''

auth_html = '''
<div class="card shadow-lg mx-auto border-0" style="max-width: 450px; border-radius: 20px;">
    <div class="card-body p-5">
        <h2 class="text-center mb-4 fw-bold text-primary">{{ title }}</h2>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label text-muted">ชื่อผู้ใช้งาน (Username)</label>
                <input type="text" class="form-control form-control-lg bg-light" name="username" required>
            </div>
            <div class="mb-4">
                <label class="form-label text-muted">รหัสผ่าน (Password)</label>
                <input type="password" class="form-control form-control-lg bg-light" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary w-100 py-3 fw-bold fs-5 shadow">{{ btn_text }}</button>
        </form>
        <div class="text-center mt-4">
            <a href="{{ alt_link }}" class="text-decoration-none">{{ alt_text }}</a>
        </div>
    </div>
</div>
'''

home_html = '''
<div class="text-center mb-4">
    <h1 class="fw-bold text-dark">พจนานุกรมเปิดเสรี</h1>
</div>
<!-- หมวดหมู่ตัวอักษร -->
<div class="card p-3 mb-4 shadow-sm text-center">
    <div>
        {% for letter in "กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ" %}
            <a href="?letter={{ letter }}" class="btn btn-sm btn-outline-secondary m-1">{{ letter }}</a>
        {% endfor %}
    </div>
    <hr>
    <div>
        {% for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" %}
            <a href="?letter={{ letter }}" class="btn btn-sm btn-outline-secondary m-1">{{ letter }}</a>
        {% endfor %}
        <a href="{{ url_for('home') }}" class="btn btn-sm btn-dark m-1">ดูทั้งหมด</a>
    </div>
</div>

<div class="row">
    {% for word in words %}
    <div class="col-md-6 mb-3">
        <div class="card h-100 shadow-sm border-0 hover-card">
            <div class="card-body">
                <h3 class="fw-bold"><a href="{{ url_for('view_word', word_id=word.id) }}" class="text-primary text-decoration-none">{{ word.word }}</a></h3>
                <p class="text-muted text-truncate">{{ word.meaning }}</p>
            </div>
            <div class="card-footer bg-white border-0 d-flex justify-content-between">
                <small class="text-secondary">โดย: <a href="{{ url_for('profile', username=word.nominated_by) }}">{{ word.nominated_by }}</a></small>
                <div>
                    <span class="text-success me-2">👍 {{ word.likes }}</span>
                    <span class="text-danger">👎 {{ word.dislikes }}</span>
                </div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="text-center py-5"><p class="text-muted fs-5">ไม่พบคำศัพท์ในหมวดหมู่นี้</p></div>
    {% endfor %}
</div>
'''

word_detail_html = '''
<div class="card shadow border-0 mb-4">
    <div class="card-body p-5">
        <div class="d-flex justify-content-between align-items-start">
            <h1 class="display-4 fw-bold text-primary">{{ word.word }}</h1>
            <a href="{{ url_for('report_word', word_id=word.id) }}" class="btn btn-outline-danger btn-sm" onclick="return confirm('ยืนยันการ Report คำศัพท์นี้?')">🚩 Report</a>
        </div>
        <hr>
        <p class="fs-4">{{ word.meaning }}</p>
        <div class="mt-4 p-3 bg-light rounded d-flex justify-content-between align-items-center">
            <span class="text-muted">ผู้บัญญัติ: <a href="{{ url_for('profile', username=word.nominated_by) }}">{{ word.nominated_by }}</a></span>
            <div>
                <a href="{{ url_for('vote_word', word_id=word.id, type='like') }}" class="btn btn-success">👍 ชอบ ({{ word.likes }})</a>
                <a href="{{ url_for('vote_word', word_id=word.id, type='dislike') }}" class="btn btn-danger">👎 ไม่ชอบ ({{ word.dislikes }})</a>
            </div>
        </div>
    </div>
</div>

<div class="card shadow border-0">
    <div class="card-body p-4">
        <h4 class="fw-bold mb-4">💬 คอมเมนต์</h4>
        <form method="POST" action="{{ url_for('add_comment', word_id=word.id) }}" class="mb-4">
            <div class="input-group">
                <input type="text" class="form-control" name="comment" placeholder="แสดงความคิดเห็นที่นี่..." required>
                <button class="btn btn-primary" type="submit">ส่งคอมเมนต์</button>
            </div>
        </form>
        
        {% for c in comments %}
        <div class="border-bottom pb-2 mb-2">
            <strong><a href="{{ url_for('profile', username=c.username) }}">{{ c.username }}</a></strong> 
            <small class="text-muted">{{ c.created_at }}</small>
            <p class="mb-0">{{ c.comment }}</p>
        </div>
        {% else %}
        <p class="text-muted text-center">ยังไม่มีคอมเมนต์ เป็นคนแรกที่แสดงความคิดเห็นสิ!</p>
        {% endfor %}
    </div>
</div>
'''

profile_html = '''
<div class="card shadow border-0">
    <div class="card-body p-5 text-center">
        <div class="mb-3">
            <span class="display-1">👤</span>
        </div>
        <h2 class="fw-bold">{{ user.username }}</h2>
        <span class="badge bg-secondary mb-4">สถานะ: {{ user.role }}</span>
        
        <div class="bg-light p-4 rounded mb-4 text-start">
            <h5 class="fw-bold">📝 แนะนำตัว</h5>
            <p>{{ user.bio if user.bio else 'ผู้ใช้นี้ยังไม่ได้เขียนแนะนำตัว' }}</p>
            {% if session.get('username') == user.username %}
                <form method="POST" class="mt-3">
                    <textarea class="form-control mb-2" name="bio" rows="2" placeholder="อัปเดตคำแนะนำตัวของคุณ...">{{ user.bio }}</textarea>
                    <button type="submit" class="btn btn-sm btn-primary">บันทึกการเปลี่ยนแปลง</button>
                </form>
            {% endif %}
        </div>

        <div class="text-start">
            <h5 class="fw-bold">🏅 เหรียญตรา (Badges - เร็วๆ นี้)</h5>
            <div class="mt-2">
                <div class="badge-slot"></div> <div class="badge-slot"></div>
                <div class="badge-slot"></div> <div class="badge-slot"></div>
                <div class="badge-slot"></div>
            </div>
        </div>
    </div>
</div>
'''

wotw_html = '''
<div class="text-center mb-5">
    <h1 class="display-4 fw-bold text-warning" style="text-shadow: 2px 2px 4px rgba(0,0,0,0.2);">🏆 ศัพท์เก๋ประจำสัปดาห์</h1>
    {% if is_sunday %}
        <p class="fs-4 text-danger fw-bold mt-3">วันนี้วันอาทิตย์! ปิดโหวตและประกาศผลผู้ชนะแล้ว!</p>
    {% else %}
        <p class="fs-5 text-muted">โหวตให้คำศัพท์ที่คุณชื่นชอบ (ปิดโหวตวันอาทิตย์)</p>
    {% endif %}
</div>

<div class="row justify-content-center">
    {% for word in words %}
    <div class="col-md-8 mb-4">
        <div class="card shadow {% if loop.index == 1 and is_sunday %}border-warning border-3{% else %}border-0{% endif %}">
            <div class="card-body text-center p-5">
                {% if loop.index == 1 and is_sunday %}
                    <h2 class="text-warning mb-3">👑 ผู้ชนะอันดับ 1 👑</h2>
                {% endif %}
                <h2 class="fw-bold text-primary">{{ word.word }}</h2>
                <p class="fs-5">{{ word.meaning }}</p>
                <div class="mt-4">
                    <span class="fs-4 me-3">👍 {{ word.likes }} โหวต</span>
                    <a href="{{ url_for('view_word', word_id=word.id) }}" class="btn btn-outline-primary">ดูรายละเอียด/คอมเมนต์</a>
                </div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="text-center"><p class="text-muted">สัปดาห์นี้ยังไม่มีคำศัพท์</p></div>
    {% endfor %}
</div>
'''

admin_html = '''
<h2 class="fw-bold mb-4">🛡️ แผงควบคุมระบบ (Admin)</h2>

<div class="card shadow border-0 mb-4">
    <div class="card-header bg-danger text-white fw-bold">🚩 คำศัพท์ที่ถูก Report</div>
    <div class="card-body p-0">
        <table class="table table-hover mb-0">
            <tr><th>คำศัพท์</th><th>ผู้เสนอ</th><th>จัดการ</th></tr>
            {% for w in reported %}
            <tr>
                <td><a href="{{ url_for('view_word', word_id=w.id) }}">{{ w.word }}</a></td>
                <td>{{ w.nominated_by }}</td>
                <td>
                    <a href="{{ url_for('admin_action', action='clear', word_id=w.id) }}" class="btn btn-sm btn-success">ปกติ (ยกเลิก Report)</a>
                    <a href="{{ url_for('admin_action', action='delete', word_id=w.id) }}" class="btn btn-sm btn-danger" onclick="return confirm('ลบถาวรแน่ใจนะ?')">ลบทิ้ง</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="3" class="text-center text-muted py-3">ไม่มีคำศัพท์ถูกรายงาน</td></tr>
            {% endfor %}
        </table>
    </div>
</div>

<div class="card shadow border-0">
    <div class="card-header bg-dark text-white fw-bold">📜 Audit Logs (ประวัติระบบ)</div>
    <div class="card-body p-0" style="max-height: 400px; overflow-y: auto;">
        <table class="table table-striped mb-0 text-sm">
            <tr><th>เวลา</th><th>ผู้ใช้</th><th>การกระทำ</th></tr>
            {% for log in logs %}
            <tr>
                <td>{{ log.timestamp }}</td>
                <td class="fw-bold">{{ log.username }}</td>
                <td>{{ log.action }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</div>
'''

add_word_html = '''
<div class="card shadow mx-auto border-0" style="max-width: 600px;">
    <div class="card-body p-5">
        <h2 class="fw-bold mb-4 text-center">✍️ บัญญัติศัพท์ใหม่</h2>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label fw-bold">คำศัพท์</label>
                <input type="text" class="form-control form-control-lg bg-light" name="word" required>
            </div>
            <div class="mb-4">
                <label class="form-label fw-bold">ความหมาย</label>
                <textarea class="form-control bg-light" name="meaning" rows="4" required></textarea>
            </div>
            <button type="submit" class="btn btn-primary w-100 py-3 fw-bold fs-5">ส่งคำศัพท์ลงพจนานุกรม</button>
        </form>
    </div>
</div>
'''

# ==========================================
# 3. Logic & Routes
# ==========================================
def render_page(template_string, **kwargs):
    full_template = base_html.replace('<!-- CONTENT_PLACEHOLDER -->', template_string)
    return render_template_string(full_template, **kwargs)

# ระบบดักจับการ Login (ถ้าไม่ล็อกอิน ห้ามเข้าหน้าอื่นเด็ดขาด!)
@app.before_request
def require_login():
    allowed_routes = ['login', 'signup', 'static']
    if request.endpoint not in allowed_routes and 'username' not in session:
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
            log_action(username, 'เข้าสู่ระบบ')
            return redirect(url_for('home'))
            
    return render_page(auth_html, title='เข้าสู่ระบบ', btn_text='Login', 
                       alt_link=url_for('signup'), alt_text='ยังไม่มีบัญชีใช่ไหม? สมัครสมาชิก (Sign up)')

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
            log_action(username, 'สมัครสมาชิกใหม่')
            flash('สมัครสมาชิกสำเร็จ! เข้าสู่ระบบได้เลย', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('ขออภัยด้วยครับ username นี้มีคนใช้แล้ว', 'danger')
        finally:
            conn.close()
    return render_page(auth_html, title='สร้างบัญชีใหม่', btn_text='Sign Up', 
                       alt_link=url_for('login'), alt_text='มีบัญชีอยู่แล้ว? เข้าสู่ระบบ (Login)')

@app.route('/logout')
def logout():
    log_action(session.get('username', 'Unknown'), 'ออกจากระบบ')
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    letter = request.args.get('letter')
    conn = get_db_connection()
    if letter:
        words = conn.execute("SELECT * FROM words WHERE first_letter = ? ORDER BY word", (letter.upper(),)).fetchall()
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
    return render_page(word_detail_html, word=word, comments=comments)

@app.route('/nominate', methods=['GET', 'POST'])
def nominate():
    if request.method == 'POST':
        word_text = request.form['word']
        meaning = request.form['meaning']
        first_letter = word_text[0].upper() if word_text else ''
        
        conn = get_db_connection()
        conn.execute('INSERT INTO words (word, meaning, first_letter, nominated_by) VALUES (?, ?, ?, ?)',
                     (word_text, meaning, first_letter, session['username']))
        conn.commit()
        conn.close()
        log_action(session['username'], f'บัญญัติศัพท์ใหม่: {word_text}')
        flash('บัญญัติศัพท์ใหม่สำเร็จ!', 'success')
        return redirect(url_for('home'))
    return render_page(add_word_html)

@app.route('/vote/<int:word_id>/<type>')
def vote_word(word_id, type):
    username = session['username']
    conn = get_db_connection()
    # เช็กว่าเคยโหวตคำนี้ไปหรือยัง
    exist_vote = conn.execute('SELECT * FROM votes WHERE word_id = ? AND username = ?', (word_id, username)).fetchone()
    if exist_vote:
        flash('คุณได้โหวตคำศัพท์นี้ไปแล้ว!', 'warning')
    else:
        conn.execute('INSERT INTO votes (word_id, username, vote_type) VALUES (?, ?, ?)', (word_id, username, type))
        if type == 'like':
            conn.execute('UPDATE words SET likes = likes + 1 WHERE id = ?', (word_id,))
            log_action(username, f'กด Like คำศัพท์ ID:{word_id}')
        elif type == 'dislike':
            conn.execute('UPDATE words SET dislikes = dislikes + 1 WHERE id = ?', (word_id,))
            log_action(username, f'กด Dislike คำศัพท์ ID:{word_id}')
        conn.commit()
        flash('บันทึกผลโหวตแล้ว!', 'success')
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
    log_action(session['username'], f'คอมเมนต์ในศัพท์ ID:{word_id}')
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/profile/<username>', methods=['GET', 'POST'])
def profile(username):
    conn = get_db_connection()
    if request.method == 'POST' and session.get('username') == username:
        new_bio = request.form['bio']
        conn.execute('UPDATE users SET bio = ? WHERE username = ?', (new_bio, username))
        conn.commit()
        log_action(username, 'อัปเดตโปรไฟล์')
        flash('อัปเดตข้อมูลแนะนำตัวสำเร็จ', 'success')
        
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if not user: return redirect(url_for('home'))
    return render_page(profile_html, user=user)

@app.route('/wotw')
def wotw():
    # 0=Mon, 1=Tue, ..., 6=Sun
    today = datetime.now().weekday()
    is_sunday = (today == 6)
    
    conn = get_db_connection()
    # ดึง Top 5 คำศัพท์ที่มีไลค์เยอะสุด
    top_words = conn.execute('SELECT * FROM words ORDER BY likes DESC LIMIT 5').fetchall()
    conn.close()
    
    return render_page(wotw_html, words=top_words, is_sunday=is_sunday)

@app.route('/report/<int:word_id>')
def report_word(word_id):
    conn = get_db_connection()
    conn.execute("UPDATE words SET status='reported' WHERE id=?", (word_id,))
    conn.commit()
    conn.close()
    log_action(session['username'], f'Report คำศัพท์ ID:{word_id}')
    flash('รายงานคำศัพท์ไปยังแอดมินแล้ว', 'info')
    return redirect(url_for('view_word', word_id=word_id))

@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin':
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'danger')
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
        log_action(session['username'], f'ปลดแบนศัพท์ ID:{word_id}')
    elif action == 'delete':
        conn.execute("DELETE FROM words WHERE id=?", (word_id,))
        conn.execute("DELETE FROM comments WHERE word_id=?", (word_id,))
        log_action(session['username'], f'ลบศัพท์ถาวร ID:{word_id}')
    conn.commit()
    conn.close()
    flash('ดำเนินการเสร็จสิ้น', 'success')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
