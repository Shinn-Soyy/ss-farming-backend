import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# File path to store user data in Render's filesystem
DATA_FILE = "users.json"

# Telegram Bot Token and Channel ID
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace with your Telegram Bot Token
TELEGRAM_CHANNEL_ID = "@your_channel"  # Replace with your Telegram channel username (e.g., @your_channel)

# Hash Rate Configurations
HASH_RATE_CONFIG = {
    1: {"points_per_hour": 50, "daily_farm_hours": 3},
    2: {"points_per_hour": 100, "daily_farm_hours": 4},
    3: {"points_per_hour": 200, "daily_farm_hours": 5},
    4: {"points_per_hour": 300, "daily_farm_hours": 6},
    5: {"points_per_hour": 500, "daily_farm_hours": 8},
    6: {"points_per_hour": 700, "daily_farm_hours": 7},
    7: {"points_per_hour": 900, "daily_farm_hours": 8},
    8: {"points_per_hour": 1200, "daily_farm_hours": 9},
    9: {"points_per_hour": 1500, "daily_farm_hours": 10},
    10: {"points_per_hour": 2000, "daily_farm_hours": 10}
}

# Boost Costs
BOOST_COSTS = {
    2: {"ss_points": 1000, "ton": 0},
    3: {"ss_points": 2000, "ton": 0},
    4: {"ss_points": 3000, "ton": 0},
    5: {"ss_points": 6000, "ton": 0.5},
    6: {"ss_points": 8000, "ton": 1},
    7: {"ss_points": 10000, "ton": 2},
    8: {"ss_points": 12000, "ton": 2.5},
    9: {"ss_points": 15000, "ton": 3.2},
    10: {"ss_points": 20000, "ton": 4}
}

# TON to SS Points conversion rate
TON_TO_SS_POINTS = 10000  # 1 TON = 10000 SS Points

# Initialize the data file if it doesn't exist
def init_data_file():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)

# Load user data from file
def load_users():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

# Save user data to file
def save_users(users):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        print(f"Error saving users: {e}")

# Initialize the data file
init_data_file()

# Missions data (hardcoded for now)
MISSIONS = [
    {
        "mission_type": "join_channel",
        "name": "Join Our Telegram Channel",
        "link": f"https://t.me/{TELEGRAM_CHANNEL_ID[1:]}",
        "reward": 50,
        "status": "Not Completed"
    },
    {
        "mission_type": "invite_friend",
        "name": "Invite a Friend",
        "link": "",
        "reward": 100,
        "status": "Not Completed"
    }
]

