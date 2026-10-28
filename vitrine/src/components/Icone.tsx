import { semAcento } from "@/lib/catalogo";

// Tracos no estilo Lucide (mesma familia de icones do Vertex desktop).
const TRACOS = {
  busca: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  fechar: <path d="M18 6 6 18M6 6l12 12" />,
  conversa: <><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z" /><path d="M9 10h.01M12 10h.01M15 10h.01" /></>,
  instagram: <><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" /><path d="M17.5 6.5h.01" /></>,
  relogio: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  local: <><path d="M19 10c0 5-7 11-7 11s-7-6-7-11a7 7 0 0 1 14 0" /><circle cx="12" cy="10" r="2.5" /></>,
  seta: <path d="M5 12h14M13 6l6 6-6 6" />,
  etiqueta: <><path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z" /><path d="M7.5 7.5h.01" /></>,
  roupa: <path d="M20.4 3.5 16 2a4 4 0 0 1-8 0L3.6 3.5a2 2 0 0 0-1.3 2.2l.6 3.5a1 1 0 0 0 1 .8H6v10a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V10h2.2a1 1 0 0 0 1-.8l.6-3.5a2 2 0 0 0-1.3-2.2z" />,
  calcado: <><path d="M3 15c0-4 1-8 3.5-8L10 9.5l3.5-.5c4 0 7.5 2.5 7.5 6v2H3z" /><path d="M3 19h18" /></>,
  perfume: <><rect x="6" y="9" width="12" height="12" rx="3" /><path d="M10 9V6h4v3M12 3v3M9 14h6" /></>,
  maquiagem: <path d="M12 3l1.8 5.4L19.5 10l-5.7 1.6L12 17l-1.8-5.4L4.5 10l5.7-1.6zM19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" />,
  mochila: <><path d="M5 10a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v10a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1z" /><path d="M9 6V4.5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 4.5V6M8.5 14h7v4h-7z" /></>,
  brinquedo: <><rect x="3" y="13" width="8" height="8" rx="1.5" /><rect x="13" y="13" width="8" height="8" rx="1.5" /><rect x="8" y="3" width="8" height="8" rx="1.5" /></>,
  variedades: <><rect x="3" y="3" width="7.5" height="7.5" rx="1.5" /><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" /><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" /><circle cx="17.25" cy="17.25" r="3.75" /></>,
};

export type NomeIcone = keyof typeof TRACOS;

export function Icone({ nome, tamanho = 20 }: { nome: NomeIcone; tamanho?: number }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {TRACOS[nome]}
    </svg>
  );
}

const PALAVRAS: [RegExp, NomeIcone][] = [
  [/roupa|vestido|blusa|moda|infantil|lingerie|camis|calca/, "roupa"],
  [/calcad|sapato|tenis|sandalia|chinelo/, "calcado"],
  [/perfum|colonia|natura|fragranc/, "perfume"],
  [/maqui|batom|beleza|cosmet/, "maquiagem"],
  [/mochila|bolsa/, "mochila"],
  [/brinq/, "brinquedo"],
];

export function iconeDaCategoria(nome: string): NomeIcone {
  const n = semAcento(nome);
  return PALAVRAS.find(([re]) => re.test(n))?.[1] ?? "variedades";
}
