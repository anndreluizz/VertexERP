import { BASE, config, NOME_PADRAO } from "@/lib/catalogo";
import { Icone } from "./Icone";

export const ATUALIZADO_EM = "28/10/2026";

export function PaginaLegal({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <>
      <header className="cabecalho">
        <div className="contido cabecalho-linha">
          <a href={`${BASE}/`} className="marca" aria-label={`${NOME_PADRAO}, início`}>
            <img src={`${BASE}/marca/nome-verde.png`} alt={NOME_PADRAO} width={80} height={48} />
          </a>
        </div>
      </header>
      <main className="contido legal">
        <article className="legal-texto">
          <a className="legal-voltar" href={`${BASE}/`}><Icone nome="seta" tamanho={16} /> Voltar para a vitrine</a>
          <h1>{titulo}</h1>
          <p className="legal-data">Atualizado em {ATUALIZADO_EM}</p>
          {children}
        </article>
      </main>
      <footer className="rodape">
        <div className="contido rodape-fim">
          <p>© {new Date().getFullYear()} {NOME_PADRAO}</p>
          <nav aria-label="Informações legais">
            <a href={`${BASE}/privacidade/`}>Política de Privacidade</a>
            <a href={`${BASE}/termos/`}>Termos e Condições</a>
          </nav>
        </div>
      </footer>
    </>
  );
}

/** Como falar com a loja, com os dados configurados no .env. */
export function ContatoLoja() {
  const telefone = config.whatsapp.replace(/^55(\d{2})(\d{4,5})(\d{4})$/, "($1) $2-$3");
  return (
    <ul>
      {config.whatsapp && <li>WhatsApp: {telefone}</li>}
      {config.endereco && <li>Endereço: {config.endereco}</li>}
      {config.horario && <li>Atendimento: {config.horario}</li>}
    </ul>
  );
}
