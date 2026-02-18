#!/usr/bin/env python3
"""
License activation server for Render.com.
"""
import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify

from license_utils import parse_license_key

app = Flask(__name__)
MAX_ACTIVATIONS_PER_KEY = int(os.environ.get("MAX_ACTIVATIONS_PER_KEY", "1"))
DB_PATH = os.environ.get("LICENSE_DB_PATH", "license_activations.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            client_id TEXT NOT NULL,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(license_key, client_id)
        )
    """)
    conn.commit()
    return conn


@app.route("/api/activate", methods=["POST"])
def activate():
    if not request.is_json:
        return jsonify({"success": False, "message": "Content-Type must be application/json"}), 400
    data = request.get_json() or {}
    license_key = (data.get("license_key") or "").strip()
    client_id = (data.get("client_id") or "").strip() or request.remote_addr or "unknown"
    if not license_key:
        return jsonify({"success": False, "message": "license_key is required"}), 400
    valid, expiry_ymd = parse_license_key(license_key)
    if not valid:
        return jsonify({"success": False, "message": "Invalid or unrecognized license key"}), 200
    if expiry_ymd:
        try:
            if datetime.strptime(expiry_ymd, "%Y-%m-%d").date() < datetime.now().date():
                return jsonify({"success": False, "message": "License has expired"}), 200
        except ValueError:
            return jsonify({"success": False, "message": "Invalid license"}), 200
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(DISTINCT client_id) FROM activations WHERE license_key = ?",
            (license_key,),
        )
        count = cur.fetchone()[0] or 0
        if count >= MAX_ACTIVATIONS_PER_KEY:
            try:
                cur.execute(
                    "SELECT 1 FROM activations WHERE license_key = ? AND client_id = ?",
                    (license_key, client_id),
                )
                if cur.fetchone():
                    conn.close()
                    return jsonify({
                        "success": True,
                        "expiry_date": expiry_ymd,
                        "message": "Already activated on this device",
                    }), 200
            except Exception:
                pass
            conn.close()
            return jsonify({
                "success": False,
                "message": f"License already activated on {MAX_ACTIVATIONS_PER_KEY} device(s). Contact vendor for more.",
            }), 200
        cur.execute(
            "INSERT OR REPLACE INTO activations (license_key, client_id, activated_at) VALUES (?, ?, ?)",
            (license_key, client_id, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception:
        return jsonify({"success": False, "message": "Server error"}), 500
    return jsonify({
        "success": True,
        "expiry_date": expiry_ymd,
        "message": "Activated successfully",
    }), 200


@app.route("/api/verify", methods=["POST"])
def verify():
    if not request.is_json:
        return jsonify({"success": False, "message": "Content-Type must be application/json"}), 400
    data = request.get_json() or {}
    license_key = (data.get("license_key") or "").strip()
    client_id = (data.get("client_id") or "").strip() or request.remote_addr or "unknown"
    if not license_key:
        return jsonify({"success": False, "message": "license_key is required"}), 400
    valid, expiry_ymd = parse_license_key(license_key)
    if not valid:
        return jsonify({"success": False, "message": "Invalid license key"}), 200
    if expiry_ymd and datetime.strptime(expiry_ymd, "%Y-%m-%d").date() < datetime.now().date():
        return jsonify({"success": False, "message": "License expired"}), 200
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM activations WHERE license_key = ? AND client_id = ?",
            (license_key, client_id),
        )
        found = cur.fetchone() is not None
        conn.close()
    except Exception:
        return jsonify({"success": False, "message": "Server error"}), 500
    if not found:
        return jsonify({"success": False, "message": "This device is not activated for this license"}), 200
    return jsonify({"success": True, "expiry_date": expiry_ymd}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
