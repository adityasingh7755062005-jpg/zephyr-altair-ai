# ==============================
# FILE 1: core_18_control_server.py
# ==============================

from flask import Flask, jsonify, request
import os
import json
import secrets
import time
import hashlib

# 🔐 Path to trusted device file
TRUSTED_DEVICE_PATH = "data/trusted_device.json"

# ⏱️ Max allowed timestamp difference (5 minutes)
MAX_TIME_DIFF = 300


def start_control_server(core18, port=5001):
    app = Flask("zephyr_control_server")

    # ==============================
    # LOAD TRUSTED DEVICE
    # ==============================
    def load_device():
        try:
            if not os.path.exists(TRUSTED_DEVICE_PATH):
                return None
            with open(TRUSTED_DEVICE_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            print("[Control] Load device error:", e)
            return None

    # ==============================
    # SAVE TRUSTED DEVICE
    # ==============================
    def save_device(data):
        os.makedirs("data", exist_ok=True)
        with open(TRUSTED_DEVICE_PATH, "w") as f:
            json.dump(data, f, indent=4)

    # ==============================
    # TOKEN GENERATOR (SECURITY)
    # ==============================
    def generate_token(device_id, secret_key, action, timestamp):
        raw = f"{device_id}{secret_key}{timestamp}{action}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ==============================
    # VERIFY REQUEST SECURITY
    # ==============================
    def verify_request(req):
        device = load_device()

        # If no device paired → allow
        if not device:
            return True

        try:
            data = req.get_json(force=True)
        except:
            return False

        device_id = data.get("device_id")
        timestamp = data.get("timestamp")
        token = data.get("token")
        action = req.path.replace("/", "")

        if not all([device_id, timestamp, token]):
            return False

        try:
            timestamp = int(timestamp)
        except:
            return False

        # ⏱️ Check timestamp freshness
        if abs(int(time.time()) - timestamp) > MAX_TIME_DIFF:
            return False

        expected = generate_token(
            device["device_id"],
            device["secret_key"],
            action,
            timestamp
        )

        return token == expected

    # ==============================
    # ROUTES
    # ==============================

    @app.route("/", methods=["GET"])
    def home():
        return jsonify({"status": "Local Control Server Running"})

    @app.route("/pair", methods=["POST"])
    def pair():
        data = request.get_json(force=True)

        device_id = data.get("device_id")
        device_name = data.get("device_name", "Unknown")

        secret_key = secrets.token_hex(16)

        save_device({
            "device_name": device_name,
            "device_id": device_id,
            "secret_key": secret_key
        })

        return jsonify({
            "status": "paired",
            "secret_key": secret_key
        })

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

    @app.route("/status", methods=["GET"])
    def status():
        return jsonify({"state": core18.security_state.value})

    print(f"[Control] Running on {port}")
    app.run(host="0.0.0.0", port=port, debug=False)