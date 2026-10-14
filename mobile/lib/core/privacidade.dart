import 'package:flutter/widgets.dart';

import 'formatadores.dart';

/// Olhinho "ocultar valores": troca o dinheiro mostrado nas telas por
/// "R$ ••••" pra quem estiver do lado nao ver. Comeca SEMPRE oculto ao
/// abrir o app (igual o Desktop). So afeta o que aparece na tela --
/// mensagens de WhatsApp, PDF e recibos usam formatarMoeda direto.
final valoresOcultos = ValueNotifier<bool>(true);

const mascaraValor = 'R\$ ••••';

/// formatarMoeda pra exibir na tela: respeita o olhinho.
String moedaTela(num valor) =>
    valoresOcultos.value ? mascaraValor : formatarMoeda(valor);

/// Alterna e reconstroi a arvore inteira mantendo o estado (rolagem,
/// abas): os textos chamam moedaTela no build, entao basta rebuildar.
void alternarValoresOcultos() {
  valoresOcultos.value = !valoresOcultos.value;
  void reconstruir(Element el) {
    el.markNeedsBuild();
    el.visitChildren(reconstruir);
  }

  WidgetsBinding.instance.rootElement?.visitChildren(reconstruir);
}
