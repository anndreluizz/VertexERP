"use client";

import { useEffect, useRef, useState } from "react";
import { linkWhatsApp, Produto, ROTULO_DISPONIBILIDADE } from "@/lib/catalogo";
import { Foto, Preco, Selos } from "./CardProduto";
import { Icone } from "./Icone";

const TEXTO_DISPONIBILIDADE = {
  disponivel: "Tem na loja segundo o último envio do sistema. Confirme pelo WhatsApp antes de sair de casa.",
  esgotado: "Acabou por enquanto. Chame no WhatsApp para saber quando chega de novo.",
  consulte: "Disponibilidade sob consulta pelo WhatsApp.",
};

// <dialog> nativo: Esc fecha, foco fica preso dentro, fundo inerte.
export function DetalheProduto({ produto, atualizadoEm, fechar, porNaSacola, naSacola }: {
  produto: Produto | null; atualizadoEm: string; fechar: () => void;
  porNaSacola: (p: Produto) => void; naSacola: number;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [foto, setFoto] = useState(0);

  useEffect(() => {
    setFoto(0);
    const dialogo = ref.current;
    if (!dialogo) return;
    if (produto && !dialogo.open) dialogo.showModal();
    if (!produto && dialogo.open) dialogo.close();
  }, [produto]);

  const zap = produto ? linkWhatsApp(produto) : null;

  return (
    <dialog ref={ref} className="detalhe" onClose={fechar}
      onClick={(e) => e.target === ref.current && fechar()} aria-labelledby="detalhe-nome">
      {produto && (
        <div className="detalhe-corpo">
          <button type="button" className="detalhe-fechar" onClick={fechar} aria-label="Fechar">
            <Icone nome="fechar" />
          </button>
          <div className="detalhe-galeria">
            <div className="detalhe-foto">
              <Foto produto={produto} indice={foto} prioridade />
              <Selos produto={produto} />
            </div>
            {produto.fotos.length > 1 && (
              <div className="miniaturas" role="group" aria-label="Fotos do produto">
                {produto.fotos.map((url, i) => (
                  <button key={url} type="button" aria-label={`Foto ${i + 1}`} aria-pressed={i === foto}
                    onClick={() => setFoto(i)}>
                    <img src={url} alt="" loading="lazy" width={72} height={72} />
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="detalhe-info">
            {produto.categoria && <span className="card-cat">{produto.categoria}</span>}
            <h2 id="detalhe-nome">{produto.nome}</h2>
            <p className="detalhe-cod">Cód. {produto.codigo}{produto.marca ? ` · ${produto.marca}` : ""}</p>
            <Preco produto={produto} />
            {produto.promocao_fim && (
              <p className="detalhe-promo">
                Oferta válida até {new Date(produto.promocao_fim + "T12:00").toLocaleDateString("pt-BR")}
              </p>
            )}
            {(produto.cor || produto.tamanho) && (
              <dl className="detalhe-atributos">
                {produto.cor && <><dt>Cor</dt><dd>{produto.cor}</dd></>}
                {produto.tamanho && <><dt>Tamanho</dt><dd>{produto.tamanho}</dd></>}
              </dl>
            )}
            {produto.descricao && <p className="detalhe-desc">{produto.descricao}</p>}
            <div className={`detalhe-disp disp-${produto.disponibilidade}`}>
              <strong>{ROTULO_DISPONIBILIDADE[produto.disponibilidade]}</strong>
              <span>{TEXTO_DISPONIBILIDADE[produto.disponibilidade]}</span>
            </div>
            {produto.disponibilidade !== "esgotado" && (
              <button type="button" className="botao botao-verde botao-largo" onClick={() => porNaSacola(produto)}>
                <Icone nome="sacola" /> {naSacola ? `Na sacola (${naSacola}) · pôr mais um` : "Pôr na sacola"}
              </button>
            )}
            {zap ? (
              <a className="botao botao-zap" href={zap} target="_blank" rel="noopener noreferrer">
                <Icone nome="conversa" /> Consultar pelo WhatsApp
              </a>
            ) : (
              <p className="aviso-config">WhatsApp da loja ainda não configurado.</p>
            )}
            <p className="detalhe-atualizado">Preço e estoque do sistema da loja em {atualizadoEm}.</p>
          </div>
        </div>
      )}
    </dialog>
  );
}
