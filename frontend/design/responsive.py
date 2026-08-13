"""Ajuda telas com tamanho fixo (diálogos, popups) a não passarem do
que cabe na tela — sem isso, um QDialog.setFixedSize(largura, altura)
maior que a área útil do monitor abre parcialmente atrás da barra de
tarefas ou cortado, sem nenhuma rolagem pra alcançar o resto (ex.:
notebook em 1366x768 ou 1280x720, resoluções bem comuns em PC de
loja)."""

from PySide6.QtWidgets import QApplication


def tamanho_fixo_seguro(janela, largura, altura, margem=48):
    """Substitui setFixedSize(largura, altura) direto -- aplica o
    tamanho pedido, mas nunca maior que a área útil da tela (descontada
    a barra de tarefas) menos uma margem de folga pro próprio chrome
    da janela (barra de título). Em monitores normais (>=1600x900) o
    tamanho pedido cabe inteiro e nada muda; só encolhe quando
    realmente precisa.

    Não adiciona rolagem sozinho -- quem chama continua responsável
    por ter uma QScrollArea internamente se o conteúdo puder precisar
    de mais espaço vertical do que o tamanho final aplicado aqui."""

    tela = QApplication.primaryScreen()

    if tela is None:
        janela.setFixedSize(largura, altura)
        return

    disponivel = tela.availableGeometry()

    largura_final = min(largura, disponivel.width() - margem)
    altura_final = min(altura, disponivel.height() - margem)

    janela.setFixedSize(max(1, largura_final), max(1, altura_final))
