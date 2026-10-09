import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../util.dart';
import '../widgets/common.dart';
import 'positions.dart';
import 'team.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final roleLabel = {'owner': 'Owner', 'manager': 'Manager'}[s.role] ?? 'Employee';
    return Scaffold(
      appBar: AppBar(title: Text(s.isManager ? 'Team' : 'Me')),
      body: ListView(padding: const EdgeInsets.only(bottom: 32), children: [
        Card(
          child: ListTile(
            leading: Avatar(initials(s.name), highlight: true),
            title: Text(s.name, style: const TextStyle(fontWeight: FontWeight.w700)),
            subtitle: Text('$roleLabel · ${s.restaurantName}\n${s.user?.email ?? ''}'),
            isThreeLine: true,
          ),
        ),
        if (s.memberships.length > 1 || s.isAdmin) ...[
          const SectionHeader('Your restaurants'),
          Card(
            child: Column(children: [
              for (final m in s.memberships)
                ListTile(
                  leading: Icon(m.rid == s.rid ? Icons.radio_button_checked : Icons.radio_button_off,
                      color: m.rid == s.rid ? kAccent : kFgSec),
                  title: Text(m.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text({'owner': 'Owner', 'manager': 'Manager'}[m.role] ?? 'Employee'),
                  onTap: () => s.switchTo(m.rid),
                ),
            ]),
          ),
        ],
        Align(
          alignment: Alignment.centerLeft,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: TextButton.icon(
              onPressed: () => s.reload(),
              icon: const Icon(Icons.mark_email_unread_outlined, size: 18),
              label: const Text('Check for invites from other restaurants'),
            ),
          ),
        ),
        if (s.isManager) ...[
          SectionHeader('Employees', trailing: TextButton.icon(
            onPressed: () => openEmployeeEditor(context),
            icon: const Icon(Icons.person_add_alt_1, size: 18),
            label: const Text('Add'),
          )),
          const EmployeeList(),
          const SectionHeader('Settings'),
          Card(
            child: Column(children: [
              ListTile(
                leading: const Icon(Icons.badge_outlined),
                title: const Text('Positions'),
                subtitle: const Text('Tip points and usual times (cooks earlier than servers…)'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openPositions(context),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.payments_outlined),
                title: const Text('Tip rules'),
                subtitle: Text((s.tipSettings['method'] ?? 'points') == 'time' ? 'By time worked × points' : 'By points only'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openTipRules(context),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.inventory_2_outlined),
                title: const Text('Who can add to inventory'),
                subtitle: Text(s.inventoryPositions.isEmpty
                    ? 'Managers, plus people you allow one by one'
                    : 'Managers, ${s.inventoryPositions.join(', ')}, plus people you allow'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openInventoryPermissions(context),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.schedule),
                title: const Text('Usual shift times'),
                subtitle: const Text('For positions without their own times'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openShiftTimes(context),
              ),
              if (s.isOwner) ...[
                const Divider(height: 1),
                ListTile(
                  leading: const Icon(Icons.storefront_outlined),
                  title: const Text('Restaurant name'),
                  subtitle: Text(s.restaurantName),
                  trailing: const Icon(Icons.edit_outlined),
                  onTap: () => _rename(context),
                ),
              ],
            ]),
          ),
        ],
        const SectionHeader('Account'),
        Card(
          child: Column(children: [
            ListTile(
              leading: const Icon(Icons.key_outlined),
              title: const Text('Change password'),
              subtitle: const Text('We email you a link'),
              onTap: () async {
                try {
                  await s.sendReset(s.user?.email ?? '');
                  if (context.mounted) toast(context, 'Check ${s.user?.email} for the link.');
                } catch (e) {
                  if (context.mounted) toast(context, friendlyError(e), error: true);
                }
              },
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.logout, color: kDanger),
              title: const Text('Sign out', style: TextStyle(color: kDanger)),
              onTap: () async {
                if (await confirm(context, 'Sign out?', 'You can sign in again any time.', yes: 'Sign out')) {
                  await s.signOut();
                }
              },
            ),
          ]),
        ),
        const SizedBox(height: 18),
        const Center(child: NumeLogo(width: 110)),
      ]),
    );
  }

  Future<void> _rename(BuildContext context) async {
    final s = SessionScope.read(context);
    final c = TextEditingController(text: s.restaurantName);
    final ok = await showDialog<bool>(
      context: context,
      builder: (d) => AlertDialog(
        title: const Text('Restaurant name'),
        content: TextField(controller: c, autofocus: true),
        actions: [
          TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Save')),
        ],
      ),
    );
    if (ok != true || c.text.trim().isEmpty) return;
    try {
      await s.db.doc('restaurants/${s.rid}').update({'name': c.text.trim()});
    } catch (e) {
      if (context.mounted) toast(context, friendlyError(e), error: true);
    }
  }
}

