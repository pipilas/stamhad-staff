import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../util.dart';
import '../widgets/common.dart';

Future<void> openDayPlanner(BuildContext context, {required DateTime monday, String? date}) {
  return Navigator.of(context).push(MaterialPageRoute(
    fullscreenDialog: true,
    builder: (_) => DayPlanner(monday: monday, date: date),
  ));
}

class _Pick {
  String position, start, end;
  final String? shiftId; // already on the schedule
  _Pick(this.position, this.start, this.end, [this.shiftId]);
}

/// Plan one day: pick the shift, tick who works. Times come from each position's usual times.
class DayPlanner extends StatefulWidget {
  const DayPlanner({super.key, required this.monday, this.date});
  final DateTime monday;
  final String? date;
  @override
  State<DayPlanner> createState() => _DayPlannerState();
}

class _DayPlannerState extends State<DayPlanner> {
  late String _date;
  String _shift = 'Dinner';
  final Map<String, _Pick> _picked = {}; // employeeId -> pick
  Map<String, Shift> _existing = {}; // employeeId -> shift already saved
  String _loadedKey = '';
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    final today = dateOnly(DateTime.now());
    final inWeek = !today.isBefore(widget.monday) && today.isBefore(addDays(widget.monday, 7));
    _date = widget.date ?? ymd(inWeek ? today : widget.monday);
    final wd = parseYmd(_date).weekday;
    _shift = wd >= 6 ? 'Brunch' : 'Dinner';
  }

  void _load(List<Shift> dayShifts, List<Employee> emps) {
    final key = '$_date|$_shift';
    if (key == _loadedKey) return;
    _loadedKey = key;
    _picked.clear();
    _existing = {for (final x in dayShifts.where((x) => x.shift == _shift)) x.employeeId: x};
    _existing.forEach((eid, x) => _picked[eid] = _Pick(x.position, x.start, x.end, x.id));
  }

  _Pick _defaultFor(Session s, Employee e) {
    final pos = e.positions.isNotEmpty ? e.positions.first : '';
    final t = s.timesFor(pos, _shift);
    return _Pick(pos, t[0], t[1]);
  }

  Future<void> _editTimes(Session s, Employee e) async {
    final p = _picked[e.id]!;
    Future<String?> pick(String cur, String label) async {
      final m = parseTime(cur) ?? 16 * 60;
      final t = await showTimePicker(
          context: context, helpText: label, initialTime: TimeOfDay(hour: m ~/ 60, minute: m % 60));
      return t == null ? null : fmtTime(t.hour * 60 + t.minute);
    }

    final a = await pick(p.start, '${e.name} comes in');
    if (a == null || !mounted) return;
    final b = await pick(p.end, '${e.name} leaves');
    if (b == null) return;
    setState(() {
      p.start = a;
      p.end = b;
    });
  }

  Future<void> _save(Session s, List<Employee> emps) async {
    setState(() => _busy = true);
    try {
      final b = s.db.batch();
      final week = ymd(mondayOf(parseYmd(_date)));
      var added = 0, changed = 0, removed = 0;
      for (final e in emps) {
        final p = _picked[e.id];
        final had = _existing[e.id];
        if (p == null && had != null) {
          b.delete(s.col('shifts').doc(had.id));
          removed++;
        } else if (p != null) {
          final data = Shift(
            id: '',
            week: week,
            date: _date,
            employeeId: e.id,
            employeeName: e.name,
            position: p.position,
            shift: _shift,
            start: p.start,
            end: p.end,
            note: had?.note ?? '',
          ).toJson()
            ..['updatedBy'] = s.name
            ..['updatedAt'] = FieldValue.serverTimestamp();
          if (had == null) {
            b.set(s.col('shifts').doc(), data);
            added++;
          } else if (had.position != p.position || had.start != p.start || had.end != p.end) {
            b.set(s.col('shifts').doc(had.id), data);
            changed++;
          }
        }
      }
      await b.commit();
      _loadedKey = ''; // reload from what's saved
      if (mounted) {
        toast(context, [
          if (added > 0) 'added $added',
          if (changed > 0) 'changed $changed',
          if (removed > 0) 'removed $removed',
        ].join(', ').let((t) => t.isEmpty ? 'No changes' : '${shortDay(parseYmd(_date))} $_shift: $t'));
      }
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final week = ymd(mondayOf(parseYmd(_date)));
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: s.col('employees').snapshots(),
      builder: (c, es) => StreamBuilder<QuerySnapshot<Json>>(
        stream: s.col('shifts').where('week', isEqualTo: week).snapshots(),
        builder: (c, ss) => StreamBuilder<QuerySnapshot<Json>>(
          stream: s.col('timeoff').where('status', isEqualTo: 'approved').snapshots(),
          builder: (c, os) {
            final emps = (es.data?.docs.map(Employee.from).where((e) => e.active).toList() ?? [])
              ..sort((a, b) {
                final pa = a.positions.isEmpty ? '~' : a.positions.first, pb = b.positions.isEmpty ? '~' : b.positions.first;
                final ka = s.position(pa).isKitchen ? 1 : 0, kb = s.position(pb).isKitchen ? 1 : 0;
                if (ka != kb) return ka - kb;
                final o = pa.compareTo(pb);
                return o != 0 ? o : a.name.toLowerCase().compareTo(b.name.toLowerCase());
              });
            final dayShifts = (ss.data?.docs.map(Shift.from).toList() ?? []).where((x) => x.date == _date).toList();
            if (ss.hasData && es.hasData) _load(dayShifts, emps);
            final off = {
              for (final t in os.data?.docs.map(TimeOff.from) ?? const <TimeOff>[])
                if (t.from.compareTo(_date) <= 0 && _date.compareTo(t.to) <= 0) t.employeeId
            };
            final otherShift = {for (final x in dayShifts.where((x) => x.shift != _shift)) x.employeeId: x.shift};
            return Scaffold(
              appBar: AppBar(title: const Text('Plan a day')),
              bottomNavigationBar: SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 6, 16, 10),
                  child: FilledButton.icon(
                    onPressed: _busy || !es.hasData ? null : () => _save(s, emps),
                    icon: const Icon(Icons.check),
                    label: Text('Save ${shortDay(parseYmd(_date))} · $_shift (${_picked.length})'),
                  ),
                ),
              ),
              body: ListView(padding: const EdgeInsets.only(bottom: 16), children: [
                SizedBox(
                  height: 56,
                  child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 12), children: [
                    for (var i = 0; i < 7; i++)
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 8),
                        child: ChoiceChip(
                          label: Text('${kDays[i].substring(0, 3)} ${addDays(widget.monday, i).day}'),
                          selected: _date == ymd(addDays(widget.monday, i)),
                          onSelected: (_) => setState(() => _date = ymd(addDays(widget.monday, i))),
                        ),
                      ),
                  ]),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: SegmentedButton<String>(
                    segments: [for (final k in kShifts) ButtonSegment(value: k, label: Text(k))],
                    selected: {_shift},
                    onSelectionChanged: (v) => setState(() => _shift = v.first),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 8, 0),
                  child: Row(children: [
                    Expanded(
                      child: Text('Tick who works. Times come from each position (Team → Positions); tap a time to change it.',
                          style: const TextStyle(color: kFgSec, fontSize: 13)),
                    ),
                    TextButton(
                      onPressed: () => setState(() {
                        for (final e in emps) {
                          if (!off.contains(e.id)) _picked.putIfAbsent(e.id, () => _defaultFor(s, e));
                        }
                      }),
                      child: const Text('All'),
                    ),
                    TextButton(onPressed: () => setState(_picked.clear), child: const Text('None')),
                  ]),
                ),
                if (!es.hasData) const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
                if (es.hasData && emps.isEmpty)
                  const Empty(Icons.group_add_outlined, 'No employees yet', 'Add them in Team first.'),
                ..._rows(s, emps, off, otherShift),
              ]),
            );
          },
        ),
      ),
    );
  }

  List<Widget> _rows(Session s, List<Employee> emps, Set<String> off, Map<String, String> otherShift) {
    final out = <Widget>[];
    String? group;
    for (final e in emps) {
      final g = e.positions.isEmpty ? 'No position' : e.positions.first;
      if (g != group) {
        group = g;
        out.add(SectionHeader(g));
      }
      final p = _picked[e.id];
      final isOff = off.contains(e.id);
      out.add(Card(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 3),
        color: p != null ? const Color(0xFFEEF0FF) : null,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: Row(children: [
            Checkbox(
              value: p != null,
              onChanged: (v) => setState(() {
                if (v == true) {
                  _picked[e.id] = _defaultFor(s, e);
                } else {
                  _picked.remove(e.id);
                }
              }),
            ),
            Expanded(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => setState(() => p == null ? _picked[e.id] = _defaultFor(s, e) : _picked.remove(e.id)),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(e.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                  if (isOff || otherShift[e.id] != null)
                    Text(isOff ? 'Day off (approved)' : 'Also on ${otherShift[e.id]}',
                        style: TextStyle(fontSize: 12, color: isOff ? kWarnFg : kFgSec)),
                ]),
              ),
            ),
            if (p != null && e.positions.length > 1)
              DropdownButton<String>(
                value: e.positions.contains(p.position) ? p.position : e.positions.first,
                underline: const SizedBox.shrink(),
                items: [for (final x in e.positions) DropdownMenuItem(value: x, child: Text(x, style: const TextStyle(fontSize: 13)))],
                onChanged: (v) => setState(() {
                  if (v == null) return;
                  p.position = v;
                  final t = s.timesFor(v, _shift);
                  p.start = t[0];
                  p.end = t[1];
                }),
              ),
            if (p != null)
              TextButton(
                onPressed: () => _editTimes(s, e),
                child: Text('${shortTime(p.start)}–${shortTime(p.end)}'),
              ),
            const SizedBox(width: 6),
          ]),
        ),
      ));
    }
    return out;
  }
}

extension _Let<T> on T {
  R let<R>(R Function(T) f) => f(this);
}
