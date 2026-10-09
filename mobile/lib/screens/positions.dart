import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../tipsplit.dart';
import '../util.dart';
import '../widgets/common.dart';

Future<void> _saveList(Session s, List<Position> list) =>
    s.doc('settings/positions').set({'list': [for (final p in list) p.toJson()]}, SetOptions(merge: true));

/// Add positions (by name) that aren't in the restaurant's list yet, with sensible tip settings.
Future<void> addPositions(BuildContext context, List<String> names) async {
  final s = SessionScope.read(context);
  final have = s.positions.map((p) => p.name.toLowerCase()).toSet();
  final add = [for (final n in names) if (n.trim().isNotEmpty && !have.contains(n.trim().toLowerCase())) Position.guess(n.trim())];
  if (add.isEmpty) return;
  try {
    await _saveList(s, [...s.positions, ...add]);
  } catch (e) {
    if (context.mounted) toast(context, friendlyError(e), error: true);
  }
}

Future<void> openPositions(BuildContext context) =>
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PositionsScreen()));

class PositionsScreen extends StatelessWidget {
  const PositionsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final list = [...s.positions]..sort((a, b) {
        if (a.department != b.department) return a.department.compareTo(b.department) * -1; // FOH first
        return a.name.toLowerCase().compareTo(b.name.toLowerCase());
      });
    return Scaffold(
      appBar: AppBar(title: const Text('Positions')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _new(context),
        icon: const Icon(Icons.add),
        label: const Text('Position'),
      ),
      body: ListView(padding: const EdgeInsets.only(bottom: 96), children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(20, 4, 20, 4),
          child: Text(
            'Each position has tip points and the times it usually comes in and leaves '
            '(e.g. cooks earlier than servers). Those times fill in automatically when you plan a day.',
            style: TextStyle(color: kFgSec),
          ),
        ),
        if (list.isEmpty)
          Padding(
            padding: const EdgeInsets.all(16),
            child: FilledButton.tonalIcon(
              onPressed: () => addPositions(context, kStarterPositions),
              icon: const Icon(Icons.auto_awesome),
              label: const Text('Add the usual positions (Server, Bartender, Cook…)'),
            ),
          ),
        for (final p in list)
          Card(
            child: ListTile(
              title: Text(p.name, style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text([
                p.isKitchen ? 'Kitchen' : 'Floor',
                if (!p.isKitchen) '${_n(p.points)} pts',
                if (p.barTips) 'shares bar tips',
                if (p.barbackPct > 0) '${_n(p.barbackPct)}% of bar',
                for (final sh in kShifts)
                  if (p.times[sh] != null && p.times[sh]![0].isNotEmpty)
                    '$sh ${shortTime(p.times[sh]![0])}–${shortTime(p.times[sh]![1])}',
              ].join(' · ')),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => _PositionEditor(p))),
            ),
          ),
      ]),
    );
  }

  Future<void> _new(BuildContext context) async {
    final c = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (d) => AlertDialog(
        title: const Text('New position'),
        content: TextField(
            controller: c, autofocus: true, textCapitalization: TextCapitalization.words,
            decoration: const InputDecoration(hintText: 'e.g. Line cook, Host')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Add')),
        ],
      ),
    );
    if (ok == true && c.text.trim().isNotEmpty && context.mounted) await addPositions(context, [c.text]);
  }
}

String _n(double v) => v == v.roundToDouble() ? v.toInt().toString() : v.toString();

class _PositionEditor extends StatefulWidget {
  const _PositionEditor(this.p);
  final Position p;
  @override
  State<_PositionEditor> createState() => _PositionEditorState();
}

class _PositionEditorState extends State<_PositionEditor> {
  late Position _p = widget.p;
  late final _pts = TextEditingController(text: _n(widget.p.points));
  late final _pct = TextEditingController(text: _n(widget.p.barbackPct));

  Future<void> _pick(String shift, int i) async {
    final s = SessionScope.read(context);
    final cur = parseTime(_p.times[shift]?[i]) ?? parseTime(s.defaultTimes[shift]?[i]) ?? 12 * 60;
    final t = await showTimePicker(context: context, initialTime: TimeOfDay(hour: cur ~/ 60, minute: cur % 60));
    if (t == null) return;
    final cur2 = List<String>.from(_p.times[shift] ?? s.defaultTimes[shift] ?? const ['', '']);
    cur2[i] = fmtTime(t.hour * 60 + t.minute);
    setState(() => _p = _p.copyWith(times: {..._p.times, shift: cur2}));
  }

  Future<void> _save() async {
    final s = SessionScope.read(context);
    final p = _p.copyWith(
      points: double.tryParse(_pts.text.trim()) ?? 0,
      barbackPct: double.tryParse(_pct.text.trim()) ?? 0,
    );
    final list = [for (final x in s.positions) x.name == widget.p.name ? p : x];
    try {
      await _saveList(s, list);
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    }
  }

