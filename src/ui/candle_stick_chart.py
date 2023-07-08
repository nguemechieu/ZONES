import pandas as pd


class CandleSticksChart(object):
    def __init__(self):
        self.chart = None
        self.candlestick = None
        self.volume = None
        self.candlestickSeries = None
        self.volumeSeries = None
        self.candlesticks = None
        self.volumes = None
        self.candlesticksSeries = None
        self.volumesSeries = None
        self.candlesticksPlot = None
        self.volumesPlot = None


        # Create the candlestick chart

        pd.set_option('display.max_rows', 500)
        pd.set_option('display.max_columns', 500)
        pd.set_option('display.width', 1000)
        pd.set_option('display.max_colwidth', 1000)
        pd.set_option('display.float_format', lambda x: '%.2f' % x)
        pd.set_option('display.precision', 2)
        pd.set_option('display.expand_frame_repr', False)

