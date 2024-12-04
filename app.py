from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)


def get_db_connection():
    try:
        conn = sqlite3.connect('usage.db')
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None


def create_table():
    conn = get_db_connection()

    # Tabela użytkowników
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            login TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    # Tabela zużycia prądu
    conn.execute('''
        CREATE TABLE IF NOT EXISTS electricity (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date TEXT,
            L1_usage REAL,
            L2_usage REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Tabela zużycia gazu
    conn.execute('''
        CREATE TABLE IF NOT EXISTS gas_usage (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date TEXT,
            usage REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return "Witaj, Railway!"


# Rejestracja użytkownika
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    login = data.get('login')
    password = data.get('password')
    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO users (login, password_hash) VALUES (?, ?)', (login, password_hash))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Taki użytkownik już istnieje!'}), 400
    finally:
        conn.close()

    return jsonify({'message': 'Rejestracja pomyślna!'}), 201


# Logowanie użytkownika
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    login = data.get('login')
    password = data.get('password')

    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE login = ?', (login,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        return jsonify({'message': 'Logowanie zakończone sukcesem!', 'user_id': user['id']}), 200
    return jsonify({'message': 'Nieprawidłowy login lub hasło!'}), 401


# Dodanie danych zużycia prądu
@app.route('/usage/electricity', methods=['POST'])
def add_electricity():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO electricity (user_id, date, L1_usage, L2_usage) VALUES (?, ?, ?, ?)
    ''', (data['user_id'], data['date'], data['L1_usage'], data['L2_usage']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Electricity data added successfully!'}), 201


# Dodanie danych zużycia gazu
@app.route('/usage/gas', methods=['POST'])
def add_gas_usage():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO gas_usage (user_id, date, usage) VALUES (?, ?, ?)
    ''', (data['user_id'], data['date'], data['usage']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Gas data added successfully!'}), 201


# Pobranie danych prądu dla użytkownika
@app.route('/usage/electricity/<int:user_id>', methods=['GET'])
def get_electricity_usage(user_id):
    conn = get_db_connection()
    usage = conn.execute(
        'SELECT * FROM electricity WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return jsonify([dict(u) for u in usage])


# Pobranie danych gazu dla użytkownika
@app.route('/usage/gas/<int:user_id>', methods=['GET'])
def get_gas_usage(user_id):
    conn = get_db_connection()
    usage = conn.execute(
        'SELECT * FROM gas_usage WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return jsonify([dict(u) for u in usage])


@app.route('/delete_last/<resource>/<int:user_id>', methods=['DELETE'])
def delete_last(resource, user_id):
    table = 'electricity' if resource == 'electricity' else 'gas_usage'
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        f"SELECT id FROM {table} WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
    last_id = cursor.fetchone()

    if last_id:
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (last_id[0],))
        conn.commit()
        conn.close()
        return jsonify({'message': f'Last record in {table} for user {user_id} deleted successfully.'}), 200
    else:
        conn.close()
        return jsonify({'message': f'No records to delete in {table} for user {user_id}.'}), 404


if __name__ == "__main__":
    create_table()
    # app.run(debug=True)
