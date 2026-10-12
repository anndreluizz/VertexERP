from utils.pix import ler_pix, texto_pra_copiar

# exemplo do manual do BR Code do Banco Central
COPIA_E_COLA = (
    "00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-426655440000"
    "5204000053039865406150.005802BR5913FULANO DE TAL6008BRASILIA62070503***6304ABCD"
)


def test_copia_e_cola_traz_valor_nome_e_chave():
    lido = ler_pix(COPIA_E_COLA)
    assert lido["tipo"] == "copia_e_cola"
    assert lido["valor"] == 150.0
    assert lido["nome"] == "FULANO DE TAL"
    assert lido["cidade"] == "BRASILIA"
    assert lido["chave"] == "123e4567-e12b-12d1-a456-426655440000"
    assert lido["copiar"] == COPIA_E_COLA


def test_tipos_de_chave():
    assert ler_pix("maria@email.com")["tipo_chave"] == "E-mail"
    assert ler_pix("123e4567-e12b-12d1-a456-426655440000")["tipo_chave"] == "Chave aleatória"
    assert ler_pix("529.982.247-25")["tipo_chave"] == "CPF"
    assert ler_pix("12.345.678/0001-95")["tipo_chave"] == "CNPJ"
    assert ler_pix("(97) 99902-3190")["tipo_chave"] == "Telefone"


def test_copiar_deixa_no_formato_do_app_do_banco():
    assert texto_pra_copiar("529.982.247-25") == "52998224725"
    assert texto_pra_copiar("(97) 99902-3190") == "+5597999023190"
    assert texto_pra_copiar("+55 97 99902-3190") == "+5597999023190"
    assert texto_pra_copiar("  ") is None
