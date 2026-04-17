from flask import Flask, jsonify, request
import os
import json
import secrets
import time
import hashlib

TRUSTED_DEVICE_PATH = "data/trusted_device.json"


def start_control_server(core18, port=5002):

    app = Flask("zephyr_control_server")

    def load_device():
        try:
            if not os.path.exists(TRUSTED_DEVICE_PATH):
                return None
            with open(TRUSTED_DEVICE_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            print("[Control] Load error:", e)
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
            return False

        if abs(int(time.time()) - int(timestamp)) > 10:
            return False

        expected = generate_token(device["device_id"], device["secret_key"], action, timestamp)

        return token == expected

    @app.route("/", methods=["GET"])
    def home():
        return jsonify({"status": "Control Server Running"})

    @app.route("/test", methods=["POST"])
    def test():
        print("🔥 TEST RECEIVED")
        return jsonify({"status": "ok"})

    @app.route("/lock", methods=["POST"])
    def lock():
        if not verify_request(request):
            return jsonify({"error": "unauthorized"}), 401
        core18.lock()
        return jsonify({"status": "locked"})

    @app.route("/unlock", methods=["POST"])
    def unlock():
        if not verify_request(request):
            return jsonify({"error": "unauthorized"}), 401
        core18.unlock()
        return jsonify({"status": "unlocked"})

    print(f"[Control] 🚀 Running on port {port}")

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)