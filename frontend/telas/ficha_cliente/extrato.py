import csv
from datetime import datetime

from PySide6.QtGui import (
    QFont, QTextDocument,
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)

from services import api
from services.movimento_fiado_service import (
    saldo_cliente,
)
from services.cliente_service import (
    listar_observacoes_cliente,
)
from services import impressora_termica_service, preferencias_service
from design import tokens
from utils.formatacao import formatar_moeda
from utils.documento_html import (
    ESTILO_BODY,
    bloco_total,
    cabecalho_html,
    cabecalho_tabela,
    linha_zebra,
)
from telas.ficha_cliente.comum import NOMES_FORMA_FIADO, _parse_data


class ExtratoMixin:
    """Extrato do cliente: impressao (A4 e termica) e exportacao CSV."""

    # ======================================
    # EXTRATO (PDF) / EXPORTAR CSV
    # ======================================

    def _montar_html_extrato(self):

        config = api.configuracoes()

        usuario = api.me()
        responsavel = usuario.get("nome") or "—"

        saldo = saldo_cliente(self.cliente["id"])
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        linhas_tabela = []

        for mov, saldo_apos in reversed(self._movimentos):

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")[:16]

            tipo = mov.get("tipo")
            valor = float(mov.get("valor", 0) or 0)
            descricao = self._descricao_com_itens(mov)

            debito = (
                f"<span style='color:#DC2626;'>{formatar_moeda(valor)}</span>"
                if tipo == "COMPRA" else ""
            )
            credito = (
                f"<span style='color:#16A34A;'>{formatar_moeda(valor)}</span>"
                if tipo == "PAGAMENTO" else ""
            )

            linhas_tabela.append(
                linha_zebra(
                    [data, descricao, debito, credito, formatar_moeda(saldo_apos)],
                    len(linhas_tabela),
                    alinhamentos=["left", "left", "right", "right", "right"],
                )
            )

        linhas_html = "".join(linhas_tabela) or (
            "<tr><td colspan='5' align='center' style='padding:10px;'>"
            "Nenhuma movimentação registrada.</td></tr>"
        )

        observacoes = listar_observacoes_cliente(self.cliente["id"])

        linhas_observacoes = "".join(
            f"<p style='margin:4px 0;'>"
            f"<b>{(_parse_data(obs.get('criado_em')) or datetime.now()).strftime('%d/%m/%Y')}:</b> "
            f"{obs.get('texto', '')}</p>"
            for obs in observacoes
        )

        bloco_observacoes = (
            f"<h3>Observações</h3>{linhas_observacoes}"
            if linhas_observacoes
            else ""
        )

        return f"""
        <body style="{ESTILO_BODY}">
        {cabecalho_html("EXTRATO FINANCEIRO", config)}
        <table width="100%" cellspacing="4">
            <tr><td style="color:#64748B;"><b>Cliente:</b></td><td>{self.cliente.get('nome', '')}</td></tr>
            <tr><td style="color:#64748B;"><b>CPF/CNPJ:</b></td><td>{self.cliente.get('cpf_cnpj') or '—'}</td></tr>
            <tr><td style="color:#64748B;"><b>Telefone:</b></td><td>{self.cliente.get('telefone') or '—'}</td></tr>
            <tr><td style="color:#64748B;"><b>Emitido em:</b></td><td>{agora}</td></tr>
        </table>
        <h4 style="margin:16px 0 6px; color:#1E293B;">MOVIMENTAÇÕES</h4>
        <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB;">
            {cabecalho_tabela(
                ["Data", "Descrição", "Débito", "Crédito", "Saldo"],
                ["left", "left", "right", "right", "right"],
            )}
            {linhas_html}
        </table>
        {bloco_observacoes}
        {bloco_total("TOTAL DEVEDOR", formatar_moeda(saldo))}
        <p style="margin:8px 0 0; color:#64748B; font-size:9pt;">
            Responsável pela emissão: {responsavel}
        </p>
        </body>
        """

    def _montar_documento_extrato(self):

        documento = QTextDocument()
        documento.setDefaultFont(QFont(tokens.FONTE_FAMILIA_PADRAO, 10))
        documento.setHtml(self._montar_html_extrato())

        return documento

    def _montar_movimentos_extrato_termico(self):
        """Mesma lista usada no HTML (ver _montar_html_extrato), só que
        como dicts simples -- formato que impressora_termica_service
        espera, sem acoplar esse serviço ao formato interno de `mov`."""

        movimentos = []

        for mov, saldo_apos in reversed(self._movimentos):

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")[:16]

            movimentos.append({
                "data": data,
                "descricao": self._descricao_com_itens(mov),
                "tipo": mov.get("tipo"),
                "valor": mov.get("valor", 0),
                "saldo_apos": saldo_apos,
            })

        return movimentos

    def imprimir_extrato(self):

        config_impressora = preferencias_service.carregar_impressora_termica()

        if config_impressora and config_impressora.get("ativa"):

            saldo = saldo_cliente(self.cliente["id"])
            usuario = api.me()
            responsavel = usuario.get("nome") or "—"
            observacoes = listar_observacoes_cliente(self.cliente["id"])

            ok, erro = impressora_termica_service.imprimir_extrato(
                self.cliente,
                self._montar_movimentos_extrato_termico(),
                observacoes,
                saldo,
                responsavel,
                api.configuracoes(),
                config_impressora,
            )

            if ok:
                return

            resposta = QMessageBox.question(
                self,
                "Falha na impressora térmica",
                f"{erro}\n\nQuer tentar imprimir pela janela normal do Windows?",
            )

            if resposta != QMessageBox.Yes:
                return

        printer = QPrinter(QPrinter.HighResolution)

        dialogo = QPrintDialog(printer, self)

        if dialogo.exec() != QPrintDialog.Accepted:
            return

        self._montar_documento_extrato().print_(printer)

    def exportar_csv(self):

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Extrato (CSV)",
            f"extrato_{self.cliente['nome'].replace(' ', '_')}.csv",
            "Arquivo CSV (*.csv)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".csv"):
            caminho += ".csv"

        try:
            with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:

                escritor = csv.writer(arquivo, delimiter=";")
                escritor.writerow(
                    ["Data", "Tipo", "Descrição", "Forma Pagamento", "Valor", "Saldo Após"]
                )

                for mov, saldo_apos in reversed(self._movimentos):

                    data = str(mov.get("data", ""))
                    if "T" in data:
                        data = data.replace("T", " ")[:16]

                    forma = mov.get("forma_pagamento")
                    texto_forma = NOMES_FORMA_FIADO.get(forma, forma) if forma else ""

                    escritor.writerow([
                        data,
                        mov.get("tipo", ""),
                        self._descricao_com_itens(mov),
                        texto_forma,
                        f"{float(mov.get('valor', 0) or 0):.2f}",
                        f"{saldo_apos:.2f}",
                    ])

            QMessageBox.information(
                self, "Sucesso", "Extrato exportado com sucesso."
            )

        except OSError as erro:
            QMessageBox.critical(self, "Erro", str(erro))
