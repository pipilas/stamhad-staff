import 'package:flutter/material.dart';

import '../theme.dart';

class NumeLogo extends StatelessWidget {
  const NumeLogo({super.key, this.width = 200, this.dark = false, this.tagline = true});
  final double width;
  final bool dark;
  final bool tagline;
  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Image.asset(dark ? 'assets/wordmark_dark.png' : 'assets/wordmark_light.png', width: width),
        if (tagline) ...[
          const SizedBox(height: 6),
          Text('powered by StamHad',
              style: TextStyle(
                  color: dark ? const Color(0xFF7EB8FF) : kAccent, fontWeight: FontWeight.w700, fontSize: 13)),
        ],
      ],
    );
  }
}

class ShiftPill extends StatelessWidget {
  const ShiftPill(this.shift, {super.key});
  final String shift;
  @override
  Widget build(BuildContext context) {
    final c = kShiftColors[shift] ?? [Colors.grey.shade300, Colors.black87];
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(color: c[0], borderRadius: BorderRadius.circular(20)),
      child: Text(shift, style: TextStyle(color: c[1], fontSize: 12, fontWeight: FontWeight.w700)),
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip(this.status, {super.key});
  final String status;
  @override
  Widget build(BuildContext context) {
    final (bg, fg, label) = switch (status) {
      'approved' => (const Color(0xFFD1FAE5), const Color(0xFF065F46), 'Approved'),
      'denied' => (const Color(0xFFFEE2E2), const Color(0xFF991B1B), 'Not approved'),
      'cancelled' => (const Color(0xFFE5E7EB), const Color(0xFF374151), 'Cancelled'),
      _ => (kWarnBg, kWarnFg, 'Waiting'),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Text(label, style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w700)),
    );
  }
}

class Empty extends StatelessWidget {
  const Empty(this.icon, this.title, [this.sub = '']);
  final IconData icon;
  final String title, sub;
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 48, color: kFgSec.withValues(alpha: 0.6)),
          const SizedBox(height: 12),
          Text(title, textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
          if (sub.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(sub, textAlign: TextAlign.center, style: const TextStyle(color: kFgSec)),
          ],
        ]),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.text, {super.key, this.trailing});
  final String text;
  final Widget? trailing;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 16, 6),
      child: Row(children: [
        Expanded(
          child: Text(text.toUpperCase(),
              style: const TextStyle(color: kFgSec, fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 0.6)),
        ),
        if (trailing != null) trailing!,
      ]),
    );
  }
}

class Avatar extends StatelessWidget {
  const Avatar(this.text, {super.key, this.highlight = false});
  final String text;
  final bool highlight;
  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: 18,
      backgroundColor: highlight ? kAccent : const Color(0xFFE5E7F0),
      child: Text(text,
          style: TextStyle(color: highlight ? Colors.white : kNavy, fontWeight: FontWeight.w700, fontSize: 13)),
    );
  }
}

/// Small "< label >" switcher used for weeks / months / years.
class PeriodBar extends StatelessWidget {
  const PeriodBar({super.key, required this.label, required this.onPrev, required this.onNext, this.onToday});
  final String label;
  final VoidCallback onPrev, onNext;
  final VoidCallback? onToday;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Row(children: [
        IconButton(onPressed: onPrev, icon: const Icon(Icons.chevron_left)),
        Expanded(
          child: GestureDetector(
            onTap: onToday,
            child: Text(label,
                textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
          ),
        ),
        IconButton(onPressed: onNext, icon: const Icon(Icons.chevron_right)),
      ]),
    );
  }
}

void toast(BuildContext context, String text, {bool error = false}) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(text),
      backgroundColor: error ? kDanger : kNavy,
      behavior: SnackBarBehavior.floating,
    ));
}

Future<bool> confirm(BuildContext context, String title, String body, {String yes = 'OK', bool danger = false}) async {
  final r = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: Text(title),
      content: Text(body),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
        FilledButton(
          style: danger ? FilledButton.styleFrom(backgroundColor: kDanger) : null,
          onPressed: () => Navigator.pop(c, true),
          child: Text(yes),
        ),
      ],
    ),
  );
  return r ?? false;
}

String friendlyError(Object e) {
  final s = '$e';
  if (s.contains('permission-denied')) return "You don't have permission to do that.";
  if (s.contains('network') || s.contains('unavailable')) return 'No internet connection. Try again.';
  if (s.contains('invalid-credential') || s.contains('wrong-password') || s.contains('user-not-found')) {
    return 'Wrong email or password.';
  }
  if (s.contains('user-disabled')) return 'This account has been turned off.';
  if (s.contains('too-many-requests')) return 'Too many attempts. Wait a few minutes.';
  if (s.contains('email-already-in-use')) return 'This email already has a NUME login.';
  if (s.contains('invalid-email')) return "That email address doesn't look right.";
  return s.replaceAll(RegExp(r'^\[[^\]]+\]\s*'), '');
}
