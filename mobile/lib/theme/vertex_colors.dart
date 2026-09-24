import 'package:flutter/material.dart';

/// Uma paleta completa (clara ou escura) -- mesmos papeis e valores de
/// frontend/design/tokens.py (_CLARO/_ESCURO), pra o Mobile ter a mesma
/// cara do Desktop. Mudou la, muda aqui.
class VertexPaleta {
  const VertexPaleta({
    required this.primaria,
    required this.primariaHover,
    required this.primariaClara,
    required this.secundaria,
    required this.secundariaHover,
    required this.sucesso,
    required this.sucessoClaro,
    required this.alerta,
    required this.alertaClaro,
    required this.alertaTexto,
    required this.erro,
    required this.erroHover,
    required this.erroClaro,
    required this.fundo,
    required this.sidebar,
    required this.card,
    required this.borda,
    required this.bordaForte,
    required this.texto,
    required this.textoSecundario,
    required this.textoTerciario,
  });

  final Color primaria;
  final Color primariaHover;
  final Color primariaClara;
  final Color secundaria;
  final Color secundariaHover;
  final Color sucesso;
  final Color sucessoClaro;
  final Color alerta;
  final Color alertaClaro;
  final Color alertaTexto;
  final Color erro;
  final Color erroHover;
  final Color erroClaro;
  final Color fundo;
  final Color sidebar;
  final Color card;
  final Color borda;
  final Color bordaForte;
  final Color texto;
  final Color textoSecundario;
  final Color textoTerciario;

  static const claro = VertexPaleta(
    primaria: Color(0xFF1B4B8F),
    primariaHover: Color(0xFF123A73),
    primariaClara: Color(0xFFE8EEF9),
    secundaria: Color(0xFF0D7D6C),
    secundariaHover: Color(0xFF095F52),
    sucesso: Color(0xFF149174),
    sucessoClaro: Color(0xFFE7F5F1),
    alerta: Color(0xFFB4750F),
    alertaClaro: Color(0xFFFBF1E1),
    alertaTexto: Color(0xFF8A5A0C),
    erro: Color(0xFFA9362A),
    erroHover: Color(0xFF8A2B21),
    erroClaro: Color(0xFFFBEBE8),
    fundo: Color(0xFFF5F3EF),
    sidebar: Color(0xFF101F38),
    card: Color(0xFFFFFFFF),
    borda: Color(0xFFE4DFD5),
    bordaForte: Color(0xFFD3CCBD),
    texto: Color(0xFF16213B),
    textoSecundario: Color(0xFF5B6B85),
    textoTerciario: Color(0xFF5C6A82),
  );

  static const escuro = VertexPaleta(
    primaria: Color(0xFF4C7FC9),
    primariaHover: Color(0xFF6E9CDA),
    primariaClara: Color(0xFF1C2A3F),
    secundaria: Color(0xFF2FA88F),
    secundariaHover: Color(0xFF4FC2A8),
    sucesso: Color(0xFF3FBFA0),
    sucessoClaro: Color(0xFF163A31),
    alerta: Color(0xFFD69A3E),
    alertaClaro: Color(0xFF3A2A11),
    alertaTexto: Color(0xFFE4B063),
    erro: Color(0xFFD9695C),
    erroHover: Color(0xFFE68A7F),
    erroClaro: Color(0xFF3A1B17),
    fundo: Color(0xFF0E1420),
    sidebar: Color(0xFF0A121F),
    card: Color(0xFF182130),
    borda: Color(0xFF29334A),
    bordaForte: Color(0xFF39445E),
    texto: Color(0xFFECE7DC),
    textoSecundario: Color(0xFF9AA3B0),
    textoTerciario: Color(0xFF818B9D),
  );
}

/// Paleta ativa, lida pelas telas como `VertexColors.primaria` -- mesmo
/// esquema do Desktop (tokens.aplicar): main.dart chama [aplicar]
/// conforme o tema claro/escuro do celular, e as telas continuam lendo
/// os mesmos nomes sem saber de tema.
class VertexColors {
  VertexColors._();

  static VertexPaleta _p = VertexPaleta.claro;

  static bool get escuro => identical(_p, VertexPaleta.escuro);

  static void aplicar({required bool escuro}) {
    _p = escuro ? VertexPaleta.escuro : VertexPaleta.claro;
  }

  static Color get primaria => _p.primaria;
  static Color get primariaHover => _p.primariaHover;
  static Color get primariaClara => _p.primariaClara;
  static Color get secundaria => _p.secundaria;
  static Color get secundariaHover => _p.secundariaHover;
  static Color get sucesso => _p.sucesso;
  static Color get sucessoClaro => _p.sucessoClaro;
  static Color get alerta => _p.alerta;
  static Color get alertaClaro => _p.alertaClaro;
  static Color get alertaTexto => _p.alertaTexto;
  static Color get erro => _p.erro;
  static Color get erroHover => _p.erroHover;
  static Color get erroClaro => _p.erroClaro;
  static Color get fundo => _p.fundo;
  static Color get sidebar => _p.sidebar;
  static Color get card => _p.card;
  static Color get borda => _p.borda;
  static Color get bordaForte => _p.bordaForte;
  static Color get texto => _p.texto;
  static Color get textoSecundario => _p.textoSecundario;
  static Color get textoTerciario => _p.textoTerciario;
}
