import os
import psycopg2
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# Get database URL from environment variable
DATABASE_URL = os.getenv('DATABASE_URL')

# Database initialization
def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        # Create users table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id TEXT PRIMARY KEY, 
                      balance INTEGER DEFAULT 0, 
                      hash_rate INTEGER DEFAULT 2, 
                      farm_active BOOLEAN DEFAULT FALSE, 
                      last_farm TIMESTAMP)''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")

# Call init_db when the app starts
init_db()

@app.route('/api/register', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        # Check if user already exists
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        if user:
            conn.close()
            return jsonify({"status": "success", "message": "User already registered"})
        
        # Register new user
        c.execute("INSERT INTO users (user_id, balance, hash_rate, farm_active) VALUES (%s, %s, %s, %s)",
                  (user_id, 0, 2, False))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "User registered successfully"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/user', methods=['GET'])
def get_user():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            # If user not found, register them
            c = conn.cursor()
            c.execute("INSERT INTO users (user_id, balance, hash_rate, farm_active) VALUES (%s, %s, %s, %s)",
                      (user_id, 0, 2, False))
            conn.commit()
            c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = c.fetchone()
        
        # Calculate balance increase if farm is active
        if user[3]:  # farm_active
            last_farm = user[4]  # last_farm timestamp
            if last_farm:
                last_farm = datetime.strptime(last_farm, '%Y-%m-%d %H:%M:%S.%f')
                now = datetime.utcnow()
                seconds_passed = (now - last_farm).total_seconds()
                balance_increase = int(seconds_passed * user[2] / 3600)  # hash_rate per hour
                new_balance = user[1] + balance_increase
                c.execute("UPDATE users SET balance = %s, last_farm = %s WHERE user_id = %s",
                          (new_balance, now, user_id))
                conn.commit()
                # Refresh user data
                c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                user = c.fetchone()
        
        conn.close()
        return jsonify({
            "status": "success",
            "user": {
                "user_id": user[0],
                "balance": user[1],
                "hash_rate": user[2],
                "farm_active": user[3]
            }
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/claim', methods=['POST'])
def claim():
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        if not user[3]:  # farm_active
            conn.close()
            return jsonify({"status": "error", "message": "Farming is not active"}), 400
        
        # Stop farming and update balance
        last_farm = user[4]
        if last_farm:
            last_farm = datetime.strptime(last_farm, '%Y-%m-%d %H:%M:%S.%f')
            now = datetime.utcnow()
            seconds_passed = (now - last_farm).total_seconds()
            balance_increase = int(seconds_passed * user[2] / 3600)  # hash_rate per hour
            new_balance = user[1] + balance_increase
            c.execute("UPDATE users SET balance = %s, farm_active = %s, last_farm = NULL WHERE user_id = %s",
                      (new_balance, False, user_id))
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "message": f"Claimed {balance_increase} SS Points"})
        else:
            conn.close()
            return jsonify({"status": "error", "message": "No farming data available"}), 400
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/farm', methods=['POST'])
def farm():
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        if user[3]:  # farm_active
            conn.close()
            return jsonify({"status": "error", "message": "Farming is already active"}), 400
        
        # Start farming
        now = datetime.utcnow()
        c.execute("UPDATE users SET farm_active = %s, last_farm = %s WHERE user_id = %s",
                  (True, now, user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Farming started"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/boost', methods=['POST'])
def boost():
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        # Increase hash_rate (e.g., +1 GH/s per boost)
        new_hash_rate = user[2] + 1
        c.execute("UPDATE users SET hash_rate = %s WHERE user_id = %s", (new_hash_rate, user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Hash rate boosted to {new_hash_rate} GH/s"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/')
def home():
    return jsonify({"status": "success", "message": "Welcome to SS Farming Backend"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
