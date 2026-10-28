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
  endereco: process.env.NEXT_PUBLIC_ENDERECO || "",
  // video da loja (mp4 leve, em public/) na secao que expande; vazio = foto de destaque
  video: process.env.NEXT_PUBLIC_VIDEO ? noSite(process.env.NEXT_PUBLIC_VIDEO) : "",
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

export function linkWhatsApp(produto?: Produto): string | null {
  if (!config.whatsapp) return null;
  const texto = produto
    ? produto.disponibilidade === "esgotado"
      ? `Olá! Vi na vitrine o produto ${produto.nome} (cód. ${produto.codigo}). Vai chegar de novo?`
      : `Olá! Vi na vitrine o produto ${produto.nome} (cód. ${produto.codigo}). Ainda está disponível?`
    : "Olá! Vim pela vitrine da loja.";
  return `https://wa.me/${config.whatsapp}?text=${encodeURIComponent(texto)}`;
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
