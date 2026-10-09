// Dates, times and money helpers (no Flutter imports, so they're easy to test).

const List<String> kShifts = ['Morning', 'Brunch', 'Dinner'];

const Map<String, List<String>> kDefaultTimes = {
  'Morning': ['7:00 AM', '3:00 PM'],
  'Brunch': ['9:30 AM', '4:00 PM'],
  'Dinner': ['4:00 PM', '11:00 PM'],
};

const List<String> kMonths = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];
const List<String> kDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

String two(int n) => n.toString().padLeft(2, '0');

DateTime dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);

/// Monday of the week that contains [d].
DateTime mondayOf(DateTime d) => dateOnly(d).subtract(Duration(days: d.weekday - 1));

/// '2026-10-05'
String ymd(DateTime d) => '${d.year.toString().padLeft(4, '0')}-${two(d.month)}-${two(d.day)}';

DateTime parseYmd(String s) {
  final p = s.split('-').map(int.parse).toList();
  return DateTime(p[0], p[1], p[2]);
}

DateTime addDays(DateTime d, int n) => DateTime(d.year, d.month, d.day + n);

/// 'Mon, Oct 5'
String shortDay(DateTime d) => '${kDays[d.weekday - 1].substring(0, 3)}, ${kMonths[d.month - 1].substring(0, 3)} ${d.day}';

/// 'Oct 5 – 11' or 'Sep 28 – Oct 4'
String weekLabel(DateTime monday) {
  final sun = addDays(monday, 6);
  final m1 = kMonths[monday.month - 1].substring(0, 3);
  final m2 = kMonths[sun.month - 1].substring(0, 3);
  return monday.month == sun.month ? '$m1 ${monday.day} – ${sun.day}' : '$m1 ${monday.day} – $m2 ${sun.day}';
}

/// 'Oct 10 – 12', or 'Oct 10' for one day
String rangeLabel(String from, String to) {
  final a = parseYmd(from), b = parseYmd(to);
  final m1 = kMonths[a.month - 1].substring(0, 3);
  if (from == to) return '${kDays[a.weekday - 1].substring(0, 3)}, $m1 ${a.day}';
  final m2 = kMonths[b.month - 1].substring(0, 3);
  return a.month == b.month ? '$m1 ${a.day} – ${b.day}' : '$m1 ${a.day} – $m2 ${b.day}';
}

/// '4:05 PM' -> minutes after midnight (also '16:05', '4p'); null if unreadable.
int? parseTime(String? s) {
  if (s == null) return null;
  final m = RegExp(r'^\s*(\d{1,2})(?::?(\d{2}))?\s*([ap])?\.?\s*m?\.?\s*$', caseSensitive: false)
      .firstMatch(s.trim());
  if (m == null) return null;
  var h = int.parse(m.group(1)!);
  final mi = int.parse(m.group(2) ?? '0');
  final ap = (m.group(3) ?? '').toLowerCase();
  if (mi > 59) return null;
  if (ap.isNotEmpty) {
    if (h < 1 || h > 12) return null;
    if (ap == 'a') {
      h = h == 12 ? 0 : h;
    } else {
      h = h == 12 ? 12 : h + 12;
    }
  } else if (h > 23) {
    return null;
  }
  return h * 60 + mi;
}

/// minutes -> '4:05 PM'
String fmtTime(int mins) {
  mins %= 1440;
  final h = mins ~/ 60, m = mins % 60;
  final ap = h < 12 ? 'AM' : 'PM';
  final h12 = h % 12 == 0 ? 12 : h % 12;
  return '$h12:${two(m)} $ap';
}

/// '4:00 PM' -> '4p', '4:30 PM' -> '4:30p'
String shortTime(String? s) {
  final m = parseTime(s);
  if (m == null) return '';
  final h = (m ~/ 60) % 24, mi = m % 60;
  final ap = h < 12 ? 'a' : 'p';
  final h12 = h % 12 == 0 ? 12 : h % 12;
  return mi == 0 ? '$h12$ap' : '$h12:${two(mi)}$ap';
}

/// Hours between two times; an end before the start means it crossed midnight.
double shiftHours(String? start, String? end) {
  final a = parseTime(start), b = parseTime(end);
  if (a == null || b == null) return 0;
  var d = b - a;
  if (d <= 0) d += 1440;
  return d / 60.0;
}

String money(num v) {
  final neg = v < 0;
  final s = v.abs().toStringAsFixed(2);
  final parts = s.split('.');
  final whole = parts[0].replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
  return '${neg ? '-' : ''}\$$whole.${parts[1]}';
}

String hoursText(num h) {
  final s = h.toStringAsFixed(h == h.roundToDouble() ? 0 : 2);
  return '$s h';
}

/// Days from..to inclusive (as 'yyyy-mm-dd').
List<String> daysBetween(String from, String to) {
  final out = <String>[];
  var d = parseYmd(from);
  final end = parseYmd(to);
  while (!d.isAfter(end)) {
    out.add(ymd(d));
    d = addDays(d, 1);
  }
  return out;
}

bool overlaps(String from, String to, String a, String b) => from.compareTo(b) <= 0 && a.compareTo(to) <= 0;

/// The period shown on the Tips page.
enum Period { week, month, year }

class Range {
  final DateTime start; // inclusive
  final DateTime end; // inclusive
  const Range(this.start, this.end);
  bool containsYmd(String s) {
    final d = parseYmd(s);
    return !d.isBefore(start) && !d.isAfter(end);
  }
}

Range periodRange(Period p, DateTime anchor) {
  switch (p) {
    case Period.week:
      final m = mondayOf(anchor);
      return Range(m, addDays(m, 6));
    case Period.month:
      return Range(DateTime(anchor.year, anchor.month, 1), DateTime(anchor.year, anchor.month + 1, 0));
    case Period.year:
      return Range(DateTime(anchor.year, 1, 1), DateTime(anchor.year, 12, 31));
  }
}

DateTime shiftPeriod(Period p, DateTime anchor, int by) {
  switch (p) {
    case Period.week:
      return addDays(anchor, 7 * by);
    case Period.month:
      return DateTime(anchor.year, anchor.month + by, 1);
    case Period.year:
      return DateTime(anchor.year + by, 1, 1);
  }
}

String periodLabel(Period p, DateTime anchor) {
  switch (p) {
    case Period.week:
      return weekLabel(mondayOf(anchor));
    case Period.month:
      return '${kMonths[anchor.month - 1]} ${anchor.year}';
    case Period.year:
      return '${anchor.year}';
  }
}

/// Week docs that can hold days of [r]: every Monday from the week of r.start to r.end.
List<String> weeksTouching(Range r) {
  final out = <String>[];
  var m = mondayOf(r.start);
  while (!m.isAfter(r.end)) {
    out.add(ymd(m));
    m = addDays(m, 7);
  }
  return out;
}

String initials(String name) {
  final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
  if (parts.isEmpty) return '?';
  if (parts.length == 1) return parts[0].substring(0, 1).toUpperCase();
  return (parts[0][0] + parts.last[0]).toUpperCase();
}

String randomPassword() {
  final t = DateTime.now().microsecondsSinceEpoch;
  return 'Nm!${t.toRadixString(36)}${(t * 7919 % 1000003).toRadixString(36)}x';
}

/// First element matching [test], or null.
T? firstWhereOr<T>(Iterable<T> items, bool Function(T) test) {
  for (final x in items) {
    if (test(x)) return x;
  }
  return null;
}
