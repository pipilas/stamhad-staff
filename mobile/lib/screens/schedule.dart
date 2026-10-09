import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../util.dart';
import '../widgets/common.dart';
import 'day_planner.dart';
import 'shift_editor.dart';

class ScheduleScreen extends StatefulWidget {
  const ScheduleScreen({super.key});
  @override
  State<ScheduleScreen> createState() => _ScheduleScreenState();
}

class _ScheduleScreenState extends State<ScheduleScreen> {
  DateTime _monday = mondayOf(DateTime.now());
  bool? _mineOnly; // null = default for the role

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final mine = _mineOnly ?? (!s.isManager && s.employeeId.isNotEmpty);
    final week = ymd(_monday);
    final offStream = s.isManager
        ? s.col('timeoff').where('status', isEqualTo: 'approved').snapshots()
        : s.col('timeoff').where('uid', isEqualTo: s.uid).snapshots();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Schedule'),
        actions: [
          if (s.isManager)
            PopupMenuButton<String>(
              onSelected: (v) {
                if (v == 'copy') _copyLastWeek(s);
                if (v == 'one') openShiftEditor(context, monday: _monday);
              },
              itemBuilder: (c) => const [
                PopupMenuItem(value: 'one', child: Text('Add one shift')),
                PopupMenuItem(value: 'copy', child: Text('Copy last week into this week')),
              ],
            ),
        ],
      ),
      floatingActionButton: s.isManager
          ? FloatingActionButton.extended(
              onPressed: () => openDayPlanner(context, monday: _monday),
              icon: const Icon(Icons.playlist_add_check),
              label: const Text('Plan a day'),
            )
          : null,
      body: Column(children: [
        PeriodBar(
          label: weekLabel(_monday),
          onPrev: () => setState(() => _monday = addDays(_monday, -7)),
          onNext: () => setState(() => _monday = addDays(_monday, 7)),
          onToday: () => setState(() => _monday = mondayOf(DateTime.now())),
        ),
        if (s.employeeId.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
            child: SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: true, label: Text('My shifts'), icon: Icon(Icons.person)),
                ButtonSegment(value: false, label: Text('Everyone'), icon: Icon(Icons.groups)),
              ],
              selected: {mine},
              onSelectionChanged: (v) => setState(() => _mineOnly = v.first),
            ),
          ),
        Expanded(
          child: StreamBuilder<QuerySnapshot<Json>>(
            stream: s.col('shifts').where('week', isEqualTo: week).snapshots(),
            builder: (c, snap) {
              if (snap.hasError) return Empty(Icons.error_outline, 'Couldn\'t load the schedule', friendlyError(snap.error!));
              if (!snap.hasData) return const Center(child: CircularProgressIndicator());
              var shifts = snap.data!.docs.map(Shift.from).toList();
              if (mine) shifts = shifts.where((x) => x.employeeId == s.employeeId).toList();
              return StreamBuilder<QuerySnapshot<Json>>(
                stream: offStream,
                builder: (c, offSnap) {
                  final offs = (offSnap.data?.docs.map(TimeOff.from).toList() ?? [])
                      .where((t) => t.status == 'approved')
                      .where((t) => overlaps(t.from, t.to, week, ymd(addDays(_monday, 6))))
                      .toList();
                  return _WeekList(monday: _monday, shifts: shifts, offs: offs, mine: mine);
                },
              );
            },
          ),
        ),
      ]),
    );
  }

  Future<void> _copyLastWeek(Session s) async {
    final prev = ymd(addDays(_monday, -7));
    final week = ymd(_monday);
    try {
      final have = await s.col('shifts').where('week', isEqualTo: week).get();
      if (have.size > 0 && mounted) {
        final go = await confirm(context, 'Copy last week?',
            'This week already has ${have.size} shift(s). Last week\'s shifts will be added to them.',
            yes: 'Copy');
        if (!go) return;
      }
      final last = await s.col('shifts').where('week', isEqualTo: prev).get();
      if (last.size == 0) {
        if (mounted) toast(context, 'Last week has no shifts.');
        return;
      }
      final b = s.db.batch();
      for (final d in last.docs) {
        final x = Shift.from(d);
        final j = x.toJson()
          ..['week'] = week
          ..['date'] = ymd(addDays(parseYmd(x.date), 7))
          ..['updatedBy'] = s.name
          ..['updatedAt'] = FieldValue.serverTimestamp();
        b.set(s.col('shifts').doc(), j);
      }
      await b.commit();
      if (mounted) toast(context, 'Copied ${last.size} shift(s) from last week.');
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    }
  }
}

