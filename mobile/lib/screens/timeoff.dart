import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../util.dart';
import '../widgets/common.dart';

class TimeOffScreen extends StatelessWidget {
  const TimeOffScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final fab = FloatingActionButton.extended(
      onPressed: () => requestDaysOff(context),
      icon: const Icon(Icons.add),
      label: const Text('Request days off'),
    );
    if (!s.isManager) {
      return Scaffold(
        appBar: AppBar(title: const Text('Days off')),
        floatingActionButton: fab,
        body: _List(stream: s.col('timeoff').where('uid', isEqualTo: s.uid).snapshots(), manager: false),
      );
    }
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Days off'),
          bottom: const TabBar(tabs: [Tab(text: 'Waiting'), Tab(text: 'All requests'), Tab(text: 'Mine')]),
        ),
        floatingActionButton: fab,
        body: TabBarView(children: [
          _List(stream: s.col('timeoff').where('status', isEqualTo: 'pending').snapshots(), manager: true,
              emptyTitle: 'No requests waiting'),
          _List(stream: s.col('timeoff').snapshots(), manager: true),
          _List(stream: s.col('timeoff').where('uid', isEqualTo: s.uid).snapshots(), manager: false),
        ]),
      ),
    );
  }
}

class _List extends StatelessWidget {
  const _List({required this.stream, required this.manager, this.emptyTitle = 'No day-off requests'});
  final Stream<QuerySnapshot<Json>> stream;
  final bool manager;
  final String emptyTitle;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: stream,
      builder: (c, snap) {
        if (snap.hasError) return Empty(Icons.error_outline, 'Couldn\'t load requests', friendlyError(snap.error!));
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final today = ymd(DateTime.now());
        final list = snap.data!.docs.map(TimeOff.from).toList()
          ..sort((a, b) {
            // waiting first, then upcoming (soonest first), then past (latest first)
            int rank(TimeOff t) => t.status == 'pending' ? 0 : (t.to.compareTo(today) >= 0 ? 1 : 2);
            final r = rank(a).compareTo(rank(b));
            if (r != 0) return r;
            return rank(a) == 2 ? b.from.compareTo(a.from) : a.from.compareTo(b.from);
          });
        if (list.isEmpty) {
          return Empty(Icons.beach_access_outlined, emptyTitle,
              manager ? '' : 'Tap "Request days off" — your manager gets it right away.');
        }
        return ListView(
          padding: const EdgeInsets.only(top: 8, bottom: 96),
          children: [for (final t in list) _Tile(t: t, manager: manager)],
        );
      },
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile({required this.t, required this.manager});
  final TimeOff t;
  final bool manager;

  int get _days => daysBetween(t.from, t.to).length;

  Future<void> _decide(BuildContext context, String status) async {
    final s = SessionScope.read(context);
    final reply = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(status == 'approved' ? 'Approve ${t.employeeName}\'s days off?' : 'Say no to this request?'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(rangeLabel(t.from, t.to)),
          const SizedBox(height: 10),
          TextField(controller: reply, decoration: const InputDecoration(labelText: 'Message (optional)')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
          FilledButton(
            style: status == 'denied' ? FilledButton.styleFrom(backgroundColor: kDanger) : null,
            onPressed: () => Navigator.pop(c, true),
            child: Text(status == 'approved' ? 'Approve' : 'Not approved'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await s.col('timeoff').doc(t.id).update({
        'status': status,
        'reply': reply.text.trim(),
        'decidedBy': s.uid,
        'decidedByName': s.name,
        'decidedAt': FieldValue.serverTimestamp(),
      });
      if (!context.mounted) return;
      if (status == 'approved') {
        final shifts = await s.col('shifts').where('employeeId', isEqualTo: t.employeeId).get();
        final clash = shifts.docs.map(Shift.from).where((x) => t.from.compareTo(x.date) <= 0 && x.date.compareTo(t.to) <= 0).length;
        if (clash > 0 && context.mounted) {
          toast(context, '${t.employeeName} is scheduled on $clash of those days — change the schedule.');
          return;
        }
      }
      if (context.mounted) toast(context, status == 'approved' ? 'Approved' : 'Marked as not approved');
    } catch (e) {
      if (context.mounted) toast(context, friendlyError(e), error: true);
    }
  }

  Future<void> _cancel(BuildContext context) async {
    final s = SessionScope.read(context);
    final go = await confirm(context, 'Cancel this request?', rangeLabel(t.from, t.to), yes: 'Cancel request');
    if (!go) return;
    try {
      await s.col('timeoff').doc(t.id).update({'status': 'cancelled'});
    } catch (e) {
      if (context.mounted) toast(context, friendlyError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sub = <String>[
      '$_days day${_days == 1 ? '' : 's'}',
      if (t.note.isNotEmpty) '“${t.note}”',
    ].join(' · ');
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 12, 10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text(manager ? t.employeeName : rangeLabel(t.from, t.to),
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            ),
            StatusChip(t.status),
          ]),
          const SizedBox(height: 4),
          if (manager) Text(rangeLabel(t.from, t.to), style: const TextStyle(fontWeight: FontWeight.w600)),
          Text(sub, style: const TextStyle(color: kFgSec)),
          if (t.status != 'pending' && t.status != 'cancelled' && t.decidedByName.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('${t.status == 'approved' ? 'Approved' : 'Answered'} by ${t.decidedByName}'
                  '${t.reply.isNotEmpty ? ': “${t.reply}”' : ''}',
                  style: const TextStyle(color: kFgSec, fontSize: 13)),
            ),
          if (t.status == 'pending')
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                if (manager) ...[
                  TextButton(onPressed: () => _decide(context, 'denied'), child: const Text('Not approved')),
                  const SizedBox(width: 6),
                  FilledButton(onPressed: () => _decide(context, 'approved'), child: const Text('Approve')),
                ] else
                  TextButton(onPressed: () => _cancel(context), child: const Text('Cancel request')),
              ]),
            ),
          if (manager && t.status == 'approved')
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(onPressed: () => _decide(context, 'denied'), child: const Text('Change to not approved')),
            ),
        ]),
      ),
    );
  }
}

Future<void> requestDaysOff(BuildContext context) async {
  final s = SessionScope.read(context);
  final now = DateTime.now();
  final range = await showDateRangePicker(
    context: context,
    firstDate: dateOnly(now),
    lastDate: DateTime(now.year + 1, now.month, now.day),
    helpText: 'Which days do you need off?',
    saveText: 'Next',
  );
  if (range == null || !context.mounted) return;
  final note = TextEditingController();
  final from = ymd(range.start), to = ymd(range.end);
  final ok = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: const Text('Request days off'),
      content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(rangeLabel(from, to), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
        const SizedBox(height: 10),
        TextField(
          controller: note,
          decoration: const InputDecoration(labelText: 'Reason (optional)'),
          textCapitalization: TextCapitalization.sentences,
        ),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Send request')),
      ],
    ),
  );
  if (ok != true) return;
  try {
    await s.col('timeoff').add({
      'uid': s.uid,
      'employeeId': s.employeeId,
      'employeeName': s.name,
      'from': from,
      'to': to,
      'note': note.text.trim(),
      'status': 'pending',
      'createdAt': FieldValue.serverTimestamp(),
    });
    if (context.mounted) toast(context, 'Request sent to your manager.');
  } catch (e) {
    if (context.mounted) toast(context, friendlyError(e), error: true);
  }
}
