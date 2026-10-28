"use client";

import { useEffect, useRef } from "react";

// Efeitos visuais sem biblioteca. Todos desligam com
// prefers-reduced-motion (ver globals.css) e nenhum esconde conteudo
// se o JS falhar: [data-revelar] so' some depois que <html> ganha .anima.

/** Revela [data-revelar] ao entrar na tela. `chave` muda = procura novos. */
export function useRevelar(chave: unknown) {
  useEffect(() => {
    document.documentElement.classList.add("anima");
    const pendentes = document.querySelectorAll("[data-revelar]:not(.visivel)");
    if (!("IntersectionObserver" in window)) {
      pendentes.forEach((el) => el.classList.add("visivel"));
      return;
    }
    const observador = new IntersectionObserver(
      (entradas) => entradas.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("visivel");
          observador.unobserve(e.target);
        }
      }),
      { rootMargin: "0px 0px -8% 0px", threshold: 0.1 },
    );
    pendentes.forEach((el) => observador.observe(el));
    return () => observador.disconnect();
  }, [chave]);
}

/** --rolagem (px) no <html>, atualizado 1x por quadro: parallax via CSS. */
export function useRolagem() {
  useEffect(() => {
    let quadro = 0;
    const atualizar = () => {
      quadro = 0;
      document.documentElement.style.setProperty("--rolagem", String(Math.round(window.scrollY)));
    };
    const aoRolar = () => { if (!quadro) quadro = requestAnimationFrame(atualizar); };
    atualizar();
    window.addEventListener("scroll", aoRolar, { passive: true });
    return () => { window.removeEventListener("scroll", aoRolar); cancelAnimationFrame(quadro); };
  }, []);
}

/** Inclina o conteudo em 3D seguindo o mouse (so' mouse; toque nao). */
export function Tilt({ children, className = "", forca = 10 }: {
  children: React.ReactNode; className?: string; forca?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mover = (e: React.PointerEvent) => {
    const el = ref.current;
    if (!el || e.pointerType !== "mouse") return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const y = (e.clientY - r.top) / r.height;
    el.style.setProperty("--rx", `${(0.5 - y) * forca}deg`);
    el.style.setProperty("--ry", `${(x - 0.5) * forca}deg`);
    el.style.setProperty("--mx", `${x * 100}%`);
    el.style.setProperty("--my", `${y * 100}%`);
  };
  const sair = () => {
    ref.current?.style.setProperty("--rx", "0deg");
    ref.current?.style.setProperty("--ry", "0deg");
  };
  return (
    <div ref={ref} className={`tilt ${className}`} onPointerMove={mover} onPointerLeave={sair}>
      {children}
    </div>
  );
}

/** Filtro SVG de distorcao "liquida", usado no hover das fotos (url(#liquido)). */
export function FiltroLiquido() {
  return (
    <svg width="0" height="0" aria-hidden="true" focusable="false" style={{ position: "absolute" }}>
      <filter id="liquido" x="-10%" y="-10%" width="120%" height="120%">
        <feTurbulence type="fractalNoise" baseFrequency="0.010 0.018" numOctaves={2} seed={4} result="ruido">
          <animate attributeName="baseFrequency" dur="7s" repeatCount="indefinite"
            values="0.010 0.018;0.018 0.010;0.010 0.018" />
        </feTurbulence>
        <feDisplacementMap in="SourceGraphic" in2="ruido" scale={18} xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </svg>
  );
}

/** Quadro que cresce de um cartao arredondado ate' a tela inteira
 *  enquanto a secao rola (--p de 0 a 1, posicao sticky). Com video da
 *  loja, mostra o video; sem, um painel verde liso com os enderecos. */
export function VideoExpansivo({ video, titulo, lojas, horario }: {
  video: string; titulo: string; lojas: { nome: string; endereco: string }[]; horario: string;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    let quadro = 0;
    const calcular = () => {
      quadro = 0;
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const percurso = Math.max(1, r.height - window.innerHeight);
      el.style.setProperty("--p", Math.min(1, Math.max(0, -r.top / percurso)).toFixed(3));
    };
    const pedir = () => { if (!quadro) quadro = requestAnimationFrame(calcular); };
    calcular();
    window.addEventListener("scroll", pedir, { passive: true });
    window.addEventListener("resize", pedir);
    return () => {
      window.removeEventListener("scroll", pedir);
      window.removeEventListener("resize", pedir);
      cancelAnimationFrame(quadro);
    };
  }, []);

  return (
    <section ref={ref} className={`expansivo${video ? "" : " expansivo-sem-video"}`} aria-label={titulo}>
      <div className="expansivo-fixo">
        <div className="expansivo-moldura">
          {video && <video src={video} autoPlay muted loop playsInline preload="metadata" />}
          <div className="expansivo-texto">
            <h2>{titulo}</h2>
            {lojas.length > 0 && (
              <ul className="expansivo-lojas">
                {lojas.map((l) => (
                  <li key={l.endereco}>{l.nome && <strong>{l.nome}</strong>}{l.endereco}</li>
                ))}
              </ul>
            )}
            {horario && <p>{horario}</p>}
          </div>
        </div>
      </div>
    </section>
  );
}
