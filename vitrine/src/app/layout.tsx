import type { Metadata, Viewport } from "next";
import { Cormorant_Garamond, Manrope } from "next/font/google";
import "./globals.css";

const titulo = Cormorant_Garamond({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--fonte-titulo" });
const texto = Manrope({ subsets: ["latin"], variable: "--fonte-texto" });

const descricao =
  "Roupas, calçados, perfumes, maquiagens, mochilas, brinquedos e variedades em Tonantins-AM. Veja os produtos e consulte pelo WhatsApp.";

export const metadata: Metadata = {
  metadataBase: process.env.NEXT_PUBLIC_SITE_URL ? new URL(process.env.NEXT_PUBLIC_SITE_URL) : undefined,
  title: "3.L.A Variedades | Vitrine virtual",
  description: descricao,
  openGraph: { title: "3.L.A Variedades", description: descricao, type: "website", locale: "pt_BR" },
};

export const viewport: Viewport = { themeColor: "#1f3b2d", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${titulo.variable} ${texto.variable}`}>
      <body>{children}</body>
    </html>
  );
}
