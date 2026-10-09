import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/widgets.dart';

import 'models.dart';
import 'util.dart';

enum Phase { loading, signedOut, noRestaurant, locked, ready }

/// One restaurant this login belongs to (a person can work in several).
class Membership {
  final String rid, name, role;
  const Membership(this.rid, this.name, this.role);
}

/// Who is signed in, which restaurant is open, their role there, and whether
/// that restaurant's subscription is active. Everything else reads from here.
class Session extends ChangeNotifier {
  Session({FirebaseAuth? auth, FirebaseFirestore? db})
      : auth = auth ?? FirebaseAuth.instance,
        db = db ?? FirebaseFirestore.instance;

  final FirebaseAuth auth;
  final FirebaseFirestore db;

  Phase phase = Phase.loading;
  User? user;
  bool isAdmin = false; // Stamhad Software: can always open the app
  List<Membership> memberships = [];
  String? rid;
  Map<String, dynamic> member = {};
  Map<String, dynamic> restaurant = {};
  List<String> inventoryPositions = [];
  List<Position> positions = [];
  Map<String, List<String>> defaultTimes = {for (final k in kShifts) k: List.of(kDefaultTimes[k]!)};
  Map<String, dynamic> tipSettings = {};
  String? error;

  StreamSubscription? _authSub;
  final List<StreamSubscription> _subs = [];
  bool _gotMember = false, _gotRest = false, _settingsOn = false;

  void start() {
    _authSub = auth.authStateChanges().listen(_onUser);
  }

  @override
  void dispose() {
    _authSub?.cancel();
    _cancelDocs();
    super.dispose();
  }

  void _cancelDocs() {
    for (final s in _subs) {
      s.cancel();
    }
    _subs.clear();
    _settingsOn = false;
  }

  void _set(Phase p) {
    phase = p;
    notifyListeners();
  }

  Future<void> reload() => _onUser(auth.currentUser);

  Future<void> _onUser(User? u) async {
    _cancelDocs();
    user = u;
    isAdmin = false;
    memberships = [];
    rid = null;
    error = null;
    _clearRestaurant();
    if (u == null) {
      _set(Phase.signedOut);
      return;
    }
    _set(Phase.loading);
    try {
      isAdmin = await db.doc('admins/${u.uid}').get().then((d) => d.exists).catchError((_) => false);
      var udata = <String, dynamic>{};
      try {
        udata = (await db.doc('users/${u.uid}').get()).data() ?? {};
      } catch (_) {}
      await _migrateOld(u, udata);
      await _joinInvites(u);
      memberships = await _loadMemberships(u);
      if (memberships.isEmpty) {
        _set(Phase.noRestaurant);
        return;
      }
      final last = udata['lastRid'] as String?;
      final pick = memberships.any((m) => m.rid == last) ? last! : memberships.first.rid;
      _open(pick);
    } catch (e) {
      error = '$e';
      _set(Phase.noRestaurant);
    }
  }

  Future<List<Membership>> _loadMemberships(User u) async {
    final q = await db.collection('users/${u.uid}/restaurants').get();
    final out = [
      for (final d in q.docs)
        Membership(d.id, (d.data()['name'] ?? 'Restaurant') as String, (d.data()['role'] ?? 'employee') as String)
    ]..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    return out;
  }

  /// Logins made before multi-restaurant support kept {rid} on users/{uid}.
  Future<void> _migrateOld(User u, Map<String, dynamic> udata) async {
    final old = udata['rid'];
    if (old is! String || old.isEmpty) return;
    try {
      final have = await db.doc('users/${u.uid}/restaurants/$old').get();
      if (!have.exists) {
        final r = await db.doc('restaurants/$old').get();
        await db.doc('users/${u.uid}/restaurants/$old').set({'name': r.data()?['name'] ?? 'Restaurant'});
      }
      await db.doc('users/${u.uid}').set({'lastRid': old, 'rid': FieldValue.delete()}, SetOptions(merge: true));
    } catch (_) {}
  }

