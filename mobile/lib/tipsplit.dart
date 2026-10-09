// The tip split — the same rule as the NUME desktop app (core.py):
//   Floor pool -> every floor (FOH) person with points > 0.
//                 weight = points            (method "points")
//                 weight = tip hours × points (method "time")
//   Bar pool   -> barbacks take their fixed % first, the rest goes to
//                 bartenders (equally, or by tip hours with method "time").
// Amounts are rounded to cents and always add up to the pool.

import 'models.dart';
import 'util.dart';

const Map<String, String?> kFullShareDefault = {'Morning': null, 'Brunch': null, 'Dinner': '11:00 PM'};
const Map<String, String?> kTipStartDefault = {'Morning': null, 'Brunch': null, 'Dinner': '4:05 PM'};

class TipPerson {
  final String id; // shift id
  final String position;
  final String timeIn, timeOut;
  const TipPerson(this.id, this.position, this.timeIn, this.timeOut);
}

class TipLine {
  final double floor, bar, hours, tipHours;
  const TipLine(this.floor, this.bar, this.hours, this.tipHours);
  double get total => _r2(floor + bar);
}

class SplitResult {
  final Map<String, TipLine> lines;
  final double floorUnassigned, barUnassigned;
  const SplitResult(this.lines, this.floorUnassigned, this.barUnassigned);
}

double _r2(double v) => (v * 100).roundToDouble() / 100;

/// Split [total] by [weights] into cents that add up exactly.
Map<String, double> roundSplit(double total, Map<String, double> weights) {
  final out = {for (final k in weights.keys) k: 0.0};
  final tw = weights.values.fold<double>(0, (a, b) => a + b);
  if (tw <= 0 || total <= 0) return out;
  final cents = (total * 100).round();
  final raw = {for (final e in weights.entries) e.key: cents * e.value / tw};
  final fl = {for (final e in raw.entries) e.key: e.value.floor()};
  var left = cents - fl.values.fold<int>(0, (a, b) => a + b);
  final order = raw.keys.toList()..sort((a, b) => (raw[b]! - fl[b]!).compareTo(raw[a]! - fl[a]!));
  for (final k in order) {
    if (left <= 0) break;
    fl[k] = fl[k]! + 1;
    left--;
  }
  return {for (final e in fl.entries) e.key: e.value / 100};
}

/// Hours counted for tips: the clock starts no earlier than [start] and stops at [fullShare].
double tipHoursBetween(String timeIn, String timeOut, String? fullShare, String? start) {
  var a = parseTime(timeIn);
  final b = parseTime(timeOut);
  if (a == null || b == null) return 0;
  var span = b - a;
  if (span < 0) span += 1440;
  final end = a + span;
  final st = start == null ? null : parseTime(start);
  if (st != null && st - 8 * 60 <= a && a < st) {
    a = st;
    if (end < a) return 0;
  }
  var stop = end;
  var cap = fullShare == null ? null : parseTime(fullShare);
  if (cap != null) {
    if (cap < a - 6 * 60) cap += 1440;
    if (cap < stop) stop = cap;
  }
  final m = stop - a;
  return m <= 0 ? 0 : _r2(m / 60);
}

SplitResult splitShiftTips({
  required List<TipPerson> people,
  required double floorPool,
  required double barPool,
  required Position Function(String) positionOf,
  required bool byTime,
  String? fullShare,
  String? tipStart,
}) {
  final hours = <String, double>{};
  final th = <String, double>{};
  for (final p in people) {
    hours[p.id] = shiftHours(p.timeIn, p.timeOut);
    th[p.id] = tipHoursBetween(p.timeIn, p.timeOut, fullShare, tipStart);
  }
  // floor
  final fw = <String, double>{};
  for (final p in people) {
    final pos = positionOf(p.position);
    if (pos.isKitchen) continue;
    final w = pos.points * (byTime ? th[p.id]! : 1.0);
    if (w > 0) fw[p.id] = w;
  }
  final floorPoolC = floorPool < 0 ? 0.0 : floorPool;
  final fshare = roundSplit(floorPoolC, fw);
  final floorUnassigned = fw.isEmpty ? floorPoolC : 0.0;

  // bar
  final barPoolC = barPool < 0 ? 0.0 : barPool;
  final bshare = <String, double>{};
  final bartenders = <String, double>{};
  var rem = barPoolC;
  for (final p in people) {
    final pos = positionOf(p.position);
    if (pos.barbackPct > 0) {
      var amt = _r2(barPoolC * pos.barbackPct / 100);
      if (amt > rem) amt = rem;
      bshare[p.id] = (bshare[p.id] ?? 0) + amt;
      rem = _r2(rem - amt);
    } else if (pos.barTips) {
      bartenders[p.id] = byTime ? th[p.id]! : 1.0;
    }
  }
  var barUnassigned = 0.0;
  if (bartenders.isNotEmpty) {
    final total = bartenders.values.fold<double>(0, (a, b) => a + b);
    final weights = total <= 0 ? {for (final k in bartenders.keys) k: 1.0} : bartenders;
    roundSplit(rem, weights).forEach((k, v) => bshare[k] = _r2((bshare[k] ?? 0) + v));
  } else {
    barUnassigned = rem;
  }
  return SplitResult(
    {
      for (final p in people)
        p.id: TipLine(fshare[p.id] ?? 0, _r2(bshare[p.id] ?? 0), hours[p.id]!, th[p.id]!),
    },
    _r2(floorUnassigned),
    _r2(barUnassigned),
  );
}
