"""Stamhad account: sign in with Firebase and check this app's subscription.

One Firebase project serves all Stamhad apps:
  accounts/{uid}                 business name, owner, notes          (only admins write)
  subscriptions/{uid}/{app}      active, plan, paid_until, stripe ids (only admins / Stripe write)
  usage/{uid}/{app}/{device}     last_seen, version, computer         (the app writes its own)
  admins/{uid} = true            who may manage accounts              (set in the Firebase console)

The app never stores the password - only Firebase's refresh token.
If there's no internet it keeps working for GRACE_DAYS after the last successful check.
"""

from __future__ import annotations

import json
import platform
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

# ── configuration (the web config of the Firebase project; safe to ship) ─────
FIREBASE = {
    "api_key": "AIzaSyDO-_gyJXTyBQzdfXQ56T2w8z716FgCM3k",
    "db_url": "https://stamhad-accounts-default-rtdb.firebaseio.com",
    "project_id": "stamhad-accounts",
}
APP_ID = "staff"
APP_NAME = "Stamhad Staff"
GRACE_DAYS = 7
RECHECK_HOURS = 6
SUPPORT_EMAIL = "stamhadsoftware@gmail.com"

AUTH_BASE = "https://identitytoolkit.googleapis.com/v1"
TOKEN_URL = "https://securetoken.googleapis.com/v1/token"


def configured() -> bool:
    return bool(FIREBASE.get("api_key") and FIREBASE.get("db_url"))


class Offline(Exception):
    """Couldn't reach Firebase (no internet, DNS, timeout)."""


