import os
import psycopg2
from flask import Flask, request, jsonify

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
                     (user_id TEXT PRIMARY KEY, balance INTEGER)''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")

# Call init_db when the app starts
init_db()

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
        conn.close()
        
        if user:
            return jsonify({"status": "success", "user": {"user_id": user[0], "balance": user[1]}})
        return jsonify({"status": "error", "message": "User not found"}), 404
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/user', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        balance = data.get('balance', 0)  # Default balance to 0 if not provided
        
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        # Insert or update user
        c.execute("INSERT INTO users (user_id, balance) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET balance = %s",
                  (user_id, balance, balance))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": f"User {user_id} created/updated successfully"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/user/balance', methods=['POST'])
def update_balance():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        
        if not user_id or amount is None:
            return jsonify({"status": "error", "message": "user_id and amount are required"}), 400
        
        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        # Get current balance
        c.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        new_balance = user[0] + amount
        if new_balance < 0:
            conn.close()
            return jsonify({"status": "error", "message": "Balance cannot be negative"}), 400
        
        # Update balance
        c.execute("UPDATE users SET balance = %s WHERE user_id = %s", (new_balance, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": f"Balance updated for user {user_id}", "new_balance": new_balance})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/')
def home():
    return jsonify({"status": "success", "message": "Welcome to SS Farming Backend"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
