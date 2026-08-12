from datetime import datetime

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter


class GraficoVendas(QChartView):

    def __init__(self, vendas_por_dia):

        chart = QChart()
        chart.setTitle("Vendas dos Últimos 7 Dias")
        chart.setTitleFont(QFont("", 13, QFont.Bold))
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().hide()
        chart.setBackgroundVisible(False)
        chart.setMargins(chart.margins())

        bar_set = QBarSet("Vendas")
        bar_set.setColor(QColor("#1565C0"))
        bar_set.setBorderColor(QColor("#0D47A1"))

        categorias = []

        for item in vendas_por_dia:
            bar_set.append(item["total"])
            dia = datetime.strptime(item["data"], "%Y-%m-%d")
            categorias.append(dia.strftime("%d/%m"))

        series = QBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsFormat("R$ @value")
        series.setLabelsPosition(
            QBarSeries.LabelsPosition.LabelsOutsideEnd
        )
        chart.addSeries(series)

        eixo_x = QBarCategoryAxis()
        eixo_x.append(categorias)
        chart.addAxis(eixo_x, Qt.AlignBottom)
        series.attachAxis(eixo_x)

        maior_valor = max(
            (item["total"] for item in vendas_por_dia), default=0
        )

        eixo_y = QValueAxis()
        eixo_y.setLabelFormat("R$ %.0f")
        eixo_y.setRange(0, max(maior_valor * 1.3, 10))
        chart.addAxis(eixo_y, Qt.AlignLeft)
        series.attachAxis(eixo_y)

        super().__init__(chart)

        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(280)
        self.setStyleSheet("""
            background:white;
            border-radius:12px;
            border:1px solid #dcdcdc;
        """)
