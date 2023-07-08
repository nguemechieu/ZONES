import json
from datetime import time


class Trade:
    def __init__(self):
        self.id = None
        self.symbol = None
        self.side = None
        self.type = None
        self.price = None
        self.amount = None
        self.timestamp = None
        self.datetime = None
        self.fee = None
        self.info = None
        self.order_id = None
        self.pending_id = None
        self.pending_datetime = None
        self.pending_price = None
        self.pending_amount = None
        self.pending_fee = None
        self.time = time

    def order_send(self, symbol, side, _type, price, amount):
        self.symbol = symbol
        self.side = side
        self.type = _type
        self.price = price
        self.amount = amount
        self.timestamp = int(time.strftime(
            "%s", time.time()
        ))
        self.datetime = self.timestamp * 1000
        self.fee = None
        self.info = None

    def order_close(self):
        self.symbol = None
        self.side = None
        self.type = None
        self.price = None
        self.amount = None
        self.timestamp = None
        self.datetime = None
        self.fee = None
        self.info = None

    def pending_order_send(self, symbol, side, _type, price, amount):
        self.symbol = symbol
        self.side = side
        self.type = _type
        self.price = price
        self.amount = amount
        self.timestamp = int(time.strftime(
            "%s",
            time.time()
        ))
        self.datetime = self.timestamp * 1000
        self.fee = None
        self.info = None

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
            self.info = data['info']
            self.order_id = data['order_id']
            self.pending_id = data['pending_id']
            self.pending_datetime = data['pending_datetime']
            self.pending_price = data['pending_price']
            self.pending_amount = data['pending_amount']
            self.pending_fee = data['pending_fee']

            self.time = data['time']

    def pending_order_close(self):
        self.symbol = None
        self.side = None
        self.type = None
        self.price = None
        self.amount = None
        self.timestamp = None
        self.datetime = None
        self.fee = None
        self.info = None

    def trailing_order_send(self, symbol, side, type, price, amount):
        self.symbol = symbol
        self.side = side
        self.type = type
        self.price = price
        self.amount = amount
        self.timestamp = int(time.time())
        self.datetime = self.timestamp * 1000
        self.fee = None
        self.info = None

    def trailing_order_close(self):
        self.symbol = None
        self.side = None
        self.type = None
        self.price = None
        self.amount = None
        self.timestamp = None
        self.datetime = None
        self.fee = None
        self.info = None

    def trailing_trade_send(self, symbol, side, _type, price, amount):
        self.symbol = symbol
        self.side = side
        self.type = _type
        self.price = price
        self.amount = amount
        self.timestamp = int(time.time())
        self.datetime = self.timestamp * 1000
        self.fee = None
        self.info = None

    def modify_order_send(self, symbol, side, _type, price, amount):
        self.symbol = symbol
        self.side = side
        self.type = _type
        self.price = price
        self.amount = amount
        self.timestamp = int(time.time())
        self.datetime = self.timestamp * 1000
        self.fee = None
        self.info = None

    def save_to_file(self, filename: str):
        with open(filename, 'w') as f:
            data = {
                'id': self.id,
              'symbol': self.symbol,
              'side': self.side,
                'type': self.type,
                'price': self.price,
                'amount': self.amount,
                'timestamp': self.timestamp,
                'datetime': self.datetime,
                'fee': self.fee,
                'info': self.info,
                'order_id': self.order_id,
                'pending_id': self.pending_id,
                'pending_datetime': self.pending_datetime,
                'pending_price': self.pending_price,
                'pending_amount': self.pending_amount,
                'pending_fee': self.pending_fee,
                'time': self.time
            }
            json.dump(data, f, indent=4)

