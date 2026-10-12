import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:dio/io.dart';

import 'tls_confianca.dart';

/// Porta padrao do backend empacotado do Vertex ERP — mesma usada pelo
/// Desktop em modo Servidor/Terminal (ver backend/backend_entry.py e
/// frontend/services/api.py). O celular e, na pratica, mais um
/// "Terminal" apontando pro mesmo Servidor da loja.
const _portaPadrao = '58734';

/// Callback chamado quando uma resposta 401 chega e a renovacao (ver
/// abaixo) tambem falhou — o app usa isso pra derrubar a sessao e
/// voltar pro login, sem o ApiClient precisar saber nada sobre
/// navegacao ou estado de autenticacao.
typedef AoDeslogar = void Function();

/// Tenta renovar o access_token usando o refresh_token guardado.
/// Retorna o novo access_token, ou null se nao tinha refresh_token
/// guardado ou ele ja nao vale mais (expirado/revogado).
typedef AoRenovarToken = Future<String?> Function();

/// Guardado quando o certificado do servidor mudou desde o último pin
/// confiável -- a tela de configurar servidor usa isso pra oferecer o
/// "confiar de novo?" (ver ApiClient.confiarNoCertificadoQueFalhou).
class FalhaCertificado {
  const FalhaCertificado(this.host, this.porta, this.pemNovo);

  final String host;
  final int porta;
  final String pemNovo;
}

class ApiClient {
  ApiClient() : _dio = Dio(), _tls = TlsConfianca() {
    (_dio.httpClientAdapter as IOHttpClientAdapter).createHttpClient = () {
      final client = HttpClient();
      client.badCertificateCallback = _validarCertificado;
      return client;
    };

    _dio.interceptors.add(
      InterceptorsWrapper(
        onError: (erro, handler) async {
          final foiNaoAutorizado = erro.response?.statusCode == 401;

          // extra['renovacaoTentada'] evita ficar tentando de novo pra
          // sempre se o token renovado tambem vier a dar 401 por algum
          // motivo -- so tenta renovar UMA vez por requisicao original.
          final jaTentouRenovar =
              erro.requestOptions.extra['renovacaoTentada'] == true;

          if (foiNaoAutorizado && !jaTentouRenovar && aoRenovarToken != null) {
            final String? novoToken;
            try {
              novoToken = await aoRenovarToken!.call();
            } catch (_) {
              // sem conexao pra renovar: a sessao continua valida, so
              // repassa o erro (sem deslogar)
              handler.next(erro);
              return;
            }

            if (novoToken != null) {
              definirToken(novoToken);

              final requisicaoOriginal = erro.requestOptions
                ..extra['renovacaoTentada'] = true
                ..headers['Authorization'] = 'Bearer $novoToken';

              try {
                final resposta = await _dio.fetch(requisicaoOriginal);
                handler.resolve(resposta);
                return;
              } catch (_) {
                // nem com o token novo funcionou -- segue pro deslogar
              }
            }
          }

          if (foiNaoAutorizado) {
            aoReceber401?.call();
          }

          handler.next(erro);
        },
      ),
    );
  }

  final Dio _dio;
  final TlsConfianca _tls;

  /// Preenchidos de fora (ver core/providers.dart) — o ApiClient nao
  /// conhece o SessaoController pra evitar dependencia circular na
  /// construcao dos providers.
  AoDeslogar? aoReceber401;
  AoRenovarToken? aoRenovarToken;

  /// Setado pelo badCertificateCallback quando um certificado ja
  /// pinado nao bate mais com o que o servidor apresenta agora --
  /// null quando nao ha nenhuma falha desse tipo pendente. A tela de
  /// configurar servidor le isso pra oferecer "confiar de novo?".
  FalhaCertificado? ultimaFalhaCertificado;

  Dio get dio => _dio;

