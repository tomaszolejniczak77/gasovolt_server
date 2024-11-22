from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os

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

    conn.execute('''
        CREATE TABLE IF NOT EXISTS electricity (
            id INTEGER PRIMARY KEY,
            date TEXT,
            L1_usage REAL,
            L2_usage REAL
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS gas_usage (
            id INTEGER PRIMARY KEY,
            date TEXT,
            usage REAL
        )
    ''')

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return "Hello, Railway!"


@app.route('/usage/electricity', methods=['POST'])
def add_electricity():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO electricity (date, L1_usage, L2_usage) VALUES (?, ?, ?)
    ''', (data['date'], data['L1_usage'], data['L2_usage']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Electricity data added successfully!'}), 201


@app.route('/usage/gas', methods=['POST'])
def add_gas_usage():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO gas_usage (date, usage) VALUES (?, ?)
    ''', (data['date'], data['usage']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Gas data added successfully!'}), 201


@app.route('/usage/electricity', methods=['GET'])
def get_electricity_usage():
    conn = get_db_connection()
    usage = conn.execute('SELECT * FROM electricity').fetchall()
    conn.close()
    return jsonify([dict(u) for u in usage])


@app.route('/usage/gas', methods=['GET'])
def get_gas_usage():
    conn = get_db_connection()
    usage = conn.execute('SELECT * FROM gas_usage').fetchall()
    conn.close()
    return jsonify([dict(u) for u in usage])


@app.route('/usage/all', methods=['GET'])
def get_all_usage():
    conn = get_db_connection()

    electricity_usage = conn.execute('SELECT * FROM electricity').fetchall()

    gas_usage = conn.execute('SELECT * FROM gas_usage').fetchall()

    conn.close()

    data = {
        'electricity': [dict(row) for row in electricity_usage],
        'gas': [dict(row) for row in gas_usage]
    }

    return jsonify(data)


if __name__ == '__main__':
    create_table()
    # Umożliwia dostęp do aplikacji z innych urządzeń w sieci
    port = int(os.environ.get("PORT", 5000))  # Railway ustawia zmienną PORT
    app.run(host="0.0.0.0", port=port)
