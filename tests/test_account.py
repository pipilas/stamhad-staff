"""Sign-in + subscription rules, against the fake Firebase.  Run:  python tests/test_account.py"""

import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import account as A                      # noqa: E402
from fake_firebase import FakeFirebase   # noqa: E402

fb = FakeFirebase()
fb.install(A)
admin = fb.add_user("me@stamhad.com", "adminpass", admin=True)
uid = fb.add_user("rest@example.com", "secret123")
today = date.today()


def fresh():
    return A.Session(Path(tempfile.mkdtemp()))


# evaluate()
assert A.evaluate(None)[0] is False
assert A.evaluate({"active": False})[0] is False
assert A.evaluate({"active": True})[0] is True
assert A.evaluate({"active": True, "paid_until": str(today)})[0] is True                       # last paid day
assert A.evaluate({"active": True, "paid_until": str(today - timedelta(days=1))})[0] is False

# wrong password
s = fresh()
try:
    A.complete_sign_in(s, "rest@example.com", "nope")
    raise SystemExit("wrong password accepted")
except A.AuthError as e:
    assert str(e) == "Wrong email or password.", e

# right password, no subscription yet
r = A.complete_sign_in(s, "rest@example.com", "secret123", "0.8.0")
assert r["state"] == "locked" and "doesn't include" in r["message"], r
assert "secret123" not in s.path.read_text()                                    # password never stored

# the restaurant can't switch itself on
idt = A.sign_in("rest@example.com", "secret123")["id_token"]
try:
    A.db_put(f"subscriptions/{uid}/staff", {"active": True}, idt)
    raise SystemExit("restaurant could write its own subscription!")
except A.AuthError as e:
    assert e.code == "PERMISSION_DENIED"
# …and can't read other people's
other = fb.add_user("other@example.com", "secret456")
try:
    A.db_get(f"subscriptions/{other}/staff", idt)
    raise SystemExit("could read someone else's subscription")
except A.AuthError:
    pass

# admin turns it on (paid until next month)
adm = A.sign_in("me@stamhad.com", "adminpass")["id_token"]
A.db_put(f"accounts/{uid}", {"business_name": "Corner House", "email": "rest@example.com"}, adm)
A.db_put(f"subscriptions/{uid}/staff", {"active": True, "plan": "Standard",
                                        "paid_until": str(today + timedelta(days=30))}, adm)
r = A.check(s, "0.8.0")
assert r["state"] == "ok", r
assert s.data["business"] == "Corner House" and s.within_grace()
assert fb.get(f"usage/{uid}/staff/{s.data['device']}")["version"] == "0.8.0"   # last seen recorded

# admin turns it off -> locked at the next check
A.db_patch(f"subscriptions/{uid}/staff", {"active": False}, adm)
r = A.check(s)
assert r["state"] == "locked" and "turned off" in r["message"], r
assert not s.within_grace()                                                      # no grace once locked

# expired
A.db_patch(f"subscriptions/{uid}/staff", {"active": True, "paid_until": str(today - timedelta(days=2))}, adm)
r = A.check(s)
assert r["state"] == "locked" and "ended on" in r["message"], r

# active again
A.db_patch(f"subscriptions/{uid}/staff", {"paid_until": str(today + timedelta(days=30))}, adm)
assert A.check(s)["state"] == "ok"

# user disabled in the Firebase console
fb.users["rest@example.com"]["disabled"] = True
r = A.check(s)
assert r["state"] == "locked" and "turned off" in r["message"], r
fb.users["rest@example.com"]["disabled"] = False
s2 = fresh()
assert A.complete_sign_in(s2, "rest@example.com", "secret123")["state"] == "ok"

# offline: grace period
fb.stop()
try:
    A.check(s2)
    raise SystemExit("expected Offline")
except A.Offline:
    pass
assert s2.within_grace() and s2.grace_left_days() == 7
s2.data["last_ok"] = (datetime.now() - timedelta(days=6, hours=23)).isoformat()
assert s2.within_grace()
s2.data["last_ok"] = (datetime.now() - timedelta(days=7, hours=1)).isoformat()
assert not s2.within_grace()                                                     # 7 days are up
s2.data["last_ok"] = datetime.now().isoformat()
s2.data["sub"]["paid_until"] = str(today - timedelta(days=1))
assert not s2.within_grace()                                                     # paid period ended while offline
s2.data["sub"]["paid_until"] = str(today + timedelta(days=5))
s2.data["last_ok"] = (datetime.now() + timedelta(days=3)).isoformat()            # clock set backwards
assert not s2.within_grace()

# signing out forgets the token but keeps the email
s2.sign_out()
assert not s2.signed_in and s2.data["email"] == "rest@example.com"
print("ACCOUNT OK")