@app.route('/api/register', methods=['POST'])
def register_user():
    users = load_users()
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        referrer_id = str(data.get('referrer_id')) if data.get('referrer_id') else None
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        if user_id in users:
            return jsonify({"status": "success", "message": "User already registered"})
        
        # Register new user
        users[user_id] = {
            "user_id": user_id,
            "balance": 0,
            "hash_rate": 1,  # Start with 1 GH/s
            "farm_active": False,
            "last_farm": None,
            "daily_farm_duration": 0,  # Track daily farming duration in seconds
            "last_reset": datetime.utcnow().isoformat(),  # Track last reset time
            "wallet_address": None,
            "referrer_id": referrer_id,
            "missions": {mission["mission_type"]: "Not Completed" for mission in MISSIONS}
        }
        
        # If there's a referrer, give them a reward
        if referrer_id and referrer_id in users:
            users[referrer_id]["balance"] += 50
            if "invite_friend" in users[referrer_id]["missions"]:
                users[referrer_id]["missions"]["invite_friend"] = "Completed"
        
        save_users(users)
        return jsonify({"status": "success", "message": "User registered successfully"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/user', methods=['GET'])
def get_user():
    users = load_users()
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        if user_id not in users:
            users[user_id] = {
                "user_id": user_id,
                "balance": 0,
                "hash_rate": 1,
                "farm_active": False,
                "last_farm": None,
                "daily_farm_duration": 0,
                "last_reset": datetime.utcnow().isoformat(),
                "wallet_address": None,
                "referrer_id": None,
                "missions": {mission["mission_type"]: "Not Completed" for mission in MISSIONS}
            }
            save_users(users)
        
        user = users[user_id]
        # Reset daily farm duration if 24 hours have passed
        last_reset = datetime.fromisoformat(user["last_reset"])
        now = datetime.utcnow()
        if (now - last_reset).total_seconds() >= 24 * 3600:
            user["daily_farm_duration"] = 0
            user["last_reset"] = now.isoformat()
        
        # Calculate balance increase if farm is active
        if user["farm_active"] and user["last_farm"]:
            last_farm = datetime.fromisoformat(user["last_farm"])
            seconds_passed = (now - last_farm).total_seconds()
            
            # Check daily farm limit
            hash_rate = int(user["hash_rate"])
            daily_farm_limit = HASH_RATE_CONFIG[hash_rate]["daily_farm_hours"] * 3600  # Convert hours to seconds
            new_duration = user["daily_farm_duration"] + seconds_passed
            
            if new_duration <= daily_farm_limit:
                points_per_hour = HASH_RATE_CONFIG[hash_rate]["points_per_hour"]
                balance_increase = seconds_passed * points_per_hour / 3600  # Points per second
                user["balance"] += balance_increase
                user["daily_farm_duration"] = new_duration
            else:
                # Limit exceeded, stop farming
                user["farm_active"] = False
                user["last_farm"] = None
                save_users(users)
                return jsonify({"status": "error", "message": "Daily farming limit reached"})
            
            user["last_farm"] = now.isoformat()
            save_users(users)
        
        return jsonify({
            "status": "success",
            "user": {
                "user_id": user["user_id"],
                "balance": user["balance"],
                "hash_rate": user["hash_rate"],
                "farm_active": user["farm_active"],
                "daily_farm_duration": user["daily_farm_duration"],
                "daily_farm_limit": HASH_RATE_CONFIG[int(user["hash_rate"])]["daily_farm_hours"] * 3600,
                "wallet_address": user["wallet_address"] if user["wallet_address"] else "Not linked"
            }
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/claim', methods=['POST'])
def claim():
    users = load_users()
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        if user_id not in users:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        user = users[user_id]
        if not user["farm_active"]:
            return jsonify({"status": "error", "message": "Farming is not active"}), 400
        
        # Stop farming and update balance
        if user["last_farm"]:
            last_farm = datetime.fromisoformat(user["last_farm"])
            now = datetime.utcnow()
            seconds_passed = (now - last_farm).total_seconds()
            
            # Check daily farm limit
            hash_rate = int(user["hash_rate"])
            daily_farm_limit = HASH_RATE_CONFIG[hash_rate]["daily_farm_hours"] * 3600
            new_duration = user["daily_farm_duration"] + seconds_passed
            
            if new_duration <= daily_farm_limit:
                points_per_hour = HASH_RATE_CONFIG[hash_rate]["points_per_hour"]
                balance_increase = seconds_passed * points_per_hour / 3600
                user["balance"] += balance_increase
                user["daily_farm_duration"] = new_duration
            else:
                user["farm_active"] = False
                user["last_farm"] = None
                save_users(users)
                return jsonify({"status": "error", "message": "Daily farming limit reached"})
            
            user["farm_active"] = False
            user["last_farm"] = None
            save_users(users)
            return jsonify({"status": "success", "message": f"Claimed {balance_increase:.2f} SS Points"})
        else:
            return jsonify({"status": "error", "message": "No farming data available"}), 400
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/farm', methods=['POST'])
def farm():
    users = load_users()
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        if user_id not in users:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        user = users[user_id]
        if user["farm_active"]:
            return jsonify({"status": "error", "message": "Farming is already active"}), 400
        
        # Check daily farm limit
        hash_rate = int(user["hash_rate"])
        daily_farm_limit = HASH_RATE_CONFIG[hash_rate]["daily_farm_hours"] * 3600
        if user["daily_farm_duration"] >= daily_farm_limit:
            return jsonify({"status": "error", "message": "Daily farming limit reached"}), 400
        
        # Start farming
        user["farm_active"] = True
        user["last_farm"] = datetime.utcnow().isoformat()
        save_users(users)
        return jsonify({"status": "success", "message": "Farming started"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/boost', methods=['POST'])
def boost():
    users = load_users()
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        payment_method = data.get('payment_method')  # "ss_points" or "ton"
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        if not payment_method:
            return jsonify({"status": "error", "message": "payment_method is required"}), 400
        
        if user_id not in users:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        user = users[user_id]
        current_hash_rate = int(user["hash_rate"])
        if current_hash_rate >= 10:
            return jsonify({"status": "error", "message": "Maximum hash rate reached (10 GH/s)"}), 400
        
        next_hash_rate = current_hash_rate + 1
        if next_hash_rate not in BOOST_COSTS:
            return jsonify({"status": "error", "message": "Invalid hash rate upgrade"}), 400
        
        # Check boost cost
        cost = BOOST_COSTS[next_hash_rate]
        if payment_method == "ss_points":
            if user["balance"] < cost["ss_points"]:
                return jsonify({"status": "error", "message": f"Insufficient SS Points. Need {cost['ss_points']} SS Points"}), 400
            user["balance"] -= cost["ss_points"]
        elif payment_method == "ton":
            if cost["ton"] == 0:
                return jsonify({"status": "error", "message": "TON payment not available for this upgrade"}), 400
            # Convert TON to SS Points for simplicity
            ton_cost_in_ss_points = cost["ton"] * TON_TO_SS_POINTS
            if user["balance"] < ton_cost_in_ss_points:
                return jsonify({"status": "error", "message": f"Insufficient balance. Need {cost['ton']} TON (equivalent to {ton_cost_in_ss_points} SS Points)"}), 400
            user["balance"] -= ton_cost_in_ss_points
        else:
            return jsonify({"status": "error", "message": "Invalid payment method"}), 400
        
        # Upgrade hash rate
        user["hash_rate"] = next_hash_rate
        save_users(users)
        return jsonify({"status": "success", "message": f"Hash rate boosted to {user['hash_rate']} GH/s"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/update_wallet', methods=['POST'])
def update_wallet():
    users = load_users()
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        wallet_address = data.get('wallet_address')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        if not wallet_address:
            return jsonify({"status": "error", "message": "wallet_address is required"}), 400
        
        if user_id not in users:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        user = users[user_id]
        user["wallet_address"] = wallet_address
        save_users(users)
        return jsonify({"status": "success", "message": "Wallet address updated", "wallet_address": wallet_address})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

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
    users = load_users()
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        if user_id not in users:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        user = users[user_id]
        missions = MISSIONS.copy()
        for mission in missions:
            mission_type = mission["mission_type"]
            mission["status"] = user["missions"].get(mission_type, "Not Completed")
            if mission_type == "invite_friend":
                mission["link"] = f"https://t.me/SS_FarmingBot?start={user_id}"
        
        return jsonify({"status": "success", "missions": missions})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/check_membership', methods=['GET'])
def check_membership():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
        params = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "user_id": user_id
        }
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("ok") and data.get("result"):
            status = data["result"]["status"]
            if status in ["member", "administrator", "creator"]:
                return jsonify({"status": "success", "is_member": True})
            else:
                return jsonify({"status": "success", "is_member": False})
        else:
            return jsonify({"status": "error", "message": "Failed to check membership"}), 500
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/api/complete_mission', methods=['POST'])
def complete_mission():
    users = load_users()
    try:
        data = request.get_json()
        user_id = str(data.get('user_id'))
        mission_type = data.get('mission_type')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        if not mission_type:
            return jsonify({"status": "error", "message": "mission_type is required"}), 400
        
        if user_id not in users:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        user = users[user_id]
        if mission_type not in user["missions"]:
            return jsonify({"status": "error", "message": "Mission not found"}), 404
        
        if user["missions"][mission_type] == "Completed":
            return jsonify({"status": "error", "message": "Mission already completed"}), 400
        
        if mission_type == "join_channel":
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
            params = {
                "chat_id": TELEGRAM_CHANNEL_ID,
                "user_id": user_id
            }
            response = requests.get(url, params=params)
            data = response.json()
            
            if not (data.get("ok") and data.get("result")):
                return jsonify({"status": "error", "message": "Please join the Telegram channel to complete this mission"}), 400
            
            status = data["result"]["status"]
            if status not in ["member", "administrator", "creator"]:
                return jsonify({"status": "error", "message": "Please join the Telegram channel to complete this mission"}), 400
        
        user["missions"][mission_type] = "Completed"
        mission = next((m for m in MISSIONS if m["mission_type"] == mission_type), None)
        if mission:
            user["balance"] += mission["reward"]
            save_users(users)
            return jsonify({"status": "success", "message": f"Mission completed! You earned {mission['reward']} SS Points"})
        else:
            return jsonify({"status": "error", "message": "Mission not found"}), 404
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/')
def home():
    return jsonify({"status": "success", "message": "Welcome to SS Farming Backend"})

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
