#!/usr/bin/env python3
"""
Vendor-only: list all activations stored on the license server.
Requires LICENSE_SERVER_URL and ADMIN_SECRET in env.

Usage:
  set LICENSE_SERVER_URL=https://your-app.onrender.com
  set ADMIN_SECRET=your_admin_secret
  python list_activations.py
"""
import os
import sys
import json
import urllib.request
import urllib.error

def main():
    base_url = (os.environ.get("LICENSE_SERVER_URL") or "").strip().rstrip("/")
    admin_secret = (os.environ.get("ADMIN_SECRET") or "").strip()
    if not base_url or not admin_secret:
        print("Set env: LICENSE_SERVER_URL and ADMIN_SECRET", file=sys.stderr)
        sys.exit(1)
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    url = base_url + "/api/admin/activations?admin_secret=" + urllib.request.quote(admin_secret)
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
            print(data.get("message", str(e)), file=sys.stderr)
        except Exception:
            print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if not data.get("success"):
        print(data.get("message", "Failed"), file=sys.stderr)
        sys.exit(1)

    activations = data.get("activations") or []
    print(f"Total activations: {len(activations)}\n")
    if not activations:
        return
    print(f"{'License key':<45} {'Client ID':<20} {'Expiry':<12} {'Activated at':<25} {'Token (partial)'}")
    print("-" * 120)
    for a in activations:
        print(f"{a.get('license_key', ''):<45} {a.get('client_id', ''):<20} {a.get('expiry_date', ''):<12} {str(a.get('activated_at', '')):<25} {a.get('activation_token', '')}")


if __name__ == "__main__":
    main()
