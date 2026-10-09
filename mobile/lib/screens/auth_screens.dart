import 'package:flutter/material.dart';

import '../session.dart';
import '../theme.dart';
import '../widgets/common.dart';

const kSupportEmail = 'stamhadsoftware@gmail.com';

class LoadingScreen extends StatelessWidget {
  const LoadingScreen({super.key});
  @override
  Widget build(BuildContext context) => const Scaffold(
        backgroundColor: kNavy,
        body: Center(child: NumeLogo(width: 180, dark: true)),
      );
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _pass = TextEditingController();
  bool _busy = false, _show = false;
  String _err = '';

  Future<void> _go() async {
    if (_email.text.trim().isEmpty || _pass.text.isEmpty) {
      setState(() => _err = 'Type your email and password.');
      return;
    }
    setState(() {
      _busy = true;
      _err = '';
    });
    try {
      await SessionScope.read(context).signIn(_email.text, _pass.text);
    } catch (e) {
      if (mounted) setState(() => _err = friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _forgot() async {
    if (_email.text.trim().isEmpty) {
      setState(() => _err = 'Type your email first, then tap "Forgot password?".');
      return;
    }
    try {
      await SessionScope.read(context).sendReset(_email.text);
      if (mounted) toast(context, 'Check your email for a link to set a new password.');
    } catch (e) {
      if (mounted) setState(() => _err = friendlyError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kNavy,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Card(
                margin: EdgeInsets.zero,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(24, 28, 24, 20),
                  child: AutofillGroup(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      const Align(alignment: Alignment.centerLeft, child: NumeLogo(width: 190)),
                      const SizedBox(height: 26),
                      const Text('Sign in', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 4),
                      const Text('Use the email and password your restaurant gave you.',
                          style: TextStyle(color: kFgSec)),
                      const SizedBox(height: 18),
                      TextField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.email],
                        autocorrect: false,
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(labelText: 'Email'),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _pass,
                        obscureText: !_show,
                        autofillHints: const [AutofillHints.password],
                        onSubmitted: (_) => _go(),
                        decoration: InputDecoration(
                          labelText: 'Password',
                          suffixIcon: IconButton(
                            icon: Icon(_show ? Icons.visibility_off : Icons.visibility),
                            onPressed: () => setState(() => _show = !_show),
                          ),
                        ),
                      ),
                      if (_err.isNotEmpty) ...[
                        const SizedBox(height: 10),
                        Text(_err, style: const TextStyle(color: kDanger)),
                      ],
                      const SizedBox(height: 18),
                      FilledButton(
                        onPressed: _busy ? null : _go,
                        child: _busy
                            ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
                            : const Text('Sign in', style: TextStyle(fontSize: 16)),
                      ),
                      TextButton(onPressed: _forgot, child: const Text('Forgot password?')),
                    ]),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class NoRestaurantScreen extends StatelessWidget {
  const NoRestaurantScreen({super.key});

  Future<void> _setUp(BuildContext context) async {
    final s = SessionScope.read(context);
    final rest = TextEditingController(), you = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Set up your restaurant'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text('Only for the owner. Employees: ask your manager to invite you instead.',
              style: TextStyle(color: kFgSec)),
          const SizedBox(height: 12),
          TextField(controller: rest, decoration: const InputDecoration(labelText: 'Restaurant name')),
          const SizedBox(height: 10),
          TextField(controller: you, decoration: const InputDecoration(labelText: 'Your name')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Set up')),
        ],
      ),
    );
    if (ok != true || rest.text.trim().isEmpty) return;
    try {
      await s.setUpRestaurant(rest.text, you.text);
    } catch (e) {
      if (context.mounted) toast(context, friendlyError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    if (s.isAdmin) {
      return _Message(
        icon: Icons.admin_panel_settings_outlined,
        title: 'Stamhad Software admin',
        body: 'Your admin login isn\'t linked to a restaurant yet. Set up a test restaurant to try every '
            'screen. As admin it opens without a subscription.\n\n'
            'Real restaurants: create the owner\'s account in the desktop app (Settings → Account → '
            'Manage customers). The owner signs in here and sets up their restaurant.',
        actions: [
          FilledButton(onPressed: () => _setUp(context), child: const Text('Set up a test restaurant')),
          TextButton(onPressed: () => s.signOut(), child: const Text('Sign out')),
        ],
      );
    }
    return _Message(
      icon: Icons.storefront_outlined,
      title: 'Not part of a restaurant yet',
      body: 'You\'re signed in as ${s.user?.email ?? ''}, but this login isn\'t linked to a restaurant.\n\n'
          'Ask your manager to invite you from the NUME app (Team → Invite).',
      actions: [
        FilledButton(onPressed: () => s.reload(), child: const Text('Check again')),
        TextButton(onPressed: () => _setUp(context), child: const Text("I'm the owner — set up my restaurant")),
        TextButton(onPressed: () => s.signOut(), child: const Text('Sign out')),
      ],
    );
  }
}

class LockedScreen extends StatelessWidget {
  const LockedScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final sub = s.restaurant['subscription'];
    final never = sub == null;
    return _Message(
      icon: Icons.lock_outline,
      title: never ? 'Waiting for activation' : 'Subscription not active',
      body: never
          ? '${s.restaurantName} is set up. Stamhad Software will switch it on once the subscription starts.\n\n'
              'Questions: $kSupportEmail'
          : '${s.restaurantName}\'s NUME subscription isn\'t active right now.\n\n'
              '${s.isOwner ? 'Contact $kSupportEmail to turn it back on.' : 'Please tell your manager.'}',
      actions: [
        FilledButton(onPressed: () => s.reload(), child: const Text('Check again')),
        TextButton(onPressed: () => s.signOut(), child: const Text('Sign out')),
      ],
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.icon, required this.title, required this.body, required this.actions});
  final IconData icon;
  final String title, body;
  final List<Widget> actions;
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kNavy,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Card(
                margin: EdgeInsets.zero,
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    const Align(alignment: Alignment.centerLeft, child: NumeLogo(width: 150)),
                    const SizedBox(height: 22),
                    Icon(icon, size: 40, color: kAccent),
                    const SizedBox(height: 10),
                    Text(title, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 8),
                    Text(body, style: const TextStyle(color: kFgSec, height: 1.35)),
                    const SizedBox(height: 18),
                    ...actions,
                  ]),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
