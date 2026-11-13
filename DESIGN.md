---
name: Vertex ERP
description: ERP comercial para loja de balcao. Navy de tinta, azul primario, fundo quente de papel, cartoes brancos. Fonte da verdade no codigo - frontend/design/tokens.py.
reference: Stripe (awesome-design-md/design-md/stripe), adaptado - ver "Referencia"
---

## Cores (tokens.py, tema claro)

| Papel | Token | Valor |
|---|---|---|
| Acao primaria | PRIMARIA | #1B4B8F |
| Acao positiva / receber | SECUNDARIA | #0D7D6C |
| Sucesso / Alerta / Erro | SUCESSO / ALERTA / ERRO | #0F7A61 / #9C6509 / #A9362A |
| Fundo da tela | FUNDO | #EAE6DD (quente, de proposito: "tela muito branca") |
| Cartao | CARD | #FFFFFF |
| Barra lateral | SIDEBAR | #101F38 |
| Texto | TEXTO / SECUNDARIO / TERCIARIO | #0E1830 / #3F4C63 / #4A5770 |
| Borda de campo | BORDA_CAMPO | #8A826E (>= 3:1) |
| Texto sobre cor cheia | TEXTO_SOBRE_COR | branco (claro) / #0E1420 (escuro) |

Regras: texto nunca preto puro; todo par texto/fundo >= 4,5:1 nos DOIS temas
(tests/test_contraste_tokens.py guarda isso); hex solto fora de tokens.py e erro.

## Tipografia

- Texto: Figtree. Titulos grandes: Bricolage Grotesque. Reserva: Inter.
- Escala (px): 12 / 13 / 14 / 15 / 17 / 20 / 28. Minimo 12 - nada de 10 ou 11.
- **Numeros tabulares** (`tnum`) em toda a fonte do app (`design/fonts.fonte`):
  valor em coluna alinha nas casas.
- Peso 500 no corpo (Figtree 400 afina demais no Windows); 600/700 so em titulo e valor.

## Forma e profundidade

- Raio: 8 (campos, botoes), 12 (cartoes e paineis), pilula so em chip/selo.
- Cartao: borda 1px BORDA + sombra azulada leve (SOMBRA_COR, blur 24, alpha 18).
- Cartao "destaque" (cor cheia) = no maximo um por grade de KPIs.
- Seta de menu: icone chevron-down desenhado, nunca caractere unicode (falta na Figtree).

## Componentes

- Uma acao cheia por area; as demais em contorno (BotaoSecundario). Ficha do cliente: Receber cheio, Cobrar no WhatsApp em contorno.
- Botao: hover anima a cor, foco por teclado desenha anel por dentro.
- Campo: 44px de altura, borda BORDA_CAMPO, foco troca para PRIMARIA.
- Dialogo: DialogoPadrao (560/760/860), Cancelar + acao principal a direita.
- Confirmacao: `perguntar()` com verbo no botao ("Excluir marca" / "Cancelar").
- Formulario com dados: herda ProtegeAlteracoes (avisa antes de perder alteracoes).
- Card clicavel: `tornar_acionavel` (Tab, Enter/Espaco, anel de foco).

## Referencia: Stripe, o que entrou e o que ficou de fora

Entrou: tinta navy no texto; numeros tabulares; sombra azulada em dois niveis,
sutil; uma unica acao cheia por area; cartao de destaque escuro como o "tier"
em evidencia; contraste e hierarquia por tamanho, nao por cor.

Ficou de fora, de proposito: malha de gradiente e indigo (e marca de site, nao
de balcao); peso 300 nos titulos (some no monitor de loja); botao em pilula
(ERP denso pede retangulo de 8px); fundo branco/cinza-azulado (o dono pediu
fundo mais escuro para os cartoes se destacarem).
