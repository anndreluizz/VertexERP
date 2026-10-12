import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_auth/local_auth.dart';

import '../../core/providers.dart';
import '../../core/sessao_controller.dart';
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

  /// Busca os dados da conta. Se ainda estiver nesta tela depois
  /// (sessao recusada leva pro login), foi falta de conexao: a sessao
  /// continua guardada e o botao Desbloquear tenta de novo.
  Future<void> _entrar() async {
    final ok = await ref
        .read(sessaoControllerProvider.notifier)
        .desbloquearComBiometria();
    final aindaTravado =
        ref.read(sessaoControllerProvider).status == StatusSessao.bloqueado;
    if (!ok && mounted && aindaTravado) {
      setState(
        () => _aviso =
            'Sem conexão com o servidor. Verifique a internet e toque em '
            'Desbloquear para tentar de novo.',
      );
    }
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
        await _entrar();
        return;
      }

      final autenticado = await _auth.authenticate(
        localizedReason: 'Confirme sua identidade pra acessar o Vertex ERP',
        biometricOnly: false, // aceita PIN/padrao do aparelho tambem
        persistAcrossBackgrounding: true,
      );

      if (!mounted) return;

      if (autenticado) {
        await _entrar();
      } else {
        // usuario recusou/cancelou o prompt de proposito -- continua
        // exigindo (ou biometria de novo, ou email/senha manual)
        setState(() => _aviso = 'Não foi possível confirmar sua identidade.');
      }
    } on LocalAuthException catch (e) {
      // So faz sentido deixar entrar quando a checagem em si nao pode
      // rodar por o aparelho nao ter NENHUMA trava configurada -- isso
      // NAO foi o usuario recusando de proposito, e travar numa tela
      // sem saida por uma seguranca que nem existe no aparelho e pior
      // do que deixar entrar ("Manter conectado" ja e a escolha
      // consciente do usuario, mesmo raciocinio do Desktop).
      //
      // temporaryLockout/biometricLockout (sensor bloqueado por
      // tentativas biometricas erradas) e qualquer outro codigo NAO
      // caem aqui -- ali a checagem existe e falhou, entao continua
      // exigindo (biometria de novo, ou email/senha manual) em vez de
      // virar um bypass.
      final codigosSemTravaNoAparelho = {
        LocalAuthExceptionCode.noCredentialsSet,
        LocalAuthExceptionCode.noBiometricsEnrolled,
        LocalAuthExceptionCode.noBiometricHardware,
      };

      if (codigosSemTravaNoAparelho.contains(e.code)) {
        if (mounted) {
          await _entrar();
        }
      } else if (mounted) {
        setState(() => _aviso = 'Não foi possível confirmar sua identidade.');
      }
    } catch (_) {
      // Erro que nem veio do plugin de biometria (ex.: falha no
      // proprio app/estado) -- mesmo raciocinio do ramo acima: a
      // checagem nao pode ser dada como bem-sucedida so por ter
      // explodido, entao continua travado em vez de virar bypass.
      if (mounted) {
        setState(() => _aviso = 'Não foi possível confirmar sua identidade.');
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
                  child: Icon(
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
                    style: TextStyle(
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
                  onPressed: () => ref
                      .read(sessaoControllerProvider.notifier)
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