class AuthError(Exception):
    """Firebase said no. .code is Firebase's code (e.g. USER_DISABLED)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


MESSAGES = {
    "EMAIL_NOT_FOUND": "Wrong email or password.",
    "INVALID_PASSWORD": "Wrong email or password.",
    "INVALID_LOGIN_CREDENTIALS": "Wrong email or password.",
    "INVALID_EMAIL": "That email address doesn't look right.",
    "MISSING_PASSWORD": "Type your password.",
    "USER_DISABLED": "This account has been turned off.",
    "USER_NOT_FOUND": "This account doesn't exist any more.",
    "TOKEN_EXPIRED": "Please sign in again.",
    "INVALID_REFRESH_TOKEN": "Please sign in again.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Wait a few minutes and try again.",
    "EMAIL_EXISTS": "An account with this email already exists.",
    "WEAK_PASSWORD": "Password must be at least 6 characters.",
    "PERMISSION_DENIED": "Not allowed.",
}


# ── HTTP ──────────────────────────────────────────────────────────────────────
def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _request(method, url, payload=None, timeout=12):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            body = r.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
        except Exception:
            err = {}
        msg = err.get("error")
        if isinstance(msg, dict):
            code = str(msg.get("message", "")).split(" ")[0].split(":")[0]
        else:
            code = str(msg or e.code)
        if e.code in (401, 403) and not code.isupper():
            code = "PERMISSION_DENIED"
        raise AuthError(code, MESSAGES.get(code, f"Firebase error {e.code}: {code}"))
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        raise Offline(str(getattr(e, "reason", e)))


def _auth(endpoint, payload):
    return _request("POST", f"{AUTH_BASE}/{endpoint}?key={FIREBASE['api_key']}", payload)


# ── Firebase Auth ─────────────────────────────────────────────────────────────
def sign_in(email: str, password: str) -> dict:
    r = _auth("accounts:signInWithPassword",
              {"email": email.strip(), "password": password, "returnSecureToken": True})
    return {"uid": r["localId"], "email": r.get("email", email.strip()),
            "id_token": r["idToken"], "refresh_token": r["refreshToken"]}


def refresh(refresh_token: str) -> dict:
    r = _request("POST", f"{TOKEN_URL}?key={FIREBASE['api_key']}",
                 {"grant_type": "refresh_token", "refresh_token": refresh_token})
    return {"uid": r["user_id"], "id_token": r["id_token"], "refresh_token": r["refresh_token"]}


def send_password_reset(email: str):
    _auth("accounts:sendOobCode", {"requestType": "PASSWORD_RESET", "email": email.strip()})


def create_user(email: str, password: str) -> str:
    """Admin tool: create a Firebase Auth user, return its uid."""
    r = _auth("accounts:signUp", {"email": email.strip(), "password": password, "returnSecureToken": True})
    return r["localId"]


# ── Realtime Database ─────────────────────────────────────────────────────────
def _db_url(path, id_token):
    return f"{FIREBASE['db_url'].rstrip('/')}/{path}.json?auth={urllib.parse.quote(id_token)}"


def db_get(path, id_token):
    return _request("GET", _db_url(path, id_token))


def db_put(path, data, id_token):
    return _request("PUT", _db_url(path, id_token), data)


def db_patch(path, data, id_token):
    return _request("PATCH", _db_url(path, id_token), data)


# ── the rule: may this account use this app today? ────────────────────────────
def evaluate(sub: dict | None, today: date | None = None) -> tuple[bool, str]:
    today = today or date.today()
    if not sub:
        return False, f"This account doesn't include {APP_NAME} yet."
    if not sub.get("active", False):
        return False, "This subscription is turned off."
    pu = sub.get("paid_until")
    if pu:
        try:
            until = date.fromisoformat(str(pu)[:10])
        except ValueError:
            until = None
        if until and until < today:
            return False, f"This subscription ended on {until:%B %d, %Y}."
    return True, ""


# ── session on this computer ──────────────────────────────────────────────────
class Session:
    """account.json in the data folder: email, uid, refresh token, last good check."""

    def __init__(self, root: Path):
        self.path = Path(root) / "account.json"
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.data = {}
        if not self.data.get("device"):
            self.data["device"] = uuid.uuid4().hex[:12]

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @property
    def signed_in(self) -> bool:
        return bool(self.data.get("refresh_token") and self.data.get("uid"))

    def sign_out(self):
        keep = {"device": self.data.get("device"), "email": self.data.get("email", "")}
        self.data = keep
        self.save()

    def last_ok(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.data["last_ok"])
        except Exception:
            return None

    def within_grace(self, now: datetime | None = None) -> bool:
        lo = self.last_ok()
        now = now or datetime.now()
        if not lo or self.data.get("last_state") != "ok":
            return False
        # the last good check said "paid until X": never let the grace run past that
        pu = (self.data.get("sub") or {}).get("paid_until")
        if pu:
            try:
                if date.fromisoformat(str(pu)[:10]) < now.date():
                    return False
            except ValueError:
                pass
        return timedelta(0) <= now - lo <= timedelta(days=GRACE_DAYS)

    def grace_left_days(self) -> int:
        lo = self.last_ok()
        if not lo:
            return 0
        return max(0, GRACE_DAYS - (datetime.now() - lo).days)


def check(session: Session, version: str = "") -> dict:
    """Ask Firebase. Returns {"state": ok|locked|signed_out, "message", "sub", "account"}.
    Raises Offline when Firebase can't be reached (the caller applies the grace period)."""
    if not session.signed_in:
        return {"state": "signed_out", "message": ""}
    try:
        tok = refresh(session.data["refresh_token"])
    except AuthError as e:
        if e.code in ("USER_DISABLED",):
            _remember(session, "locked", MESSAGES["USER_DISABLED"])
            return {"state": "locked", "message": MESSAGES["USER_DISABLED"]}
        session.sign_out()
        return {"state": "signed_out", "message": e.args[0]}
    session.data["refresh_token"] = tok["refresh_token"]
    uid, idt = tok["uid"], tok["id_token"]
    sub = db_get(f"subscriptions/{uid}/{APP_ID}", idt)
    try:
        acc = db_get(f"accounts/{uid}", idt) or {}
    except AuthError:
        acc = {}
    ok, why = evaluate(sub)
    session.data["sub"] = sub or {}
    session.data["business"] = acc.get("business_name", "")
    _remember(session, "ok" if ok else "locked", why)
    try:                                   # so you can see who uses it (best effort)
        db_patch(f"usage/{uid}/{APP_ID}/{session.data['device']}",
                 {"last_seen": datetime.now().isoformat(timespec="seconds"), "version": version,
                  "computer": socket.gethostname().split(".")[0][:40],
                  "os": f"{platform.system()} {platform.release()}"}, idt)
    except Exception:
        pass
    return {"state": "ok" if ok else "locked", "message": why, "sub": sub or {}, "account": acc}


def _remember(session: Session, state: str, message: str):
    session.data["last_check"] = datetime.now().isoformat(timespec="seconds")
    session.data["last_state"] = state
    session.data["last_message"] = message
    if state == "ok":
        session.data["last_ok"] = session.data["last_check"]
    session.save()


def complete_sign_in(session: Session, email: str, password: str, version: str = "") -> dict:
    """Sign in, then run the subscription check. Raises AuthError / Offline."""
    s = sign_in(email, password)
    session.data.update(email=s["email"], uid=s["uid"], refresh_token=s["refresh_token"])
    session.save()
    return check(session, version)
