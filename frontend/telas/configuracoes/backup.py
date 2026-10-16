from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from services import backup_service
from services.worker import rodar_em_thread

from design import tokens
from design.widgets import (
    BotaoPrimario, BotaoSecundario, estilo_lista,
)


def _formatar_data_backup(texto_iso):
    from datetime import datetime
    try:
        return datetime.fromisoformat(texto_iso).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return texto_iso or "—"


def _formatar_tamanho(bytes_):
    valor = float(bytes_ or 0)
    for unidade in ("B", "KB", "MB", "GB"):
        if valor < 1024:
            return f"{valor:.0f} {unidade}" if unidade == "B" else f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} TB"


class BackupMixin:
    """Pagina Backup: lista, backup manual e abrir pasta."""

    def _criar_pagina_backup(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl_secao = QLabel("BACKUP DO BANCO DE DADOS")
        lbl_secao.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:800; color:{tokens.TEXTO_SECUNDARIO}; letter-spacing:0.6px;
        """)
        layout.addWidget(lbl_secao)

        dica = QLabel(
            "Um backup completo é gerado automaticamente ao abrir o "
            "Vertex ERP no PC-Servidor e depois a cada 4 horas, e "
            "guardado em Documentos\\VertexERP\\Backups. Os backups "
            "dos últimos 7 dias ficam todos; até 30 dias fica só o "
            "último de cada dia. Use \"Fazer Backup Agora\" pra gerar "
            "uma cópia extra na hora, sem esperar o próximo automático."
        )
        dica.setWordWrap(True)
        dica.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO}; line-height:1.5;
        """)
        layout.addWidget(dica)

        self.lbl_alerta_backup = QLabel()
        self.lbl_alerta_backup.setWordWrap(True)
        self.lbl_alerta_backup.setStyleSheet(f"""
            background:{tokens.ALERTA_CLARO}; color:{tokens.ALERTA_TEXTO};
            border:1px solid {tokens.ALERTA};
            border-radius:{tokens.RADIUS_MD}px; padding:10px 12px;
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.lbl_alerta_backup.setVisible(False)
        layout.addWidget(self.lbl_alerta_backup)

        self.lbl_copia_externa = QLabel()
        self.lbl_copia_externa.setWordWrap(True)
        self.lbl_copia_externa.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.SUCESSO};
        """)
        self.lbl_copia_externa.setVisible(False)
        layout.addWidget(self.lbl_copia_externa)

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        self.bt_backup_manual = BotaoPrimario("Fazer Backup Agora")
        self.bt_backup_manual.setMinimumHeight(44)
        self.bt_backup_manual.clicked.connect(self._fazer_backup_manual)
        botoes.addWidget(self.bt_backup_manual)

        bt_abrir_pasta = BotaoSecundario("Abrir Pasta de Backups")
        bt_abrir_pasta.setMinimumHeight(44)
        bt_abrir_pasta.clicked.connect(self._abrir_pasta_backups)
        botoes.addWidget(bt_abrir_pasta)

        botoes.addStretch()
        layout.addLayout(botoes)

        linha_divisoria = QFrame()
        linha_divisoria.setFixedHeight(1)
        linha_divisoria.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha_divisoria)

        lbl_historico = QLabel("Histórico")
        lbl_historico.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:800; color:{tokens.TEXTO_SECUNDARIO}; letter-spacing:0.6px;
        """)
        layout.addWidget(lbl_historico)

        self.tabela_backups = QTableWidget()
        self.tabela_backups.setColumnCount(3)
        self.tabela_backups.setHorizontalHeaderLabels(
            ["Arquivo", "Data", "Tamanho"]
        )
        self.tabela_backups.verticalHeader().setVisible(False)
        self.tabela_backups.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela_backups.setSelectionMode(QTableWidget.NoSelection)
        self.tabela_backups.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela_backups.setMinimumHeight(260)
        self.tabela_backups.setShowGrid(False)
        self.tabela_backups.verticalHeader().setDefaultSectionSize(40)
        self.tabela_backups.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.tabela_backups.setStyleSheet(estilo_lista())
        layout.addWidget(self.tabela_backups, stretch=1)

        return self._envolver_com_rolagem(pagina, 8)

    def _atualizar_backups(self):

        if self._carregando_backups:
            return
        self._carregando_backups = True

        rodar_em_thread(
            self,
            backup_service.listar_backups,
            ao_sucesso=self._ao_atualizar_backups_sucesso,
            ao_erro=self._ao_atualizar_backups_erro,
            ao_finalizar=self._ao_atualizar_backups_finalizado,
        )

    def _ao_atualizar_backups_finalizado(self):
        self._carregando_backups = False

    def _ao_atualizar_backups_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar o histórico de backups.\n{erro}"
        )

    def _ao_atualizar_backups_sucesso(self, dados):

        self._backups_carregados = True
        self._pasta_backups_atual = dados["pasta"]

        alerta = dados.get("alerta")
        self.lbl_alerta_backup.setText(f"⚠ {alerta}" if alerta else "")
        self.lbl_alerta_backup.setVisible(bool(alerta))

        copia_externa = dados.get("copia_externa")
        self.lbl_copia_externa.setText(
            f"✓ Cada backup também é copiado para {copia_externa}"
            if copia_externa else ""
        )
        self.lbl_copia_externa.setVisible(bool(copia_externa))

        itens = dados["itens"]
        self.tabela_backups.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_backups.setItem(
                linha, 0, QTableWidgetItem(item["nome"])
            )
            self.tabela_backups.setItem(
                linha, 1,
                QTableWidgetItem(_formatar_data_backup(item["criado_em"])),
            )
            self.tabela_backups.setItem(
                linha, 2, QTableWidgetItem(_formatar_tamanho(item["tamanho_bytes"]))
            )

    def _fazer_backup_manual(self):

        self.bt_backup_manual.setEnabled(False)

        rodar_em_thread(
            self,
            backup_service.criar_backup_manual,
            ao_sucesso=self._ao_backup_manual_sucesso,
            ao_erro=self._ao_backup_manual_erro,
            ao_finalizar=self._ao_backup_manual_finalizado,
        )

    def _ao_backup_manual_finalizado(self):
        self.bt_backup_manual.setEnabled(True)

    def _ao_backup_manual_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível gerar o backup.\n{erro}")

    def _ao_backup_manual_sucesso(self, response):

        if response.status_code != 200:
            try:
                erro = response.json().get("detail", response.text)
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", f"Não foi possível gerar o backup.\n{erro}")
            return

        QMessageBox.information(self, "Sucesso", "Backup gerado com sucesso.")
        self._atualizar_backups()

    def _abrir_pasta_backups(self):

        # so' sabemos o caminho de verdade depois do backend responder
        # (ver _ao_atualizar_backups_sucesso) -- o backend resolve via
        # SHGetFolderPath (a pasta Documentos pode estar redirecionada
        # pro OneDrive), um "~/Documents" chutado aqui podia abrir uma
        # pasta errada/vazia
        if not self._pasta_backups_atual:
            QMessageBox.information(
                self, "Aguarde",
                "Aguarde o histórico de backups carregar antes de abrir a pasta.",
            )
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(self._pasta_backups_atual))
