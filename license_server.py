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


def _require_admin():
    """Check admin_secret from JSON body or query param. Returns (None, None) if OK, else (response, status)."""
    secret = ""
    if request.is_json and request.get_json(silent=True):
        secret = (request.get_json().get("admin_secret") or "").strip()
    if not secret:
        secret = (request.args.get("admin_secret") or "").strip()
    expected = os.environ.get("ADMIN_SECRET", "").strip()
    if not expected or secret != expected:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    return None, None


@app.route("/api/admin/activations", methods=["GET"])
def admin_list_activations():
    """Vendor-only: list all activations. GET ?admin_secret=YOUR_SECRET or POST JSON { admin_secret }."""
    err, status = _require_admin()
    if err is not None:
        return err, status
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT license_key, client_id, expiry_date, activated_at, activation_token
            FROM activations ORDER BY activated_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        out = []
        for r in rows:
            out.append({
                "license_key": r[0],
                "client_id": r[1],
                "expiry_date": r[2] or "Perpetual",
                "activated_at": r[3],
                "activation_token": (r[4] or "")[:16] + "..." if (r[4] and len(r[4]) > 16) else (r[4] or ""),
            })
        return jsonify({"success": True, "count": len(out), "activations": out}), 200
    except Exception:
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route("/api/admin/extend", methods=["POST"])
def admin_extend():
    """Vendor-only: extend expiry for an existing activation (e.g. after customer pays for renewal).
    POST JSON: { "admin_secret": "...", "activation_token": "..." or "license_key"+"client_id", "new_expiry": "YYYY-MM-DD" }
    Set ADMIN_SECRET env on Render; keep it secret."""
    if not request.is_json:
        return jsonify({"success": False, "message": "Content-Type must be application/json"}), 400
    err, status = _require_admin()
    if err is not None:
        return err, status
    data = request.get_json() or {}
    new_expiry = (data.get("new_expiry") or "").strip()
    if len(new_expiry) != 10 or new_expiry[4] != "-" or new_expiry[7] != "-":
        return jsonify({"success": False, "message": "new_expiry must be YYYY-MM-DD"}), 400
    try:
        datetime.strptime(new_expiry, "%Y-%m-%d")
    except ValueError:
        return jsonify({"success": False, "message": "Invalid new_expiry date"}), 400
    activation_token = (data.get("activation_token") or "").strip()
    license_key = (data.get("license_key") or "").strip()
    client_id = (data.get("client_id") or "").strip()
    try:
        conn = get_db()
        cur = conn.cursor()
        if activation_token:
            cur.execute(
                "UPDATE activations SET expiry_date = ? WHERE activation_token = ?",
                (new_expiry, activation_token),
            )
            updated = cur.rowcount
        elif license_key and client_id:
            cur.execute(
                "UPDATE activations SET expiry_date = ? WHERE license_key = ? AND client_id = ?",
                (new_expiry, license_key, client_id),
            )
            updated = cur.rowcount
        else:
            conn.close()
            return jsonify({"success": False, "message": "Provide activation_token or (license_key + client_id)"}), 400
        conn.commit()
        conn.close()
        if updated == 0:
            return jsonify({"success": False, "message": "No activation found"}), 200
        return jsonify({"success": True, "message": f"Expiry extended to {new_expiry}"}), 200
    except Exception:
        return jsonify({"success": False, "message": "Server error"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
