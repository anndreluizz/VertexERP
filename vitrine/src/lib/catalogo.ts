// Formato de GET /vitrine/ do Vertex (backend/app/schemas/vitrine.py) --
// o snapshot gerado por scripts/exportar_vitrine.py tem o mesmo formato.

export type Disponibilidade = "disponivel" | "esgotado" | "consulte";

export interface Produto {
  id: number;
  slug: string;
  codigo: string;
  nome: string;
  descricao: string | null;
  categoria: string | null;
  marca: string | null;
  cor: string | null;
  tamanho: string | null;
  unidade: string;
  preco: number;
  preco_anterior: number | null;
  promocao_fim: string | null;
  disponibilidade: Disponibilidade;
  destaque: boolean;
  novidade: boolean;
  fotos: string[];
}

export interface Catalogo {
  gerado_em: string;
  demo?: boolean;
  loja: { nome: string | null; endereco: string | null };
  categorias: { nome: string; quantidade: number }[];
  mais_vendidos: number[];
  produtos: Produto[];
}

// subpasta do site (GitHub Pages de projeto: /3la-variedades); vazio em dominio proprio
export const BASE = process.env.NEXT_PUBLIC_BASE_PATH || "";
const noSite = (c: string) => (c.startsWith("/") ? BASE + c : c);

export const config = {
  dados: noSite(process.env.NEXT_PUBLIC_VITRINE_DADOS || "/demo/vitrine.json"),
  whatsapp: (process.env.NEXT_PUBLIC_WHATSAPP || "").replace(/\D/g, ""),
  instagram: (process.env.NEXT_PUBLIC_INSTAGRAM || "").replace(/^@/, ""),
  horario: process.env.NEXT_PUBLIC_HORARIO || "",
  // "Matriz: Rua X, Bairro, Cidade|Filial: Rua Y, ..." (nome antes dos dois-pontos)
  lojas: (process.env.NEXT_PUBLIC_LOJAS || "").split("|").map((l) => l.trim()).filter(Boolean).map((l) => {
    const [nome, ...resto] = l.split(":");
    return resto.length ? { nome: nome.trim(), endereco: resto.join(":").trim() } : { nome: "", endereco: l };
  }),
  avisos: (process.env.NEXT_PUBLIC_AVISOS || "").split("|").map((a) => a.trim()).filter(Boolean),
};

export const NOME_PADRAO = "3.L.A Variedades";

export async function carregarCatalogo(): Promise<Catalogo> {
  // no-cache = revalida sempre (ETag/304): preco mudou no ERP, aparece
  // na proxima visita, sem servir copia velha como se fosse atual.
  const resposta = await fetch(config.dados, { cache: "no-cache" });
  if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
  const catalogo: Catalogo = await resposta.json();
  const base = new URL(config.dados, window.location.href);
  const absoluta = (u: string) => new URL(u, base).href;
  catalogo.produtos.forEach((p) => (p.fotos = p.fotos.map(absoluta)));
  return catalogo;
}

const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
export const real = (v: number) => moeda.format(v);

export const semAcento = (t: string) =>
  t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// pagina de cada produto (p/<slug>/, gerada por scripts/publicar_vitrine.py)
// so' com as tags de previa: o WhatsApp mostra a foto do produto na conversa
const SITE = (process.env.NEXT_PUBLIC_SITE_URL || "").replace(/\/$/, "");
export const linkProduto = (p: Produto) => (SITE ? `${SITE}/p/${p.slug}/` : "");

const zap = (texto: string) => `https://wa.me/${config.whatsapp}?text=${encodeURIComponent(texto)}`;

export function linkWhatsApp(produto?: Produto): string | null {
  if (!config.whatsapp) return null;
  if (!produto) return zap("Olá! Vim pela vitrine da loja.");
  const pergunta = produto.disponibilidade === "esgotado" ? "Vai chegar de novo?" : "Ainda está disponível?";
  return zap(
    `Olá! Vi na vitrine o produto ${produto.nome} (cód. ${produto.codigo}), ${real(produto.preco)}. ${pergunta}\n${linkProduto(produto)}`.trim(),
  );
}

export function linkPedido(itens: { produto: Produto; qtd: number }[]): string | null {
  if (!config.whatsapp || !itens.length) return null;
  const total = itens.reduce((s, i) => s + i.produto.preco * i.qtd, 0);
  const linhas = itens.map(
    ({ produto, qtd }) => `${qtd}x ${produto.nome} (cód. ${produto.codigo}): ${real(produto.preco * qtd)}\n${linkProduto(produto)}`.trim(),
  );
  return zap(
    `Olá! Quero fazer este pedido pela vitrine:\n\n${linhas.join("\n\n")}\n\nTotal: ${real(total)}\n\nAguardo a confirmação da loja.`,
  );
}

export function busca(produtos: Produto[], termo: string, categoria: string | null): Produto[] {
  const q = semAcento(termo.trim());
  return produtos.filter(
    (p) =>
      (!categoria || p.categoria === categoria) &&
      (!q ||
        semAcento([p.nome, p.descricao, p.categoria, p.marca, p.codigo].filter(Boolean).join(" ")).includes(q)),
  );
}

export const ROTULO_DISPONIBILIDADE: Record<Disponibilidade, string> = {
  disponivel: "Disponível",
  esgotado: "Esgotado",
  consulte: "Consulte",
};
