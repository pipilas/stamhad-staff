import 'package:cloud_firestore/cloud_firestore.dart';

typedef Json = Map<String, dynamic>;
typedef Snap = DocumentSnapshot<Json>;

List<String> _strings(dynamic v) => v is List ? v.map((e) => '$e').toList() : <String>[];

class Employee {
  final String id, name, email, uid, role;
  final List<String> positions;
  final bool active, canInventory;
  Employee({
    required this.id,
    required this.name,
    this.email = '',
    this.uid = '',
    this.role = 'employee',
    this.positions = const [],
    this.active = true,
    this.canInventory = false,
  });
  factory Employee.from(Snap s) {
    final d = s.data() ?? {};
    return Employee(
      id: s.id,
      name: (d['name'] ?? '') as String,
      email: (d['email'] ?? '') as String,
      uid: (d['uid'] ?? '') as String,
      role: (d['role'] ?? 'employee') as String,
      positions: _strings(d['positions']),
      active: d['active'] != false,
      canInventory: d['canInventory'] == true,
    );
  }
  bool get hasLogin => uid.isNotEmpty;
}

class Shift {
  final String id, week, date, employeeId, employeeName, position, shift, start, end, note;
  Shift({
    required this.id,
    required this.week,
    required this.date,
    required this.employeeId,
    required this.employeeName,
    this.position = '',
    this.shift = 'Dinner',
    this.start = '',
    this.end = '',
    this.note = '',
  });
  factory Shift.from(Snap s) {
    final d = s.data() ?? {};
    return Shift(
      id: s.id,
      week: (d['week'] ?? '') as String,
      date: (d['date'] ?? '') as String,
      employeeId: (d['employeeId'] ?? '') as String,
      employeeName: (d['employeeName'] ?? '') as String,
      position: (d['position'] ?? '') as String,
      shift: (d['shift'] ?? 'Dinner') as String,
      start: (d['start'] ?? '') as String,
      end: (d['end'] ?? '') as String,
      note: (d['note'] ?? '') as String,
    );
  }
  Json toJson() => {
        'week': week,
        'date': date,
        'employeeId': employeeId,
        'employeeName': employeeName,
        'position': position,
        'shift': shift,
        'start': start,
        'end': end,
        'note': note,
      };
}

class TimeOff {
  final String id, uid, employeeId, employeeName, from, to, note, status, decidedByName, reply;
  final DateTime? createdAt;
  TimeOff({
    required this.id,
    required this.uid,
    required this.employeeId,
    required this.employeeName,
    required this.from,
    required this.to,
    this.note = '',
    this.status = 'pending',
    this.decidedByName = '',
    this.reply = '',
    this.createdAt,
  });
  factory TimeOff.from(Snap s) {
    final d = s.data() ?? {};
    return TimeOff(
      id: s.id,
      uid: (d['uid'] ?? '') as String,
      employeeId: (d['employeeId'] ?? '') as String,
      employeeName: (d['employeeName'] ?? '') as String,
      from: (d['from'] ?? '') as String,
      to: (d['to'] ?? '') as String,
      note: (d['note'] ?? '') as String,
      status: (d['status'] ?? 'pending') as String,
      decidedByName: (d['decidedByName'] ?? '') as String,
      reply: (d['reply'] ?? '') as String,
      createdAt: (d['createdAt'] as Timestamp?)?.toDate(),
    );
  }
}

class Item {
  final String id, name, unit, category, website, link, notes;
  final bool active;
  Item({
    required this.id,
    required this.name,
    this.unit = '',
    this.category = '',
    this.website = '',
    this.link = '',
    this.notes = '',
    this.active = true,
  });
  factory Item.from(Snap s) {
    final d = s.data() ?? {};
    return Item(
      id: s.id,
      name: (d['name'] ?? '') as String,
      unit: (d['unit'] ?? '') as String,
      category: (d['category'] ?? '') as String,
      website: (d['website'] ?? '') as String,
      link: (d['link'] ?? '') as String,
      notes: (d['notes'] ?? '') as String,
      active: d['active'] != false,
    );
  }
}

