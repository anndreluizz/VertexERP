"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BASE, busca, carregarCatalogo, Catalogo, config, linkWhatsApp, NOME_PADRAO, Produto,
} from "@/lib/catalogo";
import { CardProduto, Foto } from "./CardProduto";
import { DetalheProduto } from "./DetalheProduto";
import { FiltroLiquido, Tilt, useRevelar, useRolagem, VideoExpansivo } from "./Efeitos";
import { Icone, iconeDaCategoria } from "./Icone";

type Estado = { tipo: "carregando" } | { tipo: "erro" } | { tipo: "ok"; catalogo: Catalogo };

// Filtros e produto aberto vivem na URL (?categoria=&busca=&produto=),
// pra dar pra mandar o link de um produto no WhatsApp/Instagram.
function lerUrl() {
  const q = new URLSearchParams(window.location.search);
  return { categoria: q.get("categoria"), termo: q.get("busca") || "", produto: q.get("produto") };
}

function gravarUrl(valores: { categoria: string | null; termo: string; produto: string | null }, empilhar = false) {
  const q = new URLSearchParams();
  if (valores.categoria) q.set("categoria", valores.categoria);
  if (valores.termo) q.set("busca", valores.termo);
  if (valores.produto) q.set("produto", valores.produto);
  const url = `${window.location.pathname}${q.size ? `?${q}` : ""}${window.location.hash}`;
  if (empilhar) window.history.pushState(null, "", url);
  else window.history.replaceState(null, "", url);
}

const formatarData = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

const formatarTelefone = (d: string) =>
  d.replace(/^55(\d{2})(\d{4,5})(\d{4})$/, "($1) $2-$3");