  /// Managers invited this email to one or more restaurants: join each, exactly as invited.
  Future<void> _joinInvites(User u) async {
    final email = (u.email ?? '').toLowerCase();
    if (email.isEmpty) return;
    QuerySnapshot<Map<String, dynamic>> ptrs;
    try {
      ptrs = await db.collection('invites/$email/rids').get();
    } catch (_) {
      return;
    }
    for (final p in ptrs.docs) {
      final r = p.id;
      try {
        final invRef = db.doc('restaurants/$r/invites/$email');
        final d = (await invRef.get()).data();
        final b = db.batch();
        if (d != null) {
          b.set(db.doc('restaurants/$r/members/${u.uid}'), {
            'role': d['role'],
            'employeeId': d['employeeId'] ?? '',
            'positions': List<String>.from(d['positions'] ?? const []),
            'canInventory': d['canInventory'] ?? false,
            'name': d['name'] ?? '',
            'email': email,
            'joinedAt': FieldValue.serverTimestamp(),
          });
          b.set(db.doc('users/${u.uid}/restaurants/$r'), {'name': p.data()['name'] ?? 'Restaurant', 'role': d['role']});
          b.set(db.doc('users/${u.uid}'), {'lastRid': r}, SetOptions(merge: true));
          b.delete(invRef);
        }
        b.delete(p.reference);
        await b.commit();
      } catch (e) {
        error = '$e';
      }
    }
  }

  void _clearRestaurant() {
    member = {};
    restaurant = {};
    inventoryPositions = [];
    positions = [];
    defaultTimes = {for (final k in kShifts) k: List.of(kDefaultTimes[k]!)};
    tipSettings = {};
    _gotMember = _gotRest = false;
  }

  void _open(String r) {
    _cancelDocs();
    _clearRestaurant();
    rid = r;
    _set(Phase.loading);
    final u = user!;
    _subs.add(db.doc('restaurants/$r/members/${u.uid}').snapshots().listen((s) {
      member = s.data() ?? {};
      _gotMember = true;
      _recompute();
    }, onError: (e) {
      error = '$e';
      _set(Phase.noRestaurant);
    }));
    _subs.add(db.doc('restaurants/$r').snapshots().listen((s) {
      restaurant = s.data() ?? {};
      _gotRest = true;
      _recompute();
    }, onError: (e) {
      error = '$e';
      _set(Phase.noRestaurant);
    }));
  }

  /// Switch to another restaurant this login belongs to.
  Future<void> switchTo(String r) async {
    if (r == rid) return;
    _open(r);
    try {
      await db.doc('users/$uid').set({'lastRid': r}, SetOptions(merge: true));
    } catch (_) {}
  }

  void _recompute() {
    if (!_gotMember || !_gotRest) return;
    if (member.isEmpty) {
      _set(Phase.noRestaurant);
      return;
    }
    final ok = subscriptionActive;
    if (ok && !_settingsOn) {
      _settingsOn = true;
      _subs.add(db.doc('restaurants/$rid/settings/inventory').snapshots().listen((s) {
        inventoryPositions = List<String>.from(s.data()?['positions'] ?? const []);
        notifyListeners();
      }, onError: (_) {}));
      _subs.add(db.doc('restaurants/$rid/settings/positions').snapshots().listen((s) {
        final list = s.data()?['list'];
        positions = list is List
            ? list.map((e) => Position.fromJson(Map<String, dynamic>.from(e as Map))).toList()
            : <Position>[];
        notifyListeners();
      }, onError: (_) {}));
      _subs.add(db.doc('restaurants/$rid/settings/schedule').snapshots().listen((s) {
        final m = s.data()?['defaultTimes'];
        if (m is Map) {
          defaultTimes = {
            for (final k in kShifts) k: List<String>.from((m[k] as List?) ?? kDefaultTimes[k]!),
          };
        }
        notifyListeners();
      }, onError: (_) {}));
      _subs.add(db.doc('restaurants/$rid/settings/tips').snapshots().listen((s) {
        tipSettings = s.data() ?? {};
        notifyListeners();
      }, onError: (_) {}));
    }
    _set(ok ? Phase.ready : Phase.locked);
  }

