import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'financeiro_provider.dart';

/// Pergunta camera ou galeria e devolve o anexo escolhido (foto do
/// comprovante) ja em memoria, pronto pra base64-encodar -- usado
/// tanto no formulario de pagamento quanto na troca de comprovante.
///
/// Mobile aceita so foto (JPG/PNG) pra anexo de comprovante -- o PDF
/// que o Desktop aceita fica de fora por enquanto, ja que fotografar
/// o comprovante (PIX, transferência) é o caso de uso mais comum no
/// celular.
Future<AnexoEscolhido?> escolherAnexoComprovante(BuildContext context) async {
  final origem = await showModalBottomSheet<ImageSource>(
    context: context,
    builder: (context) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.photo_camera_outlined),
            title: const Text('Tirar foto'),
            onTap: () => Navigator.of(context).pop(ImageSource.camera),
          ),
          ListTile(
            leading: const Icon(Icons.photo_library_outlined),
            title: const Text('Escolher da galeria'),
            onTap: () => Navigator.of(context).pop(ImageSource.gallery),
          ),
        ],
      ),
    ),
  );

  if (origem == null) return null;

  final arquivo = await ImagePicker().pickImage(
    source: origem,
    imageQuality: 85,
  );
  if (arquivo == null) return null;

  final bytes = await arquivo.readAsBytes();
  final extensao = arquivo.name.split('.').last.toLowerCase();
  final tipo = switch (extensao) {
    'png' => 'image/png',
    _ => 'image/jpeg',
  };

  return AnexoEscolhido(bytes: bytes, nome: arquivo.name, tipo: tipo);
}
