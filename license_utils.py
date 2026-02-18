"""
Shared license validation for app and license server.
Key format: HM-{CODE}-{YYYYMMDD}-{16 hex signature}
"""
import os
import re
import hmac
import hashlib
from datetime import datetime
from typing import Tuple, Optional

# Use env LICENSE_SECRET on server (e.g. Render); else fallback. Must match license_keygen.py.
_raw = os.environ.get("LICENSE_SECRET", "ResortManager-License-Secret-Change-Me-In-Production-8f3a2b1c")
LICENSE_SECRET = _raw.encode("utf-8") if isinstance(_raw, str) else _raw

LICENSE_PATTERN = re.compile(r"^HM-[A-Za-z0-9]{2,12}-(\d{8})(?:-([A-Fa-f0-9]{16}))?$")


def verify_signature(payload: str, signature: str) -> bool:
    if not payload or not signature or len(signature) != 16:
        return False
    expected = hmac.new(
        LICENSE_SECRET,
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16].upper()
    return hmac.compare_digest(expected, signature.upper())


def parse_license_key(license_key: str) -> Tuple[bool, Optional[str]]:
    """Validate format and signature; return (valid, expiry_yyyy_mm_dd or None for perpetual)."""
    if not license_key or not license_key.strip():
        return False, None
    key = license_key.strip()
    m = LICENSE_PATTERN.match(key)
    if not m:
        return False, None
    ymd = m.group(1)
    sig = m.group(2)
    if len(ymd) != 8:
        return False, None
    if not sig or len(sig) != 16:
        return False, None
    payload = key.rsplit("-", 1)[0]
    if not verify_signature(payload, sig):
        return False, None
    try:
        if ymd == "99991231":
            return True, None
        expiry_str = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
        datetime.strptime(expiry_str, "%Y-%m-%d")
        return True, expiry_str
    except ValueError:
        return False, None
