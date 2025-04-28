const express = require('express');
const mysql = require('mysql2/promise');
const cors = require('cors');
const app = express();
const port = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Database connection
const db = mysql.createPool({
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'your_username',
    password: process.env.DB_PASSWORD || 'your_password',
    database: process.env.DB_NAME || 'your_database'
});

// Test database connection
db.getConnection()
    .then(() => console.log('Connected to MySQL database'))
    .catch(err => console.error('Database connection error:', err));

// Register a new user
app.post('/api/register', async (req, res) => {
    const { user_id, referrer_id } = req.body;
    try {
        const [existingUser] = await db.query('SELECT * FROM users WHERE user_id = ?', [user_id]);
        if (existingUser.length > 0) {
            return res.json({ status: "success", message: "User already registered" });
        }

        await db.query(
            'INSERT INTO users (user_id, balance, hash_rate, daily_farm_limit, daily_farm_duration, referrer_id, is_verified) VALUES (?, 0, 1, 86400, 0, ?, FALSE)',
            [user_id, referrer_id]
        );

        if (referrer_id) {
            await db.query('UPDATE users SET balance = balance + 100 WHERE user_id = ?', [referrer_id]);
        }

        res.json({ status: "success", message: "User registered successfully" });
    } catch (error) {
        console.error('Error registering user:', error);
        res.status(500).json({ status: "error", message: "Failed to register user" });
    }
});

// Get user data
app.get('/api/user', async (req, res) => {
    const { user_id } = req.query;
    try {
        const [user] = await db.query('SELECT * FROM users WHERE user_id = ?', [user_id]);
        if (!user.length) {
            return res.status(404).json({ status: "error", message: "User not found" });
        }
        res.json({
            status: "success",
            user: {
                user_id: user[0].user_id,
                balance: user[0].balance,
                hash_rate: user[0].hash_rate,
                wallet_address: user[0].wallet_address,
                daily_farm_limit: user[0].daily_farm_limit,
                daily_farm_duration: user[0].daily_farm_duration,
                is_verified: user[0].is_verified
            }
        });
    } catch (error) {
        console.error('Error fetching user:', error);
        res.status(500).json({ status: "error", message: "Failed to fetch user data" });
    }
});

// Update wallet address
app.post('/api/update_wallet', async (req, res) => {
    const { user_id, wallet_address } = req.body;
    try {
        await db.query('UPDATE users SET wallet_address = ? WHERE user_id = ?', [wallet_address, user_id]);
        res.json({ status: "success", message: "Wallet address updated successfully" });
    } catch (error) {
        console.error('Error updating wallet address:', error);
        res.status(500).json({ status: "error", message: "Failed to update wallet address" });
    }
});

// Verify user (new endpoint)
app.post('/api/verify', async (req, res) => {
    const { user_id } = req.body;
    try {
        await db.query('UPDATE users SET is_verified = TRUE WHERE user_id = ?', [user_id]);
        res.json({ status: "success", message: "User verified successfully" });
    } catch (error) {
        console.error('Error verifying user:', error);
        res.status(500).json({ status: "error", message: "Failed to verify user" });
    }
});

// Claim points
app.post('/api/claim', async (req, res) => {
    const { user_id } = req.body;
    try {
        const [user] = await db.query('SELECT * FROM users WHERE user_id = ?', [user_id]);
        if (!user.length) {
            return res.status(404).json({ status: "error", message: "User not found" });
        }

        const hashRate = user[0].hash_rate;
        const pointsPerHour = { 1: 50, 2: 100, 3: 200, 4: 300, 5: 500, 6: 700, 7: 900, 8: 1200, 9: 1500, 10: 2000 };
        const points = pointsPerHour[hashRate] || 50;

        await db.query('UPDATE users SET balance = balance + ? WHERE user_id = ?', [points, user_id]);
        res.json({ status: "success", message: `${points} SS Points claimed successfully` });
    } catch (error) {
        console.error('Error claiming points:', error);
        res.status(500).json({ status: "error", message: "Failed to claim points" });
    }
});

