import json

from src.modules.DwxZmqReporting import DwxZmqReporting
from src.zmq_connector import DwxZeromqConnector


class Trade:
    def __init__(self):
        super().__init__()

        # Binding to events using Zeromq
        self.slippage = None
        self.order_id = None
        self.amount = None
        self.type = None
        self.id = None
        self.symbol = None
        self.side = None
        self.price = None
        self.timestamp = None
        self.datetime = None
        self.fee = None

        self.zones_connect = DwxZeromqConnector(_client_id='dwx-zeromq', _monitor=True)

        self.reporting = DwxZmqReporting(_zmq=self.zones_connect)
        print(str(self.reporting.get_data()))



    def load_from_file(self, filename: str):
        with open(filename) as f:
            data = json.load(f)
            self.id = data['id']
            self.symbol = data['symbol']
            self.side = data['side']
            self.type = data['type']
            self.price = data['price']
            self.amount = data['amount']
            self.timestamp = data['timestamp']
            self.datetime = data['datetime']
            self.fee = data['fee']

            self.order_id = data['order_id']

    def get_instrument_list(self):
        return self.zones_connect._get_instrument_list()

    def save_to_file(self, filename):
        with open(filename, 'w') as outfile:
            json.dump(self.__dict__, outfile)
            outfile.close()

    def get_signal(self, symbol: str):
        return self.reporting.get_signal(symbol=symbol)
    def open_order(self, slippage: int = 1, stop_loss: int = 100, take_profit: int = 100, type='limit',
                   side: str = 'buy'):
        self.slippage = slippage
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.type = type
        self.side = side
        if self.type == 'limit' and self.side == 'buy':
            self.zones_connect._order_send(
                symbol=self.symbol,
                order_type=self.type,
                price=self.price,
                quantity=self.amount,
                slippage=self.slippage, loss=self.stop_loss,
                profit=self.take_profit

            )

        elif self.type == 'market' and self.side == 'buy':
            self.zones_connect._order_send(
                symbol=self.symbol,
                order_type=self.type,
                price=self.price,
                quantity=self.amount,
                slippage=self.slippage, loss=self.stop_loss,
                profit=self.take_profit
            )

        elif self.type == 'stop' and self.side == 'buy':
            self.zones_connect._order_send(
                symbol=self.symbol,
                order_type=self.type,
                price=self.price,
                quantity=self.amount,
                slippage=self.slippage, loss=self.stop_loss,
                profit=self.take_profit
            )

        elif self.type == 'limit' and self.side == 'sell':
            self.zones_connect._order_send(
                symbol=self.symbol,
                order_type=self.type,
                price=self.price,
                quantity=self.amount,
                slippage=self.slippage, loss=self.stop_loss,
                profit=self.take_profit
            )

        elif self.type == 'stop' and self.side == 'sell':
            self.zones_connect._order_send(
                symbol=self.symbol,
                order_type=self.type,
                price=self.price,
                quantity=self.amount,
                slippage=self.slippage, loss=self.stop_loss,
                profit=self.take_profit
            )

        elif self.type == 'market' and self.side == 'sell':
            self.zones_connect._order_send(
                symbol=self.symbol,
                order_type=self.type,
                price=self.price,
                quantity=self.amount,
                slippage=self.slippage, loss=self.stop_loss,
                profit=self.take_profit
            )

    def _get_all_closed_orders_(self):


        pass
