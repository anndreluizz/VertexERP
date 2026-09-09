"""Confia no certificado autoassinado do servidor via TOFU (trust on
first use -- mesmo modelo do SSH com known_hosts): sem CA de verdade
(servidor local, só IP na rede da loja, sem domínio), cada Terminal
aprende a confiar no certificado do Servidor na primeira conexão bem
sucedida, e passa a EXIGIR esse mesmo certificado dali pra frente --
se um dia vier diferente, é sinal de servidor reinstalado (o esperado
depois de trocar de máquina) ou de algo suspeito na rede."""

import os
import re
import ssl


def _pasta_confianca():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    pasta = os.path.join(base, "VertexERP", "certificados_confiaveis")
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _nome_arquivo(host, porta):
    seguro = re.sub(r"[^a-zA-Z0-9.]", "_", host or "")
    return f"{seguro}_{porta}.pem"


def caminho_pinado(host, porta):
    return os.path.join(_pasta_confianca(), _nome_arquivo(host, porta))


def esta_confiavel(host, porta):
    return os.path.exists(caminho_pinado(host, porta))


def obter_certificado_do_servidor(host, porta, timeout=5):
    """Conecta via TLS ignorando validação -- só pra capturar o
    certificado que o servidor apresenta agora. É exatamente o
    "primeiro contato" do TOFU, não uma verificação de identidade."""

    return ssl.get_server_certificate((host, int(porta)), timeout=timeout)


def confiar(host, porta, pem=None):
    """Salva um certificado como confiável pra esse host:porta --
    busca na hora se pem não foi passado. Sobrescreve um pin anterior
    (é assim que um "re-confiar" depois de um servidor reinstalado
    funciona)."""

    if pem is None:
        pem = obter_certificado_do_servidor(host, porta)

    with open(caminho_pinado(host, porta), "w", encoding="utf-8") as arquivo:
        arquivo.write(pem)

    return pem


def eh_endereco_local(host):
    """127.0.0.1/localhost nunca saem da própria máquina -- não tem
    "rede" no meio pra um atacante interceptar, então um certificado
    mudando aí é sempre auto-causado (o próprio backend local gerou
    outro, ex.: IP mudou), nunca um risco de segurança de verdade."""

    return (host or "").strip().lower() in ("127.0.0.1", "localhost", "::1")
