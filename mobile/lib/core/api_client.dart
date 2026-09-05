import 'package:dio/dio.dart';

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

class ApiClient {
  ApiClient() : _dio = Dio() {
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
            final novoToken = await aoRenovarToken!.call();

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

  /// Preenchidos de fora (ver core/providers.dart) — o ApiClient nao
  /// conhece o SessaoController pra evitar dependencia circular na
  /// construcao dos providers.
  AoDeslogar? aoReceber401;
  AoRenovarToken? aoRenovarToken;

  Dio get dio => _dio;

  /// Aceita so o IP (usa a porta padrao), IP:porta, ou uma URL
  /// completa com http(s):// — mesma tolerancia que o Desktop ja tem
  /// em ConectarServidorDialog, pra nao exigir que o dono da loja
  /// saiba o numero da porta de cor.
  static String normalizarEndereco(String bruto) {
    var endereco = bruto.trim();

    if (!endereco.startsWith('http://') && !endereco.startsWith('https://')) {
      endereco = 'http://$endereco';
    }

    final uri = Uri.parse(endereco);

    if (uri.hasPort) {
      return endereco;
    }

    return '$endereco:$_portaPadrao';
  }

  void definirServidor(String enderecoBruto) {
    _dio.options.baseUrl = normalizarEndereco(enderecoBruto);
    _dio.options.connectTimeout = const Duration(seconds: 6);
    _dio.options.receiveTimeout = const Duration(seconds: 10);
  }

  void definirToken(String token) {
    _dio.options.headers['Authorization'] = 'Bearer $token';
  }

  void removerToken() {
    _dio.options.headers.remove('Authorization');
  }

  /// GET "/" e o endpoint publico de handshake (backend/main.py) —
  /// usado so pra confirmar que da pra alcancar o servidor.
  Future<bool> testarConexao(String enderecoBruto) async {
    try {
      final resposta = await Dio().get(
        normalizarEndereco(enderecoBruto),
        options: Options(
          sendTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
        ),
      );
      return resposta.statusCode == 200;
    } catch (_) {
      return false;
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
