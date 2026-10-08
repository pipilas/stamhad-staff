"""A tiny stand-in for Firebase Auth + Realtime Database, for tests.
Implements the REST calls account.py uses and the same access rules as
firebase/database.rules.json (admins write; users read their own subscription)."""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


class FakeFirebase:
    def __init__(self):
        self.users = {}        # email -> {uid, password, disabled}
        self.tokens = {}       # id/refresh token -> uid
        self.db = {}
        self.resets = []
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    # ── wiring into account.py ──
    def install(self, account):
        account.AUTH_BASE = f"http://127.0.0.1:{self.port}/v1"
        account.TOKEN_URL = f"http://127.0.0.1:{self.port}/v1/token"
        account.FIREBASE.update(api_key="test-key", db_url=f"http://127.0.0.1:{self.port}/db", project_id="test")

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()          # refuse connections, like being offline

    # ── helpers for tests ──
    def add_user(self, email, password, admin=False):
        uid = uuid.uuid4().hex[:20]
        self.users[email] = {"uid": uid, "password": password, "disabled": False}
        if admin:
            self.db.setdefault("admins", {})[uid] = True
        return uid

    def set(self, path, value):
        node = self.db
        parts = [p for p in path.split("/") if p]
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value

    def get(self, path):
        node = self.db
        for p in [p for p in path.split("/") if p]:
            if not isinstance(node, dict) or p not in node:
                return None
            node = node[p]
        return node

    def _issue(self, uid):
        idt, ref = "id-" + uuid.uuid4().hex, "rf-" + uuid.uuid4().hex
        self.tokens[idt] = uid
        self.tokens[ref] = uid
        return idt, ref

    def _is_admin(self, uid):
        return bool(uid) and (self.db.get("admins") or {}).get(uid) is True

    def _allowed(self, method, parts, uid):
        if not uid:
            return False
        if not parts:
            return False
        top = parts[0]
        own = len(parts) > 1 and parts[1] == uid
        if method == "GET":
            if top in ("accounts", "subscriptions", "usage", "admins"):
                return self._is_admin(uid) or own
            return False
        if top in ("accounts", "subscriptions"):
            return self._is_admin(uid)
        if top == "usage":
            return own and len(parts) >= 4
        return False

    def _handler(fb):
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def _err(self, code, msg):
                self._send(code, {"error": {"code": code, "message": msg}})

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n) or b"null")

            def do_POST(self):
                u = urlparse(self.path)
                if parse_qs(u.query).get("key") != ["test-key"]:
                    return self._err(400, "API_KEY_INVALID")
                b = self._body() or {}
                if u.path == "/v1/accounts:signInWithPassword":
                    usr = fb.users.get(b.get("email", "").lower())
                    if not usr or usr["password"] != b.get("password"):
                        return self._err(400, "INVALID_LOGIN_CREDENTIALS")
                    if usr["disabled"]:
                        return self._err(400, "USER_DISABLED")
                    idt, ref = fb._issue(usr["uid"])
                    return self._send(200, {"localId": usr["uid"], "email": b["email"].lower(),
                                            "idToken": idt, "refreshToken": ref})
                if u.path == "/v1/token":
                    uid = fb.tokens.get(b.get("refresh_token"))
                    if not uid:
                        return self._err(400, "INVALID_REFRESH_TOKEN")
                    usr = next((x for x in fb.users.values() if x["uid"] == uid), None)
                    if not usr:
                        return self._err(400, "USER_NOT_FOUND")
                    if usr["disabled"]:
                        return self._err(400, "USER_DISABLED")
                    idt, ref = fb._issue(uid)
                    return self._send(200, {"user_id": uid, "id_token": idt, "refresh_token": ref})
                if u.path == "/v1/accounts:sendOobCode":
                    fb.resets.append(b.get("email"))
                    return self._send(200, {"email": b.get("email")})
                if u.path == "/v1/accounts:signUp":
                    e = b.get("email", "").lower()
                    if e in fb.users:
                        return self._err(400, "EMAIL_EXISTS")
                    if len(b.get("password", "")) < 6:
                        return self._err(400, "WEAK_PASSWORD : Password should be at least 6 characters")
                    uid = fb.add_user(e, b["password"])
                    idt, ref = fb._issue(uid)
                    return self._send(200, {"localId": uid, "idToken": idt, "refreshToken": ref})
                return self._err(404, "NOT_FOUND")

            def _db(self, method):
                u = urlparse(self.path)
                if not u.path.startswith("/db/") or not u.path.endswith(".json"):
                    return self._err(404, "NOT_FOUND")
                parts = [p for p in u.path[4:-5].split("/") if p]
                uid = fb.tokens.get((parse_qs(u.query).get("auth") or [""])[0])
                if not fb._allowed(method, parts, uid):
                    return self._send(401, {"error": "Permission denied"})
                path = "/".join(parts)
                if method == "GET":
                    return self._send(200, fb.get(path))
                b = self._body()
                if method == "PUT":
                    fb.set(path, b)
                else:
                    cur = fb.get(path) or {}
                    cur.update(b or {})
                    fb.set(path, cur)
                return self._send(200, b)

            def do_GET(self):
                self._db("GET")

            def do_PUT(self):
                self._db("PUT")

            def do_PATCH(self):
                self._db("PATCH")
        return H
