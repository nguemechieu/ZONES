import tkinter

import pandas as pd

from src.modules.DwxZmqReporting import DwxZmqReporting

from src.zmq_connector import DwxZeromqConnector


class CandlestickChart(object):
    def __init__(self, controller):
        self.data = None
        self.reporting = None

        self.controller = controller

        # read data from zeromq
        self.read_data()
        self.pd = pd.DataFrame(columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        # self.pd['Time'] = self.data['Time']
        # self.pd['Open'] = self.data['Open'].astype(float)
        # self.pd['High'] = self.data['High'].astype(float)
        # self.pd['Low'] = self.data['Low'].astype(float)
        # self.pd['Close'] = self.data['Close'].astype(float)
        # self.pd['Volume'] = self.data['Volume'].astype(float)

        self.canvas = tkinter.Canvas(self.controller, width=800, height=600)
        self.canvas.pack()
        self.canvas.create_line(0, 0, 800, 0, fill='black')
        self.canvas.create_line(0, 600, 800, 600, fill='black')
        self.canvas.create_line(0, 1200, 800, 1200, fill='black')
        self.canvas.create_line(0, 1800, 800, 1800, fill='black')

        self.canvas.create_text(100, 100, text='Candlestick Chart')
        self.canvas.create_text(100, 200, text='Time')
        self.canvas.create_text(100, 300, text='Open')
        self.canvas.create_text(100, 400, text='High')
        self.canvas.create_text(100, 500, text='Low')
        self.canvas.create_text(100, 600, text='Close')
        self.canvas.create_text(100, 700, text='Volume')
        self.canvas.create_text(100, 800, text='Total')
        self.canvas.create_text(100, 900, text='Average')

        self.canvas.create_text(100, 1100, text=self.pd.to_string())
        self.canvas.create_text(100, 1200, text=self.pd.to_string())
        self.canvas.create_text(100, 1300, text=self.pd.to_string())
        self.canvas.create_text(100, 1400, text=self.pd.to_string())
        self.canvas.create_text(100, 1500, text=self.pd.to_string())
        self.canvas.pack()

    def read_data(self):
        # read data from zeromq
        self.reporting = DwxZmqReporting(_zmq=DwxZeromqConnector(_client_id='dwx-zeromq', _monitor=True))
        self.data = self.reporting.get_data()
        self.data['Time'] = pd.to_datetime(self.data['Time'], unit='ms')
        self.data['Open'] = self.data['Open'].astype(float)
        self.data['High'] = self.data['High'].astype(float)
        self.data['Low'] = self.data['Low'].astype(float)
        self.data['Close'] = self.data['Close'].astype(float)
        self.data['Volume'] = self.data['Volume'].astype(float)
        self.data['Total'] = self.data['Open'] + self.data['High'] + self.data['Low'] + self.data['Close']
        self.data['Average'] = self.data['Total'] / self.data['Volume']
        return self.data


class Home(tkinter.Frame):
    def __init__(self, parent,controller):
        super().__init__()

        self.controller = controller
        self.master = parent

        # create Menu Bar

        self.menu_bar = tkinter.Menu(self.master)

        # Binding to events using Zeromq
        self.zones_connect = DwxZeromqConnector(_client_id='dwx-zeromq', _monitor=True)
        self.zones_connect._dwx_zmq_heartbeat_()
        self.reporting = DwxZmqReporting(_zmq=self.zones_connect)
        self.zones_connect._get_all_open_orders_()
        self.zones_connect.get_account_info()

    def logout(self):
        self.controller.show_pages('Login')
