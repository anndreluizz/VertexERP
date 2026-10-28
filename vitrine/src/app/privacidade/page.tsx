import type { Metadata } from "next";
import { ContatoLoja, PaginaLegal } from "@/components/PaginaLegal";
import { NOME_PADRAO } from "@/lib/catalogo";

export const metadata: Metadata = {
  title: `Política de Privacidade | ${NOME_PADRAO}`,
  description: `Como a ${NOME_PADRAO} trata os seus dados pessoais.`,
};

export default function Privacidade() {
  return (
    <PaginaLegal titulo="Política de Privacidade">
      <p>
        Esta política explica quais dados pessoais a {NOME_PADRAO} trata quando você usa esta vitrine
        e quando compra com a gente, de acordo com a Lei Geral de Proteção de Dados (Lei 13.709/2018).
      </p>

      <h2>O que o site coleta</h2>
      <p>
        A vitrine não tem cadastro, login, formulário nem carrinho. Ela não usa cookies, não usa
        ferramentas de análise de visitas e não exibe anúncios. Você navega sem informar nenhum dado pessoal.
      </p>
      <p>
        A empresa que hospeda o site pode registrar dados técnicos de cada acesso, como endereço IP,
        tipo de navegador, data e hora. Esses registros servem para segurança e funcionamento do serviço.
      </p>

      <h2>Quando você chama no WhatsApp</h2>
      <p>
        Os botões de consulta abrem uma conversa no WhatsApp, um serviço da Meta com política de
        privacidade própria. Nessa conversa, a loja recebe o seu nome de perfil, o seu número e as
        mensagens que você enviar. Usamos essas informações apenas para responder, vender, combinar
        entrega ou retirada e atender trocas.
      </p>

      <h2>Quando você compra na loja</h2>
      <p>
        Ao comprar, podemos registrar no sistema da loja o seu nome, telefone e o histórico da compra.
        Em compras a prazo, também registramos os dados necessários para a cobrança. Esses dados são
        usados para emitir comprovantes, controlar trocas e cobrar valores em aberto.
      </p>

      <h2>Com quem compartilhamos</h2>
      <p>
        Não vendemos nem alugamos seus dados. Eles só são compartilhados quando a lei exige ou para
        cumprir obrigações fiscais e legais.
      </p>

      <h2>Seus direitos</h2>
      <p>Você pode pedir a qualquer momento:</p>
      <ul>
        <li>a confirmação de que tratamos seus dados e o acesso a eles;</li>
        <li>a correção de dados incompletos ou desatualizados;</li>
        <li>a eliminação de dados que não precisamos mais guardar por obrigação legal;</li>
        <li>informações sobre com quem seus dados foram compartilhados.</li>
      </ul>

      <h2>Contato</h2>
      <p>Para qualquer pedido sobre seus dados, fale com a {NOME_PADRAO}:</p>
      <ContatoLoja />
    </PaginaLegal>
  );
}
