import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../util.dart';
import '../widgets/common.dart';

Future<void> openShiftEditor(BuildContext context, {required DateTime monday, Shift? shift}) {
  return Navigator.of(context).push(MaterialPageRoute(
    fullscreenDialog: true,
    builder: (_) => ShiftEditor(monday: monday, shift: shift),
  ));
}

class ShiftEditor extends StatefulWidget {
  const ShiftEditor({super.key, required this.monday, this.shift});
  final DateTime monday;
  final Shift? shift;
  @override
  State<ShiftEditor> createState() => _ShiftEditorState();
}

class _ShiftEditorState extends State<ShiftEditor> {
  String? _emp;
  late String _date;
  String _type = 'Dinner';
  String _position = '';
  String _start = '';
  String _end = '';
  final _note = TextEditingController();
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    final x = widget.shift;
    final today = dateOnly(DateTime.now());
    final inWeek = !today.isBefore(widget.monday) && today.isBefore(addDays(widget.monday, 7));
    _date = x?.date ?? ymd(inWeek ? today : widget.monday);
    if (x != null) {
      _emp = x.employeeId;
      _type = x.shift;
      _position = x.position;
      _start = x.start;
      _end = x.end;
      _note.text = x.note;
    }
    if (x == null) WidgetsBinding.instance.addPostFrameCallback((_) => _applyDefaults());
  }

  void _applyDefaults() {
    final t = SessionScope.read(context).timesFor(_position, _type);
    setState(() {
      _start = t[0];
      _end = t[1];
    });
  }

  Future<void> _pick(bool start) async {
    final cur = parseTime(start ? _start : _end) ?? (start ? 16 * 60 : 23 * 60);
    final t = await showTimePicker(context: context, initialTime: TimeOfDay(hour: cur ~/ 60, minute: cur % 60));
    if (t == null) return;
    setState(() {
      final v = fmtTime(t.hour * 60 + t.minute);
      if (start) {
        _start = v;
      } else {
        _end = v;
      }
    });
  }

  Future<void> _save(List<Employee> emps) async {
    final s = SessionScope.read(context);
    final e = firstWhereOr(emps, (Employee x) => x.id == _emp);
    if (e == null) {
      toast(context, 'Pick who works this shift.', error: true);
      return;
    }
    setState(() => _busy = true);
    try {
      // warn about an approved day off
      final offs = await s.col('timeoff').where('status', isEqualTo: 'approved').get();
      final clash = offs.docs.map(TimeOff.from).any((t) => t.employeeId == e.id && t.from.compareTo(_date) <= 0 && _date.compareTo(t.to) <= 0);
      if (clash && mounted) {
        final go = await confirm(context, '${e.name} has this day off',
            'Their day-off request for ${shortDay(parseYmd(_date))} was approved. Schedule them anyway?',
            yes: 'Schedule anyway');
        if (!go) return;
      }
      final data = Shift(
        id: widget.shift?.id ?? '',
        week: ymd(mondayOf(parseYmd(_date))),
        date: _date,
        employeeId: e.id,
        employeeName: e.name,
        position: _position,
        shift: _type,
        start: _start,
        end: _end,
        note: _note.text.trim(),
      ).toJson()
        ..['updatedBy'] = s.name
        ..['updatedAt'] = FieldValue.serverTimestamp();
      if (widget.shift == null) {
        await s.col('shifts').add(data);
      } else {
        await s.col('shifts').doc(widget.shift!.id).set(data);
      }
      if (mounted) Navigator.pop(context);
    } catch (err) {
      if (mounted) toast(context, friendlyError(err), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _delete() async {
    final s = SessionScope.read(context);
    final go = await confirm(context, 'Delete this shift?', '${widget.shift!.employeeName}, ${shortDay(parseYmd(_date))}',
        yes: 'Delete', danger: true);
    if (!go) return;
    try {
      await s.col('shifts').doc(widget.shift!.id).delete();
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: s.col('employees').snapshots(),
      builder: (c, snap) {
        final emps = (snap.data?.docs.map(Employee.from).where((e) => e.active).toList() ?? [])
          ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
        final emp = firstWhereOr(emps, (Employee x) => x.id == _emp);
        final positions = <String>{...?emp?.positions, if (_position.isNotEmpty) _position}.toList();
        return Scaffold(
          appBar: AppBar(
            title: Text(widget.shift == null ? 'New shift' : 'Edit shift'),
            actions: [
              if (widget.shift != null)
                IconButton(onPressed: _delete, icon: const Icon(Icons.delete_outline, color: kDanger)),
            ],
          ),
          body: ListView(padding: const EdgeInsets.all(16), children: [
            DropdownButtonFormField<String>(
              key: ValueKey('emp-${emps.length}'),
              initialValue: emps.any((x) => x.id == _emp) ? _emp : null,
              decoration: const InputDecoration(labelText: 'Who'),
              items: [for (final e in emps) DropdownMenuItem(value: e.id, child: Text(e.name))],
              onChanged: (v) => setState(() {
                _emp = v;
                final e2 = firstWhereOr(emps, (Employee x) => x.id == v);
                if (e2 != null && !e2.positions.contains(_position)) {
                  _position = e2.positions.isNotEmpty ? e2.positions.first : '';
                }
                if (widget.shift == null) {
                  final t = SessionScope.read(context).timesFor(_position, _type);
                  _start = t[0];
                  _end = t[1];
                }
              }),
            ),
            if (emps.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('No employees yet — add them in Team first.', style: TextStyle(color: kDanger)),
              ),
            const SizedBox(height: 16),
            const Text('Day', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (var i = 0; i < 7; i++)
                ChoiceChip(
                  label: Text(shortDay(addDays(widget.monday, i)).split(',').first +
                      ' ${addDays(widget.monday, i).day}'),
                  selected: _date == ymd(addDays(widget.monday, i)),
                  onSelected: (_) => setState(() => _date = ymd(addDays(widget.monday, i))),
                ),
            ]),
            const SizedBox(height: 16),
            const Text('Shift', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            SegmentedButton<String>(
              segments: [for (final k in kShifts) ButtonSegment(value: k, label: Text(k))],
              selected: {_type},
              onSelectionChanged: (v) {
                _type = v.first;
                _applyDefaults();
              },
            ),
            const SizedBox(height: 16),
            if (positions.isNotEmpty)
              DropdownButtonFormField<String>(
                key: ValueKey('pos-$_emp-${positions.length}'),
                initialValue: positions.contains(_position) ? _position : null,
                decoration: const InputDecoration(labelText: 'Position'),
                items: [for (final p in positions) DropdownMenuItem(value: p, child: Text(p))],
                onChanged: (v) {
                  _position = v ?? '';
                  _applyDefaults();
                },
              ),
            const SizedBox(height: 16),
            Row(children: [
              Expanded(child: _TimeBox(label: 'Start', value: _start, onTap: () => _pick(true))),
              const SizedBox(width: 12),
              Expanded(child: _TimeBox(label: 'End', value: _end, onTap: () => _pick(false))),
            ]),
            if (_start.isNotEmpty && _end.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(hoursText(shiftHours(_start, _end)), style: const TextStyle(color: kFgSec)),
              ),
            const SizedBox(height: 16),
            TextField(controller: _note, decoration: const InputDecoration(labelText: 'Note (optional)')),
            const SizedBox(height: 24),
            FilledButton(onPressed: _busy ? null : () => _save(emps), child: const Text('Save')),
          ]),
        );
      },
    );
  }
}

class _TimeBox extends StatelessWidget {
  const _TimeBox({required this.label, required this.value, required this.onTap});
  final String label, value;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: InputDecorator(
        decoration: InputDecoration(labelText: label, suffixIcon: const Icon(Icons.schedule)),
        child: Text(value.isEmpty ? '—' : value, style: const TextStyle(fontSize: 16)),
      ),
    );
  }
}
