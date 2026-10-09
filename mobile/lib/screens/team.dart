import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';

import '../firebase_options.dart';
import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../util.dart';
import '../widgets/common.dart';
import 'positions.dart';

/// Login status of one employee, from the members + invites the manager can see.
class Access {
  final String? memberUid; // joined
  final bool invited;
  final String role;
  const Access({this.memberUid, this.invited = false, this.role = 'employee'});
  bool get joined => memberUid != null;
}

class EmployeeList extends StatelessWidget {
  const EmployeeList({super.key});
  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: s.col('employees').snapshots(),
      builder: (c, es) => StreamBuilder<QuerySnapshot<Json>>(
        stream: s.col('members').snapshots(),
        builder: (c, ms) => StreamBuilder<QuerySnapshot<Json>>(
          stream: s.col('invites').snapshots(),
          builder: (c, inv) {
            if (es.hasError) return Empty(Icons.error_outline, 'Couldn\'t load employees', friendlyError(es.error!));
            if (!es.hasData) return const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()));
            final emps = es.data!.docs.map(Employee.from).toList()
              ..sort((a, b) {
                if (a.active != b.active) return a.active ? -1 : 1;
                return a.name.toLowerCase().compareTo(b.name.toLowerCase());
              });
            final access = accessMap(ms.data?.docs ?? const [], inv.data?.docs ?? const []);
            if (emps.isEmpty) {
              return const Padding(
                padding: EdgeInsets.all(20),
                child: Text('No employees yet. Tap Add to create the first one and invite them to the app.'),
              );
            }
            return Card(
              child: Column(children: [
                for (final e in emps) ...[
                  ListTile(
                    leading: Avatar(initials(e.name)),
                    title: Text(e.name,
                        style: TextStyle(fontWeight: FontWeight.w600, color: e.active ? null : kFgSec)),
                    subtitle: Text([
                      if (e.positions.isNotEmpty) e.positions.join(', '),
                      if (!e.active) 'not working here'
                    ].join(' · ')),
                    trailing: _AccessChip(access[e.id] ?? const Access()),
                    onTap: () => openEmployeeEditor(context, employee: e),
                  ),
                  if (e != emps.last) const Divider(height: 1, indent: 64),
                ],
              ]),
            );
          },
        ),
      ),
    );
  }
}

Map<String, Access> accessMap(List<Snap> members, List<Snap> invites) {
  final out = <String, Access>{};
  for (final i in invites) {
    final d = i.data() ?? {};
    final eid = (d['employeeId'] ?? '') as String;
    if (eid.isNotEmpty) out[eid] = Access(invited: true, role: (d['role'] ?? 'employee') as String);
  }
  for (final m in members) {
    final d = m.data() ?? {};
    final eid = (d['employeeId'] ?? '') as String;
    if (eid.isNotEmpty) out[eid] = Access(memberUid: m.id, role: (d['role'] ?? 'employee') as String);
  }
  return out;
}

class _AccessChip extends StatelessWidget {
  const _AccessChip(this.a);
  final Access a;
  @override
  Widget build(BuildContext context) {
    final (label, bg, fg) = a.joined
        ? (a.role == 'manager' ? 'Manager' : (a.role == 'owner' ? 'Owner' : 'On the app'), const Color(0xFFD1FAE5), const Color(0xFF065F46))
        : a.invited
            ? ('Invited', kWarnBg, kWarnFg)
            : ('No login', const Color(0xFFE5E7EB), const Color(0xFF374151));
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Text(label, style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w700)),
    );
  }
}

Future<void> openEmployeeEditor(BuildContext context, {Employee? employee}) {
  return Navigator.of(context)
      .push(MaterialPageRoute(fullscreenDialog: true, builder: (_) => _EmployeeEditor(employee: employee)));
}

/// Keep the login (member) and any open invite in step with the employee record,
/// so the security rules see the same positions / permission.
Future<void> saveEmployeeAccess(BuildContext context, Employee e,
    {bool? canInventory, List<String>? positions, String? role, String? name}) async {
  final s = SessionScope.read(context);
  final patch = <String, dynamic>{
    if (canInventory != null) 'canInventory': canInventory,
    if (positions != null) 'positions': positions,
    if (role != null) 'role': role,
    if (name != null) 'name': name,
  };
  if (patch.isEmpty) return;
  try {
    final b = s.db.batch();
    b.set(s.col('employees').doc(e.id), patch, SetOptions(merge: true));
    final ms = await s.col('members').where('employeeId', isEqualTo: e.id).get();
    for (final m in ms.docs) {
      if (m.data()['role'] == 'owner') {
        b.update(m.reference, Map.of(patch)..remove('role'));
      } else {
        b.update(m.reference, patch);
      }
    }
    final inv = await s.col('invites').where('employeeId', isEqualTo: e.id).get();
    for (final i in inv.docs) {
      b.update(i.reference, patch);
    }
    await b.commit();
  } catch (err) {
    if (context.mounted) toast(context, friendlyError(err), error: true);
  }
}