  /// Confia no certificado autoassinado do servidor via TOFU (trust on
  /// first use, mesmo modelo do SSH) -- sem CA de verdade (servidor
  /// local, so IP na rede da loja), aprende a confiar no primeiro
  /// contato e passa a EXIGIR esse mesmo certificado dali pra frente.
  /// Em localhost, reconfia sozinho se mudar (nao ha rede de verdade
  /// no meio pra desconfiar). Em host remoto, rejeita a conexao e
  /// guarda em ultimaFalhaCertificado pra tela decidir o que fazer.
  bool _validarCertificado(X509Certificate cert, String host, int port) {
    final pinado = _tls.certificadoEmMemoria(host, port);

    if (pinado == null) {
      // primeiro contato -- fire-and-forget: o callback e sincrono,
      // nao da pra esperar o storage persistir antes de responder
      unawaited(_tls.confiar(host, port, cert.pem));
      return true;
    }

    if (pinado == cert.pem) {
      return true;
    }

    if (TlsConfianca.ehEnderecoLocal(host)) {
      unawaited(_tls.confiar(host, port, cert.pem));
      return true;
    }

    ultimaFalhaCertificado = FalhaCertificado(host, port, cert.pem);
    return false;
  }

  /// Depois que o usuario confirma "sim, confio nesse certificado
  /// novo" (ver features/server/server_setup_screen.dart) -- grava o
  /// certificado que causou a ultima falha como confiavel.
  Future<void> confiarNoCertificadoQueFalhou() async {
    final falha = ultimaFalhaCertificado;
    if (falha == null) return;

    await _tls.confiar(falha.host, falha.porta, falha.pemNovo);
    ultimaFalhaCertificado = null;
  }

  /// Aceita so o IP (usa a porta padrao), IP:porta, ou uma URL
  /// completa com http(s):// — mesma tolerancia que o Desktop ja tem
  /// em ConectarServidorDialog, pra nao exigir que o dono da loja
  /// saiba o numero da porta de cor.
  static String normalizarEndereco(String bruto) {
    var endereco = bruto.trim();

    if (!endereco.startsWith('http://') && !endereco.startsWith('https://')) {
      endereco = 'https://$endereco';
    }

    final uri = Uri.parse(endereco);

    if (uri.hasPort) {
      return endereco;
    }

    return '$endereco:$_portaPadrao';
  }

  Future<void> definirServidor(String enderecoBruto) async {
    final endereco = normalizarEndereco(enderecoBruto);
    final uri = Uri.parse(endereco);

    await _tls.prepararConfianca(uri.host, uri.port);

    _dio.options.baseUrl = endereco;
    // VPN (Tailscale) pelo 4G as vezes leva 10s+ pra responder -- com
    // prazo curto a tela desistia antes e mostrava erro em vez de carregar
    _dio.options.connectTimeout = const Duration(seconds: 15);
    _dio.options.receiveTimeout = const Duration(seconds: 30);
  }

  void definirToken(String token) {
    _dio.options.headers['Authorization'] = 'Bearer $token';
  }

  void removerToken() {
    _dio.options.headers.remove('Authorization');
  }

  /// GET "/" e o endpoint publico de handshake (backend/main.py) —
  /// usado so pra confirmar que da pra alcancar o servidor. Usa o
  /// mesmo tratamento de certificado (TOFU) que qualquer outra
  /// chamada -- deixa CertificadoServidorMudou (ultimaFalhaCertificado)
  /// setado pra quem chamou decidir, em vez de engolir a causa.
  Future<bool> testarConexao(String enderecoBruto) async {
    final endereco = normalizarEndereco(enderecoBruto);
    final uri = Uri.parse(endereco);

    await _tls.prepararConfianca(uri.host, uri.port);

    final clientTeste = HttpClient()
      ..badCertificateCallback = _validarCertificado;

    final dioTeste = Dio()
      ..httpClientAdapter = IOHttpClientAdapter(
        createHttpClient: () => clientTeste,
      );

    try {
      final resposta = await dioTeste.get(
        endereco,
        options: Options(
          sendTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
        ),
      );
      return resposta.statusCode == 200;
    } catch (_) {
      return false;
    } finally {
      dioTeste.close();
    }
  }
}

/// Extrai o motivo real de uma falha de API pra mostrar ao usuario --
/// um "detail" vindo do backend (permissao negada, regra de negocio
/// violada, sessao expirada etc.) sempre diz mais que um texto fixo
/// generico tipo "Não foi possível fazer X" igual pra qualquer causa
/// (mesmo criterio ja usado em SessaoController._mensagemDeErro).
String mensagemDeErro(Object erro, {required String fallback}) {
  if (erro is DioException) {
    final dados = erro.response?.data;
    if (dados is Map && dados['detail'] is String) {
      return dados['detail'] as String;
    }
  }

  return fallback;
}
