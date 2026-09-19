from decimal import Decimal

import pytest

from app.services.nfe_service import NFeInvalidaError, parsear_nfe

_XML_VALIDO = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe1" versao="4.00">
      <emit>
        <CNPJ>12.345.678/0001-99</CNPJ>
        <xNome>Fornecedor Teste Ltda</xNome>
        <xFant>Fornecedor Teste</xFant>
      </emit>
      <det nItem="1">
        <prod>
          <cProd>ABC123</cProd>
          <cEAN>7891234567890</cEAN>
          <xProd>Produto Um</xProd>
          <qCom>10.0000</qCom>
          <vUnCom>15.5000</vUnCom>
        </prod>
      </det>
      <det nItem="2">
        <prod>
          <cProd>DEF456</cProd>
          <cEAN>SEM GTIN</cEAN>
          <xProd>Produto Dois</xProd>
          <qCom>3.4000</qCom>
          <vUnCom>7.2500</vUnCom>
        </prod>
      </det>
    </infNFe>
  </NFe>
  <protNFe>
    <infProt>
      <cStat>100</cStat>
    </infProt>
  </protNFe>
</nfeProc>"""


def test_parsear_nfe_extrai_fornecedor_e_itens():
    extraida = parsear_nfe(_XML_VALIDO)

    assert extraida.fornecedor.cnpj == "12345678000199"  # so' digitos, mascara removida
    assert extraida.fornecedor.razao_social == "Fornecedor Teste Ltda"
    assert extraida.fornecedor.nome_fantasia == "Fornecedor Teste"

    assert len(extraida.itens) == 2

    item1 = extraida.itens[0]
    assert item1.codigo == "ABC123"
    assert item1.codigo_barras == "7891234567890"
    assert item1.quantidade == 10
    assert item1.valor_unitario == Decimal("15.5000")

    item2 = extraida.itens[1]
    assert item2.codigo_barras is None  # "SEM GTIN" vira None
    assert item2.quantidade == 3  # 3.4 arredonda pra 3 (ROUND_HALF_UP)


_XML_SEM_WRAPPER_PROC = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe Id="NFe1" versao="4.00">
    <emit>
      <CNPJ>12345678000199</CNPJ>
      <xNome>Fornecedor Sem Proc Ltda</xNome>
    </emit>
    <det nItem="1">
      <prod>
        <cProd>XYZ789</cProd>
        <cEAN>SEM GTIN</cEAN>
        <xProd>Produto Sem Proc</xProd>
        <qCom>5.0000</qCom>
        <vUnCom>10.0000</vUnCom>
      </prod>
    </det>
  </infNFe>
</NFe>"""


def test_parsear_nfe_sem_wrapper_nfeproc_tambem_funciona():
    """Nota ainda nao processada pela SEFAZ (so' <NFe>, sem <nfeProc>/
    <protNFe>) -- sem cStat pra checar, mas o parsing continua valido."""

    extraida = parsear_nfe(_XML_SEM_WRAPPER_PROC)
    assert extraida.fornecedor.cnpj == "12345678000199"
    assert len(extraida.itens) == 1
    assert extraida.itens[0].codigo == "XYZ789"


def test_parsear_nfe_arquivo_nao_reconhecivel_da_erro_claro():
    with pytest.raises(NFeInvalidaError):
        parsear_nfe("<algumaOutraCoisa></algumaOutraCoisa>")


def test_parsear_nfe_xml_mal_formado_da_erro_claro():
    with pytest.raises(NFeInvalidaError):
        parsear_nfe("<nfeProc><NFe>")


def test_parsear_nfe_cancelada_da_erro():
    xml_cancelada = _XML_VALIDO.replace("<cStat>100</cStat>", "<cStat>101</cStat>")
    with pytest.raises(NFeInvalidaError):
        parsear_nfe(xml_cancelada)


def test_parsear_nfe_emitente_so_cpf_da_erro():
    xml_sem_cnpj = _XML_VALIDO.replace(
        "<CNPJ>12.345.678/0001-99</CNPJ>", "<CPF>12345678900</CPF>"
    )
    with pytest.raises(NFeInvalidaError):
        parsear_nfe(xml_sem_cnpj)


def test_parsear_nfe_sem_itens_da_erro():
    import re

    xml_sem_itens = re.sub(r"<det.*?</det>", "", _XML_VALIDO, flags=re.DOTALL)
    with pytest.raises(NFeInvalidaError):
        parsear_nfe(xml_sem_itens)
