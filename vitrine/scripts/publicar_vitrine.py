"""Publica a vitrine no GitHub Pages (repositorio so' do site).

    python publicar_vitrine.py                 # so' precos/fotos (tarefa agendada)
    python publicar_vitrine.py --site          # tambem reconstroi o site (codigo mudou)
    python publicar_vitrine.py --sem-enviar    # gera tudo e faz commit local, sem push

Roda no PC da loja: le' o Vertex local (exportar_vitrine.py), grava em
<clone>/dados e da' commit+push so' quando algo mudou. Falhou a exportacao
(Vertex desligado)? Nao publica nada -- o site segue com o ultimo snapshot.
"""

import argparse
import html
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from exportar_vitrine import exportar

PASTA_VITRINE = Path(__file__).resolve().parent.parent
# o que vem do build mas nao vai pro ar: dados de dev e de demonstracao
FORA_DO_SITE = {"dados", "demo"}
# o que vive so' no clone e o --site nao apaga
DO_CLONE = {".git", "dados", "p", ".nojekyll", "README.md"}


def rodar(*comando, cwd):
    return subprocess.run(comando, cwd=cwd, check=True, text=True, capture_output=True).stdout


def real(valor) -> str:
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_paginas_produto(clone: Path, catalogo: dict, site: str) -> None:
    """p/<slug>/index.html por produto: so' as tags de previa (foto, nome,
    preco) para o WhatsApp mostrar a foto quando o link vai na mensagem,
    e redireciona para o produto aberto no site."""
    pasta = clone / "p"
    pasta.mkdir(exist_ok=True)
    slugs = set()
    for produto in catalogo["produtos"]:
        slug = produto["slug"]
        slugs.add(slug)
        preco = real(produto["preco"])
        if produto.get("preco_anterior"):
            preco += f" (de {real(produto['preco_anterior'])})"
        descricao = f"{preco} · Cód. {produto['codigo']} · 3.L.A Variedades, Tonantins-AM"
        foto = f"{site}/dados/{produto['fotos'][0]}" if produto["fotos"] else f"{site}/previa.png"
        destino = f"{site}/?produto={slug}"
        e = lambda v: html.escape(str(v), quote=True)
        pagina = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(produto['nome'])} | 3.L.A Variedades</title>
<meta name="description" content="{e(descricao)}">
<meta property="og:type" content="product">
<meta property="og:title" content="{e(produto['nome'])}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:image" content="{e(foto)}">
<meta property="og:url" content="{e(f'{site}/p/{slug}/')}">
<meta http-equiv="refresh" content="0; url={e(destino)}">
</head><body><a href="{e(destino)}">Ver {e(produto['nome'])} na vitrine</a></body></html>
"""
        arquivo = pasta / slug / "index.html"
        arquivo.parent.mkdir(exist_ok=True)
        if not arquivo.exists() or arquivo.read_text(encoding="utf-8") != pagina:
            arquivo.write_text(pagina, encoding="utf-8")
    for velha in pasta.iterdir():
        if velha.is_dir() and velha.name not in slugs:  # saiu do site
            shutil.rmtree(velha)


def atualizar_site(clone: Path) -> None:
    npm = shutil.which("npm") or "npm"
    subprocess.run([npm, "run", "build"], cwd=PASTA_VITRINE, check=True)
    for item in clone.iterdir():
        if item.name not in DO_CLONE:
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    for item in (PASTA_VITRINE / "out").iterdir():
        if item.name in FORA_DO_SITE:
            continue
        destino = clone / item.name
        shutil.copytree(item, destino) if item.is_dir() else shutil.copy2(item, destino)
    (clone / ".nojekyll").touch()  # GitHub Pages nao ignorar a pasta _next


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--clone", type=Path, default=Path(r"C:\servidor\vitrine-site"))
    argumentos.add_argument("--api", default="https://127.0.0.1:58734")
    argumentos.add_argument("--site", action="store_true")
    argumentos.add_argument("--sem-enviar", action="store_true")
    argumentos.add_argument("--url-site", default="https://anndreluizz.github.io/3la-variedades")
    opcoes = argumentos.parse_args()

    if opcoes.site:
        atualizar_site(opcoes.clone)
    try:
        catalogo = exportar(opcoes.api, opcoes.clone / "dados")
    except OSError as erro:
        if not opcoes.site:
            raise
        # mudanca so' no visual: publica o site com os dados do ultimo envio
        print(f"Vertex fora do ar ({erro}); mantendo os dados do ultimo envio.")
        catalogo = json.loads((opcoes.clone / "dados" / "vitrine.json").read_text(encoding="utf-8"))

    gerar_paginas_produto(opcoes.clone, catalogo, opcoes.url_site.rstrip("/"))

    rodar("git", "add", "-A", cwd=opcoes.clone)
    if not rodar("git", "status", "--porcelain", cwd=opcoes.clone).strip():
        print("Nada mudou.")
        return 0
    quando = datetime.now().strftime("%d/%m/%Y %H:%M")
    rodar("git", "commit", "-m", f"Vitrine {quando}: {len(catalogo['produtos'])} produto(s)", cwd=opcoes.clone)
    if not opcoes.sem_enviar:
        rodar("git", "push", cwd=opcoes.clone)
    print(f"Publicado: {len(catalogo['produtos'])} produto(s) em {quando}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
