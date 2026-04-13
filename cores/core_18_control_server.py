from flask import Flask, jsonify, request
import os
import json
import secrets

TRUSTED_DEVICE_PATH = "data/trusted_device.json"


def start_control_server(core18, port=5001):
    app = Flask("zephyr_control_server")

    # =========================
    # DEVICE STORAGE
    # =========================
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

    # =========================
    # VERIFY REQUEST
    # =========================
    def verify_request(req):
        device = load_device()

        # ✅ LOCAL MODE (no device paired yet)
        if not device:
            return True

        try:
            data = req.get_json(force=True)
        except:
            # allow simple POST (from cloud client)
            return True

        return (
            data.get("device_id") == device.get("device_id") and
            data.get("secret_key") == device.get("secret_key")
        )

    # =========================
    # HEALTH CHECK
    # =========================
    @app.route("/", methods=["GET"])
    def home():
        return jsonify({"status": "Local Control Server Running 🚀"})

    # =========================
    # PAIRING
    # =========================
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

    # =========================
    # TEST (🔥 IMPORTANT)
    # =========================
    @app.route("/test", methods=["POST"])
    def test():
        print("🔥 TEST COMMAND RECEIVED FROM CLOUD")
        return jsonify({"status": "test success"})

    # =========================
    # LOCK
    # =========================
    @app.route("/lock", methods=["POST"])
    def lock():
        print("[Control] 🔒 Lock command received")

        if not verify_request(request):
            return jsonify({"error": "unauthorized"}), 401

        core18.lock()
        return jsonify({"status": "locked"})

    # =========================
    # UNLOCK
    # =========================
    @app.route("/unlock", methods=["POST"])
    def unlock():
        print("[Control] 🔓 Unlock command received")

        if not verify_request(request):
            return jsonify({"error": "unauthorized"}), 401

        core18.unlock()
        return jsonify({"status": "unlocked"})

    # =========================
    # STATUS
    # =========================
    @app.route("/status", methods=["GET"])
    def status():
        return jsonify({"state": core18.security_state.value})

    # =========================
    # START SERVER
    # =========================
    print(f"[Control] 🚀 Server running on port {port}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )