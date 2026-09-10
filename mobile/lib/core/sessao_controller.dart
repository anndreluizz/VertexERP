import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/usuario.dart';
import 'api_client.dart';
import 'vertex_storage.dart';

enum StatusSessao {
  carregando,
  semServidor,
  deslogado,
  // sessao valida (token lembrado) mas ainda esperando confirmacao de
  // biometria antes de mostrar qualquer dado da empresa.
  bloqueado,
  logado,
}

class SessaoState {
  const SessaoState({
    required this.status,
    this.usuario,
    this.nomeLoja,
    this.enderecoServidor,
    this.erro,
  });

  static const inicial = SessaoState(status: StatusSessao.carregando);

  final StatusSessao status;
  final Usuario? usuario;
  final String? nomeLoja;
  final String? enderecoServidor;
  final String? erro;

  SessaoState copyWith({
    StatusSessao? status,
    Usuario? usuario,
    String? nomeLoja,
    String? enderecoServidor,
    String? erro,
  }) {
    return SessaoState(
      status: status ?? this.status,
      usuario: usuario ?? this.usuario,
      nomeLoja: nomeLoja ?? this.nomeLoja,
      enderecoServidor: enderecoServidor ?? this.enderecoServidor,
      erro: erro,
    );
  }
}

class SessaoController extends StateNotifier<SessaoState> {
  SessaoController(this._api, this._storage) : super(SessaoState.inicial) {
    _iniciar();
  }

  final ApiClient _api;
  final VertexStorage _storage;

  // Guardado em memoria (alem do secure storage) pra renovarToken()
  // conseguir usar sem precisar ficar lendo o storage a cada 401.
  String? _refreshToken;

  Future<void> _iniciar() async {
    final endereco = await _storage.lerServidor();

    if (endereco == null || endereco.isEmpty) {
      state = const SessaoState(status: StatusSessao.semServidor);
      return;
    }

    await _api.definirServidor(endereco);

    final token = await _storage.lerToken();

    if (token == null || token.isEmpty) {
      state = SessaoState(
        status: StatusSessao.deslogado,
        enderecoServidor: endereco,
      );
      return;
    }

    _api.definirToken(token);
    _refreshToken = await _storage.lerRefreshToken();

    // Existe um token lembrado — pede biometria antes de mostrar
    // qualquer dado (fica no estado "bloqueado" ate confirmarUsuarioLogado
    // ser chamado, ver desbloquearComBiometria).
    state = SessaoState(
      status: StatusSessao.bloqueado,
      enderecoServidor: endereco,
    );
  }

  /// Chamado pelo ApiClient quando uma requisicao toma 401 -- tenta
  /// trocar o access_token vencido por um novo usando o refresh_token
  /// guardado, sem precisar pedir login de novo. Usa um Dio "cru" (sem
  /// o interceptor) pra essa chamada nunca disparar a si mesma de novo.
  Future<String?> renovarToken() async {
    final refreshToken = _refreshToken;
    final endereco = state.enderecoServidor;

    if (refreshToken == null || endereco == null) {
      return null;
    }

    try {
      final resposta = await Dio().post(
        '${ApiClient.normalizarEndereco(endereco)}/auth/refresh',
        data: {'refresh_token': refreshToken},
      );

      final novoToken = resposta.data['access_token'] as String;

      // so persiste de volta se ja havia sido "lembrado" -- sessao que
      // optou por nao lembrar continua so em memoria, do jeito que ja
      // era antes do refresh token existir.
      if (await _storage.lerToken() != null) {
        await _storage.salvarToken(novoToken);
      }

      return novoToken;
    } catch (_) {
      return null;
    }
  }

  /// Chamado quando o app volta de muito tempo em segundo plano — exige
  /// biometria de novo antes de continuar mostrando dado da empresa.
  /// Sem efeito se a sessao ja nao estiver "logado" (ex.: ja esta na
  /// tela de login, nao tem porque travar o que nao esta aberto).
  void travarPorInatividade() {
    if (state.status == StatusSessao.logado) {
      state = state.copyWith(status: StatusSessao.bloqueado);
    }
  }