class _EmployeeEditor extends StatefulWidget {
  const _EmployeeEditor({this.employee});
  final Employee? employee;
  @override
  State<_EmployeeEditor> createState() => _EmployeeEditorState();
}

class _EmployeeEditorState extends State<_EmployeeEditor> {
  late final _name = TextEditingController(text: widget.employee?.name);
  late final _email = TextEditingController(text: widget.employee?.email);
  final _newPos = TextEditingController();
  late List<String> _positions = List.of(widget.employee?.positions ?? const []);
  late String _role = widget.employee?.role ?? 'employee';
  late bool _inv = widget.employee?.canInventory ?? false;
  late bool _active = widget.employee?.active ?? true;
  bool _busy = false;

  bool get _isNew => widget.employee == null;

  Future<String?> _save() async {
    final s = SessionScope.read(context);
    final name = _name.text.trim();
    if (name.isEmpty) {
      toast(context, 'Type a name.', error: true);
      return null;
    }
    final email = _email.text.trim().toLowerCase();
    if (email.isNotEmpty && !RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(email)) {
      toast(context, "That email doesn't look right.", error: true);
      return null;
    }
    setState(() => _busy = true);
    try {
      final ref = _isNew ? s.col('employees').doc() : s.col('employees').doc(widget.employee!.id);
      await ref.set({
        'name': name,
        'email': email,
        'positions': _positions,
        'role': _role,
        'canInventory': _inv,
        'active': _active,
        'updatedAt': FieldValue.serverTimestamp(),
      }, SetOptions(merge: true));
      if (!_isNew && mounted) {
        await saveEmployeeAccess(context,
            Employee(id: ref.id, name: name, positions: _positions),
            canInventory: _inv, positions: _positions, role: _role, name: name);
      }
      return ref.id;
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
      return null;
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _saveAndClose() async {
    if (await _save() != null && mounted) Navigator.pop(context);
  }

  /// Create the invite; make a login for the email if it doesn't have one; email them a link to set a password.
  Future<void> _invite() async {
    final s = SessionScope.read(context);
    final email = _email.text.trim().toLowerCase();
    if (email.isEmpty) {
      toast(context, 'Type their email first.', error: true);
      return;
    }
    final eid = await _save();
    if (eid == null || !mounted) return;
    setState(() => _busy = true);
    try {
      final b = s.db.batch();
      b.set(s.col('invites').doc(email), {
        'employeeId': eid,
        'role': _role,
        'name': _name.text.trim(),
        'positions': _positions,
        'canInventory': _inv,
        'invitedBy': s.name,
        'at': FieldValue.serverTimestamp(),
      });
      // "you're invited" pointer the person finds when they sign in (works even if they
      // already use NUME at another restaurant)
      b.set(s.db.doc('invites/$email/rids/${s.rid}'), {'rid': s.rid, 'name': s.restaurantName});
      await b.commit();
      final created = await _createLogin(email);
      if (created) {
        await s.auth.sendPasswordResetEmail(email: email);
      }
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Invite sent'),
          content: Text(created
              ? '${_name.text.trim()} gets an email at $email to set a password. Then they download NUME and sign in.'
              : '$email already has a NUME login (maybe at another restaurant). Next time they open NUME '
                  'or tap "Check for invites", ${s.restaurantName} is added to their app.'),
          actions: [FilledButton(onPressed: () => Navigator.pop(c), child: const Text('OK'))],
        ),
      );
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Uses a second Firebase connection so the manager stays signed in.
  Future<bool> _createLogin(String email) async {
    final app = await Firebase.initializeApp(
      name: 'invite${DateTime.now().millisecondsSinceEpoch}',
      options: DefaultFirebaseOptions.currentPlatform,
    );
    try {
      final a = FirebaseAuth.instanceFor(app: app);
      await a.createUserWithEmailAndPassword(email: email, password: randomPassword());
      await a.signOut();
      return true;
    } on FirebaseAuthException catch (e) {
      if (e.code == 'email-already-in-use') return false;
      rethrow;
    } finally {
      await app.delete();
    }
  }

  Future<void> _resend() async {
    final s = SessionScope.read(context);
    try {
      await s.auth.sendPasswordResetEmail(email: _email.text.trim());
      if (mounted) toast(context, 'Sent a password email to ${_email.text.trim()}.');
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    }
  }

  Future<void> _removeAccess(Access a) async {
    final s = SessionScope.read(context);
    final go = await confirm(context, 'Remove app access?',
        '${_name.text.trim()} won\'t be able to open ${s.restaurantName} in NUME any more. Their shifts and tips stay.',
        yes: 'Remove access', danger: true);
    if (!go) return;
    try {
      final b = s.db.batch();
      if (a.memberUid != null) {
        b.delete(s.col('members').doc(a.memberUid));
        b.delete(s.db.doc('users/${a.memberUid}/restaurants/${s.rid}'));
      }
      final inv = await s.col('invites').where('employeeId', isEqualTo: widget.employee!.id).get();
      for (final i in inv.docs) {
        b.delete(i.reference);
        b.delete(s.db.doc('invites/${i.id}/rids/${s.rid}'));
      }
      await b.commit();
      if (mounted) toast(context, 'App access removed.');
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: s.col('members').snapshots(),
      builder: (c, ms) => StreamBuilder<QuerySnapshot<Json>>(
        stream: s.col('invites').snapshots(),
        builder: (c, inv) {
          final a = _isNew
              ? const Access()
              : (accessMap(ms.data?.docs ?? const [], inv.data?.docs ?? const [])[widget.employee!.id] ??
                  const Access());
          final isOwner = a.role == 'owner';
          final byPosition = _positions.any(s.inventoryPositions.contains);
          return Scaffold(
            appBar: AppBar(title: Text(_isNew ? 'New employee' : _name.text)),
            body: AbsorbPointer(
              absorbing: _busy,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                TextField(controller: _name, textCapitalization: TextCapitalization.words,
                    decoration: const InputDecoration(labelText: 'Name')),
                const SizedBox(height: 12),
                TextField(controller: _email, keyboardType: TextInputType.emailAddress, autocorrect: false,
                    enabled: !a.joined,
                    decoration: InputDecoration(
                        labelText: 'Email (for their NUME login)',
                        helperText: a.joined ? 'They sign in with this email.' : null)),
                const SizedBox(height: 16),
                const Text('Positions', style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                Wrap(spacing: 6, runSpacing: 6, children: [
                  for (final p in {...s.positions.map((x) => x.name), ..._positions})
                    FilterChip(
                      label: Text(p),
                      selected: _positions.contains(p),
                      onSelected: (on) => setState(() => on ? _positions.add(p) : _positions.remove(p)),
                    ),
                ]),
                Row(children: [
                  Expanded(
                    child: TextField(
                      controller: _newPos,
                      textCapitalization: TextCapitalization.words,
                      decoration: const InputDecoration(hintText: 'Add a position (e.g. Server)', isDense: true),
                      onSubmitted: (_) => _addPos(),
                    ),
                  ),
                  IconButton(onPressed: _addPos, icon: const Icon(Icons.add_circle_outline)),
                ]),
                const SizedBox(height: 12),
                if (!isOwner)
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: 'employee', label: Text('Employee')),
                      ButtonSegment(value: 'manager', label: Text('Manager')),
                    ],
                    selected: {_role},
                    onSelectionChanged: (v) => setState(() => _role = v.first),
                  ),
                if (_role == 'manager' && !isOwner)
                  const Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Text('Managers can edit the schedule, approve days off, see everyone\'s tips and manage the team.',
                        style: TextStyle(color: kFgSec, fontSize: 13)),
                  ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Can add to inventory'),
                  subtitle: Text(byPosition ? 'Allowed by their position' : 'Add items to the order list'),
                  value: _inv || byPosition || _role == 'manager',
                  onChanged: byPosition || _role == 'manager' ? null : (v) => setState(() => _inv = v),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Works here'),
                  subtitle: const Text('Turn off when someone leaves (keeps their history)'),
                  value: _active,
                  onChanged: (v) => setState(() => _active = v),
                ),
                const SizedBox(height: 12),
                FilledButton(onPressed: _saveAndClose, child: const Text('Save')),
                const SizedBox(height: 20),
                const Divider(),
                const SizedBox(height: 8),
                const Text('NUME app', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                const SizedBox(height: 6),
                if (a.joined) ...[
                  const Text('On the app — they can see the schedule, their tips and request days off.',
                      style: TextStyle(color: kFgSec)),
                  if (!isOwner) ...[
                    TextButton.icon(onPressed: _resend, icon: const Icon(Icons.key_outlined),
                        label: const Text('Send a "set password" email')),
                    TextButton.icon(
                      onPressed: () => _removeAccess(a),
                      icon: const Icon(Icons.person_remove_outlined, color: kDanger),
                      label: const Text('Remove app access', style: TextStyle(color: kDanger)),
                    ),
                  ],
                ] else if (a.invited) ...[
                  const Text('Invited — waiting for them to sign in.', style: TextStyle(color: kFgSec)),
                  TextButton.icon(onPressed: _invite, icon: const Icon(Icons.send_outlined),
                      label: const Text('Send the invite again')),
                  TextButton.icon(onPressed: () => _removeAccess(a),
                      icon: const Icon(Icons.close, color: kDanger),
                      label: const Text('Cancel invite', style: TextStyle(color: kDanger))),
                ] else ...[
                  const Text('Invite them so they can see the schedule and their tips, and request days off.',
                      style: TextStyle(color: kFgSec)),
                  const SizedBox(height: 8),
                  FilledButton.tonalIcon(onPressed: _invite, icon: const Icon(Icons.send_outlined),
                      label: const Text('Invite to the app')),
                ],
              ]),
            ),
          );
        },
      ),
    );
  }

  void _addPos() {
    final p = _newPos.text.trim();
    if (p.isEmpty) return;
    setState(() {
      if (!_positions.contains(p)) _positions.add(p);
      _newPos.clear();
    });
    addPositions(context, [p]);
  }
}
