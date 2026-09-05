import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:open_filex/open_filex.dart';
import 'package:share_plus/share_plus.dart';

import '../../core/api_client.dart';
import '../../core/providers.dart';
import '../../models/conta_pagar.dart';
import '../../models/conta_pagar_evento.dart';
import '../../models/conta_receber.dart';

/// Nome de plataforma pra anexar nos eventos de auditoria (ver
/// ContaPagarEvento no backend) -- so um rotulo, nao muda nenhuma
/// regra de negocio.
String get _dispositivo => Platform.isAndroid ? 'Android' : 'iOS';

/// Um arquivo escolhido no aparelho (comprovante/boleto) antes de ser
/// enviado -- ja carregado em memoria, pra so precisar base64-encodar
/// na hora de montar a requisicao.
class AnexoEscolhido {
  const AnexoEscolhido({
    required this.bytes,
    required this.nome,
    required this.tipo,
  });

  final List<int> bytes;
  final String nome;
  final String tipo;

  String get base64 => base64Encode(bytes);
}

final contasPagarProvider = FutureProvider.autoDispose<List<ContaPagar>>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/contas-pagar/');

  final contas = (resposta.data as List<dynamic>)
      .map((json) => ContaPagar.fromJson(json as Map<String, dynamic>))
      .where((conta) => conta.status != 'CANCELADO')
      .toList();

  contas.sort((a, b) => a.dataVencimento.compareTo(b.dataVencimento));
  return contas;
});

/// Linha do tempo de auditoria de uma despesa (ver backend GET
/// /contas-pagar/{id}/eventos).
final eventosContaProvider = FutureProvider.autoDispose
    .family<List<ContaPagarEvento>, int>((ref, contaId) async {
      final api = ref.watch(apiClientProvider);
      final resposta = await api.dio.get('/contas-pagar/$contaId/eventos');

      return (resposta.data as List<dynamic>)
          .map(
            (json) => ContaPagarEvento.fromJson(json as Map<String, dynamic>),
          )
          .toList();
    });

final contasReceberProvider = FutureProvider.autoDispose<List<ContaReceber>>((
  ref,
) async {
  final api = ref.watch(apiClientProvider);
  final resposta = await api.dio.get('/contas-receber/');

  final contas = (resposta.data as List<dynamic>)
      .map((json) => ContaReceber.fromJson(json as Map<String, dynamic>))
      .where((conta) => conta.status != 'CANCELADO')
      .toList();

  contas.sort((a, b) => a.dataVencimento.compareTo(b.dataVencimento));
  return contas;
});

class FinanceiroActions {
  FinanceiroActions(this._ref);

  final Ref _ref;

