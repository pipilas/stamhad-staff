import 'package:flutter_test/flutter_test.dart';
import 'package:nume/models.dart';
import 'package:nume/tipsplit.dart';

void main() {
  Position pos(String n) => Position.guess(n);

  test('round split always adds up', () {
    final r = roundSplit(100, {'a': 1, 'b': 1, 'c': 1});
    expect(r.values.fold<double>(0, (a, b) => a + b), closeTo(100, 0.001));
    expect(r.values.toSet().length, greaterThan(1)); // 33.34 / 33.33 / 33.33
  });

  test('floor by points, bar: barback % then bartenders', () {
    final people = [
      const TipPerson('s1', 'Server', '4:00 PM', '11:00 PM'),
      const TipPerson('s2', 'Server', '4:00 PM', '11:00 PM'),
      const TipPerson('b1', 'Busser', '4:00 PM', '11:00 PM'),
      const TipPerson('bt', 'Bartender', '4:00 PM', '11:00 PM'),
      const TipPerson('bb', 'Barback', '4:00 PM', '11:00 PM'),
      const TipPerson('k', 'Cook', '3:00 PM', '11:00 PM'),
    ];
    final r = splitShiftTips(
        people: people, floorPool: 1000, barPool: 500, positionOf: pos, byTime: false);
    // points: server 10, server 10, busser 5, bartender 5, barback 2 = 32
    expect(r.lines['s1']!.floor, closeTo(312.5, 0.01));
    expect(r.lines['k']!.total, 0);
    expect(r.lines['bb']!.bar, 100); // 20% of the bar
    expect(r.lines['bt']!.bar, 400);
    final sum = r.lines.values.fold<double>(0, (a, l) => a + l.total);
    expect(sum, closeTo(1500, 0.001));
  });

  test('by time: full share after 11 PM, tip clock starts 4:05', () {
    expect(tipHoursBetween('3:30 PM', '11:40 PM', '11:00 PM', '4:05 PM'), closeTo(6.92, 0.01));
    expect(tipHoursBetween('5:00 PM', '10:00 PM', '11:00 PM', '4:05 PM'), 5);
    final r = splitShiftTips(
      people: const [TipPerson('a', 'Server', '4:00 PM', '11:30 PM'), TipPerson('b', 'Server', '7:00 PM', '11:00 PM')],
      floorPool: 100, barPool: 0, positionOf: pos, byTime: true, fullShare: '11:00 PM', tipStart: '4:05 PM');
    expect(r.lines['a']!.floor, greaterThan(r.lines['b']!.floor));
    expect(r.lines['a']!.floor + r.lines['b']!.floor, closeTo(100, 0.001));
  });

  test('no bartender: bar pool shows as unassigned', () {
    final r = splitShiftTips(
        people: const [TipPerson('s', 'Server', '4:00 PM', '11:00 PM')],
        floorPool: 50, barPool: 80, positionOf: pos, byTime: false);
    expect(r.barUnassigned, 80);
  });
}
