import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final int statusCode;
  final String message;

  ApiException(this.statusCode, this.message);

  @override
  String toString() => message;
}

class UnauthorizedException extends ApiException {
  UnauthorizedException() : super(401, 'Sessão expirada. Faça login novamente.');
}

/// Cliente HTTP genérico para a API do VertexERP.
///
/// A API mistura dois formatos de resposta: a maioria dos endpoints
/// (auth, produtos, clientes, vendas, dashboard) retorna o modelo cru,
/// enquanto os endpoints em /users/* embrulham em {success, message, data}.
/// [unwrap] trata as duas formas.
class ApiClient {
  static const _storage = FlutterSecureStorage();
  static const _chaveUrl = 'base_url';
  static const _chaveToken = 'access_token';

  String? _baseUrl;
  String? _token;

  String? get baseUrl => _baseUrl;
  bool get isConfigured => _baseUrl != null && _baseUrl!.isNotEmpty;
  bool get isAuthenticated => _token != null && _token!.isNotEmpty;

  Future<void> init() async {
    try {
      _baseUrl = await _storage.read(key: _chaveUrl);
      _token = await _storage.read(key: _chaveToken);
    } catch (_) {
      // Sem suporte a secure storage no ambiente atual (ex.: testes de widget);
      // segue sem servidor/token salvos.
    }
  }

  Future<void> setBaseUrl(String url) async {
    var normalizado = url.trim();
    if (normalizado.endsWith('/')) {
      normalizado = normalizado.substring(0, normalizado.length - 1);
    }
    _baseUrl = normalizado;
    await _storage.write(key: _chaveUrl, value: normalizado);
  }

  Future<void> setToken(String token) async {
    _token = token;
    await _storage.write(key: _chaveToken, value: token);
  }

  Future<void> clearToken() async {
    _token = null;
    await _storage.delete(key: _chaveToken);
  }

  Uri _uri(String path) => Uri.parse('$_baseUrl$path');

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  Future<dynamic> get(String path) async {
    final resp = await http.get(_uri(path), headers: _headers);
    return _handle(resp);
  }

  Future<dynamic> post(String path, Map<String, dynamic> body) async {
    final resp = await http.post(
      _uri(path),
      headers: _headers,
      body: jsonEncode(body),
    );
    return _handle(resp);
  }

  dynamic _handle(http.Response resp) {
    if (resp.statusCode == 401) {
      throw UnauthorizedException();
    }

    if (resp.statusCode >= 400) {
      throw ApiException(resp.statusCode, _extrairMensagemErro(resp));
    }

    if (resp.body.isEmpty) {
      return null;
    }

    return jsonDecode(utf8.decode(resp.bodyBytes));
  }

  String _extrairMensagemErro(http.Response resp) {
    try {
      final decoded = jsonDecode(utf8.decode(resp.bodyBytes));
      if (decoded is Map) {
        if (decoded['detail'] != null) return decoded['detail'].toString();
        if (decoded['message'] != null) return decoded['message'].toString();
      }
    } catch (_) {
      // corpo não é JSON válido, ignora e cai no fallback abaixo
    }
    return 'Erro na comunicação com o servidor (${resp.statusCode}).';
  }

  /// Desembrulha respostas no formato {success, message, data} usadas por /users/*.
  /// Para as demais respostas (já cruas), devolve o próprio json.
  dynamic unwrap(dynamic json) {
    if (json is Map && json.containsKey('success') && json.containsKey('data')) {
      return json['data'];
    }
    return json;
  }
}
