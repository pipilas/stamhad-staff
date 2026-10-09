// Security-rule tests, run against the Firestore emulator:  npm test
import { test, before, after, beforeEach } from "node:test";
import { readFileSync } from "node:fs";
import {
  initializeTestEnvironment, assertSucceeds, assertFails,
} from "@firebase/rules-unit-testing";
import {
  doc, getDoc, setDoc, updateDoc, deleteDoc, collection, getDocs, query, where,
  serverTimestamp, Timestamp,
} from "firebase/firestore";

let env;
const R = "owner1";          // restaurant id = owner's uid
const OTHER = "owner2";

before(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-nume",
    firestore: { rules: readFileSync("firestore.rules", "utf8"), host: "127.0.0.1", port: 8080 },
  });
});
after(async () => { await env.cleanup(); });

const future = () => Timestamp.fromDate(new Date(Date.now() + 30 * 864e5));
const past = () => Timestamp.fromDate(new Date(Date.now() - 864e5));

async function seed({ active = true, paidUntil = null } = {}) {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    const sub = { active };
    if (paidUntil) sub.paidUntil = paidUntil;
    await setDoc(doc(db, "admins/me"), { yes: true });
    await setDoc(doc(db, `restaurants/${R}`), { name: "Anemi", ownerUid: R, subscription: sub });
    await setDoc(doc(db, `restaurants/${OTHER}`), { name: "Other", ownerUid: OTHER, subscription: { active: true } });
    const m = (u, role, eid, extra = {}) => setDoc(doc(db, `restaurants/${R}/members/${u}`),
      { role, employeeId: eid, name: u, positions: [], ...extra });
    await m(R, "owner", "");
    await m("mgr", "manager", "e_mgr");
    await m("ana", "employee", "e_ana", { positions: ["Bartender"] });
    await m("bob", "employee", "e_bob", { positions: ["Server"] });
    await m("cat", "employee", "e_cat", { positions: ["Busser"], canInventory: true });
    await setDoc(doc(db, `restaurants/${OTHER}/members/x`), { role: "owner", employeeId: "" });
    await setDoc(doc(db, `restaurants/${R}/settings/inventory`), { positions: ["Bartender"] });
    await setDoc(doc(db, `restaurants/${R}/shifts/s1`), { week: "2026-10-05", employeeId: "e_ana" });
    await setDoc(doc(db, `restaurants/${R}/tips/e_ana_2026-10-05`), { employeeId: "e_ana", week: "2026-10-05" });
    await setDoc(doc(db, `restaurants/${R}/tips/e_bob_2026-10-05`), { employeeId: "e_bob", week: "2026-10-05" });
    await setDoc(doc(db, `restaurants/${R}/items/i1`), { name: "Limes" });
    await setDoc(doc(db, `users/ana`), { rid: R });
  });
}
const as = (u) => env.authenticatedContext(u).firestore();
const anon = () => env.unauthenticatedContext().firestore();

test("strangers and other restaurants see nothing", async () => {
  await seed();
  await assertFails(getDoc(doc(anon(), `restaurants/${R}/shifts/s1`)));
  await assertFails(getDoc(doc(as("x"), `restaurants/${R}/shifts/s1`)));
  await assertFails(getDoc(doc(as("ana"), `restaurants/${OTHER}`)));
});

test("everyone in the restaurant sees the whole schedule; only managers change it", async () => {
  await seed();
  await assertSucceeds(getDocs(query(collection(as("bob"), `restaurants/${R}/shifts`), where("week", "==", "2026-10-05"))));
  await assertFails(setDoc(doc(as("ana"), `restaurants/${R}/shifts/s2`), { week: "2026-10-05" }));
  await assertSucceeds(setDoc(doc(as("mgr"), `restaurants/${R}/shifts/s2`), { week: "2026-10-05" }));
  await assertSucceeds(deleteDoc(doc(as(R), `restaurants/${R}/shifts/s2`)));
});

