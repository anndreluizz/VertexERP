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

  Future<void> _iniciar() async {
    final endereco = await _storage.lerServidor();

    if (endereco == null || endereco.isEmpty) {
      state = const SessaoState(status: StatusSessao.semServidor);
      return;
    }

    _api.definirServidor(endereco);

    final token = await _storage.lerToken();

    if (token == null || token.isEmpty) {
      state = SessaoState(
        status: StatusSessao.deslogado,
        enderecoServidor: endereco,
      );
      return;
    }

    _api.definirToken(token);

    // Existe um token lembrado — pede biometria antes de mostrar
    // qualquer dado (fica no estado "bloqueado" ate confirmarUsuarioLogado
    // ser chamado, ver desbloquearComBiometria).
    state = SessaoState(
      status: StatusSessao.bloqueado,
      enderecoServidor: endereco,
    );
  }

  Future<bool> _carregarUsuarioLogado() async {
    try {
      final respostaUsuario = await _api.dio.get('/auth/me');
      final respostaConfig = await _api.dio.get('/configuracoes');

      state = state.copyWith(
        status: StatusSessao.logado,
        usuario: Usuario.fromJson(
          respostaUsuario.data as Map<String, dynamic>,
        ),
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
    final ok = await _carregarUsuarioLogado();

    if (!ok) {
      // token guardado nao vale mais (expirou/foi revogado) — descarta
      // e manda pro login normal.
      await _storage.removerToken();
      _api.removerToken();
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
    _api.definirServidor(endereco);

    state = SessaoState(
      status: StatusSessao.deslogado,
      enderecoServidor: endereco,
    );

    return alcancavel;
  }

  Future<String?> login(
    String email,
    String senha, {
    required bool lembrar,
  }) async {
    try {
      final resposta = await _api.dio.post(
        '/auth/login',
        data: {'email': email, 'senha': senha},
      );

      final token = resposta.data['access_token'] as String;
      _api.definirToken(token);

      if (lembrar) {
        await _storage.salvarToken(token);
      }

      final ok = await _carregarUsuarioLogado();

      return ok ? null : 'Não foi possível carregar os dados da conta.';
    } catch (e) {
      return _mensagemDeErro(e);
    }
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
    state = const SessaoState(status: StatusSessao.semServidor);
  }

  Future<void> logout() async {
    await _storage.removerToken();
    _api.removerToken();
    state = SessaoState(
      status: StatusSessao.deslogado,
      enderecoServidor: state.enderecoServidor,
    );
  }
}
