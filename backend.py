# backend.py
from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect("ss_farming.db", timeout=10)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY, balance INTEGER, farm_end TIMESTAMP, hash_rate INTEGER, wallet_address TEXT, completed_missions TEXT)''')
    conn.commit()
    conn.close()

# Constants
FARM_DURATION_HOURS = 3
POINTS_PER_HOUR = 10
BASE_HASH_RATE = 2
POINTS_TO_TON_RATIO = 0.0000001
MISSION_REWARD = 50
CHANNEL_LINK = "https://t.me/SS_Airdrop_Channel"

# Helper function
def generate_referral_link(user_id):
    return f"https://t.me/SS_FarmingBot?start={user_id}"

# API Endpoints
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    user_id = str(data['user_id'])

    conn = sqlite3.connect("ss_farming.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if not result:
        c.execute("INSERT INTO users (user_id, balance, farm_end, hash_rate, wallet_address, completed_missions) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, 0, None, BASE_HASH_RATE, "", ""))
        conn.commit()

    conn.close()
    return jsonify({"status": "success", "message": "User registered"})

@app.route('/api/user', methods=['GET'])
def get_user():
    user_id = request.args.get('user_id')
    conn = sqlite3.connect("ss_farming.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT balance, farm_end, hash_rate, wallet_address FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        return jsonify({"status": "error", "message": "User not found"}), 404

    balance, farm_end, hash_rate, wallet_address = result
    farm_active = False
    time_left = 0

    if farm_end:
        farm_end_time = datetime.strptime(farm_end, '%Y-%m-%d %H:%M:%S')
        if datetime.utcnow() < farm_end_time:
            farm_active = True
            time_left = (farm_end_time - datetime.utcnow()).total_seconds()

    return jsonify({
        "status": "success",
        "balance": balance,
        "farm_active": farm_active,
        "time_left": time_left,
        "hash_rate": hash_rate,
        "wallet_address": wallet_address,
        "ton": balance * POINTS_TO_TON_RATIO
    })

@app.route('/api/farm', methods=['POST'])
def farm():
    data = request.get_json()
    user_id = str(data['user_id'])

    conn = sqlite3.connect("ss_farming.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT farm_end FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if not result:
        conn.close()
        return jsonify({"status": "error", "message": "User not found"}), 404

    farm_end = result[0]
    if farm_end:
        farm_end_time = datetime.strptime(farm_end, '%Y-%m-%d %H:%M:%S')
        if datetime.utcnow() < farm_end_time:
            time_left = (farm_end_time - datetime.utcnow()).total_seconds()
            hours, remainder = divmod(int(time_left), 3600)
            minutes, seconds = divmod(remainder, 60)
            conn.close()
            return jsonify({
                "status": "error",
                "message": f"Farming in progress. Time left: {hours}h {minutes}m {seconds}s"
            })

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=FARM_DURATION_HOURS)
    c.execute("UPDATE users SET farm_end = ? WHERE user_id = ?",
              (end_time.strftime('%Y-%m-%d %H:%M:%S'), user_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Farming started"})

@app.route('/api/claim', methods=['POST'])
def claim():
    data = request.get_json()
    user_id = str(data['user_id'])

    conn = sqlite3.connect("ss_farming.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT balance, farm_end FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if not result:
        conn.close()
        return jsonify({"status": "error", "message": "User not found"}), 404

    balance, farm_end = result
    if not farm_end:
        conn.close()
        return jsonify({"status": "error", "message": "No farming in progress"})

    farm_end_time = datetime.strptime(farm_end, '%Y-%m-%d %H:%M:%S')
    if datetime.utcnow() < farm_end_time:
        time_left = (farm_end_time - datetime.utcnow()).total_seconds()
        hours, remainder = divmod(int(time_left), 3600)
        minutes, seconds = divmod(remainder, 60)
        conn.close()
        return jsonify({
            "status": "error",
            "message": f"Farming not complete. Time left: {hours}h {minutes}m {seconds}s"
        })

    hours_farmed = FARM_DURATION_HOURS
    points_earned = hours_farmed * POINTS_PER_HOUR
    new_balance = balance + points_earned

    c.execute("UPDATE users SET balance = ?, farm_end = ? WHERE user_id = ?",
              (new_balance, None, user_id))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": f"Claimed {points_earned} SS Points",
        "new_balance": new_balance
    })

@app.route('/api/boost', methods=['POST'])
def boost():
    data = request.get_json()
    user_id = str(data['user_id'])

    conn = sqlite3.connect("ss_farming.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT hash_rate FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if not result:
        conn.close()
        return jsonify({"status": "error", "message": "User not found"}), 404

    hash_rate = result[0]
    new_hash_rate = hash_rate + 1

    c.execute("UPDATE users SET hash_rate = ? WHERE user_id = ?",
              (new_hash_rate, user_id))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": "Hash rate boosted",
        "new_hash_rate": new_hash_rate
    })

@app.route('/api/update_wallet', methods=['POST'])
def update_wallet():
    data = request.get_json()
    user_id = str(data['user_id'])
    wallet_address = data['wallet_address']

    if len(wallet_address) != 48:
        return jsonify({"status": "error", "message": "Invalid wallet address (must be 48 characters)"}), 400

    conn = sqlite3.connect("ss_farming.db", timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET wallet_address = ? WHERE user_id = ?",
              (wallet_address, user_id))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": "Wallet address updated",
        "wallet_address": wallet_address
    })

@app.route('/api/referral', methods=['GET'])
def referral():
    user_id = request.args.get('user_id')
    referral_link = generate_referral_link(user_id)
    return jsonify({
        "status": "success",
        "referral_link": referral_link
    })

@app.route('/api/missions', methods=['GET'])
def missions():
    user_id = request.args.get('user_id')
    conn = sqlite3.connect("ss_farming.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT completed_missions FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        return jsonify({"status": "error", "message": "User not found"}), 404

    completed_missions = result[0] if result[0] else ""
    completed_missions_list = completed_missions.split(",") if completed_missions else []

    missions = []
    if "join_channel" not in completed_missions_list:
        missions.append({
            "name": "Join Channel",
            "reward": MISSION_REWARD,
            "link": CHANNEL_LINK,
            "status": "Not Completed"
        })
    else:
        missions.append({
            "name": "Join Channel",
            "status": "Completed"
        })

    return jsonify({"status": "success", "missions": missions})

@app.route('/api/complete_mission', methods=['POST'])
def complete_mission():
    data = request.get_json()
    user_id = str(data['user_id'])
    mission_type = data['mission_type']

    conn = sqlite3.connect("ss_farming.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT completed_missions, balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if not result:
        conn.close()
        return jsonify({"status": "error", "message": "User not found"}), 404

    completed_missions, balance = result
    completed_missions_list = completed_missions.split(",") if completed_missions else []

    if mission_type == "join_channel":
        if "join_channel" in completed_missions_list:
            conn.close()
            return jsonify({"status": "error", "message": "Mission already completed"})
        completed_missions_list.append("join_channel")
        new_balance = balance + MISSION_REWARD
    else:
        conn.close()
        return jsonify({"status": "error", "message": "Invalid mission type"}), 400

    new_completed_missions = ",".join(completed_missions_list)
    c.execute("UPDATE users SET completed_missions = ?, balance = ? WHERE user_id = ?",
              (new_completed_missions, new_balance, user_id))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": f"Mission completed. Earned {MISSION_REWARD} SS Points",
        "new_balance": new_balance
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)