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


class GraficoBarras(QChartView):
    """Gráfico de barras genérico, parametrizável — usado pros diferentes
    gráficos de relatório (vendas por dia, top produtos, formas de
    pagamento), evitando duplicar a montagem do QChart pra cada um."""

    def __init__(
        self,
        titulo,
        dados,
        campo_categoria,
        campo_valor,
        cor="#1565C0",
        formato_valor="R$ @value",
        formato_eixo_y="R$ %.0f",
    ):
        chart = QChart()
        chart.setTitle(titulo)
        chart.setTitleFont(QFont("", 13, QFont.Bold))
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().hide()
        chart.setBackgroundVisible(False)

        bar_set = QBarSet("")
        bar_set.setColor(QColor(cor))
        bar_set.setBorderColor(QColor(cor).darker(120))

        categorias = []

        for item in dados:
            bar_set.append(item[campo_valor])
            categorias.append(str(item[campo_categoria]))

        series = QBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsFormat(formato_valor)
        series.setLabelsPosition(
            QBarSeries.LabelsPosition.LabelsOutsideEnd
        )
        chart.addSeries(series)

        eixo_x = QBarCategoryAxis()
        eixo_x.append(categorias if categorias else [""])
        chart.addAxis(eixo_x, Qt.AlignBottom)
        series.attachAxis(eixo_x)

        maior_valor = max(
            (item[campo_valor] for item in dados), default=0
        )

        eixo_y = QValueAxis()
        eixo_y.setLabelFormat(formato_eixo_y)
        eixo_y.setRange(0, max(maior_valor * 1.3, 10))
        chart.addAxis(eixo_y, Qt.AlignLeft)
        series.attachAxis(eixo_y)

        super().__init__(chart)

        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(260)
        self.setStyleSheet("""
            background:white;
            border-radius:12px;
            border:1px solid #dcdcdc;
        """)
