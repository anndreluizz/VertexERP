import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_auth/local_auth.dart';

import '../../core/providers.dart';
import '../../theme/vertex_colors.dart';

/// Mostrado quando existe uma sessao lembrada ("Manter conectado") —
/// pede biometria/PIN do aparelho antes de mostrar qualquer dado da
/// empresa, sem exigir digitar a senha de novo.
class LockScreen extends ConsumerStatefulWidget {
  const LockScreen({super.key});

  @override
  ConsumerState<LockScreen> createState() => _LockScreenState();
}

class _LockScreenState extends ConsumerState<LockScreen> {
  final _auth = LocalAuthentication();
  bool _autenticando = false;
  String? _aviso;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _desbloquear());
  }

  Future<void> _desbloquear() async {
    if (_autenticando) return;
    setState(() {
      _autenticando = true;
      _aviso = null;
    });

    try {
      final suportado = await _auth.isDeviceSupported();

      if (!suportado) {
        // Aparelho sem nenhuma trava configurada (raro) — nao faz
        // sentido bloquear o acesso por uma seguranca que nem existe
        // no proprio aparelho.
        await ref.read(sessaoControllerProvider.notifier)
            .desbloquearComBiometria();
        return;
      }

      final autenticado = await _auth.authenticate(
        localizedReason: 'Confirme sua identidade pra acessar o Vertex ERP',
        biometricOnly: false, // aceita PIN/padrao do aparelho tambem
        persistAcrossBackgrounding: true,
      );

      if (!mounted) return;

      if (autenticado) {
        await ref.read(sessaoControllerProvider.notifier)
            .desbloquearComBiometria();
      } else {
        setState(() => _aviso = 'Não foi possível confirmar sua identidade.');
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _aviso = 'Não foi possível abrir a verificação do aparelho.',
        );
      }
    } finally {
      if (mounted) setState(() => _autenticando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final nomeLoja = ref.watch(
      sessaoControllerProvider.select((s) => s.nomeLoja),
    );

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 72,
                  height: 72,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: VertexColors.primariaClara,
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: const Icon(
                    Icons.fingerprint,
                    color: VertexColors.primaria,
                    size: 36,
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  nomeLoja ?? 'Vertex ERP',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 6),
                Text(
                  'Sessão protegida — confirme sua identidade pra continuar.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: VertexColors.textoSecundario),
                ),
                if (_aviso != null) ...[
                  const SizedBox(height: 14),
                  Text(
                    _aviso!,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: VertexColors.alerta,
                      fontSize: 13.5,
                    ),
                  ),
                ],
                const SizedBox(height: 26),
                ElevatedButton.icon(
                  onPressed: _autenticando ? null : _desbloquear,
                  icon: const Icon(Icons.lock_open, size: 18),
                  label: const Text('Desbloquear'),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () =>
                      ref.read(sessaoControllerProvider.notifier)
                          .recusarBiometria(),
                  child: const Text('Entrar com e-mail e senha'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