// Farm points
app.post('/api/farm', async (req, res) => {
    const { user_id } = req.body;
    try {
        const [user] = await db.query('SELECT * FROM users WHERE user_id = ?', [user_id]);
        if (!user.length) {
            return res.status(404).json({ status: "error", message: "User not found" });
        }

        if (user[0].daily_farm_duration >= user[0].daily_farm_limit) {
            return res.json({ status: "error", message: "Daily farming limit reached" });
        }

        await db.query('UPDATE users SET daily_farm_duration = daily_farm_duration + 1 WHERE user_id = ?', [user_id]);
        res.json({ status: "success", message: "Farming updated" });
    } catch (error) {
        console.error('Error farming:', error);
        res.status(500).json({ status: "error", message: "Failed to update farming" });
    }
});

// Boost hash rate
app.post('/api/boost', async (req, res) => {
    const { user_id, payment_method } = req.body;
    try {
        const [user] = await db.query('SELECT * FROM users WHERE user_id = ?', [user_id]);
        if (!user.length) {
            return res.status(404).json({ status: "error", message: "User not found" });
        }

        const currentHashRate = user[0].hash_rate;
        if (currentHashRate >= 10) {
            return res.json({ status: "error", message: "Maximum hash rate reached" });
        }

        const nextHashRate = currentHashRate + 1;
        const costs = {
            2: { ss_points: 1000, ton: 0 },
            3: { ss_points: 2000, ton: 0 },
            4: { ss_points: 3000, ton: 0 },
            5: { ss_points: 6000, ton: 0.5 },
            6: { ss_points: 8000, ton: 1 },
            7: { ss_points: 10000, ton: 2 },
            8: { ss_points: 12000, ton: 2.5 },
            9: { ss_points: 1500, ton: 3.2 },
            10: { ss_points: 20000, ton: 4 }
        };

        const cost = costs[nextHashRate];
        if (!cost) {
            return res.json({ status: "error", message: "Invalid hash rate upgrade" });
        }

        if (payment_method === "ss_points") {
            if (user[0].balance < cost.ss_points) {
                return res.json({ status: "error", message: "Insufficient SS Points" });
            }
            await db.query('UPDATE users SET balance = balance - ?, hash_rate = ? WHERE user_id = ?', [cost.ss_points, nextHashRate, user_id]);
        } else {
            await db.query('UPDATE users SET hash_rate = ? WHERE user_id = ?', [nextHashRate, user_id]);
        }

        res.json({ status: "success", message: `Hash rate upgraded to ${nextHashRate} GH/s` });
    } catch (error) {
        console.error('Error boosting:', error);
        res.status(500).json({ status: "error", message: "Failed to boost hash rate" });
    }
});

// Get referral link
app.get('/api/referral', async (req, res) => {
    const { user_id } = req.query;
    try {
        const referralLink = `https://t.me/SS_Farming_Bot?start=${user_id}`;
        res.json({ status: "success", referral_link: referralLink });
    } catch (error) {
        console.error('Error generating referral link:', error);
        res.status(500).json({ status: "error", message: "Failed to generate referral link" });
    }
});

// Check membership (simplified for this example)
app.get('/api/check_membership', async (req, res) => {
    const { user_id } = req.query;
    try {
        res.json({ status: "success", is_member: true });
    } catch (error) {
        console.error('Error checking membership:', error);
        res.status(500).json({ status: "error", message: "Failed to check membership" });
    }
});

// Get missions
app.get('/api/missions', async (req, res) => {
    const { user_id } = req.query;
    try {
        const missions = [
            { name: "Join Telegram Channel", mission_type: "join_channel", reward: 500, status: "Not Completed", link: "https://t.me/SS_Farming" },
            { name: "Follow Twitter", mission_type: "follow_twitter", reward: 300, status: "Not Completed", link: "https://twitter.com/SS_Farming" }
        ];
        res.json({ status: "success", missions });
    } catch (error) {
        console.error('Error fetching missions:', error);
        res.status(500).json({ status: "error", message: "Failed to fetch missions" });
    }
});

// Complete mission
app.post('/api/complete_mission', async (req, res) => {
    const { user_id, mission_type } = req.body;
    try {
        const missionRewards = {
            "join_channel": 500,
            "follow_twitter": 300
        };
        const reward = missionRewards[mission_type] || 0;
        await db.query('UPDATE users SET balance = balance + ? WHERE user_id = ?', [reward, user_id]);
        res.json({ status: "success", message: `Mission completed! ${reward} SS Points rewarded` });
    } catch (error) {
        console.error('Error completing mission:', error);
        res.status(500).json({ status: "error", message: "Failed to complete mission" });
    }
});

// Start the server
app.listen(port, () => {
    console.log(`Server running on port ${port}`);
});