import 'package:flutter/material.dart';

import 'vertex_colors.dart';

class VertexTheme {
  VertexTheme._();

  static ThemeData get claro {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: VertexColors.primaria,
      brightness: Brightness.light,
      primary: VertexColors.primaria,
      secondary: VertexColors.secundaria,
      error: VertexColors.erro,
      surface: VertexColors.card,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: VertexColors.fundo,
      textTheme: _textTheme(VertexColors.texto),
      appBarTheme: const AppBarTheme(
        backgroundColor: VertexColors.card,
        foregroundColor: VertexColors.texto,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: CardThemeData(
        color: VertexColors.card,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: VertexColors.borda),
        ),
      ),
      inputDecorationTheme: _inputTheme(
        preenchimento: const Color(0xFFEEF0F3),
        borda: VertexColors.borda,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: VertexColors.sidebar,
          foregroundColor: Colors.white,
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
    );
  }

  static ThemeData get escuro {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: VertexColors.primariaEscura,
      brightness: Brightness.dark,
      primary: VertexColors.primariaEscura,
      secondary: VertexColors.secundaria,
      error: VertexColors.erro,
      surface: VertexColors.cardEscuro,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: VertexColors.fundoEscuro,
      textTheme: _textTheme(VertexColors.textoEscuro),
      appBarTheme: const AppBarTheme(
        backgroundColor: VertexColors.fundoEscuro,
        foregroundColor: VertexColors.textoEscuro,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: CardThemeData(
        color: VertexColors.cardEscuro,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: VertexColors.bordaEscura),
        ),
      ),
      inputDecorationTheme: _inputTheme(
        preenchimento: const Color(0xFF1D2029),
        borda: VertexColors.bordaEscura,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: VertexColors.primariaEscura,
          foregroundColor: VertexColors.fundoEscuro,
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
    );
  }

  static TextTheme _textTheme(Color cor) {
    return TextTheme(
      headlineMedium: TextStyle(
        fontWeight: FontWeight.w800,
        color: cor,
        fontSize: 26,
      ),
      titleLarge: TextStyle(fontWeight: FontWeight.w700, color: cor),
      titleMedium: TextStyle(fontWeight: FontWeight.w600, color: cor),
      bodyLarge: TextStyle(color: cor),
      bodyMedium: TextStyle(color: cor),
    );
  }

  static InputDecorationTheme _inputTheme({
    required Color preenchimento,
    required Color borda,
  }) {
    return InputDecorationTheme(
      filled: true,
      fillColor: preenchimento,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: 16,
        vertical: 14,
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: VertexColors.primaria, width: 1.5),
      ),
    );
  }
}
