"""
Importa o histórico de fiado (compras e pagamentos) de uma planilha Excel
para o Vertex ERP, criando os clientes que ainda não existem (por nome) e
os respectivos movimentos de fiado, preservando as datas originais.

Uso:
    python scripts/importar_fiado.py "caminho\\da\\planilha.xlsx"           # simula, não grava nada
    python scripts/importar_fiado.py "caminho\\da\\planilha.xlsx" --commit  # grava de verdade

A planilha precisa ter uma aba chamada "Movimentacoes" com as colunas:
    Data | Cliente | Tipo (Compra/Pagamento) | Descricao / Produto | Valor (R$)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

import openpyxl

from app.database.session import SessionLocal
from app.models.cliente import Cliente
from app.models.movimento_fiado import MovimentoFiado
from app.models.user import User

ABA = "Movimentacoes"


def normalizar_valor(valor):
    if valor is None:
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()

    if "," in texto:
        partes = texto.split(",")
        if len(partes) > 1:
            inteiro = "".join(partes[:-1])
            decimal = partes[-1]
            texto = f"{inteiro}.{decimal}"

    try:
        return float(texto)
    except ValueError:
        return None


def normalizar_tipo(tipo):
    if tipo is None:
        return None

    texto = str(tipo).strip().lower()

    if texto == "compra":
        return "COMPRA"

    if texto == "pagamento":
        return "PAGAMENTO"

    return None


def ler_planilha(caminho):
    wb = openpyxl.load_workbook(caminho, data_only=True)
    ws = wb[ABA]

    linhas = []
    erros = []

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        data, cliente, tipo, descricao, valor = row

        if cliente is None and tipo is None and valor is None:
            continue  # linha em branco (sobra de formatação da planilha)

        problemas = []

        nome = str(cliente).strip() if cliente else None
        if not nome:
            problemas.append("cliente em branco")

        tipo_norm = normalizar_tipo(tipo)
        if tipo_norm is None:
            problemas.append(f"tipo inválido: {tipo!r}")

        valor_norm = normalizar_valor(valor)
        if valor_norm is None or valor_norm <= 0:
            problemas.append(f"valor inválido: {valor!r}")

        if not isinstance(data, datetime):
            problemas.append(f"data inválida: {data!r}")

        if problemas:
            erros.append((i, problemas))
            continue

        linhas.append(
            {
                "linha": i,
                "nome": nome,
                "tipo": tipo_norm,
                "valor": valor_norm,
                "descricao": str(descricao).strip() if descricao else None,
                "data": data,
            }
        )

    return linhas, erros


def importar(caminho, commit=False):
    linhas, erros = ler_planilha(caminho)

    print(f"Linhas válidas para importar: {len(linhas)}")
    print(f"Linhas com problema (não serão importadas): {len(erros)}")

    if erros:
        print("\n--- LINHAS COM PROBLEMA ---")
        for linha, problemas in erros:
            print(f"  Linha {linha}: {', '.join(problemas)}")

    nomes_unicos = {linha["nome"].strip().lower() for linha in linhas}
    print(f"\nClientes distintos encontrados: {len(nomes_unicos)}")

    if not commit:
        print(
            "\n(modo simulação — nada foi gravado no banco; "
            "rode de novo com --commit para importar de verdade)"
        )
        return

    db = SessionLocal()

    try:
        usuario = db.query(User).filter(User.admin.is_(True)).first()

        if not usuario:
            print("\nNenhum usuário administrador encontrado — abortando.")
            return

        clientes_cache = {
            c.nome.strip().lower(): c for c in db.query(Cliente).all()
        }

        clientes_criados = 0
        movimentos_criados = 0

        for linha in linhas:
            chave = linha["nome"].strip().lower()

            cliente = clientes_cache.get(chave)

            if cliente is None:
                cliente = Cliente(nome=linha["nome"], ativo=True)
                db.add(cliente)
                db.flush()
                clientes_cache[chave] = cliente
                clientes_criados += 1

            movimento = MovimentoFiado(
                cliente_id=cliente.id,
                venda_id=None,
                usuario_id=usuario.id,
                tipo=linha["tipo"],
                valor=linha["valor"],
                descricao=linha["descricao"],
                data=linha["data"],
            )
            db.add(movimento)
            movimentos_criados += 1

        db.commit()

        print(
            f"\nImportação concluída: {clientes_criados} clientes criados, "
            f"{movimentos_criados} movimentos importados "
            f"(atribuídos ao usuário '{usuario.email}')."
        )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Importa fichas de fiado de uma planilha Excel para o Vertex ERP."
    )
    parser.add_argument("planilha", help="Caminho do arquivo .xlsx")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Grava de verdade no banco (sem essa flag, só simula e mostra o relatório)",
    )
    args = parser.parse_args()

    importar(args.planilha, args.commit)
