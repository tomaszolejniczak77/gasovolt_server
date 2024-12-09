from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, jwt_required, get_jwt_identity
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

# Konfiguracja JWT
# Zmień na losowy i bezpieczny klucz!
app.config['JWT_SECRET_KEY'] = 'your-secret-key'
jwt = JWTManager(app)


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
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0  -- 0 = false, 1 = true
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


# def add_is_admin_column():
#     conn = get_db_connection()
#     try:
#         conn.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
#         print("Column 'is_admin' added successfully.")
#     except sqlite3.OperationalError:
#         print("Column 'is_admin' already exists.")
#     finally:
#         conn.close()


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


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    login = data.get('login')
    password = data.get('password')

    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE login = ?', (login,)
    ).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        # Generowanie access i refresh tokenów
        access_token = create_access_token(
            identity=str(user['id']), expires_delta=False)
        refresh_token = create_refresh_token(identity=str(user['id']))

        return jsonify({
            'message': 'Logowanie zakończone sukcesem!',
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200

    return jsonify({'message': 'Nieprawidłowy login lub hasło!'}), 401

# Endpoint do odświeżania access tokena


@app.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()  # Pobiera identity (id użytkownika) z refresh_token
    new_access_token = create_access_token(identity=identity)

    return jsonify({
        'access_token': new_access_token
    }), 200


@app.route('/usage/electricity', methods=['GET'])
@jwt_required()
def get_electricity():
    user_id = get_jwt_identity()  # Pobieranie user_id z tokenu JWT
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, date, L1_usage, L2_usage
        FROM electricity
        WHERE user_id = ?
        ORDER BY date ASC
    ''', (user_id,))

    records = cursor.fetchall()
    conn.close()

    # Konwersja wyników na listę słowników
    data = [dict(record) for record in records]

    return jsonify({'electricity_usage': data}), 200

# Dodanie danych zużycia prądu (zabezpieczone JWT)


@app.route('/usage/electricity', methods=['POST'])
@jwt_required()
def add_electricity():
    user_id = get_jwt_identity()  # Pobieranie user_id z tokenu JWT
    print(f"User ID: {user_id}")
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO electricity (user_id, date, L1_usage, L2_usage) VALUES (?, ?, ?, ?)
    ''', (user_id, data['date'], data['L1_usage'], data['L2_usage']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Electricity data added successfully!'}), 201

# Dodanie danych zużycia gazu (zabezpieczone JWT)


@app.route('/usage/gas', methods=['GET'])
@jwt_required()
def get_gas_usage():
    user_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, date, usage
        FROM gas_usage
        WHERE user_id = ?
        ORDER BY date ASC
    ''', (user_id,))

    records = cursor.fetchall()
    conn.close()

    data = [dict(record) for record in records]

    return jsonify({'gas_usage': data}), 200


@app.route('/usage/gas', methods=['POST'])
@jwt_required()
def add_gas_usage():
    user_id = get_jwt_identity()  # Pobieranie user_id z tokenu JWT
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO gas_usage (user_id, date, usage) VALUES (?, ?, ?)
    ''', (user_id, data['date'], data['usage']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Gas data added successfully!'}), 201


# Usunięcie ostatniego wpisu (zabezpieczone JWT)


@app.route('/delete_last/<resource>', methods=['DELETE'])
@jwt_required()
def delete_last(resource):
    user_id = get_jwt_identity()  # Pobieranie user_id z tokenu JWT
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
        return jsonify({'message': f'Last record in {table} deleted successfully.'}), 200
    else:
        conn.close()
        return jsonify({'message': f'No records to delete in {table}.'}), 404


@app.route('/user/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    current_user_id = get_jwt_identity()

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?',
                        (current_user_id,)).fetchone()

    # Sprawdzenie, czy zalogowany użytkownik to admin
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'message': 'Brak uprawnień!'}), 403

    # Usunięcie użytkownika
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': f'User {user_id} deleted successfully.'}), 200


if __name__ == "__main__":
    create_table()
    # app.run(debug=True)
