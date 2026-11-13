"""Design tokens do Vertex ERP — fonte única de verdade pra cor, espaçamento
e tipografia. Nenhuma tela deveria escrever um valor de cor hexadecimal
direto no stylesheet; sempre importar daqui, pra manter consistência e
permitir trocar o tema inteiro num lugar só.

As telas fazem `from design import tokens` e leem `tokens.PRIMARIA` etc.
(nunca `from design.tokens import PRIMARIA`, que travaria o valor no
momento do import) -- isso é o que permite aplicar() trocar a paleta
inteira em runtime só reatribuindo os atributos deste módulo: toda tela
construída depois do aplicar() já nasce com as cores certas, sem precisar
saber nada sobre tema."""

# ==========================================
# PALETA CLARA (padrão)
# ==========================================

_CLARO = {
    "PRIMARIA": "#1B4B8F",
    "PRIMARIA_HOVER": "#123A73",
    "PRIMARIA_CLARA": "#E8EEF9",

    "SECUNDARIA": "#0D7D6C",
    "SECUNDARIA_HOVER": "#095F52",

    "SUCESSO": "#0F7A61",  # era #149174 (3,94:1 com texto branco); agora 5,28:1
    "SUCESSO_CLARO": "#E7F5F1",

    "ALERTA": "#9C6509",  # era #B4750F (3,82:1 com texto branco); agora 4,91:1
    "ALERTA_CLARO": "#FBF1E1",
    "ALERTA_TEXTO": "#8A5A0C",

    "ERRO": "#A9362A",
    "ERRO_HOVER": "#8A2B21",
    "ERRO_CLARO": "#FBEBE8",

    # 06/11: "tela muito branca" -- fundo um tom mais escuro pra os cartoes
    # brancos se destacarem, bordas e textos cinza mais fortes
    "FUNDO": "#EAE6DD",
    "SIDEBAR": "#101F38",
    "SIDEBAR_HOVER": "#1C3357",
    "SIDEBAR_ATIVO": "#24406B",

    "CARD": "#FFFFFF",
    "BORDA": "#D6CFC1",
    "BORDA_FORTE": "#BDB4A2",
    # borda de campo de formulario: WCAG 1.4.11 pede 3:1 (3,82:1 sobre CARD)
    "BORDA_CAMPO": "#8A826E",
    # texto sobre fundo preenchido (botoes, chips): branco no claro
    "TEXTO_SOBRE_COR": "#FFFFFF",

    "TEXTO": "#0E1830",
    "TEXTO_SECUNDARIO": "#3F4C63",
    # era #8B96AC (~2,98:1 sobre CARD branco -- reprova WCAG AA, que
    # exige 4,5:1 pra texto normal). Usado em 38 das ~39 telas (legenda
    # de campo, texto secundario de cards etc.), boa parte em
    # TAMANHO_XS (11px). FUNDO (#F5F3EF) e' quase tao claro quanto CARD,
    # entao a cor precisa passar nos dois -- isso deixa esse tom bem
    # perto de TEXTO_SECUNDARIO (pouco espaco pra um terceiro nivel mais
    # claro continuar acessivel sobre fundo quase branco); 5,47:1
    # sobre CARD e 4,94:1 sobre FUNDO, os dois com folga sobre o 4,5:1.
    "TEXTO_TERCIARIO": "#4A5770",
    "TEXTO_CLARO": "#FFFFFF",
    "TEXTO_SIDEBAR": "#C7D2E3",
    "TEXTO_SIDEBAR_APAGADO": "#7C89A3",

    "SOMBRA_COR": "#16213B",
    # barra de comparacao nos graficos (ex.: "media" ao lado de "hoje")
    "GRAFICO_NEUTRO": "#9AA6BA",
}

# ==========================================
# PALETA ESCURA
# ==========================================

