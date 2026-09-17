"""
Cadastra em lote os 59 produtos (roupas/calçados infantis) na loja ativa
deste PC. Roda direto contra o Postgres configurado em backend/.env.

Pre-requisito: já ter feito o primeiro acesso pelo app (cria usuário admin
e a loja). Sem isso o script não sabe em qual loja lançar o estoque.

Rode com (a partir de backend/, com o .venv ativado):
    python scripts\\cadastrar_produtos_lote.py
"""

from decimal import Decimal

from app.database.session import SessionLocal
from app.models.loja import Loja
from app.schemas.produto import ProdutoCreate
from app.services.produto_service import ProdutoService

db = SessionLocal()

loja = db.query(Loja).filter(Loja.ativa.is_(True)).order_by(Loja.id).first()
if not loja:
    raise SystemExit(
        "Nenhuma loja encontrada. Faça o primeiro acesso pelo app (tela "
        "'Comece Grátis') antes de rodar este script."
    )

# (codigo_barras, nome, valor, qtd)
PRODUTOS = [
    ("2213000279731014350030", "Marlan – REF 49426 – Laranja Neon – Conjunto Infantil Milli&Nina", "190.99", 1),
    ("2224000288636030090015", "Marlan – REF 49422 – Rosa Candy – Conjunto Infantil Milli&Nina", "230.99", 1),
    ("2227000291242025920007", "Marlan – REF 44801 – Pinky – Vestido Infantil Marlan", "97.99", 1),
    ("7909886096981", "Kyly – REF 111778 – Conjunto Feminino KAV23", "99.99", 1),
    ("7909856747691", "Lecimar – REF 1.502190/93548-1 – Blusa – Branco", "79.99", 1),
    ("7909856747677", "Lecimar – REF 1.502190/93548-1 – Blusa – Amarelo Borboleta", "79.99", 1),
    ("7909856505628", "Lecimar – REF 1.502054/86609-1 – Blusa com Manga – Laranja Slow", "101.99", 1),
    ("7119999900314", "Pimentinha Kids – REF 9052 – Conjunto Cropped – Pink Glow", "72.99", 1),
    ("7908718900953", "Softex – REF 07532 – Vestido Feminino", "45.99", 1),
    ("7119999905890", "Pimentinha Kids – REF 9061 – Vestido Alça com Franzido – Paprica", "62.99", 1),
    ("7909305237414", "Kyly – REF 08570...92-0 – Preto", "58.99", 1),
    ("7909856498760", "Lecimar – REF 1.502040/83593-1 – Vestido – Laranja", "140.99", 1),
    ("2516000148164009446003", "Kamylus – REF AZ0018/57277 – Marinho", "166.99", 1),
    ("7909305325647", "Lilydee – REF 085400092-0 – Preto", "209.99", 1),
    ("7908977209880", "Pingo Lelê – REF 68668A – Vestido de Alça", "189.99", 1),
    ("2214000279573051230023", "Marlan – REF 42546/AZ0001 – Marinho Escuro – Vestido Infantil", "218.99", 1),
    ("7119999905845", "Pimentinha Kids – REF 9061 – Vestido Alça com Franzido – Marinho", "62.99", 1),
    ("7909305324374", "Lilydee – REF 0853000146-0 – Off White", "213.99", 1),
    ("7909652638797", "Marlan – REF AM0116 – Amarelo Hype – Conjunto Infantil", "153.99", 1),
    ("08891460000926", "Lecimar – REF 1.502190/93548-1 – Blusa – Branco", "68.99", 1),
    ("7890700871382", "Quimby Kids – REF 0501... – Vestido Manga – Natural", "144.99", 1),
    ("7909856859592", "Lecimar – REF 1.502281/093967-2 – Vestido – Coral Suns", "59.99", 1),
    ("7900152019147", "Kidy – Sandália Baby Equilíbrio 001-2019-0008 – Rosa", "135.00", 3),
    ("7909773334035", "Kidy – Sandália Baby Equilíbrio 001-2019-0004 – Branco", "135.00", 3),
    ("7900152155227", "Kidy – Sandália Baby 001-2027-0004 – Branco", "135.00", 3),
    ("7900152361505", "Kidy – Sandália Baby Equilíbrio 001-2051-1872 – Anis", "135.00", 3),
    ("7900294396823", "Molekinha – Napa Turim/Tira Milão – Branco/Cristal-Pérola", "60.00", 3),
    ("7900190938929", "Molekinha – Napa Metalizado Tamisa Neo – Creme 985", "120.00", 3),
    ("7900190996417", "Molekinha – Napa Metalizado Tamisa Neo – Preto 01", "120.00", 3),
    ("7900190832494", "Molekinha – Verniz London – Prata", "110.00", 3),
    ("7900190972541", "Molekinha – Verniz Premium/Tira Ostra – Preto/Grafite/Marinho Furtacor", "110.00", 3),
    ("7900190534282", "Molekinha – Verniz Premium – Preto 01", "110.00", 3),
    ("7900190659947", "Beira Rio – Napa Turim – Preto 01 (rasteira 3 tiras)", "100.00", 5),
    ("7900407336487", "Beira Rio – Napa Turim – Preto 01 (tamanco salto bloco)", "110.99", 6),
    ("7900350948010", "Beira Rio – NP Turim/TP Bri Ital/TP Cord Strass – Branco Off/Dourado/Champanhe", "135.99", 5),
    ("7900152488578", "Kidy – Tênis K360 Energy 2 – Preto/Pink Neon", "200.00", 5),
    ("7900204928151", "Ipanema – 27516 Pluma Up – Preto/Preto/Branco", "120.99", 9),
    ("7909823103338", "Nylon Tech – Nude 658/Crepado", "149.99", 5),
    ("7909694107480", "Molekinho – Napa Floter Rústico Neo – Marinho 488/Cinza 851", "99.99", 5),
    ("7900190991917", "Molekinha – Verniz Premium/Tira Ostra – Rosa 942/Cristal-Branco Furtacor-Pérola Furtacor", "110.99", 4),
    ("7900190111513", "Molekinha – Lycra Favo – Marinho 1128", "115.00", 6),
    ("7892841150777", "Pikus – Easy 3 – Mescla/Preto", "300.99", 3),
    ("7909946206787", "Fila – Tênis Speed Lite Masculino – Navy/Alloy/Federal Blue", "350.99", 5),
    ("7900407843581", "Moleca – Sandália Napa Turim – Chocolate 1271", "120.00", 4),
    ("7900245722763", "Molekinha – NP Turim/TP NP Turim/Tira Florença – Preto/Preto/Cristal-Níquel", "120.00", 6),
    ("7900245333808", "Napa Floather Nature/Elástico – Creme 985", "130.99", 4),
    ("7900123082828", "NP Floather Nature/Elast Canelado – Preto 01", "130.99", 3),
    ("7900294574979", "Napa Floather Nature – Nude 658/Creme 985/Bege 435", "130.99", 2),
    ("7900245333785", "Napa Floather Nature/Elástico – Creme 985", "110.99", 3),
    ("7909773085265", "Kidy – Sapatênis Firenze – Marinho/Tabaco", "135.99", 3),
    ("7900350915241", "Napa Floter Rústico Neo – Preto 01/Cinza 851", "99.99", 6),
    ("7900245921319", "Molekinha – Napa Brilho Milão Neo – Rosa 942-Holográfico", "110.00", 3),
    ("7900294011641", "Molekinha – Napa Turim/Milano/Tira Florença – Preto/Preto-Cristal-Níquel", "110.00", 3),
    ("7900350389608", "Moleca – Sandália Napa Turim – Nude 658", "110.99", 3),
    ("7900245962244", "Vizzano – Tira Pronta Pelica/Pelica – Preto 01", "120.00", 2),
    ("7900350840970", "Napa Turim – Preto 01 (salto bloco com strass)", "180.00", 4),
    ("5000001000073", "Rockers – Tênis Jogger Unissex URF-010 – Branco/Preto", "150.99", 5),
    ("7909946168069", "Fila – Tênis Comet 2 Masculino – Cinza Gelo/Vermelho/Preto", "350.99", 4),
]

