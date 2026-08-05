import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Guarda o endereco do servidor e o token de sessao no armazenamento
/// seguro do aparelho (Keystore no Android) — nada disso fica em
/// texto puro em disco.
class VertexStorage {
  VertexStorage() : _storage = const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _chaveServidor = 'endereco_servidor';
  static const _chaveToken = 'access_token';
  static const _chaveRefreshToken = 'refresh_token';

  Future<String?> lerServidor() => _storage.read(key: _chaveServidor);

  Future<void> salvarServidor(String endereco) =>
      _storage.write(key: _chaveServidor, value: endereco);

  Future<String?> lerToken() => _storage.read(key: _chaveToken);

  Future<void> salvarToken(String token) =>
      _storage.write(key: _chaveToken, value: token);

  Future<String?> lerRefreshToken() => _storage.read(key: _chaveRefreshToken);

  Future<void> salvarRefreshToken(String token) =>
      _storage.write(key: _chaveRefreshToken, value: token);

  /// Remove os dois juntos -- em todo lugar que a sessao acaba
  /// (logout, token invalido, troca de servidor) as duas pontas da
  /// sessao lembrada precisam sumir, nunca so uma.
  Future<void> removerToken() => Future.wait([
    _storage.delete(key: _chaveToken),
    _storage.delete(key: _chaveRefreshToken),
  ]);
}
