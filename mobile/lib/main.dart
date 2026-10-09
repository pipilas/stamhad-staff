import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';

import 'firebase_options.dart';
import 'screens/auth_screens.dart';
import 'screens/home.dart';
import 'session.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  final session = Session()..start();
  runApp(NumeApp(session: session));
}

class NumeApp extends StatelessWidget {
  const NumeApp({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    return SessionScope(
      session: session,
      child: MaterialApp(
        title: 'NUME',
        debugShowCheckedModeBanner: false,
        theme: numeTheme(),
        home: const Root(),
      ),
    );
  }
}

class Root extends StatelessWidget {
  const Root({super.key});
  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 200),
      child: switch (s.phase) {
        Phase.loading => const LoadingScreen(key: ValueKey('loading')),
        Phase.signedOut => const LoginScreen(key: ValueKey('login')),
        Phase.noRestaurant => const NoRestaurantScreen(key: ValueKey('none')),
        Phase.locked => const LockedScreen(key: ValueKey('locked')),
        Phase.ready => HomeScreen(key: ValueKey('home-${s.rid}')),
      },
    );
  }
}
