import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../tipsplit.dart';
import '../util.dart';
import '../widgets/common.dart';
import 'day_planner.dart';

Future<void> openDayTips(BuildContext context, {String? date}) => Navigator.of(context)
    .push(MaterialPageRoute(fullscreenDialog: true, builder: (_) => DayTipsScreen(date: date)));

/// Managers: type the day's floor and bar tips; the app splits them like the desktop does
/// and everyone sees their share under Tips.
class DayTipsScreen extends StatefulWidget {
  const DayTipsScreen({super.key, this.date});
  final String? date;
  @override
  State<DayTipsScreen> createState() => _DayTipsScreenState();
}

class _DayTipsScreenState extends State<DayTipsScreen> {
  late String _date = widget.date ?? ymd(DateTime.now());
  String _shift = 'Dinner';
  final _floor = TextEditingController();
  final _bar = TextEditingController();
  Map<String, List<String>> _worked = {}; // shiftId -> [in, out] (when different from the schedule)
  String _loadedKey = '';
  Map<String, dynamic> _day = {};
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _shift = parseYmd(_date).weekday >= 6 ? 'Brunch' : 'Dinner';
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadDay());
  }

  Future<void> _loadDay() async {
    final s = SessionScope.read(context);
    final key = '$_date|$_shift';
    try {
      final d = await s.doc('days/$_date').get();
      _day = d.data() ?? {};
    } catch (_) {
      _day = {};
    }
    if (!mounted) return;
    final t = ((_day['tips'] ?? {}) as Map)[_shift];
    final w = ((_day['worked'] ?? {}) as Map)[_shift];
    setState(() {
      _loadedKey = key;
      _floor.text = t is Map && t['floor'] != null ? _num(t['floor']) : '';
      _bar.text = t is Map && t['bar'] != null ? _num(t['bar']) : '';
      _worked = w is Map
          ? {for (final e in w.entries) '${e.key}': List<String>.from(e.value as List)}
          : {};
    });
  }

  String _num(dynamic v) {
    final d = (v as num).toDouble();
    return d == d.roundToDouble() ? d.toInt().toString() : d.toStringAsFixed(2);
  }

  double _money(TextEditingController c) => double.tryParse(c.text.replaceAll(RegExp(r'[^0-9.]'), '')) ?? 0;

  void _change({String? date, String? shift}) {
    setState(() {
      if (date != null) _date = date;
      if (shift != null) _shift = shift;
    });
    _loadDay();
  }

  List<String> _times(Shift x) => _worked[x.id] ?? [x.start, x.end];

  Future<void> _editTimes(Shift x) async {
    final cur = _times(x);
    Future<String?> pick(String v, String label) async {
      final m = parseTime(v) ?? 16 * 60;
      final t = await showTimePicker(context: context, helpText: label, initialTime: TimeOfDay(hour: m ~/ 60, minute: m % 60));
      return t == null ? null : fmtTime(t.hour * 60 + t.minute);
    }

    final a = await pick(cur[0], '${x.employeeName} clocked in');
    if (a == null || !mounted) return;
    final b = await pick(cur[1], '${x.employeeName} clocked out');
    if (b == null) return;
    setState(() => _worked[x.id] = [a, b]);
  }

  SplitResult _split(Session s, List<Shift> people) {
    final ts = s.tipSettings;
    final fs = Map<String, dynamic>.from(ts['fullShare'] ?? kFullShareDefault);
    final st = Map<String, dynamic>.from(ts['tipStart'] ?? kTipStartDefault);
    return splitShiftTips(
      people: [for (final x in people) TipPerson(x.id, x.position, _times(x)[0], _times(x)[1])],
      floorPool: _money(_floor),
      barPool: _money(_bar),
      positionOf: s.position,
      byTime: (ts['method'] ?? 'points') == 'time',
      fullShare: fs[_shift] as String?,
      tipStart: st[_shift] as String?,
    );
  }

  Future<void> _save(Session s, List<Shift> people) async {
    setState(() => _busy = true);
    try {
      final r = _split(s, people);
      final week = ymd(mondayOf(parseYmd(_date)));
      final b = s.db.batch();
      b.set(
          s.doc('days/$_date'),
          {
            'tips': {_shift: {'floor': _money(_floor), 'bar': _money(_bar)}},
            'worked': {_shift: {for (final e in _worked.entries) e.key: e.value}},
            'savedBy': s.name,
            'savedAt': FieldValue.serverTimestamp(),
          },
          SetOptions(merge: true));
      // per employee: add up if someone has two entries on this shift
      final per = <String, Map<String, double>>{};
      for (final x in people) {
        final l = r.lines[x.id]!;
        final m = per.putIfAbsent(x.employeeId, () => {'hours': 0, 'tips': 0, 'floor': 0, 'bar': 0});
        m['hours'] = m['hours']! + l.hours;
        m['tips'] = m['tips']! + l.total;
        m['floor'] = m['floor']! + l.floor;
        m['bar'] = m['bar']! + l.bar;
      }
      per.forEach((eid, m) {
        b.set(
            s.col('tips').doc('${eid}_$week'),
            {
              'employeeId': eid,
              'week': week,
              'days': {
                _date: {_shift: m}
              },
            },
            SetOptions(merge: true));
      });
      // people who had tips on this day/shift before but aren't on it any more
      final before = await s.col('tips').where('week', isEqualTo: week).get();
      for (final d in before.docs) {
        final eid = (d.data()['employeeId'] ?? '') as String;
        final days = d.data()['days'];
        final had = days is Map && days[_date] is Map && (days[_date] as Map).containsKey(_shift);
        if (had && !per.containsKey(eid)) {
          b.update(d.reference, {FieldPath(['days', _date, _shift]): FieldValue.delete()});
        }
      }
      await b.commit();
      if (mounted) {
        toast(context, 'Saved — everyone sees their share under Tips.');
        Navigator.pop(context);
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
      stream: s.col('shifts').where('week', isEqualTo: week).snapshots(),
      builder: (c, snap) {
        final people = (snap.data?.docs.map(Shift.from).toList() ?? [])
            .where((x) => x.date == _date && x.shift == _shift)
            .toList()
          ..sort((a, b) => a.employeeName.toLowerCase().compareTo(b.employeeName.toLowerCase()));
        final r = _split(s, people);
        final ready = _loadedKey == '$_date|$_shift';
        return Scaffold(
          appBar: AppBar(title: const Text('Tips of the day')),
          bottomNavigationBar: SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 10),
              child: FilledButton.icon(
                onPressed: _busy || !ready || people.isEmpty ? null : () => _save(s, people),
                icon: const Icon(Icons.check),
                label: const Text('Save and share tips'),
              ),
            ),
          ),
          body: ListView(padding: const EdgeInsets.only(bottom: 24), children: [
            ListTile(
              leading: const Icon(Icons.event),
              title: Text(shortDay(parseYmd(_date)), style: const TextStyle(fontWeight: FontWeight.w700)),
              trailing: const Icon(Icons.edit_calendar_outlined),
              onTap: () async {
                final d = await showDatePicker(
                  context: context,
                  initialDate: parseYmd(_date),
                  firstDate: DateTime(2024),
                  lastDate: DateTime.now().add(const Duration(days: 1)),
                );
                if (d != null) _change(date: ymd(d));
              },
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SegmentedButton<String>(
                segments: [for (final k in kShifts) ButtonSegment(value: k, label: Text(k))],
                selected: {_shift},
                onSelectionChanged: (v) => _change(shift: v.first),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
              child: Row(children: [
                Expanded(
                  child: TextField(
                    controller: _floor,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Floor tips', prefixText: '\$ '),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _bar,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Bar tips', prefixText: '\$ '),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
              ]),
            ),
            if (r.floorUnassigned > 0 || r.barUnassigned > 0)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                child: Text(
                  [
                    if (r.floorUnassigned > 0) '${money(r.floorUnassigned)} floor tips have nobody with points',
                    if (r.barUnassigned > 0) '${money(r.barUnassigned)} bar tips have no bartender',
                  ].join(' · '),
                  style: const TextStyle(color: kDanger),
                ),
              ),
            SectionHeader('Who worked (${people.length})',
                trailing: TextButton.icon(
                  onPressed: () => openDayPlanner(context, monday: mondayOf(parseYmd(_date)), date: _date),
                  icon: const Icon(Icons.edit, size: 16),
                  label: const Text('Change'),
                )),
            if (snap.hasData && people.isEmpty)
              const Empty(Icons.person_off_outlined, 'Nobody is on the schedule for this shift',
                  'Tap Change to add who worked, then enter the tips.'),
            for (final x in people)
              Card(
                child: ListTile(
                  title: Text(x.employeeName, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text([
                    x.position.isEmpty ? 'No position' : x.position,
                    '${shortTime(_times(x)[0])}–${shortTime(_times(x)[1])}${_worked.containsKey(x.id) ? ' (changed)' : ''}',
                    if ((r.lines[x.id]?.bar ?? 0) > 0) 'bar ${money(r.lines[x.id]!.bar)}',
                  ].join(' · ')),
                  trailing: Text(money(r.lines[x.id]?.total ?? 0),
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kNavy)),
                  onTap: () => _editTimes(x),
                ),
              ),
            if (people.isNotEmpty)
              const Padding(
                padding: EdgeInsets.fromLTRB(20, 6, 20, 0),
                child: Text('Tap someone to change when they really came in and left.',
                    style: TextStyle(color: kFgSec, fontSize: 13)),
              ),
          ]),
        );
      },
    );
  }
}
