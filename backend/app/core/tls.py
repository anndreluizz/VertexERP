"""Gera (e reaproveita) o certificado autoassinado que o uvicorn usa
pra servir HTTPS -- sem isso, login e token trafegavam em texto puro
na rede da loja (qualquer aparelho na mesma rede podia capturar).

Não tem domínio nem autoridade certificadora de verdade (servidor
local, só IP na rede da loja) -- o modelo de confiança é "TOFU"
(trust on first use, igual SSH): cada Terminal/celular que conecta
pela primeira vez salva esse certificado como confiável, e um aviso
aparece se ele mudar depois (ver frontend/services/tls_confianca.py
e mobile/lib/core/tls_confianca.dart)."""

import ipaddress
import os
import socket
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# 10 anos -- sem CA de verdade não tem infraestrutura de revogação
# nem motivo real pra expirar cedo; renovar automaticamente já cobre
# o único caso que realmente importa (a rede/IP muda).
_ANOS_VALIDADE = 10


def _ips_desta_maquina() -> set[str]:
    """Descobre os IPs de rede local desta máquina -- sempre inclui
    127.0.0.1 (acesso local, modo 1 PC só) e tenta achar o IP real na
    rede da loja (modo Servidor+Terminal), sem depender de internet
    de verdade estar disponível."""

    ips = {"127.0.0.1"}

    # truque clássico: um "connect" UDP não manda nenhum pacote de
    # verdade (UDP não tem handshake) -- só força o SO a escolher qual
    # interface de rede seria usada pra alcançar esse destino, e da pra
    # ler esse IP local de volta. Funciona mesmo sem internet de
    # verdade, porque nada é realmente transmitido.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
    except OSError:
        pass

    # tambem inclui qualquer outro IP que o SO souber associar a este
    # host -- cobre maquinas com mais de uma interface de rede
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass

    return ips


def _certificado_cobre_ips_atuais(caminho_cert: str, ips_atuais: set[str]) -> bool:
    """Se o IP da máquina mudou (DHCP deu outro endereço, por
    exemplo) desde que o certificado foi gerado, ele fica sem cobrir
    o endereço novo -- clientes conectando nesse IP veriam uma
    identidade que não bate. Detecta isso pra regenerar sozinho."""

    try:
        with open(caminho_cert, "rb") as arquivo:
            cert = x509.load_pem_x509_certificate(arquivo.read())
    except (OSError, ValueError):
        return False

    if cert.not_valid_after_utc < datetime.now(timezone.utc):
        return False

    try:
        san = cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        ips_no_certificado = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
    except x509.ExtensionNotFound:
        ips_no_certificado = set()

    return ips_atuais.issubset(ips_no_certificado)


def _gerar_certificado(caminho_cert: str, caminho_chave: str) -> None:

    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    nome = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Vertex ERP (servidor local)")]
    )

    ips = _ips_desta_maquina()

    nomes_alternativos = [x509.DNSName("localhost")]
    for ip in ips:
        try:
            nomes_alternativos.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            continue

    agora = datetime.now(timezone.utc)

    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)  # autoassinado: emissor == titular
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1))
        .not_valid_after(agora + timedelta(days=365 * _ANOS_VALIDADE))
        .add_extension(
            x509.SubjectAlternativeName(nomes_alternativos),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .sign(chave, hashes.SHA256())
    )

    os.makedirs(os.path.dirname(caminho_cert), exist_ok=True)

    with open(caminho_chave, "wb") as arquivo:
        arquivo.write(
            chave.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(caminho_cert, "wb") as arquivo:
        arquivo.write(certificado.public_bytes(serialization.Encoding.PEM))


def garantir_certificado(pasta: str) -> tuple[str, str]:
    """Devolve (caminho_cert, caminho_chave), gerando um novo par se
    ainda não existir, se tiver vencido, ou se não cobrir mais os IPs
    atuais desta máquina."""

    caminho_cert = os.path.join(pasta, "servidor.crt")
    caminho_chave = os.path.join(pasta, "servidor.key")

    ips_atuais = _ips_desta_maquina()

    precisa_gerar = (
        not os.path.exists(caminho_cert)
        or not os.path.exists(caminho_chave)
        or not _certificado_cobre_ips_atuais(caminho_cert, ips_atuais)
    )

    if precisa_gerar:
        _gerar_certificado(caminho_cert, caminho_chave)

    return caminho_cert, caminho_chave