  Future<void> _delete() async {
    final s = SessionScope.read(context);
    final go = await confirm(context, 'Delete ${widget.p.name}?',
        'Employees keep it on their record, but it gets no tip points and no usual times.',
        yes: 'Delete', danger: true);
    if (!go) return;
    try {
      await _saveList(s, [for (final x in s.positions) if (x.name != widget.p.name) x]);
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.p.name),
        actions: [IconButton(onPressed: _delete, icon: const Icon(Icons.delete_outline, color: kDanger))],
      ),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'FOH', label: Text('Floor / bar'), icon: Icon(Icons.room_service_outlined)),
            ButtonSegment(value: 'BOH', label: Text('Kitchen'), icon: Icon(Icons.soup_kitchen_outlined)),
          ],
          selected: {_p.department},
          onSelectionChanged: (v) => setState(() => _p = _p.copyWith(department: v.first)),
        ),
        const SizedBox(height: 16),
        if (!_p.isKitchen) ...[
          TextField(
            controller: _pts,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Floor tip points', helperText: 'Server 10, Runner 7, Busser 5… 0 = no floor tips'),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Shares the bar tips'),
            subtitle: const Text('Bartenders'),
            value: _p.barTips,
            onChanged: (v) => setState(() => _p = _p.copyWith(barTips: v)),
          ),
          TextField(
            controller: _pct,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
                labelText: '% of the bar tips', helperText: 'Barbacks: taken off the top before bartenders split the rest'),
          ),
        ] else
          const Text('Kitchen positions don\'t share floor or bar tips.', style: TextStyle(color: kFgSec)),
        const SizedBox(height: 20),
        const Text('Usual times', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        const Text('Used when you plan a day. Leave as the shift\'s usual time if it\'s the same.',
            style: TextStyle(color: kFgSec)),
        const SizedBox(height: 6),
        for (final sh in kShifts)
          Card(
            margin: const EdgeInsets.symmetric(vertical: 4),
            child: ListTile(
              leading: ShiftPill(sh),
              title: Row(children: [
                TextButton(onPressed: () => _pick(sh, 0), child: Text((_p.times[sh] ?? s.defaultTimes[sh]!)[0])),
                const Text('to'),
                TextButton(onPressed: () => _pick(sh, 1), child: Text((_p.times[sh] ?? s.defaultTimes[sh]!)[1])),
              ]),
              subtitle: _p.times[sh] == null ? const Text('the shift\'s usual time') : null,
              trailing: _p.times[sh] == null
                  ? null
                  : IconButton(
                      tooltip: 'Use the shift\'s usual time',
                      icon: const Icon(Icons.undo),
                      onPressed: () => setState(() => _p = _p.copyWith(times: Map.of(_p.times)..remove(sh))),
                    ),
            ),
          ),
        const SizedBox(height: 16),
        FilledButton(onPressed: _save, child: const Text('Save')),
      ]),
    );
  }
}

// ── Tip rules ────────────────────────────────────────────────────────────────
Future<void> openTipRules(BuildContext context) =>
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const _TipRules()));

class _TipRules extends StatelessWidget {
  const _TipRules();

  Future<void> _set(BuildContext context, Map<String, dynamic> patch) async {
    try {
      await SessionScope.read(context).doc('settings/tips').set(patch, SetOptions(merge: true));
    } catch (e) {
      if (context.mounted) toast(context, friendlyError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final method = (s.tipSettings['method'] ?? 'points') as String;
    final fs = Map<String, dynamic>.from(s.tipSettings['fullShare'] ?? kFullShareDefault);
    final ts = Map<String, dynamic>.from(s.tipSettings['tipStart'] ?? kTipStartDefault);
    Future<void> pick(String key, Map<String, dynamic> m, String sh) async {
      final cur = parseTime(m[sh] as String?) ?? 23 * 60;
      final t = await showTimePicker(context: context, initialTime: TimeOfDay(hour: cur ~/ 60, minute: cur % 60));
      if (t == null || !context.mounted) return;
      await _set(context, {key: {...m, sh: fmtTime(t.hour * 60 + t.minute)}});
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Tip rules')),
      body: ListView(padding: const EdgeInsets.only(bottom: 32), children: [
        const SectionHeader('How floor tips are split'),
        Card(
          child: Column(children: [
            RadioListTile<String>(
              value: 'points', groupValue: method,
              title: const Text('By points only'),
              subtitle: const Text('Everyone on the shift gets their position\'s points'),
              onChanged: (v) => _set(context, {'method': v}),
            ),
            RadioListTile<String>(
              value: 'time', groupValue: method,
              title: const Text('By time worked × points'),
              subtitle: const Text('Who came earlier or stayed longer gets more'),
              onChanged: (v) => _set(context, {'method': v}),
            ),
          ]),
        ),
        if (method == 'time') ...[
          const SectionHeader('Tip clock'),
          for (final sh in kShifts)
            Card(
              child: ListTile(
                leading: ShiftPill(sh),
                title: Wrap(crossAxisAlignment: WrapCrossAlignment.center, children: [
                  const Text('starts '),
                  TextButton(onPressed: () => pick('tipStart', ts, sh), child: Text((ts[sh] ?? 'clock-in') as String)),
                  const Text('stops '),
                  TextButton(onPressed: () => pick('fullShare', fs, sh), child: Text((fs[sh] ?? 'clock-out') as String)),
                ]),
                trailing: IconButton(
                  tooltip: 'Use real clock-in / clock-out',
                  icon: const Icon(Icons.undo),
                  onPressed: () => _set(context, {'tipStart': {...ts, sh: null}, 'fullShare': {...fs, sh: null}}),
                ),
              ),
            ),
          const Padding(
            padding: EdgeInsets.fromLTRB(20, 6, 20, 0),
            child: Text('Coming in before the start counts from the start. Anyone still there at the stop time gets the full share.',
                style: TextStyle(color: kFgSec)),
          ),
        ],
      ]),
    );
  }
}
