"use client";

import { useEffect, useRef } from "react";
import { limitePedido, linkPedido, Produto, real } from "@/lib/catalogo";
import { Foto } from "./CardProduto";
import { Icone } from "./Icone";

export type ItemSacola = { slug: string; qtd: number };

// Sacola: guarda so' slug+quantidade no navegador do cliente; preco e
// nome vem sempre do catalogo atual (produto que saiu do site some daqui).
// Nao reserva nada: o pedido vai pelo WhatsApp e a loja confirma.
export function Sacola({ aberta, itens, produtos, mudar, fechar }: {
  aberta: boolean;
  itens: ItemSacola[];
  produtos: Produto[];
  mudar: (slug: string, qtd: number) => void;
  fechar: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialogo = ref.current;
    if (!dialogo) return;
    if (aberta && !dialogo.open) dialogo.showModal();
    if (!aberta && dialogo.open) dialogo.close();
  }, [aberta]);

  const porSlug = new Map(produtos.map((p) => [p.slug, p]));
  const linhas = itens
    .map((i) => ({ ...i, produto: porSlug.get(i.slug) }))
    .filter((l): l is ItemSacola & { produto: Produto } => !!l.produto);
  const total = linhas.reduce((s, l) => s + l.produto.preco * l.qtd, 0);
  const pedido = linkPedido(linhas.map((l) => ({ produto: l.produto, qtd: l.qtd })));

  return (
    <dialog ref={ref} className="sacola" onClose={fechar}
      onClick={(e) => e.target === ref.current && fechar()} aria-labelledby="sacola-titulo">
      <div className="sacola-corpo">
        <div className="sacola-topo">
          <h2 id="sacola-titulo">Sua sacola</h2>
          <button type="button" className="icone-botao" onClick={fechar} aria-label="Fechar">
            <Icone nome="fechar" />
          </button>
        </div>

        {linhas.length === 0 ? (
          <p className="sacola-vazia">Sua sacola está vazia. Abra um produto e toque em &quot;Pôr na sacola&quot;.</p>
        ) : (
          <>
            <ul className="sacola-lista">
              {linhas.map(({ produto, qtd }) => (
                <li key={produto.slug}>
                  <span className="sacola-foto"><Foto produto={produto} /></span>
                  <span className="sacola-info">
                    <strong>{produto.nome}</strong>
                    <small>Cód. {produto.codigo} · {real(produto.preco)}</small>
                    {produto.disponibilidade === "esgotado" && <small className="sacola-esgotado">Esgotado</small>}
                    {qtd > limitePedido(produto) && produto.disponibilidade !== "esgotado" && (
                      <small className="sacola-esgotado">Só {limitePedido(produto)} disponível(is)</small>
                    )}
                  </span>
                  <span className="sacola-qtd">
                    <button type="button" aria-label={`Tirar um ${produto.nome}`} onClick={() => mudar(produto.slug, qtd - 1)}>
                      <Icone nome="menos" tamanho={16} />
                    </button>
                    <span aria-live="polite">{qtd}</span>
                    <button type="button" aria-label={`Pôr mais um ${produto.nome}`} onClick={() => mudar(produto.slug, qtd + 1)}
                      disabled={qtd >= limitePedido(produto)}>
                      <Icone nome="mais" tamanho={16} />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
            <p className="sacola-total"><span>Total</span><strong>{real(total)}</strong></p>
            <p className="sacola-nota">
              O pedido vai pelo WhatsApp e só fica garantido depois que a loja confirmar.
              Entrega grátis em Tonantins.
            </p>
            {pedido ? (
              <a className="botao botao-zap" href={pedido} target="_blank" rel="noopener noreferrer">
                <Icone nome="conversa" /> Enviar pedido pelo WhatsApp
              </a>
            ) : (
              <p className="aviso-config">WhatsApp da loja ainda não configurado.</p>
            )}
          </>
        )}
      </div>
    </dialog>
  );
}
