import 'package:flutter/material.dart';

import 'vertex_colors.dart';

/// Tema do app montado a partir da mesma paleta/escala do Desktop
/// (frontend/design/tokens.py): Inter, raios 8/12/16, superficie
/// branca com borda fina em vez de sombra/tinta do Material 3.
class VertexTheme {
  VertexTheme._();

  static const radiusSm = 8.0;
  static const radiusMd = 12.0;
  static const radiusLg = 16.0;

  static ThemeData get claro => _tema(VertexPaleta.claro, Brightness.light);

  static ThemeData get escuro => _tema(VertexPaleta.escuro, Brightness.dark);

  static ThemeData _tema(VertexPaleta c, Brightness brilho) {
    final escuro = brilho == Brightness.dark;
    final sobrePrimaria = Colors.white;

    final esquema = ColorScheme(
      brightness: brilho,
      primary: c.primaria,
      onPrimary: sobrePrimaria,
      primaryContainer: c.primariaClara,
      onPrimaryContainer: escuro ? c.texto : c.primaria,
      secondary: c.secundaria,
      onSecondary: Colors.white,
      secondaryContainer: c.sucessoClaro,
      onSecondaryContainer: escuro ? c.texto : c.secundariaHover,
      tertiary: c.alerta,
      onTertiary: Colors.white,
      error: c.erro,
      onError: Colors.white,
      errorContainer: c.erroClaro,
      onErrorContainer: escuro ? c.texto : c.erroHover,
      surface: c.card,
      onSurface: c.texto,
      onSurfaceVariant: c.textoSecundario,
      surfaceContainerLowest: c.card,
      surfaceContainerLow: c.card,
      surfaceContainer: c.card,
      surfaceContainerHigh: c.card,
      surfaceContainerHighest: c.fundo,
      outline: c.bordaForte,
      outlineVariant: c.borda,
      shadow: Colors.black,
      scrim: Colors.black54,
      inverseSurface: escuro ? c.texto : c.sidebar,
      onInverseSurface: escuro ? c.fundo : Colors.white,
      inversePrimary: escuro
          ? VertexPaleta.claro.primaria
          : VertexPaleta.escuro.primaria,
      surfaceTint: Colors.transparent,
    );

    final texto = _textTheme(c);

    RoundedRectangleBorder forma(double r) =>
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(r));

    const alturaBotao = Size(64, 48);
    final estiloRotuloBotao = texto.labelLarge;

