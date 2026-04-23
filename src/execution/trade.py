import json

from datetime import datetime



class Trade(object):
    def __init__(self):
        super().__init__()
        self.symbol = None
        self.price = None
        self.volume = None
        self.time = None
        self.side = None
        self.order_id = None
        self.order_type = None
        self.order_status = None

        self.order={'_action': 'OPEN',
                    '_type': 3,
                    '_symbol': 'EURUSD',
                    '_price': 0.0,
                    '_sl': 500,  # sl/tp in POINTS, not pips.
                    '_tp': 500,
                    '_comment': 456789,
                    '_lots': 0.01,
                    '_magic': 123456,
                    '_ticket': 234}
       


