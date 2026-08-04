import 'package:flutter/material.dart';

/// Paleta do Vertex ERP — os mesmos valores de
/// frontend/design/tokens.py, pra manter a marca consistente entre o
/// Desktop e o Mobile.
class VertexColors {
  VertexColors._();

  static const primaria = Color(0xFF2563EB);
  static const primariaHover = Color(0xFF1D4ED8);
  static const primariaClara = Color(0xFFEFF6FF);

  static const secundaria = Color(0xFF16A34A);
  static const secundariaHover = Color(0xFF15803D);

  static const sucesso = Color(0xFF22C55E);
  static const sucessoClaro = Color(0xFFF0FDF4);

  static const alerta = Color(0xFFF59E0B);
  static const alertaClaro = Color(0xFFFFFBEB);

  static const erro = Color(0xFFDC2626);
  static const erroHover = Color(0xFFB91C1C);
  static const erroClaro = Color(0xFFFEF2F2);

  static const fundo = Color(0xFFF5F7FA);
  static const sidebar = Color(0xFF18181B);

  static const card = Color(0xFFFFFFFF);
  static const borda = Color(0xFFE5E7EB);

  static const texto = Color(0xFF1E293B);
  static const textoSecundario = Color(0xFF64748B);
  static const textoTerciario = Color(0xFF94A3B8);

  // Tons escuros pensados pra manter o mesmo contraste do claro, nao
  // uma simples inversao (mesmo criterio usado no tema escuro do
  // roteiro do app).
  static const fundoEscuro = Color(0xFF0B0D13);
  static const cardEscuro = Color(0xFF171A22);
  static const bordaEscura = Color(0xFF272B36);
  static const textoEscuro = Color(0xFFE7E9EE);
  static const textoSecundarioEscuro = Color(0xFF9BA3B4);
  static const primariaEscura = Color(0xFF5B8DEF);
}