# Mesmos papéis semânticos da paleta clara, valores trocados pra manter
# contraste em fundo escuro (tons Tailwind slate/blue/green/amber/red,
# mesma família de cor já usada na paleta clara, só na ponta escura da
# escala) -- SIDEBAR já nascia escuro mesmo no tema claro, então quase
# não muda entre os dois.
_ESCURO = {
    "PRIMARIA": "#6B9AD8",  # era #4C7FC9 (3,99:1 como texto sobre CARD)
    "PRIMARIA_HOVER": "#8DB2E6",
    "PRIMARIA_CLARA": "#1C2A3F",

    "SECUNDARIA": "#2FA88F",
    "SECUNDARIA_HOVER": "#4FC2A8",

    "SUCESSO": "#3FBFA0",
    "SUCESSO_CLARO": "#163A31",

    "ALERTA": "#D69A3E",
    "ALERTA_CLARO": "#3A2A11",
    "ALERTA_TEXTO": "#E4B063",

    "ERRO": "#D9695C",
    "ERRO_HOVER": "#E68A7F",
    "ERRO_CLARO": "#3A1B17",

    "FUNDO": "#0E1420",
    "SIDEBAR": "#0A121F",
    "SIDEBAR_HOVER": "#16233A",
    "SIDEBAR_ATIVO": "#223655",

    "CARD": "#182130",
    "BORDA": "#29334A",
    "BORDA_FORTE": "#39445E",
    "BORDA_CAMPO": "#667391",  # 3,41:1 sobre CARD escuro
    # no escuro os fundos preenchidos sao claros: texto escuro (>= 4,5:1)
    "TEXTO_SOBRE_COR": "#0E1420",

    "TEXTO": "#ECE7DC",
    "TEXTO_SECUNDARIO": "#9AA3B0",
    # mesmo motivo do tema claro: era #6B7280, ~3,34:1 sobre CARD
    # escuro (#182130), tambem reprova AA -- este tom da ~4,70:1.
    "TEXTO_TERCIARIO": "#818B9D",
    "TEXTO_CLARO": "#FFFFFF",
    "TEXTO_SIDEBAR": "#B7C2D6",
    "TEXTO_SIDEBAR_APAGADO": "#71809C",

    "SOMBRA_COR": "#000000",
    "GRAFICO_NEUTRO": "#566379",
}

ESCURO_ATIVO = False


def aplicar(escuro: bool) -> None:
    """Troca a paleta de cores inteira -- chamado uma vez no arranque
    do app (ver app.py/design.theme.aplicar_tema), antes de qualquer
    tela ser construída. Só reatribui os nomes deste módulo; qualquer
    tela que já leia `tokens.COR_QUALQUER` (em vez de ter importado o
    valor direto) enxerga a troca automaticamente."""

    global ESCURO_ATIVO

    paleta = _ESCURO if escuro else _CLARO

    for nome, valor in paleta.items():
        globals()[nome] = valor

    ESCURO_ATIVO = escuro


# aplica a paleta clara já na carga do módulo, pra quem nunca chamar
# aplicar() (testes, scripts avulsos) continuar funcionando igual a
# antes desta troca existir
aplicar(escuro=False)

# ==========================================
# CORES DE GRADIENTE (decorativas, mesmo valor nos dois temas -- servem
# só de ponto final de gradiente/ilustração, não de texto ou superfície,
# então não precisam da troca clara/escura como o resto da paleta)
# ==========================================

PRIMARIA_ESCURA = "#0F2E57"
SECUNDARIA_ESCURA = "#084A40"
ALERTA_ESCURA = "#7A4E09"

# ==========================================
# RAIO DE BORDA
# ==========================================

RADIUS_LG = 12  # era 16; escala do Stripe: cartao 12, campo/botao 8
RADIUS_MD = 12
RADIUS_SM = 8
RADIUS_PILL = 999

# ==========================================
# TIPOGRAFIA
# ==========================================

FONTE_FAMILIA_PADRAO = "Segoe UI"

# 06/11: +1 px em tudo -- 11-13 px era pequeno pra ler no balcao
TAMANHO_XS = 12
TAMANHO_SM = 13
TAMANHO_BASE = 14
TAMANHO_MD = 15
TAMANHO_LG = 17
TAMANHO_XL = 20
TAMANHO_XXL = 28

# ==========================================
# SOMBRA (usado com QGraphicsDropShadowEffect)
# ==========================================

SOMBRA_CARD_BLUR = 24
SOMBRA_CARD_Y = 4
SOMBRA_CARD_ALPHA = 18

SOMBRA_ELEVADA_BLUR = 40
SOMBRA_ELEVADA_Y = 8
SOMBRA_ELEVADA_ALPHA = 28
