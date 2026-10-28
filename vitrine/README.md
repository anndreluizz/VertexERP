# Vitrine virtual (site da loja)

Site estático em Next.js + TypeScript que mostra os produtos marcados
**"Mostrar na vitrine"** no cadastro de produtos do Vertex. Pedido e
confirmação acontecem pelo WhatsApp: não tem carrinho nem pagamento.

## Como os dados chegam

```
Vertex (PC da loja)                           Hospedagem do site
GET /vitrine/  ──> scripts/exportar_vitrine.py ──> dados/vitrine.json + dados/fotos/*.jpg
(rota pública, só leitura)                     (o site lê esse arquivo ao abrir)
```

- O backend expõe `GET /vitrine/` e `GET /vitrine/fotos/{id}`
  (`backend/app/api/v1/vitrine.py`), sem login e só com produto **ativo e publicado**.
  O schema `backend/app/schemas/vitrine.py` é a lista do que pode sair: nunca custo,
  margem, estoque exato ou fornecedor. O estoque vira só `disponivel`, `esgotado` ou `consulte` (kit).
- O PC da loja **não fica exposto na internet**: o script de exportação roda na loja
  e só *envia* o snapshot. O site mostra a data e a hora do snapshot e pede
  confirmação pelo WhatsApp, então nunca finge ter preço "em tempo real".
- Cache: o catálogo é revalidado a cada visita (`no-cache` + ETag do host), e as
  fotos têm id imutável (trocar a foto gera um id novo).

## Rodar em desenvolvimento

```bash
npm install
cp .env.example .env.local          # ajuste as variáveis
npm run dev                          # http://localhost:3000
```

Fontes de dados para `NEXT_PUBLIC_VITRINE_DADOS`:

| Valor | Uso |
|---|---|
| `/demo/vitrine.json` | dados **fictícios** de demonstração (aparece uma faixa avisando) |
| `/dados/vitrine.json` | snapshot gerado pelo script (é o mesmo esquema da produção) |
| `http://127.0.0.1:8000/vitrine/` | backend direto; precisa de `VITRINE_ORIGENS=http://localhost:3000` no `.env` do backend |

Gerar o snapshot a partir do backend local:

```bash
python scripts/exportar_vitrine.py --api https://127.0.0.1:8000
```

## Configuração (`.env.local`)

`NEXT_PUBLIC_WHATSAPP` (DDI + DDD + número, só dígitos), `NEXT_PUBLIC_INSTAGRAM`,
`NEXT_PUBLIC_HORARIO`, `NEXT_PUBLIC_LOJAS` (`Matriz: endereço|Filial: endereço`), `NEXT_PUBLIC_AVISOS` (separados por `|`) e `NEXT_PUBLIC_SITE_URL`.
Os dados reais da loja ficam em `.env` (versionado, só informação pública); `.env.local` sobrepõe em dev.
A logo fica em `public/marca/` (recortada da arte da loja, versões verde e branca). Sem WhatsApp configurado, os botões não aparecem. **Nada secreto vai aqui:** tudo é público.

## Publicar no GitHub Pages

O site fica num repositório público só dele, `anndreluizz/3la-variedades`
(https://anndreluizz.github.io/3la-variedades/), separado do Vertex para as
atualizações de preço não encherem o histórico do ERP. O build de produção usa
`.env.production` (subpasta `/3la-variedades` e endereço público).

No PC da loja, com o clone em `C:\servidor\vitrine-site`:

```bash
python scripts/publicar_vitrine.py --site    # código do site mudou: build + preços
python scripts/publicar_vitrine.py           # só preços e fotos (tarefa agendada)
```

O script lê o Vertex local (`https://127.0.0.1:58734`), grava `dados/` no clone
e faz commit e push **só se algum produto, preço ou foto mudou**. Se o Vertex
estiver desligado, ele para com erro e o site continua com o último envio.

## Na loja: o que o administrador faz

1. Cadastra o produto no Vertex com preço, categoria e fotos.
2. No card **Vitrine virtual**, marca **Mostrar na vitrine** (e **Destaque**, se quiser no banner).
3. Na próxima exportação o produto aparece no site. Desmarcar, ou inativar o produto, tira ele do site.

Seções automáticas: **Ofertas** (preço promocional dentro da validade), **Novidades**
(cadastrado há até 30 dias), **Mais vendidos** (90 dias, sem vendas canceladas; some se não houver vendas)
e **Destaques** (marcados no cadastro).
