import 'package:flutter/material.dart';

import '../session.dart';
import 'account.dart';
import 'inventory.dart';
import 'schedule.dart';
import 'timeoff.dart';
import 'tips.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final pages = const [ScheduleScreen(), TimeOffScreen(), TipsScreen(), InventoryScreen(), AccountScreen()];
    return Scaffold(
      body: IndexedStack(index: _tab, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: [
          const NavigationDestination(
              icon: Icon(Icons.calendar_month_outlined), selectedIcon: Icon(Icons.calendar_month), label: 'Schedule'),
          NavigationDestination(
            icon: s.isManager ? PendingBadge(child: const Icon(Icons.event_busy_outlined)) : const Icon(Icons.event_busy_outlined),
            selectedIcon: const Icon(Icons.event_busy),
            label: 'Days off',
          ),
          const NavigationDestination(
              icon: Icon(Icons.payments_outlined), selectedIcon: Icon(Icons.payments), label: 'Tips'),
          const NavigationDestination(
              icon: Icon(Icons.inventory_2_outlined), selectedIcon: Icon(Icons.inventory_2), label: 'Inventory'),
          NavigationDestination(
              icon: const Icon(Icons.person_outline), selectedIcon: const Icon(Icons.person), label: s.isManager ? 'Team' : 'Me'),
        ],
      ),
    );
  }
}

/// Red dot with the number of day-off requests waiting for a manager.
class PendingBadge extends StatelessWidget {
  const PendingBadge({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return StreamBuilder(
      stream: s.col('timeoff').where('status', isEqualTo: 'pending').snapshots(),
      builder: (c, snap) {
        final n = snap.data?.size ?? 0;
        return Badge(isLabelVisible: n > 0, label: Text('$n'), child: child);
      },
    );
  }
}