export function Vitrine() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [categoria, setCategoria] = useState<string | null>(null);
  const [termo, setTermo] = useState("");
  const [slugAberto, setSlugAberto] = useState<string | null>(null);
  const [menuAberto, setMenuAberto] = useState(false);

  const carregar = useCallback(() => {
    setEstado({ tipo: "carregando" });
    carregarCatalogo()
      .then((catalogo) => setEstado({ tipo: "ok", catalogo }))
      .catch(() => setEstado({ tipo: "erro" }));
  }, []);

  useEffect(() => {
    const sincronizar = () => {
      const u = lerUrl();
      setCategoria(u.categoria);
      setTermo(u.termo);
      setSlugAberto(u.produto);
    };
    sincronizar();
    carregar();
    window.addEventListener("popstate", sincronizar);
    return () => window.removeEventListener("popstate", sincronizar);
  }, [carregar]);

  const catalogo = estado.tipo === "ok" ? estado.catalogo : null;
  const produtos = catalogo?.produtos ?? [];
  const nomeLoja = catalogo?.loja.nome || NOME_PADRAO;
  const atualizadoEm = catalogo ? formatarData(catalogo.gerado_em) : "";

  const resultado = useMemo(() => busca(produtos, termo, categoria), [produtos, termo, categoria]);
  const aberto = produtos.find((p) => p.slug === slugAberto) ?? null;

  const prateleiras = useMemo(() => {
    const porId = new Map(produtos.map((p) => [p.id, p]));
    return [
      { id: "destaques", titulo: "Destaques", itens: produtos.filter((p) => p.destaque) },
      { id: "ofertas", titulo: "Ofertas", itens: produtos.filter((p) => p.preco_anterior) },
      { id: "novidades", titulo: "Novidades", itens: produtos.filter((p) => p.novidade) },
      {
        id: "mais-vendidos", titulo: "Mais vendidos",
        itens: (catalogo?.mais_vendidos ?? []).map((id) => porId.get(id)).filter((p): p is Produto => !!p),
      },
    ].filter((s) => s.itens.length > 0);
  }, [produtos, catalogo]);

  const vitrineHero = useMemo(() => {
    const comFoto = produtos.filter((p) => p.fotos.length && p.disponibilidade !== "esgotado");
    const destaques = comFoto.filter((p) => p.destaque);
    return (destaques.length >= 3 ? destaques : [...destaques, ...comFoto.filter((p) => !p.destaque)]).slice(0, 3);
  }, [produtos]);

  const filtrar = (cat: string | null, novoTermo = termo) => {
    setCategoria(cat);
    setTermo(novoTermo);
    gravarUrl({ categoria: cat, termo: novoTermo, produto: null });
    setMenuAberto(false);
    document.getElementById("catalogo")?.scrollIntoView({ behavior: "smooth" });
  };

  const abrir = (p: Produto) => {
    setSlugAberto(p.slug);
    gravarUrl({ categoria, termo, produto: p.slug }, true);
  };

  const fechar = () => {
    if (!slugAberto) return;
    setSlugAberto(null);
    gravarUrl({ categoria, termo, produto: null });
  };

  useRolagem();
  useRevelar(`${estado.tipo}|${categoria}|${termo}|${resultado.length}`);

  const zapLoja = linkWhatsApp();
  const endereco = config.endereco || catalogo?.loja.endereco;

  return (
    <>
      <a className="pular" href="#catalogo">Pular para os produtos</a>
      <BarraAvisos />

      <header className="cabecalho">
        <div className="contido cabecalho-linha">
          <a href="./" className="marca" aria-label={`${nomeLoja}, início`}>
            <img src={`${BASE}/marca/nome-verde.png`} alt={nomeLoja} width={80} height={48} />

          </a>

          <form className="busca" role="search" onSubmit={(e) => { e.preventDefault(); filtrar(categoria); }}>
            <Icone nome="busca" tamanho={18} />
            <input id="busca" type="search" placeholder="O que você procura?" aria-label="Buscar produtos"
              value={termo} onChange={(e) => {
                setTermo(e.target.value);
                gravarUrl({ categoria, termo: e.target.value, produto: null });
              }} />
          </form>

          <div className="cabecalho-acoes">
            {zapLoja && (
              <a className="icone-botao icone-zap" href={zapLoja} target="_blank" rel="noopener noreferrer"
                aria-label="Falar no WhatsApp">
                <Icone nome="conversa" />
              </a>
            )}
            <button type="button" className="icone-botao menu-botao" aria-expanded={menuAberto}
              aria-controls="menu" aria-label={menuAberto ? "Fechar menu" : "Abrir menu"}
              onClick={() => setMenuAberto(!menuAberto)}>
              <Icone nome={menuAberto ? "fechar" : "menu"} />
            </button>
          </div>
        </div>
        <nav id="menu" className={`menu${menuAberto ? " menu-aberto" : ""}`} aria-label="Seções da loja">
          <div className="contido menu-linha">
            <a href="#categorias" onClick={() => setMenuAberto(false)}>Categorias</a>
            {prateleiras.map((s) => (
              <a key={s.id} href={`#${s.id}`} onClick={() => setMenuAberto(false)}>{s.titulo}</a>
            ))}
            <a href="#catalogo" onClick={() => setMenuAberto(false)}>Todos os produtos</a>
            <a href="#contato" onClick={() => setMenuAberto(false)}>Contato</a>
          </div>
        </nav>
      </header>

      {catalogo?.demo && (
        <p className="faixa-demo" role="note">Dados de demonstração. Estes não são produtos reais da loja.</p>
      )}

      <main>
        <section className="hero">
          <div className="contido hero-grade">
            <div className="hero-texto">
              <span className="sobretitulo">{endereco || "Tonantins, Amazonas"}</span>
              <h1>Roupas, calçados, perfumes e brinquedos da {nomeLoja}</h1>
              <p>
                Veja o preço e se tem na loja. Para comprar, chame no WhatsApp
                {config.whatsapp ? ` ${formatarTelefone(config.whatsapp)}` : ""} com o código do produto.
                {config.horario ? ` Atendimento: ${config.horario.charAt(0).toLowerCase()}${config.horario.slice(1)}.` : ""}
              </p>
              <a className="botao botao-destaque" href="#catalogo">Ver produtos <Icone nome="seta" tamanho={18} /></a>
            </div>
            <div className="hero-colagem" aria-hidden={vitrineHero.length === 0}>
              {vitrineHero.length > 0
                ? vitrineHero.map((p, i) => (
                  <div key={p.id} className={`colagem-camada colagem-${i}`}>
                    <Tilt className="colagem-item" forca={6}>
                      <button type="button" onClick={() => abrir(p)} aria-label={`Ver ${p.nome}`}>
                        <Foto produto={p} prioridade={i === 0} />
                      </button>
                    </Tilt>
                  </div>
                ))
                : (["roupa", "perfume", "calcado"] as const).map((n, i) => (
                  <div key={n} className={`colagem-camada colagem-${i}`}>
                    <div className="colagem-item colagem-vazia"><Icone nome={n} tamanho={56} /></div>
                  </div>
                ))}
            </div>
          </div>
        </section>

        <VideoExpansivo
          video={config.video}
          foto={vitrineHero[0]?.fotos[0] ?? null}
          titulo={`Venha conhecer a ${nomeLoja}`}
          texto={[endereco, config.horario].filter(Boolean).join(" · ") || "Atendimento e pedidos pelo WhatsApp"}
        />

        {estado.tipo === "carregando" && <Esqueleto />}

        {estado.tipo === "erro" && (
          <section className="contido estado-msg" role="alert">
            <h2>Não conseguimos carregar os produtos</h2>
            <p>Verifique sua internet e tente de novo. Se continuar, chame a loja no WhatsApp.</p>
            <button type="button" className="botao botao-verde" onClick={carregar}>Tentar de novo</button>
          </section>
        )}

        {catalogo && (
          <>
            {catalogo.categorias.length > 0 && (
              <section id="categorias" className="contido secao">
                <h2 className="titulo-secao" data-revelar>Categorias</h2>
                <div className="categorias">
                  {catalogo.categorias.map((c, i) => (
                    <button key={c.nome} type="button" className="categoria" onClick={() => filtrar(c.nome, "")}
                      data-revelar style={{ "--i": i % 6 } as React.CSSProperties}>
                      <span className="categoria-icone"><Icone nome={iconeDaCategoria(c.nome)} tamanho={28} /></span>
                      <span className="categoria-nome">{c.nome}</span>
                      <span className="categoria-qtd">{c.quantidade} {c.quantidade === 1 ? "produto" : "produtos"}</span>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {prateleiras.map((s) => (
              <section key={s.id} id={s.id} className="contido secao">
                <h2 className="titulo-secao" data-revelar>{s.titulo}</h2>
                <div className="prateleira">
                  {s.itens.slice(0, 8).map((p, i) => <CardProduto key={p.id} produto={p} abrir={abrir} indice={i} />)}
                </div>
              </section>
            ))}

            <section id="catalogo" className="contido secao">
              <div className="catalogo-topo">
                <h2 className="titulo-secao">{categoria ?? "Todos os produtos"}</h2>
                <p className="atualizado">
                  Preços e estoque enviados pelo sistema da loja em {atualizadoEm}. Confirme pelo WhatsApp.
                </p>
              </div>
              <div className="chips" role="group" aria-label="Filtrar por categoria">
                <button type="button" className="chip" aria-pressed={!categoria} onClick={() => filtrar(null)}>Tudo</button>
                {catalogo.categorias.map((c) => (
                  <button key={c.nome} type="button" className="chip" aria-pressed={categoria === c.nome}
                    onClick={() => filtrar(c.nome)}>{c.nome}</button>
                ))}
              </div>
              {termo && <p className="resultado-busca" aria-live="polite">{resultado.length} resultado(s) para “{termo}”</p>}
              {resultado.length > 0 ? (
                <div className="grade">
                  {resultado.map((p, i) => <CardProduto key={p.id} produto={p} abrir={abrir} indice={i} />)}
                </div>
              ) : (
                <div className="estado-msg">
                  <h3>{produtos.length ? "Nada encontrado por aqui" : "A vitrine está sendo montada"}</h3>
                  <p>
                    {produtos.length
                      ? "Tente outra palavra ou categoria. Se não achar, chame no WhatsApp que a gente procura pra você."
                      : "Em breve os produtos aparecem aqui. Enquanto isso, chame a loja no WhatsApp."}
                  </p>
                  {(termo || categoria) && (
                    <button type="button" className="botao botao-verde" onClick={() => filtrar(null, "")}>Ver todos os produtos</button>
                  )}
                </div>
              )}
            </section>
          </>
        )}
      </main>

      <footer id="contato" className="rodape">
        <div className="contido rodape-grade">
          <div>
            <img className="rodape-logo" src={`${BASE}/marca/logo-branca.png`} alt={nomeLoja} width={140} height={150} loading="lazy" />
            {endereco && <p className="rodape-linha"><Icone nome="local" tamanho={18} /> {endereco}</p>}
            {config.horario && <p className="rodape-linha"><Icone nome="relogio" tamanho={18} /> {config.horario}</p>}
          </div>
          <div hidden={!zapLoja && !config.instagram}>
            <h2>Fale com a gente</h2>
            {zapLoja && (
              <p className="rodape-linha">
                <Icone nome="conversa" tamanho={18} />
                <a href={zapLoja} target="_blank" rel="noopener noreferrer">WhatsApp {formatarTelefone(config.whatsapp)}</a>
              </p>
            )}
            {config.instagram && (
              <p className="rodape-linha">
                <Icone nome="instagram" tamanho={18} />
                <a href={`https://instagram.com/${config.instagram}`} target="_blank" rel="noopener noreferrer">@{config.instagram}</a>
              </p>
            )}
          </div>
          <div>
            <h2>Bom saber</h2>
            <p className="rodape-texto">
              Os preços e a disponibilidade vêm do sistema da loja e podem mudar ao longo do dia.
              O pedido é confirmado pelo WhatsApp, junto com pagamento, troca e entrega.
            </p>
          </div>
        </div>
        <div className="contido rodape-fim">
          <p>© {new Date().getFullYear()} {nomeLoja}</p>
          <nav aria-label="Informações legais">
            <a href={`${BASE}/privacidade/`}>Política de Privacidade</a>
            <a href={`${BASE}/termos/`}>Termos e Condições</a>
          </nav>
        </div>
      </footer>

      <FiltroLiquido />
      <DetalheProduto produto={aberto} atualizadoEm={atualizadoEm} fechar={fechar} />
    </>
  );
}

function BarraAvisos() {
  const avisos = config.avisos.length ? config.avisos : ["Atendimento e pedidos pelo WhatsApp"];
  const [i, setI] = useState(0);
  useEffect(() => {
    if (avisos.length < 2) return;
    const t = setInterval(() => setI((n) => (n + 1) % avisos.length), 5000);
    return () => clearInterval(t);
  }, [avisos.length]);
  return (
    <div className="barra-avisos">
      <p key={i} className="contido aviso"><Icone nome="etiqueta" tamanho={15} /> {avisos[i]}</p>
    </div>
  );
}

function Esqueleto() {
  return (
    <section className="contido secao" aria-busy="true" aria-label="Carregando produtos">
      <div className="esqueleto-titulo" />
      <div className="grade">
        {Array.from({ length: 8 }, (_, i) => <div key={i} className="esqueleto-card" />)}
      </div>
    </section>
  );
}
