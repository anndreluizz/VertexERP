"""Gera o snapshot publico da vitrine a partir do Vertex rodando na loja.

    python exportar_vitrine.py --api https://127.0.0.1:58734 --saida ../public/dados

Baixa GET /vitrine/ e as fotos dos produtos publicados para --saida
(vitrine.json + fotos/<id>.jpg). Essa pasta vai junto com o
site estatico -- o PC da loja nunca fica exposto na internet, so' envia.
So' biblioteca padrao: roda no Python de qualquer PC.
"""

import argparse
import json
import ssl
import sys
import tempfile
import urllib.request
from pathlib import Path


def baixar(url: str, contexto: ssl.SSLContext) -> bytes:
    with urllib.request.urlopen(url, context=contexto, timeout=30) as resposta:
        return resposta.read()


def gravar(caminho: Path, dados: bytes) -> None:
    # grava num temporario e troca: o site nunca le' um arquivo pela metade
    with tempfile.NamedTemporaryFile(dir=caminho.parent, delete=False) as tmp:
        tmp.write(dados)
    Path(tmp.name).replace(caminho)


def exportar(api: str, saida: Path) -> dict:
    api = api.rstrip("/")
    # certificado do backend e' autoassinado (app/core/tls.py) e a conexao
    # e' local/Tailscale -- verificar a cadeia aqui nao protege nada.
    contexto = ssl._create_unverified_context()
    catalogo = json.loads(baixar(f"{api}/vitrine/", contexto))

    pasta_fotos = saida / "fotos"
    pasta_fotos.mkdir(parents=True, exist_ok=True)
    usadas = set()
    for produto in catalogo["produtos"]:
        locais = []
        for url in produto["fotos"]:
            nome = f"{url.rstrip('/').rsplit('/', 1)[-1]}.jpg"
            destino = pasta_fotos / nome
            if not destino.exists():  # foto nunca muda com o mesmo id
                gravar(destino, baixar(f"{api}{url}", contexto))
            usadas.add(nome)
            locais.append(f"fotos/{nome}")
        produto["fotos"] = locais

    for velha in pasta_fotos.glob("*.jpg"):
        if velha.name not in usadas:  # produto despublicado / foto trocada
            velha.unlink()

    # so' regrava se algo alem do horario mudou: sem isso, cada execucao
    # agendada vira um commit/deploy novo no GitHub Pages
    arquivo = saida / "vitrine.json"
    sem_horario = lambda c: {k: v for k, v in c.items() if k != "gerado_em"}
    if arquivo.exists():
        anterior = json.loads(arquivo.read_text(encoding="utf-8"))
        if sem_horario(anterior) == sem_horario(catalogo):
            return anterior
    gravar(arquivo, json.dumps(catalogo, ensure_ascii=False).encode("utf-8"))
    return catalogo


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--api", default="https://127.0.0.1:58734")
    argumentos.add_argument("--saida", type=Path, default=Path(__file__).parent.parent / "public" / "dados")
    opcoes = argumentos.parse_args()
    opcoes.saida.mkdir(parents=True, exist_ok=True)
    catalogo = exportar(opcoes.api, opcoes.saida)
    print(f"{len(catalogo['produtos'])} produto(s) exportado(s) para {opcoes.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