  Future<bool> _carregarUsuarioLogado() async {
    try {
      final respostaUsuario = await _api.dio.get('/auth/me');
      final respostaConfig = await _api.dio.get('/configuracoes');

      state = state.copyWith(
        status: StatusSessao.logado,
        usuario: Usuario.fromJson(respostaUsuario.data as Map<String, dynamic>),
        nomeLoja:
            (respostaConfig.data as Map<String, dynamic>)['nome_loja']
                as String? ??
            'Vertex ERP',
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Chamado depois que o LocalAuthentication confirmou a biometria —
  /// so entao os dados de verdade sao buscados e mostrados.
  Future<bool> desbloquearComBiometria() async {
    var ok = await _carregarUsuarioLogado();

    if (!ok) {
      // access_token guardado pode so estar vencido (comum se o app
      // ficou dias fechado) -- tenta renovar antes de desistir, assim
      // o usuario so precisa da biometria, nao de logar nas 3 caixas
      // de novo toda vez que o token de 24h expira.
      final novoToken = await renovarToken();

      if (novoToken != null) {
        _api.definirToken(novoToken);
        ok = await _carregarUsuarioLogado();
      }
    }

    if (!ok) {
      // nem a renovacao resolveu (refresh_token tambem expirou ou foi
      // revogado em outro aparelho) — descarta e manda pro login normal.
      await _storage.removerToken();
      _api.removerToken();
      _refreshToken = null;
      state = state.copyWith(status: StatusSessao.deslogado);
    }

    return ok;
  }

  /// Usuario preferiu nao usar biometria agora — cai pro login manual
  /// (o token lembrado continua guardado, so nao é usado nesta sessao).
  void recusarBiometria() {
    _api.removerToken();
    state = state.copyWith(status: StatusSessao.deslogado);
  }

  Future<bool> configurarServidor(String enderecoBruto) async {
    final alcancavel = await _api.testarConexao(enderecoBruto);
    final endereco = ApiClient.normalizarEndereco(enderecoBruto);

    // Permite salvar mesmo se o teste falhar agora — o servidor pode
    // simplesmente ainda nao estar ligado (mesmo criterio do Desktop).
    await _storage.salvarServidor(endereco);
    await _api.definirServidor(endereco);

    state = SessaoState(
      status: StatusSessao.deslogado,
      enderecoServidor: endereco,
    );

    return alcancavel;
  }

  /// sucesso == false + verificacaoId != null significa que a senha
  /// bateu mas falta o segundo fator (2FA) -- a tela deve pedir o
  /// codigo (mandado por e-mail) e chamar verificarCodigo2fa() com
  /// esse verificacaoId pra completar o login (ver
  /// features/auth/login_screen.dart).
  Future<
    ({bool sucesso, String? erro, String? verificacaoId})
  > login(
    String email,
    String senha, {
    required bool lembrar,
  }) async {
    try {
      final resposta = await _api.dio.post(
        '/auth/login',
        data: {'email': email, 'senha': senha},
      );

      if (resposta.data['requer_2fa'] == true) {
        return (
          sucesso: false,
          erro: null,
          verificacaoId: resposta.data['verificacao_id'] as String,
        );
      }

      final token = resposta.data['access_token'] as String;
      final refreshToken = resposta.data['refresh_token'] as String?;

      final erro = await _concluirLogin(token, refreshToken, lembrar);

      return (sucesso: erro == null, erro: erro, verificacaoId: null);
    } catch (e) {
      return (sucesso: false, erro: _mensagemDeErro(e), verificacaoId: null);
    }
  }

  /// 2o passo do login pra quem tem 2FA ativo (ver login() acima) --
  /// troca o verificacaoId + codigo (recebido por e-mail) pelos
  /// tokens de verdade, do mesmo jeito que login() faria sem 2FA.
  Future<String?> verificarCodigo2fa(
    String verificacaoId,
    String codigo, {
    required bool lembrar,
  }) async {
    try {
      final resposta = await _api.dio.post(
        '/auth/verificar-2fa',
        data: {'verificacao_id': verificacaoId, 'codigo': codigo},
      );

      final token = resposta.data['access_token'] as String;
      final refreshToken = resposta.data['refresh_token'] as String?;

      return await _concluirLogin(token, refreshToken, lembrar);
    } catch (e) {
      return _mensagemDeErro(e);
    }
  }

  /// Guarda o token (memoria + storage se lembrar) e carrega os dados
  /// do usuario logado -- parte final comum entre login() sem 2FA e
  /// verificarCodigo2fa(). Devolve null no sucesso, ou a mensagem de
  /// erro se nao conseguir carregar os dados da conta.
  Future<String?> _concluirLogin(
    String token,
    String? refreshToken,
    bool lembrar,
  ) async {
    _api.definirToken(token);
    _refreshToken = refreshToken;

    if (lembrar) {
      await _storage.salvarToken(token);
      if (refreshToken != null) {
        await _storage.salvarRefreshToken(refreshToken);
      }
    }

    final ok = await _carregarUsuarioLogado();

    return ok ? null : 'Não foi possível carregar os dados da conta.';
  }

  String _mensagemDeErro(Object erro) {
    if (erro is DioException) {
      final dados = erro.response?.data;
      if (dados is Map && dados['detail'] is String) {
        return dados['detail'] as String;
      }
    }

    return 'Não foi possível conectar ao servidor. Verifique o endereço configurado e a rede.';
  }

  Future<void> trocarServidor() async {
    await _storage.removerToken();
    _api.removerToken();
    _refreshToken = null;
    state = const SessaoState(status: StatusSessao.semServidor);
  }

  Future<void> logout() async {
    await _storage.removerToken();
    _api.removerToken();
    _refreshToken = null;
    state = SessaoState(
      status: StatusSessao.deslogado,
      enderecoServidor: state.enderecoServidor,
    );
  }
}
