import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

/// Cache local generico (chave -> texto), pensado pra guardar o ultimo
/// JSON de qualquer tela consultada com sucesso — hoje so o Dashboard
/// usa (ver dashboard_provider.dart), mas qualquer tela nova pode
/// reaproveitar so chamando salvar()/ler() com uma chave propria.
///
/// De proposito so isso: NAO guarda fila de escrita offline (vender,
/// abrir caixa etc. continuam exigindo rede, igual ao Desktop) — o
/// objetivo aqui eso o app conseguir MOSTRAR o ultimo dado bom quando
/// a rede falha, nunca deixar operar as cegas sem o servidor confirmar.
class CacheLocal {
  static Database? _db;

  static Future<Database> _abrir() async {
    final atual = _db;
    if (atual != null) return atual;

    final caminho = join(await getDatabasesPath(), 'vertex_cache.db');

    final novo = await openDatabase(
      caminho,
      version: 1,
      onCreate: (db, versao) {
        return db.execute(
          'CREATE TABLE cache ('
          'chave TEXT PRIMARY KEY, '
          'valor TEXT NOT NULL, '
          'atualizado_em TEXT NOT NULL'
          ')',
        );
      },
    );

    _db = novo;
    return novo;
  }

  static Future<void> salvar(String chave, String valorJson) async {
    final db = await _abrir();

    await db.insert('cache', {
      'chave': chave,
      'valor': valorJson,
      'atualizado_em': DateTime.now().toIso8601String(),
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  /// Retorna (valorJson, atualizadoEm), ou null se nunca foi guardado.
  static Future<(String, DateTime)?> ler(String chave) async {
    final db = await _abrir();

    final linhas = await db.query(
      'cache',
      where: 'chave = ?',
      whereArgs: [chave],
      limit: 1,
    );

    if (linhas.isEmpty) return null;

    final linha = linhas.first;
    return (
      linha['valor'] as String,
      DateTime.parse(linha['atualizado_em'] as String),
    );
  }
}