  // ── who am I ─────────────────────────────────────────────────────────────
  bool get subscriptionActive {
    if (isAdmin) return true;
    final s = restaurant['subscription'];
    if (s is! Map || s['active'] != true) return false;
    final pu = s['paidUntil'];
    if (pu is Timestamp && pu.toDate().isBefore(DateTime.now())) return false;
    return true;
  }

  String get role => (member['role'] ?? 'employee') as String;
  bool get isOwner => role == 'owner';
  bool get isManager => role == 'owner' || role == 'manager';
  String get uid => user?.uid ?? '';
  String get employeeId => (member['employeeId'] ?? '') as String;
  String get name {
    final n = (member['name'] ?? '') as String;
    return n.isNotEmpty ? n : (user?.email ?? '');
  }

  String get restaurantName => (restaurant['name'] ?? 'Restaurant') as String;
  List<String> get myPositions => List<String>.from(member['positions'] ?? const []);

  bool get canAddInventory =>
      isManager || member['canInventory'] == true || myPositions.any(inventoryPositions.contains);

  /// Position settings by name (positions not in the list get sensible defaults).
  Position position(String name) =>
      firstWhereOr(positions, (Position p) => p.name == name) ?? Position.guess(name);

  /// When someone in [pos] usually comes in and leaves for [shift].
  List<String> timesFor(String pos, String shift) {
    final t = position(pos).times[shift];
    if (t != null && t.length == 2 && t[0].isNotEmpty) return t;
    return defaultTimes[shift] ?? kDefaultTimes[shift] ?? const ['', ''];
  }

  // ── paths ────────────────────────────────────────────────────────────────
  CollectionReference<Map<String, dynamic>> col(String name) => db.collection('restaurants/$rid/$name');
  DocumentReference<Map<String, dynamic>> doc(String path) => db.doc('restaurants/$rid/$path');

  // ── actions ──────────────────────────────────────────────────────────────
  Future<void> signIn(String email, String password) =>
      auth.signInWithEmailAndPassword(email: email.trim(), password: password);

  Future<void> signOut() => auth.signOut();

  Future<void> sendReset(String email) => auth.sendPasswordResetEmail(email: email.trim());

  /// First sign-in of a restaurant owner: create the restaurant (it stays locked
  /// until Stamhad Software switches the subscription on).
  Future<void> setUpRestaurant(String restaurantName, String yourName) async {
    final u = user!;
    final ref = db.doc('restaurants/${u.uid}');
    final exists = await ref.get().then((s) => s.exists).catchError((_) => false);
    final b = db.batch();
    if (!exists) {
      b.set(ref, {'name': restaurantName.trim(), 'ownerUid': u.uid, 'createdAt': FieldValue.serverTimestamp()});
    }
    b.set(db.doc('restaurants/${u.uid}/members/${u.uid}'), {
      'role': 'owner',
      'name': yourName.trim(),
      'email': u.email,
      'employeeId': '',
      'positions': <String>[],
    });
    b.set(db.doc('users/${u.uid}/restaurants/${u.uid}'), {'name': restaurantName.trim(), 'role': 'owner'});
    b.set(db.doc('users/${u.uid}'), {'lastRid': u.uid}, SetOptions(merge: true));
    await b.commit();
    await reload();
  }
}

class SessionScope extends InheritedNotifier<Session> {
  const SessionScope({super.key, required Session session, required super.child}) : super(notifier: session);

  static Session of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<SessionScope>()!.notifier!;

  static Session read(BuildContext context) =>
      context.getInheritedWidgetOfExactType<SessionScope>()!.notifier!;
}
