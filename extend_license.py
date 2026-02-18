#!/usr/bin/env python3
"""
Vendor-only: extend a customer's license expiry (e.g. after they pay for renewal).
Requires ADMIN_SECRET to be set on the server and passed here.

Usage:
  Set env: LICENSE_SERVER_URL and ADMIN_SECRET
  Then:
    python extend_license.py ACTIVATION_TOKEN NEW_EXPIRY
    python extend_license.py LICENSE_KEY CLIENT_ID NEW_EXPIRY

Examples:
    python extend_license.py abc123def456... 2027-12-31
    python extend_license.py HM-MGMINN-20260228-XXX MGMINN-PC 2027-12-31
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

    args = [a for a in sys.argv[1:] if a and not a.startswith("-")]
    if len(args) == 2:
        activation_token, new_expiry = args[0], args[1]
        payload = {"admin_secret": admin_secret, "activation_token": activation_token, "new_expiry": new_expiry}
    elif len(args) == 3:
        license_key, client_id, new_expiry = args[0], args[1], args[2]
        payload = {"admin_secret": admin_secret, "license_key": license_key, "client_id": client_id, "new_expiry": new_expiry}
    else:
        print(__doc__.strip())
        sys.exit(1)

    req = urllib.request.Request(
        base_url + "/api/admin/extend",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success"):
                print(data.get("message", "Done."))
            else:
                print(data.get("message", "Failed"), file=sys.stderr)
                sys.exit(1)
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


if __name__ == "__main__":
    main()