class _WeekList extends StatelessWidget {
  const _WeekList({required this.monday, required this.shifts, required this.offs, required this.mine});
  final DateTime monday;
  final List<Shift> shifts;
  final List<TimeOff> offs;
  final bool mine;

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final today = ymd(DateTime.now());
    if (shifts.isEmpty && offs.isEmpty) {
      return Empty(Icons.event_available, mine ? 'No shifts for you this week' : 'Nothing scheduled this week',
          s.isManager ? 'Tap Plan a day, or copy last week from the ⋮ menu.' : '');
    }
    final order = {for (var i = 0; i < kShifts.length; i++) kShifts[i]: i};
    final children = <Widget>[];
    var myHours = 0.0;
    for (var i = 0; i < 7; i++) {
      final day = ymd(addDays(monday, i));
      final list = shifts.where((x) => x.date == day).toList()
        ..sort((a, b) {
          final o = (order[a.shift] ?? 9).compareTo(order[b.shift] ?? 9);
          if (o != 0) return o;
          final t = (parseTime(a.start) ?? 0).compareTo(parseTime(b.start) ?? 0);
          return t != 0 ? t : a.employeeName.compareTo(b.employeeName);
        });
      final dayOffs = offs.where((t) => t.from.compareTo(day) <= 0 && day.compareTo(t.to) <= 0).toList();
      if (list.isEmpty && dayOffs.isEmpty) continue;
      children.add(SectionHeader(
        '${shortDay(parseYmd(day))}${day == today ? ' · today' : ''}',
        trailing: s.isManager
            ? TextButton(
                onPressed: () => openDayPlanner(context, monday: monday, date: day),
                child: Text('${list.length} · edit'),
              )
            : Text('${list.length} shift${list.length == 1 ? '' : 's'}',
                style: const TextStyle(color: kFgSec, fontSize: 12)),
      ));
      for (final t in dayOffs) {
        children.add(Card(
          color: kWarnBg,
          child: ListTile(
            dense: true,
            leading: const Icon(Icons.beach_access, color: kWarnFg),
            title: Text('${t.employeeName.isEmpty ? 'You' : t.employeeName} — day off',
                style: const TextStyle(color: kWarnFg, fontWeight: FontWeight.w600)),
          ),
        ));
      }
      for (final x in list) {
        final me = x.employeeId == s.employeeId && s.employeeId.isNotEmpty;
        if (me) myHours += shiftHours(x.start, x.end);
        children.add(Card(
          child: ListTile(
            onTap: s.isManager ? () => openShiftEditor(context, monday: monday, shift: x) : null,
            leading: Avatar(initials(x.employeeName), highlight: me),
            title: Text(me && !mine ? '${x.employeeName} (you)' : x.employeeName,
                style: TextStyle(fontWeight: me ? FontWeight.w700 : FontWeight.w600)),
            subtitle: Text([
              if (x.position.isNotEmpty) x.position,
              if (x.start.isNotEmpty) '${shortTime(x.start)}${x.end.isNotEmpty ? '–${shortTime(x.end)}' : ''}',
              if (x.note.isNotEmpty) x.note,
            ].join(' · ')),
            trailing: ShiftPill(x.shift),
          ),
        ));
      }
    }
    if (myHours > 0) {
      children.insert(
          0,
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 0),
            child: Text('You work about ${hoursText(myHours)} this week',
                style: const TextStyle(color: kFgSec, fontWeight: FontWeight.w600)),
          ));
    }
    children.add(const SizedBox(height: 96));
    return ListView(children: children);
  }
}
