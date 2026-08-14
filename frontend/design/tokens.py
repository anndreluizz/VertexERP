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
    "PRIMARIA": "#2563EB",
    "PRIMARIA_HOVER": "#1D4ED8",
    "PRIMARIA_CLARA": "#EFF6FF",

    "SECUNDARIA": "#16A34A",
    "SECUNDARIA_HOVER": "#15803D",

    "SUCESSO": "#22C55E",
    "SUCESSO_CLARO": "#F0FDF4",

    "ALERTA": "#F59E0B",
    "ALERTA_CLARO": "#FFFBEB",
    "ALERTA_TEXTO": "#B45309",

    "ERRO": "#DC2626",
    "ERRO_HOVER": "#B91C1C",
    "ERRO_CLARO": "#FEF2F2",

    "FUNDO": "#F5F7FA",
    "SIDEBAR": "#18181B",
    "SIDEBAR_HOVER": "#27272A",
    "SIDEBAR_ATIVO": "#27272A",

    "CARD": "#FFFFFF",
    "BORDA": "#E5E7EB",
    "BORDA_FORTE": "#D1D5DB",

    "TEXTO": "#1E293B",
    "TEXTO_SECUNDARIO": "#64748B",
    "TEXTO_TERCIARIO": "#94A3B8",
    "TEXTO_CLARO": "#FFFFFF",
    "TEXTO_SIDEBAR": "#D4D4D8",
    "TEXTO_SIDEBAR_APAGADO": "#71717A",

    "SOMBRA_COR": "#1E293B",
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
    "PRIMARIA": "#3B82F6",
    "PRIMARIA_HOVER": "#60A5FA",
    "PRIMARIA_CLARA": "#1E3A5F",

    "SECUNDARIA": "#22C55E",
    "SECUNDARIA_HOVER": "#4ADE80",

    "SUCESSO": "#4ADE80",
    "SUCESSO_CLARO": "#14532D",

    "ALERTA": "#FBBF24",
    "ALERTA_CLARO": "#451A03",
    "ALERTA_TEXTO": "#FBBF24",

    "ERRO": "#EF4444",
    "ERRO_HOVER": "#F87171",
    "ERRO_CLARO": "#450A0A",

    "FUNDO": "#0F172A",
    "SIDEBAR": "#09090B",
    "SIDEBAR_HOVER": "#27272A",
    "SIDEBAR_ATIVO": "#3F3F46",

    "CARD": "#1E293B",
    "BORDA": "#334155",
    "BORDA_FORTE": "#475569",

    "TEXTO": "#F1F5F9",
    "TEXTO_SECUNDARIO": "#94A3B8",
    "TEXTO_TERCIARIO": "#64748B",
    "TEXTO_CLARO": "#FFFFFF",
    "TEXTO_SIDEBAR": "#D4D4D8",
    "TEXTO_SIDEBAR_APAGADO": "#71717A",

    "SOMBRA_COR": "#000000",
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
# RAIO DE BORDA
# ==========================================

RADIUS_LG = 16
RADIUS_MD = 12
RADIUS_SM = 8
RADIUS_PILL = 999

# ==========================================
# TIPOGRAFIA
# ==========================================

FONTE_FAMILIA_PADRAO = "Segoe UI"

TAMANHO_XS = 11
TAMANHO_SM = 12
TAMANHO_BASE = 13
TAMANHO_MD = 14
TAMANHO_LG = 16
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
