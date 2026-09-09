from datetime import datetime, timedelta

from app.auth import rate_limit


def setup_function(_):
    # cada teste deste arquivo mexe direto no estado em memoria do
    # modulo -- limpa antes de cada um pra nao depender de ordem
    rate_limit._falhas.clear()
    rate_limit._bloqueados.clear()


def test_nao_bloqueia_antes_do_limite():
    for _ in range(rate_limit.MAX_TENTATIVAS - 1):
        rate_limit.registrar_falha("alguem@teste.com")

    assert rate_limit.segundos_ate_desbloquear("alguem@teste.com") == 0


def test_bloqueia_ao_atingir_o_limite():
    for _ in range(rate_limit.MAX_TENTATIVAS):
        rate_limit.registrar_falha("alguem@teste.com")

    assert rate_limit.segundos_ate_desbloquear("alguem@teste.com") > 0


def test_email_e_case_insensitive_e_ignora_espaco():
    for _ in range(rate_limit.MAX_TENTATIVAS):
        rate_limit.registrar_falha("  Alguem@Teste.com  ")

    assert rate_limit.segundos_ate_desbloquear("alguem@teste.com") > 0


def test_limpar_reseta_o_bloqueio():
    for _ in range(rate_limit.MAX_TENTATIVAS):
        rate_limit.registrar_falha("alguem@teste.com")

    assert rate_limit.segundos_ate_desbloquear("alguem@teste.com") > 0

    rate_limit.limpar("alguem@teste.com")

    assert rate_limit.segundos_ate_desbloquear("alguem@teste.com") == 0


def test_falha_fora_da_janela_nao_conta():
    # simula MAX_TENTATIVAS-1 falhas ja fora da janela de tempo (bem
    # antigas) mais 1 falha recente -- nao deveria bloquear, porque só
    # a falha recente ainda "conta"
    email = "alguem@teste.com"
    antigo = datetime.utcnow() - rate_limit.JANELA - timedelta(minutes=1)

    rate_limit._falhas[email] = [antigo] * (rate_limit.MAX_TENTATIVAS - 1)
    rate_limit.registrar_falha(email)

    assert rate_limit.segundos_ate_desbloquear(email) == 0


def test_bloqueio_expira_sozinho_depois_do_tempo():
    email = "alguem@teste.com"

    for _ in range(rate_limit.MAX_TENTATIVAS):
        rate_limit.registrar_falha(email)

    assert rate_limit.segundos_ate_desbloquear(email) > 0

    # avanca o "relogio" manualmente pra depois do fim do bloqueio
    rate_limit._bloqueados[email] = datetime.utcnow() - timedelta(seconds=1)

    assert rate_limit.segundos_ate_desbloquear(email) == 0
    # e o historico de falhas foi limpo junto, nao só o bloqueio
    assert email not in rate_limit._falhas