test("subscription off or expired locks everybody out", async () => {
  await seed({ active: false });
  await assertFails(getDoc(doc(as("ana"), `restaurants/${R}/shifts/s1`)));
  await assertFails(getDoc(doc(as(R), `restaurants/${R}/shifts/s1`)));
  await assertSucceeds(getDoc(doc(as("ana"), `restaurants/${R}`)));             // can still see why
  await assertSucceeds(getDoc(doc(as("ana"), `restaurants/${R}/members/ana`)));
  await env.withSecurityRulesDisabled((ctx) => setDoc(doc(ctx.firestore(), `restaurants/${R}/members/me`), { role: "owner" }));
  await assertSucceeds(getDoc(doc(as("me"), `restaurants/${R}/shifts/s1`)));      // the admin can still test
  await seed({ active: true, paidUntil: past() });
  await assertFails(getDoc(doc(as("ana"), `restaurants/${R}/shifts/s1`)));
  await seed({ active: true, paidUntil: future() });
  await assertSucceeds(getDoc(doc(as("ana"), `restaurants/${R}/shifts/s1`)));
});

test("only the admin can change the subscription", async () => {
  await seed();
  await assertFails(updateDoc(doc(as(R), `restaurants/${R}`), { subscription: { active: true, plan: "x" } }));
  await assertSucceeds(updateDoc(doc(as(R), `restaurants/${R}`), { name: "Anemi NYC" }));
  await assertSucceeds(updateDoc(doc(as("me"), `restaurants/${R}`), { subscription: { active: false } }));
});

test("owner can set up their own restaurant, but not switch it on", async () => {
  await seed();
  const db = as("newowner");
  await assertFails(setDoc(doc(db, "restaurants/newowner"), { name: "N", ownerUid: "newowner", subscription: { active: true } }));
  await assertSucceeds(setDoc(doc(db, "restaurants/newowner"), { name: "N", ownerUid: "newowner" }));
  await assertSucceeds(setDoc(doc(db, "restaurants/newowner/members/newowner"), { role: "owner" }));
  await assertSucceeds(setDoc(doc(db, "users/newowner/restaurants/newowner"), { name: "N", role: "owner" }));
  await assertSucceeds(setDoc(doc(db, "users/newowner"), { lastRid: "newowner" }));
  await assertFails(setDoc(doc(db, `users/newowner/restaurants/${R}`), { name: "x" }));   // can't join someone else
  await assertFails(setDoc(doc(as("x"), "users/newowner"), { lastRid: R }));             // not your user record
  await assertFails(setDoc(doc(as("ana"), `restaurants/${R}/members/zed`), { role: "employee" }));
});

test("managers invite people; employees can't make themselves managers", async () => {
  await seed();
  await assertSucceeds(setDoc(doc(as("mgr"), `restaurants/${R}/members/new1`), { role: "employee", employeeId: "e_new" }));
  await assertFails(setDoc(doc(as("mgr"), `restaurants/${R}/members/new2`), { role: "owner" }));
  await assertFails(updateDoc(doc(as("ana"), `restaurants/${R}/members/ana`), { role: "manager" }));
  await assertFails(updateDoc(doc(as("mgr"), `restaurants/${R}/members/${R}`), { role: "employee" }));
  await assertFails(deleteDoc(doc(as("mgr"), `restaurants/${R}/members/${R}`)));
  await assertFails(getDocs(collection(as("ana"), `restaurants/${R}/members`)));   // team emails: managers only
  await assertSucceeds(getDocs(collection(as("mgr"), `restaurants/${R}/members`)));
  await assertSucceeds(getDocs(query(collection(as("mgr"), `restaurants/${R}/members`), where("employeeId", "==", "e_ana"))));
});