    return ThemeData(
      useMaterial3: true,
      brightness: brilho,
      colorScheme: esquema,
      fontFamily: 'Inter',
      textTheme: texto,
      scaffoldBackgroundColor: c.fundo,
      canvasColor: c.fundo,
      dividerColor: c.borda,
      splashFactory: InkSparkle.splashFactory,
      visualDensity: VisualDensity.standard,

      appBarTheme: AppBarTheme(
        backgroundColor: c.fundo,
        foregroundColor: c.texto,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
        titleSpacing: 20,
        titleTextStyle: texto.titleLarge,
        iconTheme: IconThemeData(color: c.texto, size: 22),
      ),

      cardTheme: CardThemeData(
        color: c.card,
        elevation: 0,
        margin: EdgeInsets.zero,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusLg),
          side: BorderSide(color: c.borda),
        ),
      ),

      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: c.card,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        height: 66,
        indicatorColor: c.primariaClara,
        indicatorShape: forma(radiusMd),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        iconTheme: WidgetStateProperty.resolveWith(
          (s) => IconThemeData(
            size: 22,
            color: s.contains(WidgetState.selected)
                ? c.primaria
                : c.textoSecundario,
          ),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (s) => TextStyle(
            fontFamily: 'Inter',
            fontSize: 11.5,
            fontWeight: s.contains(WidgetState.selected)
                ? FontWeight.w700
                : FontWeight.w500,
            color: s.contains(WidgetState.selected)
                ? c.texto
                : c.textoSecundario,
          ),
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: c.primaria,
          foregroundColor: sobrePrimaria,
          disabledBackgroundColor: c.borda,
          disabledForegroundColor: c.textoTerciario,
          elevation: 0,
          minimumSize: alturaBotao,
          shape: forma(radiusMd),
          textStyle: estiloRotuloBotao,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: c.primaria,
          foregroundColor: sobrePrimaria,
          disabledBackgroundColor: c.borda,
          disabledForegroundColor: c.textoTerciario,
          minimumSize: alturaBotao,
          shape: forma(radiusMd),
          textStyle: estiloRotuloBotao,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: c.texto,
          backgroundColor: c.card,
          side: BorderSide(color: c.bordaForte),
          minimumSize: alturaBotao,
          shape: forma(radiusMd),
          textStyle: estiloRotuloBotao,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: c.primaria,
          shape: forma(radiusSm),
          textStyle: estiloRotuloBotao,
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(foregroundColor: c.texto),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: c.primaria,
        foregroundColor: sobrePrimaria,
        elevation: 2,
        shape: forma(radiusLg),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.card,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 14,
        ),
        labelStyle: TextStyle(color: c.textoSecundario),
        floatingLabelStyle: TextStyle(
          color: c.primaria,
          fontWeight: FontWeight.w600,
        ),
        hintStyle: TextStyle(color: c.textoTerciario),
        prefixIconColor: c.textoSecundario,
        suffixIconColor: c.textoSecundario,
        border: _borda(c.borda),
        enabledBorder: _borda(c.borda),
        disabledBorder: _borda(c.borda),
        focusedBorder: _borda(c.primaria, largura: 1.5),
        errorBorder: _borda(c.erro),
        focusedErrorBorder: _borda(c.erro, largura: 1.5),
        errorStyle: TextStyle(color: c.erro, fontSize: 12),
      ),

      chipTheme: ChipThemeData(
        backgroundColor: c.card,
        selectedColor: c.primariaClara,
        disabledColor: c.fundo,
        side: BorderSide(color: c.borda),
        shape: const StadiumBorder(),
        showCheckmark: false,
        labelStyle: TextStyle(
          fontFamily: 'Inter',
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: c.textoSecundario,
        ),
        secondaryLabelStyle: TextStyle(
          fontFamily: 'Inter',
          fontSize: 13,
          fontWeight: FontWeight.w700,
          color: escuro ? c.texto : c.primaria,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      ),

      tabBarTheme: TabBarThemeData(
        labelColor: c.texto,
        unselectedLabelColor: c.textoSecundario,
        indicatorColor: c.primaria,
        indicatorSize: TabBarIndicatorSize.label,
        dividerColor: c.borda,
        labelStyle: texto.titleSmall,
        unselectedLabelStyle: texto.titleSmall?.copyWith(
          fontWeight: FontWeight.w500,
        ),
      ),

      listTileTheme: ListTileThemeData(
        iconColor: c.textoSecundario,
        textColor: c.texto,
        titleTextStyle: texto.bodyLarge?.copyWith(fontWeight: FontWeight.w600),
        subtitleTextStyle: texto.bodySmall,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16),
        shape: forma(radiusMd),
      ),

      dividerTheme: DividerThemeData(color: c.borda, thickness: 1, space: 1),

      dialogTheme: DialogThemeData(
        backgroundColor: c.card,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusLg),
          side: BorderSide(color: c.borda),
        ),
        titleTextStyle: texto.titleLarge,
        contentTextStyle: texto.bodyMedium?.copyWith(
          color: c.textoSecundario,
          height: 1.45,
        ),
      ),

      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: c.card,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        dragHandleColor: c.bordaForte,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(radiusLg)),
        ),
      ),

      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: escuro ? c.texto : c.sidebar,
        contentTextStyle: TextStyle(
          fontFamily: 'Inter',
          fontSize: 14,
          fontWeight: FontWeight.w500,
          color: escuro ? c.fundo : Colors.white,
        ),
        actionTextColor: escuro
            ? c.primaria
            : VertexPaleta.escuro.primariaHover,
        shape: forma(radiusMd),
        elevation: 0,
      ),

      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: c.primaria,
        linearTrackColor: c.primariaClara,
        circularTrackColor: Colors.transparent,
      ),

      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: escuro ? c.texto : c.sidebar,
          borderRadius: BorderRadius.circular(radiusSm),
        ),
        textStyle: TextStyle(
          fontFamily: 'Inter',
          fontSize: 12,
          color: escuro ? c.fundo : Colors.white,
        ),
      ),

      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? Colors.white : null,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? c.primaria : null,
        ),
      ),
    );
  }

  static OutlineInputBorder _borda(Color cor, {double largura = 1}) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(radiusMd),
      borderSide: BorderSide(color: cor, width: largura),
    );
  }

  /// Escala do Desktop (tokens.TAMANHO_*: 11/12/13/14/16/20/28), um
  /// degrau acima no corpo de texto porque no celular 13px fica pequeno.
  /// Numeros tabulares nos titulos: valor em R$ nao "dança" ao atualizar.
  static TextTheme _textTheme(VertexPaleta c) {
    const tabular = [FontFeature.tabularFigures()];

    // fontFamily explicito em todo estilo: quem usa o TextStyle direto
    // (titulo da AppBar, dialogo) nao passa pelo fontFamily do ThemeData
    // e cairia na Roboto do Android.
    return TextTheme(
      displaySmall: TextStyle(
        fontSize: 32,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.8,
        height: 1.15,
        color: c.texto,
        fontFeatures: tabular,
      ),
      headlineMedium: TextStyle(
        fontSize: 28,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.6,
        height: 1.2,
        color: c.texto,
        fontFeatures: tabular,
      ),
      headlineSmall: TextStyle(
        fontSize: 22,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.4,
        color: c.texto,
        fontFeatures: tabular,
      ),
      titleLarge: TextStyle(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.3,
        color: c.texto,
        fontFeatures: tabular,
      ),
      titleMedium: TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.1,
        color: c.texto,
        fontFeatures: tabular,
      ),
      titleSmall: TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        color: c.texto,
      ),
      bodyLarge: TextStyle(fontSize: 15, height: 1.4, color: c.texto),
      bodyMedium: TextStyle(fontSize: 14, height: 1.4, color: c.texto),
      bodySmall: TextStyle(
        fontSize: 12.5,
        height: 1.35,
        color: c.textoSecundario,
      ),
      labelLarge: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 14.5,
        fontWeight: FontWeight.w600,
        letterSpacing: 0,
      ),
      labelMedium: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w600,
        color: c.textoSecundario,
      ),
      labelSmall: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.4,
        color: c.textoSecundario,
      ),
    ).apply(fontFamily: 'Inter');
  }
}
