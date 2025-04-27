import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Get database URL from environment variable
DATABASE_URL = os.getenv('DATABASE_URL')

# Initialize connection pool
try:
    db_pool = SimpleConnectionPool(
        1,  # Minimum number of connections
        10,  # Maximum number of connections
        dsn=DATABASE_URL
    )
except Exception as e:
    print(f"Error initializing connection pool: {e}")
    db_pool = None

# Database initialization
def init_db():
    if not db_pool:
        print("Connection pool not initialized")
        return
    
    conn = None
    try:
        conn = db_pool.getconn()
        c = conn.cursor()
        # Create users table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id TEXT PRIMARY KEY, 
                      balance INTEGER DEFAULT 0, 
                      hash_rate INTEGER DEFAULT 2, 
                      farm_active BOOLEAN DEFAULT FALSE, 
                      last_farm TIMESTAMP,
                      wallet_address TEXT)''')
        # Create missions table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS missions
                     (user_id TEXT, 
                      mission_type TEXT, 
                      completed BOOLEAN DEFAULT FALSE,
                      PRIMARY KEY (user_id, mission_type))''')
        conn.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        if conn:
            db_pool.putconn(conn)

# Call init_db when the app starts
init_db()

@app.route('/api/register', methods=['POST'])
def register_user():
    if not db_pool:
        return jsonify({"status": "error", "message": "Database connection not available"}), 500
    
    conn = None
    try:
        conn = db_pool.getconn()
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        c = conn.cursor()
        # Check if user already exists
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        if user:
            conn.commit()
            return jsonify({"status": "success", "message": "User already registered"})
        
        # Register new user
        c.execute("INSERT INTO users (user_id, balance, hash_rate, farm_active) VALUES (%s, %s, %s, %s)",
                  (user_id, 0, 2, False))
        conn.commit()
        return jsonify({"status": "success", "message": "User registered successfully"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route('/api/user', methods=['GET'])
def get_user():
    if not db_pool:
        return jsonify({"status": "error", "message": "Database connection not available"}), 500
    
    conn = None
    try:
        conn = db_pool.getconn()
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            # If user not found, register them
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
        
        return jsonify({
            "status": "success",
            "user": {
                "user_id": user[0],
                "balance": user[1],
                "hash_rate": user[2],
                "farm_active": user[3],
                "wallet_address": user[5] if user[5] else "Not linked",
                "ton": user[1] * 0.0000001  # Calculate TON on the backend
            }
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route('/api/claim', methods=['POST'])
def claim():
    if not db_pool:
        return jsonify({"status": "error", "message": "Database connection not available"}), 500
    
    conn = None
    try:
        conn = db_pool.getconn()
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        if not user[3]:  # farm_active
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
            return jsonify({"status": "success", "message": f"Claimed {balance_increase} SS Points"})
        else:
            return jsonify({"status": "error", "message": "No farming data available"}), 400
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route('/api/farm', methods=['POST'])
def farm():
    if not db_pool:
        return jsonify({"status": "error", "message": "Database connection not available"}), 500
    
    conn = None
    try:
        conn = db_pool.getconn()
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        if user[3]:  # farm_active
            return jsonify({"status": "error", "message": "Farming is already active"}), 400
        
        # Start farming
        now = datetime.utcnow()
        c.execute("UPDATE users SET farm_active = %s, last_farm = %s WHERE user_id = %s",
                  (True, now, user_id))
        conn.commit()
        return jsonify({"status": "success", "message": "Farming started"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route('/api/boost', methods=['POST'])
def boost():
    if not db_pool:
        return jsonify({"status": "error", "message": "Database connection not available"}), 500
    
    conn = None
    try:
        conn = db_pool.getconn()
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        # Increase hash_rate (e.g., +1 GH/s per boost)
        new_hash_rate = user[2] + 1
        c.execute("UPDATE users SET hash_rate = %s WHERE user_id = %s", (new_hash_rate, user_id))
        conn.commit()
        return jsonify({"status": "success", "message": f"Hash rate boosted to {new_hash_rate} GH/s"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route('/api/update_wallet', methods=['POST'])
def update_wallet():
    if not db_pool:
        return jsonify({"status": "error", "message": "Database connection not available"}), 500
    
    conn = None
    try:
        conn = db_pool.getconn()
        data = request.get_json()
        user_id = str(data.get('user_id'))
        wallet_address = data.get('wallet_address')
        if not user_id or not wallet_address:
            return jsonify({"status": "error", "message": "user_id and wallet_address are required"}), 400
        
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        c.execute("UPDATE users SET wallet_address = %s WHERE user_id = %s", (wallet_address, user_id))
        conn.commit()
        return jsonify({"status": "success", "message": "Wallet address updated", "wallet_address": wallet_address})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route('/api/referral', methods=['GET'])
def get_referral():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        referral_link = f"https://t.me/SS_FarmingBot?start={user_id}"
        return jsonify({"status": "success", "referral_link": referral_link})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/missions', methods=['GET'])
def get_missions():
    if not db_pool:
        return jsonify({"status": "error", "message": "Database connection not available"}), 500
    
    conn = None
    try:
        conn = db_pool.getconn()
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        c = conn.cursor()
        c.execute("SELECT mission_type, completed FROM missions WHERE user_id = %s", (user_id,))
        completed_missions = c.fetchall()
        completed_mission_types = [m[0] for m in completed_missions if m[1]]
        
        missions = [
            {"name": "Join Channel", "mission_type": "join_channel", "reward": 500, "link": "https://t.me/ss_farming_channel"}
        ]
        
        mission_data = []
        for mission in missions:
            mission_data.append({
                "name": mission["name"],
                "reward": mission["reward"],
                "link": mission["link"],
                "status": "Completed" if mission["mission_type"] in completed_mission_types else "Not Completed"
            })
        
        return jsonify({"status": "success", "missions": mission_data})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route('/api/complete_mission', methods=['POST'])
def complete_mission():
    if not db_pool:
        return jsonify({"status": "error", "message": "Database connection not available"}), 500
    
    conn = None
    try:
        conn = db_pool.getconn()
        data = request.get_json()
        user_id = str(data.get('user_id'))
        mission_type = data.get('mission_type')
        if not user_id or not mission_type:
            return jsonify({"status": "error", "message": "user_id and mission_type are required"}), 400
        
        c = conn.cursor()
        # Check if mission is already completed
        c.execute("SELECT completed FROM missions WHERE user_id = %s AND mission_type = %s", (user_id, mission_type))
        mission = c.fetchone()
        if mission and mission[0]:
            return jsonify({"status": "error", "message": "Mission already completed"}), 400
        
        # Mark mission as completed
        c.execute("INSERT INTO missions (user_id, mission_type, completed) VALUES (%s, %s, %s) ON CONFLICT (user_id, mission_type) DO UPDATE SET completed = %s",
                  (user_id, mission_type, True, True))
        
        # Add reward to user's balance
        reward = 500 if mission_type == "join_channel" else 0
        c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (reward, user_id))
        conn.commit()
        return jsonify({"status": "success", "message": f"Mission completed! You earned {reward} SS Points"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route('/')
def home():
    return jsonify({"status": "success", "message": "Welcome to SS Farming Backend"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