test("days off: employees request their own, managers approve", async () => {
  await seed();
  const ana = as("ana");
  const ref = doc(ana, `restaurants/${R}/timeoff/t1`);
  await assertFails(setDoc(ref, { uid: "ana", employeeId: "e_ana", status: "approved", from: "2026-10-10", to: "2026-10-11" }));
  await assertFails(setDoc(ref, { uid: "ana", employeeId: "e_bob", status: "pending" }));
  await assertSucceeds(setDoc(ref, { uid: "ana", employeeId: "e_ana", status: "pending", from: "2026-10-10", to: "2026-10-11" }));
  await assertFails(updateDoc(ref, { status: "approved" }));
  await assertFails(getDoc(doc(as("bob"), `restaurants/${R}/timeoff/t1`)));
  await assertSucceeds(getDocs(query(collection(ana, `restaurants/${R}/timeoff`), where("uid", "==", "ana"))));
  await assertSucceeds(updateDoc(doc(as("mgr"), `restaurants/${R}/timeoff/t1`), { status: "approved", decidedBy: "mgr" }));
  await assertFails(updateDoc(ref, { status: "cancelled" }));                       // already decided
});

test("tips: each employee sees only their own", async () => {
  await seed();
  await assertSucceeds(getDocs(query(collection(as("ana"), `restaurants/${R}/tips`), where("employeeId", "==", "e_ana"))));
  await assertFails(getDocs(query(collection(as("ana"), `restaurants/${R}/tips`), where("employeeId", "==", "e_bob"))));
  await assertFails(getDocs(collection(as("ana"), `restaurants/${R}/tips`)));
  await assertSucceeds(getDocs(collection(as("mgr"), `restaurants/${R}/tips`)));
  await assertFails(setDoc(doc(as("ana"), `restaurants/${R}/tips/e_ana_x`), { employeeId: "e_ana" }));
});

test("inventory: allowed positions or people add to the order list, with their name", async () => {
  await seed();
  const line = (u) => ({ itemId: "i1", qty: 2, byUid: u, byName: u, at: serverTimestamp() });
  await assertSucceeds(setDoc(doc(as("ana"), `restaurants/${R}/cart/c1`), line("ana")));     // Bartender position
  await assertSucceeds(setDoc(doc(as("cat"), `restaurants/${R}/cart/c2`), line("cat")));     // allowed personally
  await assertFails(setDoc(doc(as("bob"), `restaurants/${R}/cart/c3`), line("bob")));        // Server: not allowed
  await assertFails(setDoc(doc(as("ana"), `restaurants/${R}/cart/c4`), line("cat")));        // can't add as someone else
  await assertFails(setDoc(doc(as("ana"), `restaurants/${R}/cart/c5`),
    { itemId: "i1", qty: 1, byUid: "ana", byName: "ana", at: Timestamp.fromDate(new Date(2020, 1, 1)) }));  // fake time
  await assertSucceeds(getDocs(collection(as("bob"), `restaurants/${R}/cart`)));            // everyone can see who added what
  await assertFails(deleteDoc(doc(as("ana"), `restaurants/${R}/cart/c2`)));                 // not hers
  await assertSucceeds(deleteDoc(doc(as("cat"), `restaurants/${R}/cart/c2`)));
  await assertSucceeds(deleteDoc(doc(as("mgr"), `restaurants/${R}/cart/c1`)));
  await assertSucceeds(setDoc(doc(as("ana"), `restaurants/${R}/items/i2`), { name: "Mint" }));
  await assertFails(updateDoc(doc(as("ana"), `restaurants/${R}/items/i1`), { name: "x" }));
  await assertFails(setDoc(doc(as("ana"), `restaurants/${R}/orders/o1`), { lines: [] }));
  await assertSucceeds(setDoc(doc(as("mgr"), `restaurants/${R}/orders/o1`), { lines: [] }));
});