class CartLine {
  final String id, itemId, itemName, unit, byUid, byName, note;
  final num qty;
  final DateTime? at;
  CartLine({
    required this.id,
    required this.itemId,
    required this.itemName,
    required this.qty,
    required this.byUid,
    required this.byName,
    this.unit = '',
    this.note = '',
    this.at,
  });
  factory CartLine.from(Snap s) {
    final d = s.data() ?? {};
    return CartLine(
      id: s.id,
      itemId: (d['itemId'] ?? '') as String,
      itemName: (d['itemName'] ?? '') as String,
      qty: (d['qty'] ?? 0) as num,
      byUid: (d['byUid'] ?? '') as String,
      byName: (d['byName'] ?? '') as String,
      unit: (d['unit'] ?? '') as String,
      note: (d['note'] ?? '') as String,
      at: (d['at'] as Timestamp?)?.toDate(),
    );
  }
  Json toOrderEntry() => {
        'qty': qty,
        'byUid': byUid,
        'byName': byName,
        'note': note,
        'at': at == null ? null : Timestamp.fromDate(at!),
      };
}

class PastOrder {
  final String id, date, byName;
  final List<Json> lines;
  PastOrder({required this.id, required this.date, required this.byName, required this.lines});
  factory PastOrder.from(Snap s) {
    final d = s.data() ?? {};
    return PastOrder(
      id: s.id,
      date: (d['date'] ?? '') as String,
      byName: (d['byName'] ?? '') as String,
      lines: (d['lines'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)).toList(),
    );
  }
}

/// A job (Server, Bartender, Cook…): how it shares tips and when it usually works.
/// Same fields as the desktop app's positions, plus usual times per shift.
class Position {
  final String name;
  final String department; // 'FOH' (floor) or 'BOH' (kitchen)
  final double points; // floor tip points
  final bool barTips; // bartenders: share the bar pool
  final double barbackPct; // barbacks: this % of the bar pool comes off the top
  final Map<String, List<String>> times; // shift -> [comes in, leaves]; empty = the shift's usual times

  const Position({
    required this.name,
    this.department = 'FOH',
    this.points = 0,
    this.barTips = false,
    this.barbackPct = 0,
    this.times = const {},
  });

  factory Position.fromJson(Json d) {
    final t = <String, List<String>>{};
    final raw = d['times'];
    if (raw is Map) {
      raw.forEach((k, v) {
        if (v is List && v.length == 2) t['$k'] = ['${v[0] ?? ''}', '${v[1] ?? ''}'];
      });
    }
    return Position(
      name: (d['name'] ?? '') as String,
      department: (d['department'] ?? 'FOH') as String,
      points: ((d['tip_points'] ?? 0) as num).toDouble(),
      barTips: d['receives_bar_tips'] == true,
      barbackPct: ((d['bar_tip_share_pct'] ?? 0) as num).toDouble(),
      times: t,
    );
  }

  Json toJson() => {
        'name': name,
        'department': department,
        'tip_points': points,
        'receives_bar_tips': barTips,
        'bar_tip_share_pct': barbackPct,
        'times': times,
      };

  Position copyWith({
    String? name,
    String? department,
    double? points,
    bool? barTips,
    double? barbackPct,
    Map<String, List<String>>? times,
  }) =>
      Position(
        name: name ?? this.name,
        department: department ?? this.department,
        points: points ?? this.points,
        barTips: barTips ?? this.barTips,
        barbackPct: barbackPct ?? this.barbackPct,
        times: times ?? this.times,
      );

  bool get isKitchen => department == 'BOH';

  /// Sensible settings for a job name (same guesses as the desktop app).
  static Position guess(String name) {
    final n = name.toLowerCase();
    bool has(List<String> ks) => ks.any(n.contains);
    if (has(['cook', 'kitchen', 'chef', 'dish', 'prep', 'porter', 'line', 'fry', 'pizza', 'sushi'])) {
      return Position(name: name, department: 'BOH');
    }
    if (n.contains('barback') || n.contains('bar back')) return Position(name: name, points: 2, barbackPct: 20);
    if (n.contains('bartend')) return Position(name: name, points: 5, barTips: true);
    if (has(['server', 'waiter', 'waitress'])) return Position(name: name, points: 10);
    if (n.contains('runner')) return Position(name: name, points: 7);
    if (n.contains('bus')) return Position(name: name, points: 5);
    return Position(name: name);
  }
}

const List<String> kStarterPositions = [
  'Server', 'Bartender', 'Runner', 'Busser', 'Barback', 'Host', 'Cook', 'Dishwasher'
];
