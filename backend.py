import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# File path to store user data in Render's filesystem
DATA_FILE = "users.json"  # Render's filesystem မှာ သိမ်းမယ်

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
        "link": "https://t.me/SS_Communitys",  # Replace with your actual channel link
        "reward": 100,  # SS Points reward for completing the mission
        "status": "Not Completed"
    },
    {
        "mission_type": "invite_friend",
        "name": "Invite a Friend",
        "link": "",  # Will be set dynamically via referral link
        "reward": 50,  # SS Points reward for completing the mission
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
            "hash_rate": 2,
            "farm_active": False,
            "last_farm": None,
            "wallet_address": None,
            "referrer_id": referrer_id,
            "missions": {mission["mission_type"]: "Not Completed" for mission in MISSIONS}
        }
        
        # If there's a referrer, give them a reward
        if referrer_id and referrer_id in users:
            users[referrer_id]["balance"] += 50  # Reward for inviting a friend
            # Update the "invite_friend" mission for the referrer
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
            # If user not found, register them
            users[user_id] = {
                "user_id": user_id,
                "balance": 0,
                "hash_rate": 2,
                "farm_active": False,
                "last_farm": None,
                "wallet_address": None,
                "referrer_id": None,
                "missions": {mission["mission_type"]: "Not Completed" for mission in MISSIONS}
            }
            save_users(users)
        
        user = users[user_id]
        # Calculate balance increase if farm is active
        if user["farm_active"] and user["last_farm"]:
            last_farm = datetime.fromisoformat(user["last_farm"])
            now = datetime.utcnow()
            seconds_passed = (now - last_farm).total_seconds()
            balance_increase = int(seconds_passed * user["hash_rate"] / 3600)  # hash_rate per hour
            user["balance"] += balance_increase
            user["last_farm"] = now.isoformat()
            save_users(users)
        
        return jsonify({
            "status": "success",
            "user": {
                "user_id": user["user_id"],
                "balance": user["balance"],
                "hash_rate": user["hash_rate"],
                "farm_active": user["farm_active"],
                "wallet_address": user["wallet_address"] if user["wallet_address"] else "Not linked",
                "ton": user["balance"] * 0.0000001  # Calculate TON on the backend
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
            balance_increase = int(seconds_passed * user["hash_rate"] / 3600)  # hash_rate per hour
            user["balance"] += balance_increase
            user["farm_active"] = False
            user["last_farm"] = None
            save_users(users)
            return jsonify({"status": "success", "message": f"Claimed {balance_increase} SS Points"})
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
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        if user_id not in users:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        user = users[user_id]
        # Increase hash_rate (e.g., +1 GH/s per boost)
        user["hash_rate"] += 1
        save_users(users)
        return jsonify({"status": "success", "message": f"Hash rate boosted to {user['hash_rate']} GH/s"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

# New endpoint for updating wallet address
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

# New endpoint for referral link
@app.route('/api/referral', methods=['GET'])
def get_referral():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "user_id is required"}), 400
        
        # Replace with your bot's Telegram link
        referral_link = f"https://t.me/SS_FarmingBot?start={user_id}"
        return jsonify({"status": "success", "referral_link": referral_link})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

# New endpoint for missions
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
            # Dynamically set the referral link for the "invite_friend" mission
            if mission_type == "invite_friend":
                mission["link"] = f"https://t.me/SS_FarmingBot?start={user_id}"
        
        return jsonify({"status": "success", "missions": missions})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

# New endpoint for completing a mission
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
        
        # Mark mission as completed and give reward
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
    port = int(os.getenv("PORT", 5000))  # Render မှာ PORT environment variable ကို သုံးမယ်
    app.run(host='0.0.0.0', port=port)
