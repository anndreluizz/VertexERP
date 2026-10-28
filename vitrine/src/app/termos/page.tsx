import type { Metadata } from "next";
import { ContatoLoja, PaginaLegal } from "@/components/PaginaLegal";
import { NOME_PADRAO } from "@/lib/catalogo";

export const metadata: Metadata = {
  title: `Termos e Condições | ${NOME_PADRAO}`,
  description: `Regras de uso da vitrine e das compras na ${NOME_PADRAO}.`,
};

export default function Termos() {
  return (
    <PaginaLegal titulo="Termos e Condições">
      <p>
        Estes termos valem para o uso desta vitrine e para as compras combinadas com a {NOME_PADRAO}
        a partir dela. Ao usar o site, você concorda com as regras abaixo.
      </p>

      <h2>O que é a vitrine</h2>
      <p>
        O site mostra os produtos da loja para consulta. Não há venda nem pagamento pelo site.
        O pedido e a entrega ou retirada são combinados pelo WhatsApp ou na loja. A entrega em Tonantins não tem taxa.
        Pagamento no Pix, pelo WhatsApp, ou em dinheiro ou cartão na entrega ou na loja.
      </p>

      <h2>Preços e disponibilidade</h2>
      <ul>
        <li>Os preços e a disponibilidade vêm do sistema da loja e são atualizados de tempos em tempos. A data da última atualização aparece no site.</li>
        <li>Um produto pode acabar entre uma atualização e outra. Vale sempre o que for confirmado no atendimento.</li>
        <li>Ofertas valem até a data informada no produto ou enquanto houver estoque.</li>
        <li>Se houver erro evidente de preço, avisamos antes de fechar a compra.</li>
      </ul>

      <h2>Fotos</h2>
      <p>
        As fotos mostram o produto vendido, mas a cor pode variar um pouco conforme a tela do
        aparelho. Em caso de dúvida sobre cor, tamanho ou modelo, pergunte no atendimento.
      </p>

      <h2>Trocas e devoluções</h2>
      <ul>
        <li>Seguimos o Código de Defesa do Consumidor (Lei 8.078/1990).</li>
        <li>Produto com defeito pode ser reclamado em até 30 dias, para itens não duráveis, ou 90 dias, para itens duráveis.</li>
        <li>Compras fechadas pelo WhatsApp, sem você vir à loja, podem ser desistidas em até 7 dias a partir do recebimento do produto.</li>
        <li>Para trocar ou devolver, traga o produto com o comprovante ou fale com a gente pelo WhatsApp.</li>
      </ul>

      <h2>Conteúdo do site</h2>
      <p>
        A marca, a logo e as fotos deste site pertencem à {NOME_PADRAO} e não podem ser usadas
        sem autorização.
      </p>

      <h2>Mudanças nestes termos</h2>
      <p>
        Podemos atualizar estes termos. A data no topo da página mostra a versão em vigor.
      </p>

      <h2>Contato</h2>
      <ContatoLoja />
    </PaginaLegal>
  );
}
