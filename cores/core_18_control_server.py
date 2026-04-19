from flask import Flask, jsonify, request
import os
import json
import secrets
import time
import hashlib

TRUSTED_DEVICE_PATH = "data/trusted_device.json"

# 🔥 FIX: Increased tolerance (was 10)
MAX_TIME_DIFF = 300  # 5 minutes


def start_control_server(core18, port=5001):
    app = Flask("zephyr_control_server")

    def load_device():
        try:
            if not os.path.exists(TRUSTED_DEVICE_PATH):
                return None
            with open(TRUSTED_DEVICE_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            print("[Control] Load device error:", e)
            return None

    def save_device(data):
        os.makedirs("data", exist_ok=True)
        with open(TRUSTED_DEVICE_PATH, "w") as f:
            json.dump(data, f, indent=4)

    def generate_token(device_id, secret_key, action, timestamp):
        raw = f"{device_id}{secret_key}{timestamp}{action}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def verify_request(req):
        device = load_device()

        if not device:
            return True

        try:
            data = req.get_json(force=True)
        except:
            return True

        device_id = data.get("device_id")
        timestamp = data.get("timestamp")
        token = data.get("token")
        action = req.path.replace("/", "")

        if not all([device_id, timestamp, token]):
            print("❌ Missing security data")
            return False

        try:
            timestamp = int(timestamp)
        except:
            print("❌ Invalid timestamp")
            return False

        if abs(int(time.time()) - timestamp) > MAX_TIME_DIFF:
            print("❌ Expired request")
            return False

        expected = generate_token(device["device_id"], device["secret_key"], action, timestamp)

        if token != expected:
            print("❌ Invalid token (possible hacker)")
            return False

        print("✅ Request verified")
        return True

    @app.route("/", methods=["GET"])
    def home():
        return jsonify({"status": "Local Control Server Running 🚀"})

    @app.route("/pair", methods=["POST"])
    def pair():
        data = request.get_json(force=True)

        device_id = data.get("device_id")
        device_name = data.get("device_name", "Unknown Device")

        secret_key = secrets.token_hex(16)

        save_device({
            "device_name": device_name,
            "device_id": device_id,
            "secret_key": secret_key
        })

        print(f"[Control] 🔗 Paired with {device_name}")

        return jsonify({
            "status": "paired",
            "secret_key": secret_key
        })

    @app.route("/test", methods=["POST"])
    def test():
        print("🔥 TEST COMMAND RECEIVED FROM CLOUD")
        return jsonify({"status": "test success"})

    @app.route("/lock", methods=["POST"])
    def lock():
        print("[Control] 🔒 Lock command received")

        if not verify_request(request):
            return jsonify({"error": "unauthorized"}), 401

        core18.lock()
        return jsonify({"status": "locked"})

    @app.route("/unlock", methods=["POST"])
    def unlock():
        print("[Control] 🔓 Unlock command received")

        if not verify_request(request):
            return jsonify({"error": "unauthorized"}), 401

        core18.unlock()
        return jsonify({"status": "unlocked"})

    @app.route("/status", methods=["GET"])
    def status():
        return jsonify({"state": core18.security_state.value})

    print(f"[Control] 🚀 Server running on port {port}")

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)