import tkinter

from mplfinance import figure


class Trading(tkinter.Frame):
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.fig = figure(figsize=(10, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(bottom=0.15)