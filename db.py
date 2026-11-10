import sqlite3
from werkzeug.security import generate_password_hash

DB_NAME = 'library.db'


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Tabel User
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT CHECK(role IN ('pustakawan', 'peminjam')) NOT NULL
        )
    ''')

    # Tabel Buku
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # Tabel Peminjaman
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS borrowings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            borrow_date DATE DEFAULT (DATE('now')),
            return_date DATE,
            status TEXT CHECK(status IN ('dipinjam', 'dikembalikan')) DEFAULT 'dipinjam',
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (book_id) REFERENCES books (id)
        )
    ''')

    # Akun default
    admin_pw = generate_password_hash('admin123')
    user_pw = generate_password_hash('user123')

    cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, password, full_name, role)
        VALUES (1, 'pustakawan', ?, 'Petugas Perpustakaan', 'pustakawan')
    ''', (admin_pw,))

    cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, password, full_name, role)
        VALUES (2, 'peminjam', ?, 'Anggota Pembaca', 'peminjam')
    ''', (user_pw,))

    # Data awal buku
    initial_books = [
        ('Belajar Python Cepat', 'Guido Rossum', 'Teknologi', 5),
        ('Clean Architecture', 'Robert C. Martin', 'Teknologi', 3),
        ('Laskar Pelangi', 'Andrea Hirata', 'Sastra', 4),
        ('Atomic Habits', 'James Clear', 'Self Improvement', 6)
    ]

    cursor.execute("SELECT COUNT(*) FROM books")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO books (title, author, category, stock)
            VALUES (?, ?, ?, ?)
        ''', initial_books)

    conn.commit()
    conn.close()
    print("Database library.db berhasil diinisialisasi beserta data demo.")


if __name__ == '__main__':
    init_db()