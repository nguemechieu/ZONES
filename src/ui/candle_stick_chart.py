import calendar
import tkinter

import pandas as pd
from mplfinance.original_flavor import candlestick_ohlc
# Imports

from tkcalendar import DateEntry
import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


class CandlestickChart(tkinter.Canvas):
    def __init__(self, parent, controller):
        super().__init__(parent)

        self.on_scroll = None
        self.candlestick_data = None
        self.controller = controller
        self.config(bg='black', border=4, highlightthickness=3, relief='ridge', width=1200, height=600)
        self.pack(fill=tkinter.BOTH)

        self.draw_candlestick()

    def draw_candlestick(self):
        self.candlestick_data = {
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'volume': [],
            'time': []

        }

        self.pd = pd.DataFrame(self.candlestick_data)


        self.fig, self.ax = plt.subplots(figsize=(12, 6), dpi=100)
        self.fig.patch.set_facecolor('white')
        self.ax.set_facecolor('white')
        self.ax.grid(True)
        self.ax.xaxis.set_major_locator(mdates.WeekdayLocator())

        self.ax.xaxis.set_minor_locator(mdates.DayLocator())
        self.ax.xaxis.set_minor_formatter(mdates.DateFormatter('%d'))
        self.ax.tick_params(which='major', length=10, width=1, direction='in', top='on', right='on')
        self.ax.tick_params(which='minor', length=5, width=1, direction='in', top='on', right='on')
        self.ax.xaxis.grid(True, which='major')
        self.ax.xaxis.grid(True, which='minor')
        self.ax.xaxis.set_tick_params(which='major', length=10, width=1, direction='in', top='on', right='on')
        self.ax.xaxis.set_tick_params(which='minor', length=5, width=1, direction='in', top='on', right='on')
        self.ax.xaxis.set_tick_params(which='both', length=10, width=1, direction='in', top='on', right='on')
        #
        # self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        # self.fig.canvas.mpl_connect('scroll_event', self.on_scroll)
        # self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        # self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        # self.fig.canvas.mpl_connect('resize_event', self.on_resize)
        # self.fig.canvas.mpl_connect('pick_event', self.on_pick)
        # self.fig.canvas.mpl_connect('button_release_event', self.on_release)




