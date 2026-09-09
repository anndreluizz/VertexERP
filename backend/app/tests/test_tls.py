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


def test_regenera_sozinho_quando_nao_cobre_mais_o_ip_atual(pasta_certs):
    cert, _ = garantir_certificado(pasta_certs)

    with open(cert, "rb") as arquivo:
        conteudo_original = arquivo.read()

    # sobrescreve com um certificado "velho" que só cobre um IP que
    # certamente não é desta máquina -- simula "o DHCP deu outro
    # endereço desde a última vez"
    chave_fake = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome_fake = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "teste")])
    agora = datetime.now(timezone.utc)

    cert_fake = (
        x509.CertificateBuilder()
        .subject_name(nome_fake)
        .issuer_name(nome_fake)
        .public_key(chave_fake.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1))
        .not_valid_after(agora + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("10.99.99.99"))]
            ),
            critical=False,
        )
        .sign(chave_fake, hashes.SHA256())
    )

    with open(cert, "wb") as arquivo:
        arquivo.write(cert_fake.public_bytes(serialization.Encoding.PEM))

    cert_novo, _ = garantir_certificado(pasta_certs)

    with open(cert_novo, "rb") as arquivo:
        conteudo_novo = arquivo.read()

    assert conteudo_novo != cert_fake.public_bytes(serialization.Encoding.PEM)
    assert "127.0.0.1" in _sans_de(cert_novo)