  /// Marca uma despesa como paga -- forma de pagamento e comprovante
  /// sao opcionais (o card ainda oferece "Marcar como paga" direto,
  /// sem passar pelo formulario completo).
  Future<String?> pagarConta(
    int contaId, {
    String? formaPagamento,
    String? banco,
    String? numeroTransacao,
    AnexoEscolhido? comprovante,
  }) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.post(
        '/contas-pagar/$contaId/pagar',
        data: {
          'forma_pagamento': ?formaPagamento,
          if (banco != null && banco.isNotEmpty) 'banco_pagamento': banco,
          if (numeroTransacao != null && numeroTransacao.isNotEmpty)
            'numero_transacao': numeroTransacao,
          if (comprovante != null) ...{
            'comprovante_base64': comprovante.base64,
            'comprovante_nome': comprovante.nome,
            'comprovante_tipo': comprovante.tipo,
          },
          'dispositivo': _dispositivo,
        },
      );
      _ref.invalidate(contasPagarProvider);
      return null;
    } catch (e) {
      return mensagemDeErro(
        e,
        fallback: 'Não foi possível marcar essa conta como paga.',
      );
    }
  }

  /// Atualiza so a observacao da despesa -- usado pelo formulario de
  /// pagamento pra anexar a nota "Pago via X" mais o texto digitado
  /// pelo usuario, antes de confirmar o pagamento em si (mesmo padrão
  /// do Desktop).
  Future<String?> atualizarObservacao(int contaId, String observacao) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.put(
        '/contas-pagar/$contaId',
        data: {'observacao': observacao},
      );
      return null;
    } catch (e) {
      return mensagemDeErro(
        e,
        fallback: 'Não foi possível salvar a observação.',
      );
    }
  }

  /// Troca o comprovante de uma despesa ja paga (ver backend PUT
  /// /contas-pagar/{id}/comprovante-pagamento).
  Future<String?> trocarComprovante(
    int contaId,
    AnexoEscolhido comprovante,
  ) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.put(
        '/contas-pagar/$contaId/comprovante-pagamento',
        data: {
          'comprovante_base64': comprovante.base64,
          'comprovante_nome': comprovante.nome,
          'comprovante_tipo': comprovante.tipo,
          'dispositivo': _dispositivo,
        },
      );
      _ref.invalidate(contasPagarProvider);
      return null;
    } catch (e) {
      return mensagemDeErro(
        e,
        fallback: 'Não foi possível trocar o comprovante.',
      );
    }
  }

  /// Cancela uma despesa -- pendente cancela na hora; ja paga e o
  /// usuario nao e admin vira um pedido de aprovacao (ver backend
  /// POST /contas-pagar/{id}/cancelar).
  Future<({bool aprovacaoPendente, String? erro})> cancelarConta(
    int contaId,
  ) async {
    try {
      final api = _ref.read(apiClientProvider);
      final resposta = await api.dio.post(
        '/contas-pagar/$contaId/cancelar',
        queryParameters: {'dispositivo': _dispositivo},
      );
      _ref.invalidate(contasPagarProvider);

      final aprovacaoPendente =
          (resposta.data as Map<String, dynamic>)['aprovacao_pendente']
              as bool? ??
          false;

      return (aprovacaoPendente: aprovacaoPendente, erro: null);
    } catch (e) {
      return (
        aprovacaoPendente: false,
        erro: mensagemDeErro(
          e,
          fallback: 'Não foi possível cancelar essa despesa.',
        ),
      );
    }
  }

  Future<String?> receberConta(int contaId) async {
    try {
      final api = _ref.read(apiClientProvider);
      await api.dio.post('/contas-receber/$contaId/receber');
      _ref.invalidate(contasReceberProvider);
      return null;
    } catch (e) {
      return mensagemDeErro(
        e,
        fallback: 'Não foi possível marcar essa conta como recebida.',
      );
    }
  }

  /// Baixa um arquivo anexado a uma conta a pagar (boleto ou
  /// comprovante de pagamento) pra uma pasta temporaria do aparelho --
  /// devolve o caminho local, pra quem chamou decidir se abre ou
  /// compartilha.
  Future<({String? caminho, String? erro})> _baixar(
    String endpoint,
    String nomeArquivo,
  ) async {
    try {
      final api = _ref.read(apiClientProvider);

      final resposta = await api.dio.get<List<int>>(
        endpoint,
        options: Options(responseType: ResponseType.bytes),
      );

      final pasta = await Directory.systemTemp.createTemp('vertex_doc_');
      final arquivo = File('${pasta.path}/$nomeArquivo');
      await arquivo.writeAsBytes(resposta.data!);

      return (caminho: arquivo.path, erro: null);
    } catch (e) {
      return (
        caminho: null,
        erro: mensagemDeErro(
          e,
          fallback: 'Não foi possível baixar o arquivo.',
        ),
      );
    }
  }

  Future<String?> _baixarEAbrir(String endpoint, String nomeArquivo) async {
    final (:caminho, :erro) = await _baixar(endpoint, nomeArquivo);
    if (erro != null) return erro;

    final resultado = await OpenFilex.open(caminho!);

    if (resultado.type != ResultType.done) {
      return 'Não foi possível abrir o arquivo.';
    }

    return null;
  }

  Future<String?> _baixarECompartilhar(
    String endpoint,
    String nomeArquivo,
  ) async {
    final (:caminho, :erro) = await _baixar(endpoint, nomeArquivo);
    if (erro != null) return erro;

    await SharePlus.instance.share(
      ShareParams(files: [XFile(caminho!)]),
    );

    return null;
  }

  /// Boleto/nota original anexado na criação da despesa (ver backend
  /// GET /contas-pagar/{id}/documento).
  Future<String?> abrirDocumento(ContaPagar conta) {
    return _baixarEAbrir(
      '/contas-pagar/${conta.id}/documento',
      conta.documentoNome ?? 'documento.pdf',
    );
  }

  /// Comprovante de pagamento (print de PIX, transferência etc.)
  /// anexado ao marcar a despesa como paga (ver backend GET
  /// /contas-pagar/{id}/comprovante-pagamento).
  Future<String?> abrirComprovantePagamento(ContaPagar conta) {
    return _baixarEAbrir(
      '/contas-pagar/${conta.id}/comprovante-pagamento',
      conta.comprovantePagamentoNome ?? 'comprovante.pdf',
    );
  }

  /// Compartilha o boleto (WhatsApp, e-mail etc.) via a folha de
  /// compartilhamento nativa do aparelho.
  Future<String?> compartilharDocumento(ContaPagar conta) {
    return _baixarECompartilhar(
      '/contas-pagar/${conta.id}/documento',
      conta.documentoNome ?? 'documento.pdf',
    );
  }
}

final financeiroActionsProvider = Provider(
  (ref) => FinanceiroActions(ref),
);
