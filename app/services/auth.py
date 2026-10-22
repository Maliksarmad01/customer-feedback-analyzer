
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

AUTH_SECRET = os.getenv('AUTH_SECRET', 'local-development-only-change-me').encode()
TOKEN_TTL_SECONDS = int(os.getenv('TOKEN_TTL_SECONDS', '86400'))

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310_000)
    return base64.urlsafe_b64encode(salt).decode() + '$' + base64.urlsafe_b64encode(digest).decode()

def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_s, digest_s = encoded.split('$', 1)
        salt = base64.urlsafe_b64decode(salt_s.encode())
        expected = base64.urlsafe_b64decode(digest_s.encode())
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def create_token(user_id: int) -> str:
    payload = _b64(json.dumps({'sub': user_id, 'exp': int(time.time()) + TOKEN_TTL_SECONDS}, separators=(',', ':')).encode())
    signature = _b64(hmac.new(AUTH_SECRET, payload.encode(), hashlib.sha256).digest())
    return payload + '.' + signature


def read_token(token: str) -> int | None:
    try:
        payload, signature = token.split(".", 1)

        expected = _b64(
            hmac.new(
                AUTH_SECRET,
                payload.encode(),
                hashlib.sha256
            ).digest()
        )

        if not hmac.compare_digest(signature, expected):
            return None

        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(decoded)

        if not isinstance(data, dict):
            return None

        user_id = int(data["sub"])
        expires_at = int(data["exp"])

        if user_id <= 0 or expires_at <= int(time.time()):
            return None

        return user_id

    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
