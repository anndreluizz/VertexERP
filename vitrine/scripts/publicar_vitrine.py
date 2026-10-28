"""Publica a vitrine no GitHub Pages (repositorio so' do site).

    python publicar_vitrine.py                 # so' precos/fotos (tarefa agendada)
    python publicar_vitrine.py --site          # tambem reconstroi o site (codigo mudou)
    python publicar_vitrine.py --sem-enviar    # gera tudo e faz commit local, sem push

Roda no PC da loja: le' o Vertex local (exportar_vitrine.py), grava em
<clone>/dados e da' commit+push so' quando algo mudou. Falhou a exportacao
(Vertex desligado)? Nao publica nada -- o site segue com o ultimo snapshot.
"""

import argparse
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
DO_CLONE = {".git", "dados", ".nojekyll", "README.md"}


def rodar(*comando, cwd):
    return subprocess.run(comando, cwd=cwd, check=True, text=True, capture_output=True).stdout


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
