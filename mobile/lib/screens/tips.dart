import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../util.dart';
import '../widgets/common.dart';
import 'day_tips.dart';

/// One day of tips: tips/{employeeId}_{week}.days[date] = {hours, tips}
class TipDay {
  final String date;
  final double hours, tips;
  TipDay(this.date, this.hours, this.tips);
}

List<TipDay> tipDays(Iterable<Snap> docs) {
  final out = <TipDay>[];
  for (final d in docs) {
    final days = d.data()?['days'];
    if (days is! Map) continue;
    days.forEach((k, v) {
      if (v is! Map) return;
      // days[date][shift] = {hours, tips}  (older format: days[date] = {hours, tips})
      var h = 0.0, t = 0.0;
      if (v['tips'] is num || v['hours'] is num) {
        h += ((v['hours'] ?? 0) as num).toDouble();
        t += ((v['tips'] ?? 0) as num).toDouble();
      }
      for (final sub in v.values) {
        if (sub is Map) {
          h += ((sub['hours'] ?? 0) as num).toDouble();
          t += ((sub['tips'] ?? 0) as num).toDouble();
        }
      }
      if (h > 0 || t > 0) out.add(TipDay('$k', h, t));
    });
  }
  out.sort((a, b) => a.date.compareTo(b.date));
  return out;
}

class TipsScreen extends StatefulWidget {
  const TipsScreen({super.key});
  @override
  State<TipsScreen> createState() => _TipsScreenState();
}

class _TipsScreenState extends State<TipsScreen> {
  Period _period = Period.week;
  DateTime _anchor = DateTime.now();
  String? _emp; // manager's choice

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Tips')),
      floatingActionButton: s.isManager
          ? FloatingActionButton.extended(
              onPressed: () => openDayTips(context),
              icon: const Icon(Icons.add_card),
              label: const Text('Enter today\'s tips'),
            )
          : null,
      body: Column(children: [
        if (s.isManager) _employeePicker(s),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
          child: SegmentedButton<Period>(
            segments: const [
              ButtonSegment(value: Period.week, label: Text('Week')),
              ButtonSegment(value: Period.month, label: Text('Month')),
              ButtonSegment(value: Period.year, label: Text('Year')),
            ],
            selected: {_period},
            onSelectionChanged: (v) => setState(() => _period = v.first),
          ),
        ),
        PeriodBar(
          label: periodLabel(_period, _anchor),
          onPrev: () => setState(() => _anchor = shiftPeriod(_period, _anchor, -1)),
          onNext: () => setState(() => _anchor = shiftPeriod(_period, _anchor, 1)),
          onToday: () => setState(() => _anchor = DateTime.now()),
        ),
        Expanded(child: _body(s)),
      ]),
    );
  }

  Widget _employeePicker(Session s) {
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: s.col('employees').snapshots(),
      builder: (c, snap) {
        final emps = (snap.data?.docs.map(Employee.from).where((e) => e.active).toList() ?? [])
          ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
        if (emps.isEmpty) return const SizedBox.shrink();
        final cur = _emp ?? (s.employeeId.isNotEmpty ? s.employeeId : emps.first.id);
        return Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: DropdownButtonFormField<String>(
            key: ValueKey('tips-emp-${emps.length}'),
            initialValue: emps.any((e) => e.id == cur) ? cur : null,
            decoration: const InputDecoration(labelText: 'Employee', isDense: true),
            items: [for (final e in emps) DropdownMenuItem(value: e.id, child: Text(e.name))],
            onChanged: (v) => setState(() => _emp = v),
          ),
        );
      },
    );
  }

  Widget _body(Session s) {
    final eid = s.isManager ? (_emp ?? s.employeeId) : s.employeeId;
    if (eid.isEmpty) {
      return s.isManager
          ? const Empty(Icons.person_search, 'Pick an employee')
          : const Empty(Icons.link_off, 'Your login isn\'t linked to an employee',
              'Ask your manager to link you in Team.');
    }
    final range = periodRange(_period, _anchor);
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: s.col('tips').where('employeeId', isEqualTo: eid).snapshots(),
      builder: (c, snap) {
        if (snap.hasError) return Empty(Icons.error_outline, 'Couldn\'t load tips', friendlyError(snap.error!));
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final days = tipDays(snap.data!.docs).where((d) => range.containsYmd(d.date)).toList();
        final tips = days.fold<double>(0, (a, d) => a + d.tips);
        final hours = days.fold<double>(0, (a, d) => a + d.hours);
        return ListView(padding: const EdgeInsets.only(bottom: 32), children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('TIPS', style: TextStyle(color: kFgSec, fontWeight: FontWeight.w700, fontSize: 12)),
                const SizedBox(height: 4),
                Text(money(tips), style: const TextStyle(fontSize: 34, fontWeight: FontWeight.w800, color: kNavy)),
                const SizedBox(height: 12),
                Row(children: [
                  _Stat('Hours', hoursText(hours)),
                  _Stat('Per hour', hours > 0 ? money(tips / hours) : '—'),
                  _Stat('Days', '${days.where((d) => d.hours > 0 || d.tips > 0).length}'),
                ]),
              ]),
            ),
          ),
          if (days.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 24),
              child: Empty(Icons.payments_outlined, 'No tips for this period yet',
                  'Tips appear here once your manager enters the day\'s tips.'),
            )
          else if (_period == Period.year)
            ..._byMonth(days)
          else ...[
            const SectionHeader('By day'),
            for (final d in days.reversed)
              Card(
                child: ListTile(
                  title: Text(shortDay(parseYmd(d.date))),
                  subtitle: Text(hoursText(d.hours)),
                  trailing: Text(money(d.tips), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                ),
              ),
          ],
        ]);
      },
    );
  }

  List<Widget> _byMonth(List<TipDay> days) {
    final out = <Widget>[const SectionHeader('By month')];
    for (var m = 12; m >= 1; m--) {
      final ds = days.where((d) => parseYmd(d.date).month == m).toList();
      if (ds.isEmpty) continue;
      final t = ds.fold<double>(0, (a, d) => a + d.tips), h = ds.fold<double>(0, (a, d) => a + d.hours);
      out.add(Card(
        child: ListTile(
          title: Text(kMonths[m - 1]),
          subtitle: Text(hoursText(h)),
          trailing: Text(money(t), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          onTap: () => setState(() {
            _period = Period.month;
            _anchor = DateTime(_anchor.year, m, 1);
          }),
        ),
      ));
    }
    return out;
  }
}

class _Stat extends StatelessWidget {
  const _Stat(this.label, this.value);
  final String label, value;
  @override
  Widget build(BuildContext context) => Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: const TextStyle(color: kFgSec, fontSize: 12)),
          Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
        ]),
      );
}
