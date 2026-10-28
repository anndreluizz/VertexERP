import { linkWhatsApp, Produto, real, ROTULO_DISPONIBILIDADE } from "@/lib/catalogo";
import { Tilt } from "./Efeitos";
import { Icone, iconeDaCategoria } from "./Icone";

export function Foto({ produto, indice = 0, prioridade = false }: { produto: Produto; indice?: number; prioridade?: boolean }) {
  const url = produto.fotos[indice];
  if (!url) {
    return (
      <div className="foto-vazia" aria-hidden="true">
        <Icone nome={iconeDaCategoria(produto.categoria || "")} tamanho={44} />
      </div>
    );
  }
  return (
    <img src={url} alt={produto.nome} loading={prioridade ? "eager" : "lazy"} decoding="async"
      fetchPriority={prioridade ? "high" : "auto"} width={600} height={600} />
  );
}

export function Selos({ produto }: { produto: Produto }) {
  const desconto = produto.preco_anterior
    ? Math.round((1 - produto.preco / produto.preco_anterior) * 100)
    : 0;
  return (
    <div className="selos">
      {desconto > 0 && <span className="selo selo-oferta">-{desconto}%</span>}
      {produto.novidade && <span className="selo selo-novo">Novidade</span>}
      {produto.disponibilidade === "esgotado" && <span className="selo selo-esgotado">Esgotado</span>}
      {produto.disponibilidade === "disponivel" && produto.max_pedido === 1 && (
        <span className="selo selo-ultima">Última unidade</span>
      )}
    </div>
  );
}

export function Preco({ produto }: { produto: Produto }) {
  return (
    <p className="preco">
      {produto.preco_anterior && (
        <s aria-label={`De ${real(produto.preco_anterior)}`}>{real(produto.preco_anterior)}</s>
      )}
      <strong>{real(produto.preco)}</strong>
      {produto.unidade !== "UN" && <small> / {produto.unidade}</small>}
    </p>
  );
}

// Card minimalista: foto domina, preco em vidro por cima, segunda foto
// (ou distorcao liquida) e "Ver detalhes" revelados no hover, tilt 3D.
export function CardProduto({ produto, abrir, indice = 0 }: {
  produto: Produto; abrir: (p: Produto) => void; indice?: number;
}) {
  const zap = linkWhatsApp(produto);
  const segunda = produto.fotos[1];
  return (
    <article className={`card${produto.disponibilidade === "esgotado" ? " card-esgotado" : ""}${segunda ? " card-2fotos" : ""}`}
      data-revelar style={{ "--i": indice % 4 } as React.CSSProperties}>
      <Tilt className="card-midia" forca={4}>
        <button type="button" className="card-abrir" onClick={() => abrir(produto)}
          aria-label={`Ver detalhes de ${produto.nome}`}>
          <span className="card-foto">
            <Foto produto={produto} />
            {segunda && <img className="card-foto-2" src={segunda} alt="" loading="lazy" decoding="async" width={600} height={600} />}
          </span>
          <Selos produto={produto} />
          <span className="card-vidro"><Preco produto={produto} /></span>
          <span className="card-revela">Ver detalhes <Icone nome="seta" tamanho={16} /></span>
        </button>
        {zap && (
          <a className="card-zap" href={zap} target="_blank" rel="noopener noreferrer"
            aria-label={`Consultar ${produto.nome} no WhatsApp`}>
            <Icone nome="conversa" tamanho={18} />
          </a>
        )}
      </Tilt>
      <div className="card-info">
        {produto.categoria && <span className="card-cat">{produto.categoria}</span>}
        <h3><button type="button" className="card-nome" onClick={() => abrir(produto)}>{produto.nome}</button></h3>
        <span className={`disp disp-${produto.disponibilidade}`}>
          {ROTULO_DISPONIBILIDADE[produto.disponibilidade]}
        </span>
      </div>
    </article>
  );
}
