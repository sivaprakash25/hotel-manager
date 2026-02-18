#!/usr/bin/env python3
"""
License activation server for Render.com.
License keys stay on server; clients get an activation_token to store and use for verification.
"""
import os
import sqlite3
import uuid
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
            activation_token TEXT UNIQUE,
            expiry_date TEXT,
            UNIQUE(license_key, client_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activation_token ON activations(activation_token)")
    for col in ("activation_token", "expiry_date"):
        try:
            conn.execute(f"ALTER TABLE activations ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
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
                    row = cur.execute(
                        "SELECT activation_token, expiry_date FROM activations WHERE license_key = ? AND client_id = ?",
                        (license_key, client_id),
                    ).fetchone()
                    tok = row[0] if row and row[0] else None
                    exp = (row[1] if row and row[1] else expiry_ymd) or expiry_ymd
                    if not tok:
                        tok = uuid.uuid4().hex
                        cur.execute(
                            "UPDATE activations SET activation_token = ?, expiry_date = ? WHERE license_key = ? AND client_id = ?",
                            (tok, exp or expiry_ymd, license_key, client_id),
                        )
                        conn.commit()
                    conn.close()
                    return jsonify({
                        "success": True,
                        "expiry_date": exp,
                        "activation_token": tok,
                        "message": "Already activated on this device",
                    }), 200
            except Exception:
                pass
            conn.close()
            return jsonify({
                "success": False,
                "message": f"License already activated on {MAX_ACTIVATIONS_PER_KEY} device(s). Contact vendor for more.",
            }), 200
        activation_token = uuid.uuid4().hex
        cur.execute(
            """INSERT OR REPLACE INTO activations
               (license_key, client_id, activated_at, activation_token, expiry_date)
               VALUES (?, ?, ?, ?, ?)""",
            (license_key, client_id, datetime.utcnow().isoformat(), activation_token, expiry_ymd),
        )
        conn.commit()
        conn.close()
    except Exception:
        return jsonify({"success": False, "message": "Server error"}), 500
    return jsonify({
        "success": True,
        "expiry_date": expiry_ymd,
        "activation_token": activation_token,
        "message": "Activated successfully",
    }), 200


@app.route("/api/verify", methods=["POST"])
def verify():
    """Verify by license_key (legacy) or by activation_token. Prefer verify_token when client has token."""
    if not request.is_json:
        return jsonify({"success": False, "message": "Content-Type must be application/json"}), 400
    data = request.get_json() or {}
    activation_token = (data.get("activation_token") or "").strip()
    if activation_token:
        return _verify_by_token(activation_token, (data.get("client_id") or "").strip() or request.remote_addr or "unknown")
    license_key = (data.get("license_key") or "").strip()
    client_id = (data.get("client_id") or "").strip() or request.remote_addr or "unknown"
    if not license_key:
        return jsonify({"success": False, "message": "license_key or activation_token is required"}), 400
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


def _verify_by_token(activation_token: str, client_id: str):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT expiry_date FROM activations WHERE activation_token = ? AND client_id = ?",
            (activation_token, client_id),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({"success": False, "message": "Invalid or unknown activation"}), 200
        expiry_ymd = row[0]
        if expiry_ymd and datetime.strptime(expiry_ymd, "%Y-%m-%d").date() < datetime.now().date():
            return jsonify({"success": False, "message": "License expired"}), 200
        return jsonify({"success": True, "expiry_date": expiry_ymd}), 200
    except Exception:
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