test("invites: the invited email joins with exactly the invited role; one login, two restaurants", async () => {
  await seed();
  const inv = { employeeId: "e_new", role: "employee", name: "Nia", positions: ["Server"], canInventory: false };
  const mgr = as("mgr");
  await assertFails(setDoc(doc(as("ana"), `restaurants/${R}/invites/nia@x.com`), inv));          // employees can't invite
  await assertFails(setDoc(doc(mgr, `restaurants/${R}/invites/nia@x.com`), { ...inv, role: "owner" }));
  await assertSucceeds(setDoc(doc(mgr, `restaurants/${R}/invites/nia@x.com`), inv));
  await assertSucceeds(setDoc(doc(mgr, `invites/nia@x.com/rids/${R}`), { rid: R, name: "Anemi" }));
  await assertFails(setDoc(doc(mgr, `invites/nia@x.com/rids/${OTHER}`), { rid: OTHER }));        // not their restaurant
  await assertSucceeds(getDocs(collection(mgr, `restaurants/${R}/invites`)));                     // Team screen
  await assertFails(getDocs(collection(as("ana"), `restaurants/${R}/invites`)));

  const nia = env.authenticatedContext("nia", { email: "nia@x.com" }).firestore();
  const eve = env.authenticatedContext("eve", { email: "eve@x.com" }).firestore();
  await assertSucceeds(getDocs(collection(nia, "invites/nia@x.com/rids")));
  await assertFails(getDocs(collection(eve, "invites/nia@x.com/rids")));
  await assertSucceeds(getDoc(doc(nia, `restaurants/${R}/invites/nia@x.com`)));
  await assertFails(setDoc(doc(eve, `restaurants/${R}/members/eve`), { role: "employee", employeeId: "e_new", positions: ["Server"] }));
  await assertFails(setDoc(doc(nia, `restaurants/${R}/members/nia`), { role: "manager", employeeId: "e_new", positions: ["Server"] }));
  await assertFails(setDoc(doc(nia, `restaurants/${R}/members/nia`), { role: "employee", employeeId: "e_new", positions: ["Server"], canInventory: true }));
  await assertSucceeds(setDoc(doc(nia, `restaurants/${R}/members/nia`), { role: "employee", employeeId: "e_new", positions: ["Server"], canInventory: false, name: "Nia" }));
  await assertSucceeds(setDoc(doc(nia, `users/nia/restaurants/${R}`), { name: "Anemi", role: "employee" }));
  await assertSucceeds(deleteDoc(doc(nia, `restaurants/${R}/invites/nia@x.com`)));
  await assertSucceeds(deleteDoc(doc(nia, `invites/nia@x.com/rids/${R}`)));
  await assertFails(setDoc(doc(eve, `users/eve/restaurants/${R}`), { name: "x" }));

  // the same login can also join a second restaurant
  await env.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), `restaurants/${OTHER}/members/boss2`), { role: "owner", employeeId: "" });
  });
  const boss2 = as("boss2");
  await assertSucceeds(setDoc(doc(boss2, `restaurants/${OTHER}/invites/nia@x.com`), { ...inv, employeeId: "o_nia", positions: ["Bartender"] }));
  await assertSucceeds(setDoc(doc(nia, `restaurants/${OTHER}/members/nia`), { role: "employee", employeeId: "o_nia", positions: ["Bartender"], canInventory: false }));
  await assertSucceeds(setDoc(doc(nia, `users/nia/restaurants/${OTHER}`), { name: "Other", role: "employee" }));
  await assertSucceeds(getDocs(collection(nia, "users/nia/restaurants")));
  await assertSucceeds(getDoc(doc(nia, `restaurants/${OTHER}/shifts/none`)));
  await assertSucceeds(getDoc(doc(nia, `restaurants/${R}/shifts/s1`)));
  // and sees only her own tips in each
  await assertFails(getDocs(query(collection(nia, `restaurants/${OTHER}/tips`), where("employeeId", "==", "e_new"))));
});

test("daily tip totals: managers only", async () => {
  await seed();
  await assertSucceeds(setDoc(doc(as("mgr"), `restaurants/${R}/days/2026-10-09`), { tips: { Dinner: { floor: 1000, bar: 300 } } }));
  await assertFails(getDoc(doc(as("ana"), `restaurants/${R}/days/2026-10-09`)));
  await assertFails(setDoc(doc(as("ana"), `restaurants/${R}/days/2026-10-09`), { tips: {} }));
});
