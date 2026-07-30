"""Design tokens do Vertex ERP — fonte única de verdade pra cor, espaçamento
e tipografia. Nenhuma tela deveria escrever um valor de cor hexadecimal
direto no stylesheet; sempre importar daqui, pra manter consistência e
permitir trocar o tema inteiro num lugar só."""

# ==========================================
# CORES
# ==========================================

PRIMARIA = "#2563EB"
PRIMARIA_HOVER = "#1D4ED8"
PRIMARIA_CLARA = "#EFF6FF"

SECUNDARIA = "#16A34A"
SECUNDARIA_HOVER = "#15803D"

SUCESSO = "#22C55E"
SUCESSO_CLARO = "#F0FDF4"

ALERTA = "#F59E0B"
ALERTA_CLARO = "#FFFBEB"

ERRO = "#DC2626"
ERRO_HOVER = "#B91C1C"
ERRO_CLARO = "#FEF2F2"

FUNDO = "#F5F7FA"
SIDEBAR = "#18181B"
SIDEBAR_HOVER = "#27272A"
SIDEBAR_ATIVO = "#27272A"

CARD = "#FFFFFF"
BORDA = "#E5E7EB"
BORDA_FORTE = "#D1D5DB"

TEXTO = "#1E293B"
TEXTO_SECUNDARIO = "#64748B"
TEXTO_TERCIARIO = "#94A3B8"
TEXTO_CLARO = "#FFFFFF"
TEXTO_SIDEBAR = "#D4D4D8"
TEXTO_SIDEBAR_APAGADO = "#71717A"

# ==========================================
# RAIO DE BORDA
# ==========================================

RADIUS_LG = 16
RADIUS_MD = 12
RADIUS_SM = 8
RADIUS_PILL = 999

# ==========================================
# ESPAÇAMENTO (múltiplos de 4px)
# ==========================================

ESPACO_XS = 4
ESPACO_SM = 8
ESPACO_MD = 16
ESPACO_LG = 24
ESPACO_XL = 32
ESPACO_XXL = 48

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
TAMANHO_TITULO = 34

# ==========================================
# SOMBRA (usado com QGraphicsDropShadowEffect)
# ==========================================

SOMBRA_COR = "#1E293B"
SOMBRA_CARD_BLUR = 24
SOMBRA_CARD_Y = 4
SOMBRA_CARD_ALPHA = 18

SOMBRA_ELEVADA_BLUR = 40
SOMBRA_ELEVADA_Y = 8
SOMBRA_ELEVADA_ALPHA = 28
