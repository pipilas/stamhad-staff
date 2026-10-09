import 'package:flutter/material.dart';

const kNavy = Color(0xFF16213A);
const kAccent = Color(0xFF4F46E5);
const kAccentSoft = Color(0xFF8B8AFF);
const kPage = Color(0xFFF4F5F9);
const kFgSec = Color(0xFF6B7280);
const kSuccess = Color(0xFF10B981);
const kDanger = Color(0xFFEF4444);
const kWarnBg = Color(0xFFFEF3C7);
const kWarnFg = Color(0xFF92400E);

const Map<String, List<Color>> kShiftColors = {
  'Morning': [Color(0xFFFCD34D), Color(0xFF78350F)],
  'Brunch': [Color(0xFF34D399), Color(0xFF064E3B)],
  'Dinner': [Color(0xFF818CF8), Color(0xFF312E81)],
};

ThemeData numeTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: kAccent, primary: kAccent, surface: Colors.white);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: kPage,
    appBarTheme: const AppBarTheme(
      backgroundColor: kPage,
      foregroundColor: kNavy,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(color: kNavy, fontSize: 22, fontWeight: FontWeight.w700),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(64, 48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    navigationBarTheme: const NavigationBarThemeData(
      backgroundColor: Colors.white,
      indicatorColor: Color(0xFFE0E0FF),
    ),
  );
}