Future<void> openInventoryPermissions(BuildContext context) {
  return Navigator.of(context).push(MaterialPageRoute(builder: (_) => const _InventoryPermissions()));
}

class _InventoryPermissions extends StatelessWidget {
  const _InventoryPermissions();
  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Who can add to inventory')),
      body: StreamBuilder<QuerySnapshot<Json>>(
        stream: s.col('employees').snapshots(),
        builder: (c, snap) {
          final emps = (snap.data?.docs.map(Employee.from).where((e) => e.active).toList() ?? [])
            ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
          final positions = <String>{...s.positions.map((p) => p.name), for (final e in emps) ...e.positions}.toList()..sort();
          return ListView(padding: const EdgeInsets.only(bottom: 32), children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 8, 20, 0),
              child: Text(
                'Managers can always add. Turn on whole positions, or single people below. '
                'Everyone can see the order list and who added what.',
                style: TextStyle(color: kFgSec),
              ),
            ),
            const SectionHeader('By position'),
            if (positions.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 20),
                child: Text('Give employees positions first (Team → employee).'),
              ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Wrap(spacing: 8, runSpacing: 8, children: [
                for (final p in positions)
                  FilterChip(
                    label: Text(p),
                    selected: s.inventoryPositions.contains(p),
                    onSelected: (on) async {
                      final next = {...s.inventoryPositions};
                      on ? next.add(p) : next.remove(p);
                      try {
                        await s.doc('settings/inventory').set({'positions': next.toList()}, SetOptions(merge: true));
                      } catch (e) {
                        if (context.mounted) toast(context, friendlyError(e), error: true);
                      }
                    },
                  ),
              ]),
            ),
            const SectionHeader('Single people'),
            for (final e in emps)
              Card(
                child: SwitchListTile(
                  title: Text(e.name),
                  subtitle: Text(e.positions.any(s.inventoryPositions.contains)
                      ? 'Allowed by position (${e.positions.where(s.inventoryPositions.contains).join(', ')})'
                      : (e.positions.isEmpty ? 'No position' : e.positions.join(', '))),
                  value: e.canInventory || e.positions.any(s.inventoryPositions.contains),
                  onChanged: e.positions.any(s.inventoryPositions.contains)
                      ? null
                      : (on) => saveEmployeeAccess(context, e, canInventory: on),
                ),
              ),
          ]);
        },
      ),
    );
  }
}

Future<void> openShiftTimes(BuildContext context) {
  return Navigator.of(context).push(MaterialPageRoute(builder: (_) => const _ShiftTimes()));
}

class _ShiftTimes extends StatefulWidget {
  const _ShiftTimes();
  @override
  State<_ShiftTimes> createState() => _ShiftTimesState();
}

class _ShiftTimesState extends State<_ShiftTimes> {
  Map<String, List<String>> _t = {for (final k in kShifts) k: List.of(kDefaultTimes[k]!)};
  bool _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loaded) return;
    _loaded = true;
    SessionScope.read(context).doc('settings/schedule').get().then((d) {
      final m = d.data()?['defaultTimes'];
      if (m is Map && mounted) {
        setState(() => _t = {for (final k in kShifts) k: List<String>.from((m[k] as List?) ?? kDefaultTimes[k]!)});
      }
    }).catchError((_) {});
  }

  Future<void> _pick(String shift, int i) async {
    final cur = parseTime(_t[shift]![i]) ?? 12 * 60;
    final t = await showTimePicker(context: context, initialTime: TimeOfDay(hour: cur ~/ 60, minute: cur % 60));
    if (t == null) return;
    setState(() => _t[shift]![i] = fmtTime(t.hour * 60 + t.minute));
    try {
      await SessionScope.read(context).doc('settings/schedule').set({'defaultTimes': _t}, SetOptions(merge: true));
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Usual shift times')),
      body: ListView(children: [
        for (final k in kShifts)
          Card(
            child: ListTile(
              leading: ShiftPill(k),
              title: Row(children: [
                TextButton(onPressed: () => _pick(k, 0), child: Text(_t[k]![0])),
                const Text('to'),
                TextButton(onPressed: () => _pick(k, 1), child: Text(_t[k]![1])),
              ]),
            ),
          ),
      ]),
    );
  }
}
