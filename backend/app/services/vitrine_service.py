import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.repositories.configuracao_repository import ConfiguracaoRepository
from app.repositories.vitrine_repository import VitrineRepository

DIAS_NOVIDADE = 30
DIAS_MAIS_VENDIDOS = 90
LIMITE_MAIS_VENDIDOS = 8


def slug(produto: Produto) -> str:
    texto = unicodedata.normalize("NFKD", f"{produto.nome} {produto.codigo}")
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-") or str(produto.id)


def disponibilidade(produto: Produto) -> str:
    if produto.eh_kit:
        return "consulte"
    return "disponivel" if (produto.estoque or 0) > 0 else "esgotado"


class VitrineService:

    @staticmethod
    def catalogo(db: Session) -> dict:
        agora = datetime.now()
        produtos = VitrineRepository.listar_publicados(db)
        config = ConfiguracaoRepository.buscar(db)

        itens = []
        for p in produtos:
            fotos = sorted(p.fotos, key=lambda f: (not f.principal, f.ordem, f.id))
            itens.append({
                "id": p.id,
                "slug": slug(p),
                "codigo": p.codigo,
                "nome": p.nome,
                "descricao": p.descricao,
                "categoria": p.categoria,
                "marca": p.marca.nome if p.marca else None,
                "cor": p.cor,
                "tamanho": p.tamanho,
                "unidade": p.unidade or "UN",
                "preco": p.preco_efetivo,
                "preco_anterior": p.preco_venda if p.em_promocao else None,
                "promocao_fim": p.promocao_fim if p.em_promocao else None,
                "disponibilidade": disponibilidade(p),
                "destaque": p.vitrine_destaque,
                "novidade": bool(p.criado_em and p.criado_em >= agora - timedelta(days=DIAS_NOVIDADE)),
                "fotos": [f"/vitrine/fotos/{f.id}" for f in fotos],
            })

        contagem = Counter(p.categoria for p in produtos if p.categoria)

        return {
            "gerado_em": agora,
            "loja": {
                "nome": config.nome_loja if config else None,
                "endereco": config.endereco if config else None,
            },
            "categorias": [
                {"nome": nome, "quantidade": qtd}
                for nome, qtd in sorted(contagem.items())
            ],
            "mais_vendidos": VitrineRepository.mais_vendidos(
                db,
                [p.id for p in produtos],
                agora - timedelta(days=DIAS_MAIS_VENDIDOS),
                LIMITE_MAIS_VENDIDOS,
            ),
            "produtos": itens,
        }

    @staticmethod
    def foto(db: Session, foto_id: int) -> bytes | None:
        foto = VitrineRepository.buscar_foto_publicada(db, foto_id)
        return foto.imagem if foto else None

