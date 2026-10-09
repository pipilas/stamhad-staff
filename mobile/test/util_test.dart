import 'package:flutter_test/flutter_test.dart';
import 'package:nume/util.dart';

void main() {
  test('weeks start on Monday', () {
    expect(ymd(mondayOf(DateTime(2026, 10, 9))), '2026-10-05');
    expect(ymd(mondayOf(DateTime(2026, 10, 5))), '2026-10-05');
    expect(ymd(mondayOf(DateTime(2026, 10, 11))), '2026-10-05');
    expect(weekLabel(DateTime(2026, 9, 28)), 'Sep 28 – Oct 4');
    expect(weekLabel(DateTime(2026, 10, 5)), 'Oct 5 – 11');
  });

  test('times', () {
    expect(parseTime('4:05 PM'), 16 * 60 + 5);
    expect(parseTime('16:05'), 965);
    expect(parseTime('12:30 AM'), 30);
    expect(parseTime('x'), isNull);
    expect(fmtTime(16 * 60 + 5), '4:05 PM');
    expect(shortTime('4:00 PM'), '4p');
    expect(shortTime('9:30 AM'), '9:30a');
    expect(shiftHours('4:00 PM', '11:00 PM'), 7);
    expect(shiftHours('5:00 PM', '2:00 AM'), 9);
  });

  test('money and ranges', () {
    expect(money(1234.5), '\$1,234.50');
    expect(money(0), '\$0.00');
    expect(daysBetween('2026-10-30', '2026-11-02').length, 4);
    expect(overlaps('2026-10-05', '2026-10-11', '2026-10-11', '2026-10-12'), isTrue);
    expect(overlaps('2026-10-05', '2026-10-11', '2026-10-12', '2026-10-13'), isFalse);
    final m = periodRange(Period.month, DateTime(2026, 2, 10));
    expect(ymd(m.start), '2026-02-01');
    expect(ymd(m.end), '2026-02-28');
    expect(periodLabel(Period.year, DateTime(2026, 5, 1)), '2026');
    expect(weeksTouching(periodRange(Period.month, DateTime(2026, 10, 1))).first, '2026-09-28');
    expect(initials('Maria Lopez'), 'ML');
    expect(firstWhereOr([1, 2, 3], (int x) => x > 1), 2);
    expect(firstWhereOr([1], (int x) => x > 5), isNull);
  });
}
