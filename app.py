from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from db import get_db

app = Flask(__name__)
app.secret_key = 'super_secret_library_key'

# Decorator proteksi login
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Silakan masuk terlebih dahulu.', 'warning')
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('Akses ditolak: Anda tidak memiliki izin untuk halaman tersebut.', 'danger')
                return redirect(url_for('katalog'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def index():
    return redirect(url_for('katalog'))

# --- AUTHENTICATION ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            flash(f'Selamat datang kembali, {user["full_name"]}!', 'success')
            return redirect(url_for('admin_dashboard' if user['role'] == 'pustakawan' else 'katalog'))

        flash('Username atau kata sandi tidak valid.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO users (username, password, full_name, role)
                VALUES (?, ?, ?, 'peminjam')
            ''', (username, generate_password_hash(password), full_name))
            conn.commit()
            flash('Pendaftaran akun peminjam berhasil! Silakan masuk.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Username sudah digunakan, silakan pilih yang lain.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah keluar.', 'info')
    return redirect(url_for('login'))

# --- FITUR PEMINJAM ---

@app.route('/katalog')
def katalog():
    query = request.args.get('q', '').strip()
    conn = get_db()
    if query:
        books = conn.execute('''
            SELECT * FROM books 
            WHERE title LIKE ? OR author LIKE ? OR category LIKE ?
        ''', (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
    else:
        books = conn.execute('SELECT * FROM books').fetchall()
    conn.close()
    return render_template('katalog.html', books=books, query=query)

@app.route('/pinjam/<int:book_id>', methods=['POST'])
@login_required(role='peminjam')
def pinjam_buku(book_id):
    user_id = session['user_id']
    conn = get_db()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()

    if not book or book['stock'] <= 0:
        flash('Stok buku ini sedang habis.', 'danger')
        conn.close()
        return redirect(url_for('katalog'))

    # Cek apakah peminjam masih aktif meminjam buku ini
    active_borrow = conn.execute('''
        SELECT * FROM borrowings 
        WHERE user_id = ? AND book_id = ? AND status = 'dipinjam'
    ''', (user_id, book_id)).fetchone()

    if active_borrow:
        flash('Anda sedang meminjam buku ini. Kembalikan terlebih dahulu sebelum meminjam ulang.', 'warning')
        conn.close()
        return redirect(url_for('katalog'))

    # Catat peminjaman dan kurangi stok
    conn.execute('INSERT INTO borrowings (user_id, book_id) VALUES (?, ?)', (user_id, book_id))
    conn.execute('UPDATE books SET stock = stock - 1 WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()

    flash(f'Buku "{book["title"]}" berhasil dipinjam!', 'success')
    return redirect(url_for('riwayat_peminjaman'))

@app.route('/riwayat')
@login_required(role='peminjam')
def riwayat_peminjaman():
    conn = get_db()
    records = conn.execute('''
        SELECT b.id AS borrowing_id, bk.title, bk.author, bk.category, b.borrow_date, b.return_date, b.status
        FROM borrowings b
        JOIN books bk ON b.book_id = bk.id
        WHERE b.user_id = ?
        ORDER BY b.id DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('riwayat.html', records=records)

@app.route('/kembalikan/<int:borrowing_id>', methods=['POST'])
@login_required(role='peminjam')
def kembalikan_buku(borrowing_id):
    conn = get_db()
    borrowing = conn.execute('''
        SELECT * FROM borrowings WHERE id = ? AND user_id = ? AND status = 'dipinjam'
    ''', (borrowing_id, session['user_id'])).fetchone()

    if borrowing:
        conn.execute('''
            UPDATE borrowings 
            SET status = 'dikembalikan', return_date = DATE('now') 
            WHERE id = ?
        ''', (borrowing_id,))
        conn.execute('UPDATE books SET stock = stock + 1 WHERE id = ?', (borrowing['book_id'],))
        conn.commit()
        flash('Buku berhasil dikembalikan. Terima kasih!', 'success')
    else:
        flash('Data peminjaman tidak valid.', 'danger')

    conn.close()
    return redirect(url_for('riwayat_peminjaman'))

# --- FITUR PUSTAKAWAN ---

@app.route('/admin')
@login_required(role='pustakawan')
def admin_dashboard():
    conn = get_db()
    books = conn.execute('SELECT * FROM books ORDER BY id DESC').fetchall()
    borrowings = conn.execute('''
        SELECT b.id, u.full_name, bk.title, b.borrow_date, b.return_date, b.status
        FROM borrowings b
        JOIN users u ON b.user_id = u.id
        JOIN books bk ON b.book_id = bk.id
        ORDER BY b.id DESC
    ''').fetchall()
    conn.close()
    return render_template('admin.html', books=books, borrowings=borrowings)

@app.route('/admin/buku/tambah', methods=['POST'])
@login_required(role='pustakawan')
def tambah_buku():
    title = request.form['title'].strip()
    author = request.form['author'].strip()
    category = request.form['category'].strip()
    stock = int(request.form.get('stock', 1))

    conn = get_db()
    conn.execute('''
        INSERT INTO books (title, author, category, stock)
        VALUES (?, ?, ?, ?)
    ''', (title, author, category, stock))
    conn.commit()
    conn.close()

    flash(f'Buku "{title}" berhasil ditambahkan ke katalog!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/buku/hapus/<int:book_id>', methods=['POST'])
@login_required(role='pustakawan')
def hapus_buku(book_id):
    conn = get_db()
    # Pastikan buku tidak sedang dipinjam
    active = conn.execute('SELECT * FROM borrowings WHERE book_id = ? AND status = "dipinjam"', (book_id,)).fetchone()
    if active:
        flash('Buku tidak dapat dihapus karena masih dalam status peminjaman aktif.', 'danger')
    else:
        conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
        conn.commit()
        flash('Buku berhasil dihapus dari inventaris.', 'info')
    conn.close()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)