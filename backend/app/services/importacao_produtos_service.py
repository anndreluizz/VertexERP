import csv
import io
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.repositories.produto_repository import ProdutoRepository
from app.schemas.produto import ProdutoCreate, ProdutoUpdate
from app.schemas.produto_importacao import (
    ItemImportacaoConfirmar,
    ItemImportacaoPreview,
)
from app.services.produto_service import ProdutoService

# nomes de coluna aceitos por campo -- tolera variacao de acento/caixa
# porque quem preenche a planilha normalmente nao e' tecnico (ver
# MODELO_CSV_CABECALHO abaixo pro nome "oficial" de cada uma)
_COLUNAS = {
    "codigo": ["codigo", "código"],
    "nome": ["nome", "produto"],
    "categoria": ["categoria"],
    "codigo_barras": ["codigo de barras", "código de barras", "codigo_barras"],
    "preco_custo": ["preco de custo", "preço de custo", "preco_custo"],
    "preco_venda": ["preco de venda", "preço de venda", "preco_venda"],
    "estoque": ["estoque"],
    "estoque_minimo": ["estoque minimo", "estoque mínimo", "estoque_minimo"],
    "unidade": ["unidade"],
}

MODELO_CSV_CABECALHO = [
    "Código", "Nome", "Categoria", "Código de Barras",
    "Preço de Custo", "Preço de Venda", "Estoque", "Estoque Mínimo",
    "Unidade",
]

MODELO_CSV_EXEMPLO = [
    "", "Camiseta Branca P", "Roupa", "",
    "15.00", "39.90", "10", "2", "UN",
]


def _normalizar_cabecalho(texto):
    return texto.strip().lower()


def _mapear_colunas(campos_csv):
    """Devolve {nome_do_campo_interno: indice_da_coluna}, ignorando
    colunas que a planilha nao tem (tratadas como ausentes/opcionais
    mais adiante, exceto "nome" que e' sempre obrigatorio)."""

    normalizados = [_normalizar_cabecalho(c) for c in campos_csv]

    mapa = {}
    for campo, aliases in _COLUNAS.items():
        for alias in aliases:
            if alias in normalizados:
                mapa[campo] = normalizados.index(alias)
                break

    return mapa


def _valor(linha, mapa, campo, padrao=""):
    indice = mapa.get(campo)
    if indice is None or indice >= len(linha):
        return padrao
    return linha[indice].strip()


def _parse_decimal(texto, padrao=Decimal("0")):
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return padrao, None
    try:
        return Decimal(texto), None
    except InvalidOperation:
        return padrao, f'"{texto}" não é um preço válido'


def _parse_quantidade(texto, padrao=0):
    texto = (texto or "").strip()
    if not texto:
        return padrao, None
    try:
        return Decimal(texto.replace(",", ".")), None
    except InvalidOperation:
        return padrao, f'"{texto}" não é um número válido'


class ImportacaoProdutosService:

    @staticmethod
    def pre_visualizar(db: Session, csv_conteudo: str, loja_id: int | None = None):
        """So' leitura -- nenhum db.add/db.commit aqui, mesmo espirito
        do preview de NF-e (ver ImportacaoNfeService)."""

        leitor = csv.reader(io.StringIO(csv_conteudo), delimiter=";")
        linhas = list(leitor)

        if not linhas:
            return [], 0, 0, 0

        mapa = _mapear_colunas(linhas[0])
        itens = []
        proximo_codigo = ProdutoRepository.proximo_codigo_interno(db)

        for indice, linha in enumerate(linhas[1:], start=2):

            if not any(campo.strip() for campo in linha):
                continue  # linha em branco no meio da planilha

            erros = []

            nome = _valor(linha, mapa, "nome")
            if not nome:
                erros.append("nome vazio")

            preco_custo, erro_custo = _parse_decimal(
                _valor(linha, mapa, "preco_custo")
            )
            if erro_custo:
                erros.append(erro_custo)

            preco_venda, erro_venda = _parse_decimal(
                _valor(linha, mapa, "preco_venda")
            )
            if erro_venda:
                erros.append(erro_venda)

            estoque, erro_estoque = _parse_quantidade(_valor(linha, mapa, "estoque"))
            if erro_estoque:
                erros.append(erro_estoque)

            estoque_minimo, erro_minimo = _parse_quantidade(
                _valor(linha, mapa, "estoque_minimo")
            )
            if erro_minimo:
                erros.append(erro_minimo)

            codigo_barras = _valor(linha, mapa, "codigo_barras") or None
            codigo = _valor(linha, mapa, "codigo")

            # mesma regra do cadastro manual (ver ProdutoService.criar)
            if (
                not codigo and codigo_barras
                and codigo_barras.isdigit() and len(codigo_barras) <= 6
            ):
                codigo, codigo_barras = codigo_barras.zfill(4), None

            if not codigo:
                codigo = str(proximo_codigo).zfill(4)
                proximo_codigo += 1

            produto_existente = ProdutoRepository.buscar_por_codigo(
                db, codigo, loja_id
            )
            if not produto_existente and codigo_barras:
                produto_existente = ProdutoRepository.buscar_por_codigo_barras(
                    db, codigo_barras, loja_id
                )

            itens.append(ItemImportacaoPreview(
                linha=indice,
                codigo=codigo,
                nome=nome,
                categoria=_valor(linha, mapa, "categoria") or None,
                codigo_barras=codigo_barras,
                preco_custo=preco_custo,
                preco_venda=preco_venda,
                estoque=estoque,
                estoque_minimo=estoque_minimo,
                unidade=_valor(linha, mapa, "unidade") or "UN",
                produto_id=produto_existente.id if produto_existente else None,
                erro="; ".join(erros) if erros else None,
            ))

        total_com_erro = sum(1 for i in itens if i.erro)
        total_atualizados = sum(
            1 for i in itens if not i.erro and i.produto_id is not None
        )
        total_novos = len(itens) - total_com_erro - total_atualizados

        return itens, total_novos, total_atualizados, total_com_erro

    @staticmethod
    def confirmar(
        db: Session,
        itens: list[ItemImportacaoConfirmar],
        loja_id: int | None = None,
    ):
        """Reaproveita ProdutoService.criar/atualizar (mesma validacao
        de duplicidade, mesmo tratamento de estoque inicial por loja)
        em vez de escrever no banco direto -- uma linha de cada vez,
        erro numa nao derruba as outras (cada uma ja' passou pelo
        preview, entao um erro aqui e' raro: so' se algo mudou entre
        o preview e a confirmacao)."""

        criados = 0
        atualizados = 0

        for item in itens:

            if item.produto_id is not None:
                ProdutoService.atualizar(
                    db,
                    item.produto_id,
                    ProdutoUpdate(
                        codigo=item.codigo,
                        nome=item.nome,
                        categoria=item.categoria,
                        codigo_barras=item.codigo_barras,
                        preco_custo=item.preco_custo,
                        preco_venda=item.preco_venda,
                        estoque=item.estoque,
                        estoque_minimo=item.estoque_minimo,
                        unidade=item.unidade,
                    ),
                    loja_id,
                )
                atualizados += 1
            else:
                ProdutoService.criar(
                    db,
                    ProdutoCreate(
                        codigo=item.codigo,
                        nome=item.nome,
                        categoria=item.categoria,
                        codigo_barras=item.codigo_barras,
                        preco_custo=item.preco_custo,
                        preco_venda=item.preco_venda,
                        estoque=item.estoque,
                        estoque_minimo=item.estoque_minimo,
                        unidade=item.unidade,
                    ),
                    loja_id,
                )
                criados += 1

        return criados, atualizados
