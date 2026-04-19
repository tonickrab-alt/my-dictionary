import os
import sqlite3
from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_dictionary'

# ==========================================
# 1. ระบบฐานข้อมูล (Database)
# ==========================================
def get_db_connection():
    conn = sqlite3.connect('opendict.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # สร้างตาราง users (มีช่อง role แล้ว)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    # สร้างตาราง words
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
    print("Database initialized successfully.")

# ==========================================
# 2. โค้ดหน้าเว็บ (HTML Templates)
# ==========================================
# หน้าแรก (Home)
home_html = '{% extends "base" %}{% block content %}' + '''
<h2 class="mb-4">📖 คำศัพท์ทั้งหมด</h2>
<div class="row">
    {% for word in words %}
        <div class="col-md-6 mb-3">
            <div class="card shadow-sm">
                <div class="card-body">
                    <h4 class="card-title text-primary">{{ word.word }}</h4>
                    <p class="card-text">{{ word.meaning }}</p>
                    <small class="text-muted">เพิ่มโดย: {{ word.nominated_by }}</small>
                </div>
            </div>
        </div>
    {% else %}
        <p class="text-muted">ยังไม่มีคำศัพท์ในระบบ มาร่วมกันเพิ่มคำศัพท์กันเถอะ!</p>
    {% endfor %}
</div>
''' + '{% endblock %}'

# หน้าสมัครสมาชิก (ลบข้อความใบ้ admin ออกแล้ว)
signup_html = '{% extends "base" %}{% block content %}' + '''
<div class="card shadow-sm mx-auto" style="max-width: 400px;">
    <div class="card-body">
        <h3 class="card-title text-center mb-4">✨ สมัครสมาชิก</h3>
        <form method="POST">
            <div class="mb-3">
                <input type="text" class="form-control" name="username" placeholder="ตั้งชื่อผู้ใช้เท่ๆ" required>
            </div>
            <div class="mb-3">
                <input type="password" class="form-control" name="password" placeholder="ตั้งรหัสผ่าน" required>
            </div>
            <button type="submit" class="btn btn-success w-100">สมัครสมาชิก</button>
        </form>
    </div>
</div>
''' + '{% endblock %}'

# หน้าเข้าสู่ระบบ
login_html = '{% extends "base" %}{% block content %}' + '''
<div class="card shadow-sm mx-auto" style="max-width: 400px;">
    <div class="card-body">
        <h3 class="card-title text-center mb-4">🔑 เข้าสู่ระบบ</h3>
        <form method="POST">
            <div class="mb-3">
                <input type="text" class="form-control" name="username" placeholder="ชื่อผู้ใช้" required>
            </div>
            <div class="mb-3">
                <input type="password" class="form-control" name="password" placeholder="รหัสผ่าน" required>
            </div>
            <button type="submit" class="btn btn-primary w-100">เข้าสู่ระบบ</button>
        </form>
    </div>
</div>
''' + '{% endblock %}'

# หน้าเพิ่มคำศัพท์
nominate_html = '{% extends "base" %}{% block content %}' + '''
<div class="card shadow-sm">
    <div class="card-body">
        <h3 class="card-title mb-4">✍️ เสนอคำศัพท์ใหม่</h3>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label">คำศัพท์</label>
                <input type="text" class="form-control" name="word" required>
            </div>
            <div class="mb-3">
                <label class="form-label">ความหมาย</label>
                <textarea class="form-control" name="meaning" rows="3" required></textarea>
            </div>
            <button type="submit" class="btn btn-primary">ส่งคำศัพท์ให้แอดมินพิจารณา</button>
        </form>
    </div>
</div>
''' + '{% endblock %}'

# หน้าแอดมิน
admin_html = '{% extends "base" %}{% block content %}' + '''
<h2 class="mb-4">🛡️ ระบบจัดการ (Admin)</h2>
<h4>คำศัพท์ที่รอการอนุมัติ</h4>
<div class="table-responsive">
    <table class="table table-bordered bg-white">
        <thead>
            <tr>
                <th>คำศัพท์</th>
                <th>ความหมาย</th>
                <th>ผู้เสนอ</th>
                <th>จัดการ</th>
            </tr>
        </thead>
        <tbody>
            {% for word in pending_words %}
            <tr>
                <td>{{ word.word }}</td>
                <td>{{ word.meaning }}</td>
                <td>{{ word.nominated_by }}</td>
                <td>
                    <a href="{{ url_for('approve_word', word_id=word.id) }}" class="btn btn-success btn-sm">อนุมัติ</a>
                    <a href="{{ url_for('reject_word', word_id=word.id) }}" class="btn btn-danger btn-sm">ปฏิเสธ</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="4" class="text-center text-muted">ไม่มีคำศัพท์รออนุมัติ</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
''' + '{% endblock %}'


# ==========================================
# 3. ระบบเส้นทาง (Routes / Logic)
# ==========================================
def render(template_string, **kwargs):
    # รวมโค้ด base.html เข้ากับหน้าต่างๆ
    return render_template_string(template_string.replace('{% extends "base" %}', base_html), **kwargs)

@app.route('/')
def home():
    conn = get_db_connection()
    words = conn.execute("SELECT * FROM words WHERE status='approved' ORDER BY id DESC").fetchall()
    conn.close()
    return render(home_html, words=words)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        
        conn = get_db_connection()
        try:
            # เช็กว่ามีคนสมัครไปหรือยัง ถ้ายังไม่มี คนแรกจะได้เป็น admin อัตโนมัติ!
            user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            role = 'admin' if user_count == 0 else 'user'
            
            conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                         (username, hashed_pw, role))
            conn.commit()
            flash('สมัครสมาชิกสำเร็จ! เข้าสู่ระบบได้เลย', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('ชื่อผู้ใช้นี้มีคนใช้แล้วครับ', 'danger')
        finally:
            conn.close()
    return render(signup_html)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'ยินดีต้อนรับคุณ {username}', 'success')
            return redirect(url_for('home'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')
    return render(login_html)

@app.route('/logout')
def logout():
    session.clear()
    flash('ออกจากระบบเรียบร้อย', 'success')
    return redirect(url_for('home'))

@app.route('/nominate', methods=['GET', 'POST'])
def nominate():
    if 'user_id' not in session:
        flash('กรุณาเข้าสู่ระบบก่อนเพิ่มคำศัพท์', 'warning')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        word = request.form['word']
        meaning = request.form['meaning']
        
        conn = get_db_connection()
        conn.execute('INSERT INTO words (word, meaning, status, nominated_by) VALUES (?, ?, ?, ?)',
                     (word, meaning, 'pending', session['username']))
        conn.commit()
        conn.close()
        flash('ส่งคำศัพท์เรียบร้อย รอแอดมินอนุมัตินะครับ', 'success')
        return redirect(url_for('home'))
        
    return render(nominate_html)

@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin':
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'danger')
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    pending_words = conn.execute("SELECT * FROM words WHERE status='pending'").fetchall()
    conn.close()
    return render(admin_html, pending_words=pending_words)

@app.route('/admin/approve/<int:word_id>')
def approve_word(word_id):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    conn = get_db_connection()
    conn.execute("UPDATE words SET status='approved' WHERE id=?", (word_id,))
    conn.commit()
    conn.close()
    flash('อนุมัติคำศัพท์แล้ว', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/reject/<int:word_id>')
def reject_word(word_id):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    conn = get_db_connection()
    conn.execute("DELETE FROM words WHERE id=?", (word_id,))
    conn.commit()
    conn.close()
    flash('ปฏิเสธคำศัพท์แล้ว', 'danger')
    return redirect(url_for('admin_panel'))

# ==========================================
# 4. จุดสตาร์ทของระบบ (Port & Run)
# ==========================================
if __name__ == '__main__':
    init_db() # สั่งสร้างฐานข้อมูลก่อนทำงาน
    port = int(os.environ.get("PORT", 8080)) # ค้นหาพอร์ตอัตโนมัติ
    app.run(host='0.0.0.0', port=port)

