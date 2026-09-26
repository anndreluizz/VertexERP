import ipaddress
import shutil
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.tls import _ips_desta_maquina, garantir_certificado


@pytest.fixture()
def pasta_certs():
    pasta = tempfile.mkdtemp(prefix="vertexerp_certs_teste_")
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


def _sans_de(caminho_cert):
    with open(caminho_cert, "rb") as arquivo:
        cert = x509.load_pem_x509_certificate(arquivo.read())

    return {
        str(ip)
        for ip in cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value.get_values_for_type(x509.IPAddress)
    }


def test_gera_certificado_e_chave(pasta_certs):
    cert, chave = garantir_certificado(pasta_certs)

    assert cert.endswith("servidor.crt")
    assert chave.endswith("servidor.key")

    with open(cert, "rb") as arquivo:
        x509.load_pem_x509_certificate(arquivo.read())  # não deve estourar


def test_certificado_cobre_localhost_e_ips_da_maquina(pasta_certs):
    cert, _ = garantir_certificado(pasta_certs)

    sans = _sans_de(cert)

    assert "127.0.0.1" in sans
    assert _ips_desta_maquina().issubset(sans)


def test_chamada_repetida_reaproveita_o_certificado(pasta_certs):
    cert1, _ = garantir_certificado(pasta_certs)

    with open(cert1, "rb") as arquivo:
        conteudo1 = arquivo.read()

    cert2, _ = garantir_certificado(pasta_certs)

    with open(cert2, "rb") as arquivo:
        conteudo2 = arquivo.read()

    assert conteudo1 == conteudo2


def _escrever_cert_fake(caminho, ip, validade_ate):
    chave_fake = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome_fake = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "teste")])
    agora = datetime.now(timezone.utc)

    cert_fake = (
        x509.CertificateBuilder()
        .subject_name(nome_fake)
        .issuer_name(nome_fake)
        .public_key(chave_fake.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=400))
        .not_valid_after(validade_ate)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address(ip))]
            ),
            critical=False,
        )
        .sign(chave_fake, hashes.SHA256())
    )

    conteudo = cert_fake.public_bytes(serialization.Encoding.PEM)

    with open(caminho, "wb") as arquivo:
        arquivo.write(conteudo)

    return conteudo


def test_nao_regenera_quando_o_ip_da_maquina_muda(pasta_certs):
    # os clientes fixam o certificado exato e nao checam IP -- trocar a
    # chave so' porque o DHCP/Tailscale mudou o IP derrubava todos os
    # Terminais com "servidor mudou de identidade"
    cert, _ = garantir_certificado(pasta_certs)

    conteudo = _escrever_cert_fake(
        cert, "10.99.99.99", datetime.now(timezone.utc) + timedelta(days=3650)
    )

    garantir_certificado(pasta_certs)

    with open(cert, "rb") as arquivo:
        assert arquivo.read() == conteudo


def test_regenera_quando_o_certificado_venceu(pasta_certs):
    cert, _ = garantir_certificado(pasta_certs)

    vencido = _escrever_cert_fake(
        cert, "127.0.0.1", datetime.now(timezone.utc) - timedelta(days=1)
    )

    garantir_certificado(pasta_certs)

    with open(cert, "rb") as arquivo:
        novo = arquivo.read()

    assert novo != vencido
    assert "127.0.0.1" in _sans_de(cert)
