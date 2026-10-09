// (kept so `flutter create` doesn't add its counter-app sample test)
import 'package:flutter_test/flutter_test.dart';
import 'package:nume/util.dart';

void main() {
  test('shift names match the desktop app', () {
    expect(kShifts, ['Morning', 'Brunch', 'Dinner']);
  });
}