# ponytail: categoria por palavra-chave na descrição em vez de mapear
# marca a marca manualmente -- suficiente pra separar vestuário de
# calçado aqui, revisite se a loja passar a vender outras categorias.
PALAVRAS_VESTUARIO = ("vestido", "conjunto", "blusa")

criados = 0
pulados = 0

for indice, (codigo_barras, nome, valor, qtd) in enumerate(PRODUTOS, start=1):
    categoria = (
        "Vestuário"
        if any(palavra in nome.lower() for palavra in PALAVRAS_VESTUARIO)
        else "Calçados"
    )
    unidade = "UN" if categoria == "Vestuário" else "PAR"
    codigo = f"{indice:04d}"

    try:
        ProdutoService.criar(
            db,
            ProdutoCreate(
                codigo=codigo,
                codigo_barras=codigo_barras,
                nome=nome,
                categoria=categoria,
                unidade=unidade,
                preco_venda=Decimal(valor),
                estoque=qtd,
            ),
            loja.id,
        )
        criados += 1
        print(f"[ok] {codigo} - {nome}")
    except ValueError as erro:
        pulados += 1
        print(f"[pulado] {codigo} - {nome}: {erro}")

print(f"\nconcluido: {criados} criados, {pulados} pulados (loja: {loja.nome})")
