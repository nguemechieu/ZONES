# -*- coding: utf-8 -*-
"""
    DWX_ZeroMQ_Connector_v2_0_1_RC8.py
    --
    @author: Darwinex Labs (www.darwinex.com)
    
    Copyright (c) 2017-2019, Darwinex. All rights reserved.
    
    Licensed under the BSD 3-Clause License, you may not use this file except 
    in compliance with the License. 
    
    You may obtain a copy of the License at:    
    https://opensource.org/licenses/BSD-3-Clause
"""
import tkinter
from datetime import datetime
from multiprocessing import get_logger
from threading import Thread
from time import sleep

import pandas as pd
import zmq
from pandas import DataFrame, Timestamp
# 30-07-2019 10:58 CEST
from zmq.utils.monitor import recv_monitor_message


class DwxZeromqConnector:
    """
    Setup ZeroMQ -> MetaTrader Connector
    """

    def __init__(self,
                 _client_id='dwx-zeromq',  # Unique ID for this client
                 _host='localhost',  # Host to connect to
                 _protocol='tcp',  # Connection protocol
                 _push_port=32768,  # Port for Sending commands
                 _pull_port=32769,  # Port for Receiving responses
                 _sub_port=32770,  # Port for Subscribing for prices
                 _delimiter=';',
                 _pulldata_handlers=None,  # Handlers to process data received through PULL port.
                 _sub_data_handlers=None,  # Handlers to process data received through SUB port.
                 _verbose=True,  # String delimiter
                 _poll_timeout=1000,  # ZMQ Poller Timeout (ms)
                 _sleep_delay=0.001,  # 1 ms for time.sleep()
                 _monitor=True):  # Experimental ZeroMQ Socket Monitoring
        self.history_db = None
        self.date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.account_info = {

        }
        ######################################################################
        self.price: float = 123.5
        self.logger = get_logger()
        self.logger.info('DwxZeromqConnector Initialized')
        self.server_status = "Ready to send commands to METATRADER (PUSH)"
        ######################################################################
        # Strategy Status (if this is False, ZeroMQ will not listen for data)
        self.ticket = 132
        self.lot: float = 0.01
        self.take_profit: int = 100
        self.stop_loss: int = 100
        self.symbol: str = 'EURUSD'
        self.magic_number: int = 10000
        self.get_open_orders = {
            'trades': {}}
        self._Candle_List_DB = {
            '_data': {
                'open': [],
                'high': [],
                'low': [],
                'close': [],
                'volume': [],
                'time': []}

        }
        self.temp_order_dict = {}
        if _pulldata_handlers is None:
            _pulldata_handlers = []
        if _sub_data_handlers is None:
            _sub_data_handlers = []

        self._ACTIVE = True
        # Client ID
        self._ClientID = _client_id
        # ZeroMQ Host
        self._host = _host
        # Connection Protocol
        self._protocol = _protocol
        # ZeroMQ Context
        self._ZMQ_CONTEXT = zmq.Context()
        # TCP Connection URL Template
        self._URL = self._protocol + "://" + self._host + ":"
        # Handlers for received data (pull and sub ports)
        self._pulldata_handlers = _pulldata_handlers
        self._sub_data_handlers = _sub_data_handlers
        # Ports for PUSH, PULL and SUB sockets respectively
        self._PUSH_PORT = _push_port
        self._PULL_PORT = _pull_port
        self._SUB_PORT = _sub_port
        self.market_data: DataFrame = DataFrame()
        self._delimiter = _delimiter

        # Create Sockets
        self._PUSH_SOCKET = self._ZMQ_CONTEXT.socket(zmq.PUSH)
        self._PUSH_SOCKET.setsockopt(zmq.SNDHWM, 1)
        self._PUSH_SOCKET_STATUS = {'state': True, 'latest_event': 'N/A'}
        self._PULL_SOCKET = self._ZMQ_CONTEXT.socket(zmq.PULL)
        self._PULL_SOCKET.setsockopt(zmq.RCVHWM, 1)
        self._PULL_SOCKET_STATUS = {'state': True, 'latest_event': 'N/A'}
        self._SUB_SOCKET = self._ZMQ_CONTEXT.socket(zmq.SUB)

        # Bind PUSH Socket to send commands to MetaTrader
        self._PUSH_SOCKET.connect(self._URL + str(self._PUSH_PORT))
        print("[INIT] Ready to send commands to METATRADER (PUSH): " + str(self._PUSH_PORT))
        self.zone_status = "Ready to send commands to METATRADER (PUSH): " + str(self._PUSH_PORT)

        # Connect PULL Socket to receive command responses from MetaTrader
        self._PULL_SOCKET.connect(self._URL + str(self._PULL_PORT))
        print("[INIT] Listening for responses from METATRADER (PULL): " + str(self._PULL_PORT))
        self.zone_status = "Listening for responses from METATRADER (PULL): " + str(self._PULL_PORT)

        # Connect SUB Socket to receive market data from MetaTrader
        print("[INIT] Listening for market data from METATRADER (SUB): " + str(self._SUB_PORT))
        self._SUB_SOCKET.connect(self._URL + str(self._SUB_PORT))
        self.zone_status = "Listening for market data from METATRADER (SUB): " + str(self._SUB_PORT)

        # Initialize POLL set and register PULL and SUB sockets
        self._poller = zmq.Poller()
        self._poller.register(self._PULL_SOCKET, zmq.POLLIN)
        self._poller.register(self._SUB_SOCKET, zmq.POLLIN)

        # Start listening for responses to commands and new market data
        self._string_delimiter = _delimiter

        self._main_string_delimiter = ':|:'

        # BID/ASK Market Data Subscription Threads ({SYMBOL: Thread})
        self._MarketData_Thread = None
        self._BidAsk_Thread = None

        # Socket Monitor Threads
        self._PUSH_Monitor_Thread = None
        self._PULL_Monitor_Thread = None

        # Market Data Dictionary by Symbol (holds tick data)
        self._Market_Data_DB = {

        }  # {SYMBOL: {TIMESTAMP: (BID, ASK)}}

        # History Data Dictionary by Symbol (holds historic data of the last HIST request for each symbol)
        self._History_DB = {

        }  # {SYMBOL_TF: [{'time': TIME, 'open': OPEN_PRICE, 'high': HIGH_PRICE,
        #               'low': LOW_PRICE, 'close': CLOSE_PRICE, 'tick_volume': TICK_VOLUME,
        #               'spread': SPREAD, 'real_volume': REAL_VOLUME}, ...]}

        # Account Information Dictionary
        self.account_info_DB = {}  # {ACCOUNT_NUMBER:[{'current time': 'CURRENT_TIME', 'account_name': 'ACCOUNT_NAME',
        # 'account_balance': ACCOUNT_BALANCE, 'account_equity': ACCOUNT_EQUITY,
        # 'account_profit': ACCOUNT_PROFIT, 'account_free_margin': ACCOUNT_FREE_MARGIN,
        # 'account_leverage': ACCOUNT_LEVERAGE}]}

        # Temporary Order STRUCT for convenience wrappers later.
        self.temp_order_dict = self._generate_default_order_dict()

        # Thread returns the most recently received DATA block here
        self._thread_data_output = None

        # Verbosity
        self._verbose = _verbose

        # ZMQ Poller Timeout
        self._poll_timeout = _poll_timeout

        # Global Sleep Delay
        self._sleep_delay = _sleep_delay

        # Begin polling for PULL / SUB data
        self._MarketData_Thread = Thread(target=self._poll_data_,
                                         args=(self._string_delimiter,
                                               self._poll_timeout,))
        self._MarketData_Thread.daemon = True
        self._MarketData_Thread.start()

        ###########################################
        # Enable/Disable ZeroMQ Socket Monitoring #
        ###########################################
        if _monitor:
            # ZeroMQ Monitor Event Map
            self._MONITOR_EVENT_MAP = {

            }
            print("\n[KERNEL] Retrieving ZeroMQ Monitor Event Names:\n")
            self.server_status = "Listening for market data from METATRADER (SUB): " + str(self._SUB_PORT)
            # Get all ZeroMQ events
            for name in dir(zmq):
                if name.startswith('EVENT_'):
                    value = getattr(zmq, name)
                    print(f"{value}\t\t:\t{name}")
                    self._MONITOR_EVENT_MAP[value] = name

            print("\n[KERNEL] Socket Monitoring Config -> DONE!\n")
            self.zone_status = "Socket Monitoring Config -> DONE!"

            # Disable PUSH/PULL sockets and let MONITOR events control them.
            self._PUSH_SOCKET_STATUS['state'] = False
            self._PULL_SOCKET_STATUS['state'] = False

            # PUSH
            self._PUSH_Monitor_Thread = Thread(target=self._event_monitor_,
                                               args=("PUSH",
                                                     self._PUSH_SOCKET.get_monitor_socket(),))
            self._PUSH_Monitor_Thread.daemon = True
            self._PUSH_Monitor_Thread.start()

            # PULL
            self._PULL_Monitor_Thread = Thread(target=self._event_monitor_,
                                               args=("PULL",
                                                     self._PULL_SOCKET.get_monitor_socket()

                                                     ))
            self._PULL_Monitor_Thread.daemon = True
            self._PULL_Monitor_Thread.start()

    ##########################################################################

    def _shutdown_(self):

        # Set INACTIVE
        self._ACTIVE = False

        # Get all threads to shut down
        if self._MarketData_Thread is not None:
            self._MarketData_Thread.join()

        if self._PUSH_Monitor_Thread is not None:
            self._PUSH_Monitor_Thread.join()

        if self._PULL_Monitor_Thread is not None:
            self._PULL_Monitor_Thread.join()

        # Unregister sockets from Poller
        self._poller.unregister(self._PULL_SOCKET)
        self._poller.unregister(self._SUB_SOCKET)
        print("\n++ [KERNEL] Sockets unregistered from ZMQ Poller()! ++")
        self.zone_status = "Sockets unregistered from ZMQ Poller()!"

        # Terminate context 
        self._ZMQ_CONTEXT.destroy(0)
        print("\n++ [KERNEL] ZeroMQ Context Terminated.. shut down safely complete! :)")
        self.zone_status = "ZeroMQ Context Terminated.. shut down safely complete!"

    ##########################################################################

    """
    Set Status (to enable/disable strategy manually)
    """

    def _set_status(self, _new_status=False):

        self._ACTIVE = _new_status
        print("\n**\n[KERNEL] Setting Status to {} - Deactivating Threads.. please wait a bit.\n**".format(_new_status))
        self.server_status = "Setting Status to {} - Deactivating Threads.. please wait a bit.".format(_new_status)

    ##########################################################################
    """
    Function to send commands to MetaTrader (PUSH)
    """

    def _remote_send(self, _socket, _data):

        if self._PUSH_SOCKET_STATUS['state']:
            try:
                _socket.send_string(_data, zmq.DONTWAIT)
            except zmq.error.Again:
                print('\nResource timeout.. please try again.')
                self.server_status = "Resource timeout.. please try again."
                sleep(self._sleep_delay)
        else:
            print('\n[KERNEL] NO HANDSHAKE ON PUSH SOCKET.. Cannot SEND data')
            self.server_status = "NO HANDSHAKE ON PUSH SOCKET.. Cannot SEND data"

    ##########################################################################

    def _get_response_(self):

        if self._PULL_SOCKET_STATUS['state']:
            try:
                msg = self._PULL_SOCKET.recv_string(zmq.DONTWAIT)
                return msg
            except zmq.error.Again:
                print("\nResource timeout.. please try again.")
                self.server_status = "Resource timeout.. please try again."

                sleep(self._sleep_delay)

                ##########################################################################

    def _set_response_(self, _resp=None):
        self._thread_data_output = _resp

    ##########################################################################

    def _valid_response_(self, _input='zmq'):

        # Valid data types
        _types = (dict, DataFrame)

        # If _input = 'zmq', assume self._zmq._thread_data_output
        if isinstance(_input, str) and _input == 'zmq':
            return isinstance(self._get_response_, _types)
        else:
            return isinstance(_input, _types)

    """
    Function to retrieve data from MetaTrader (PULL)
    """

    def _remote_recv(self, _socket):

        if self._PULL_SOCKET_STATUS['state']:
            try:
                msg = _socket.recv_string(zmq.DONTWAIT)
                return msg
            except zmq.error.Again:
                print("\nResource timeout.. please try again.")
                self.server_status = "Resource timeout.. please try again."
                sleep(self._sleep_delay)
        else:
            print('\r[KERNEL] NO HANDSHAKE ON PULL SOCKET.. Cannot READ data', end='', flush=True)
            self.server_status = "NO HANDSHAKE ON PULL SOCKET.. Cannot READ data"

        return None

    ##########################################################################

    # Convenience functions to permit easy trading via underlying functions.

    # OPEN ORDER
    def _order_send(self, symbol: str, price: float, _lot: float, order_type: int, _loss: float,
                    _profit: float,
                    slippage: int,

                    magic_number: int = 150, expiration: int = 156):

        _order = {}

        _order['_action'] = 'NEW TRADE'
        _order['_symbol'] = symbol
        _order['_price'] = price
        _order['_lot'] = _lot
        _order['_type'] = order_type
        _order['_sl'] = _loss
        _order['_tp'] = _profit
#        _order['_slippage'] = slippage
        _order['_magic'] = magic_number
      #  _order['_expiration'] = expiration
        self.temp_order_dict = _order
        # Execute command
        self._send_command_(**self.temp_order_dict)  # Send command to MetaTrader
        print("\n[KERNEL] Order sent successfully!")
        self.server_status = "Order sent successfully!"

    # MODIFY ORDER
    # _SL and _TP given in points. _price is only used for pending orders. 
    def _modify_order_by_ticket_(self, _ticket, _sl: int = 100, _tp: int = 100, _price: float = 1.23):

        try:
            self.temp_order_dict['_action'] = 'MODIFY'
            self.temp_order_dict['_ticket'] = _ticket
            self.temp_order_dict['_sl'] = _sl
            self.temp_order_dict['_tp'] = _tp
            self.temp_order_dict['_price'] = _price

            # Execute
            self._send_command_(**self.temp_order_dict)
            print("\n[KERNEL] Order modified successfully!")
            self.server_status = "Order modified successfully!"


        except KeyError:
            print("[ERROR] Order Ticket {} not found!".format(_ticket))
            self.server_status = "Order Ticket {} not found!".format(_ticket)

    # CLOSE ORDER
    def _order_close_by_ticket(self, _ticket):

        try:
            self.temp_order_dict['_action'] = 'CLOSE'
            self.temp_order_dict['_ticket'] = _ticket

            # Execute
            self._send_command_(**self.temp_order_dict)

        except KeyError:
            print("[ERROR] Order Ticket {} not found!".format(_ticket))
            self.server_status = "Order Ticket {} not found!".format(_ticket)

    # CLOSE PARTIAL
    def _order_close_partial_by_ticket_(self, _ticket, _lot):

        try:
            self.temp_order_dict['_action'] = 'CLOSE_PARTIAL'
            self.temp_order_dict['_ticket'] = _ticket
            self.temp_order_dict['_lots'] = _lot

            # Execute
            self._send_command_(**self.temp_order_dict)

        except KeyError:
            print("[ERROR] Order Ticket {} not found!".format(_ticket))
            self.server_status = "Order Ticket {} not found!".format(_ticket)

        except ValueError:
            print("[ERROR] LOTS {} not found!".format(_lot))
            self.server_status = "LOTS {} not found!".format(_lot)

    # CLOSE MAGIC
    def _order_close_by_magic(self, _magic):

        try:
            self.temp_order_dict['_action'] = 'CLOSE_MAGIC'
            self.temp_order_dict['_magic'] = _magic

            # Execute
            self._send_command_(**self.temp_order_dict)
            self.server_status = "Order Magic {} closed successfully!".format(_magic)

        except KeyError:
            print("[ERROR] Magic Number {} not found!".format(_magic))
            self.server_status = "Magic Number {} not found!".format(_magic)

    # CLOSE ALL TRADES
    def _close_all_orders_(self):

        try:
            self.temp_order_dict['_action'] = 'CLOSE_ALL'
            # Execute
            self._send_command_(**self.temp_order_dict)
            self.server_status = "All orders closed successfully!"

        except KeyError:

            msg = "[ERROR] No orders to close!"
            print("[ERROR] No orders to close!")
            self.server_status = "No orders to close!"

    # GET OPEN TRADES
    def _get_all_open_orders_(self):
        # """
        # :retype: object
        # """
        try:
            self.temp_order_dict['_action'] = 'GET_OPEN_TRADES'

            # Execute
            self._send_command_(**self.temp_order_dict)

            self.server_status = "All open orders successfully!"
            return self.temp_order_dict

        except KeyError:

            self.msg = "[ERROR] No orders to close!"
            self.server_status = "No orders to close!"

        return self.msg

    # DEFAULT ORDER DICT
    def _generate_default_order_dict(self):
        return ({'_action': 'OPEN',
                 '_type': 0,
                 '_symbol': self.symbol,
                 '_price': self._get_live_price_(_symbols='EURUSD'),
                 '_sl': self.stop_loss,  # SL/TP in POINTS, not pips.
                 '_tp': self.take_profit,
                 '_comment': self._ClientID,
                 '_lot': self.lot,
                 '_magic': self.magic_number,
                 '_ticket': self.ticket})

    ##########################################################################

    """
    Function to construct messages for sending HIST commands to MetaTrader

    Because of broker GMT offset _end time might have to be modified.
    """

    def _get_order_history_(self,
                            _symbol='EURUSD',
                            _timeframe=3600,
                            _start='2020.01.01 00:00:00',
                            _end=Timestamp.now().strftime('%Y.%m.%d %H:%M:00')):
        # _end='2019.01.04 17:05:00'):

        msg = "{};{};{};{};{}".format('HIST',
                                      _symbol,
                                      _timeframe,
                                      _start,
                                      _end)

        # Send via PUSH Socket
        self._remote_send(self._PUSH_SOCKET, msg)

    ##########################################################################
    """
    Function to construct messages for sending TRACK_PRICES commands to 
    MetaTrader for real-time price updates
    """

    def _get_live_price_(self,
                         _symbols: str = 'EURUSD'):
        # """
        # :retype: object
        # """
        msg = "{};{}".format('TRACK_PRICES', _symbols)

        # Send via PUSH Socket
        return self._remote_send(self._PUSH_SOCKET, msg)


    ##########################################################################
    """
    Function to construct messages for sending TRACK_RATES commands to 
    MetaTrader for OHLC
    """

    def _send_tracksides_request_(self,
                                  _instruments=None):
        if _instruments is None:
            _instruments = [('EURUSD_M1', 'EURUSD', 1)]
        if _instruments is None:
            _instruments = [('EURUSD_M2', 'EURUSD', 1)]
        msg = 'TRACK_RATES'
        for i in _instruments:
            msg = msg + ";{};{};{}".format(i, i, i)
            print(msg)
        # Send via PUSH Socket
        self._remote_send(self._PUSH_SOCKET, msg)

    ##########################################################################

    ##########################################################################
    """
    Function to construct messages for sending Trade commands to MetaTrader
    """

    def _send_command_(self, _action='OPEN', _type=0,
                       _symbol='EURUSD', _price=0,
                       _sl=50, _tp=50, _comment='ZONES  | AI POWERED MT4 TRADER',
                       _lot=0.01, _magic=123456, _ticket=0):

        msg = "{};{};{};{};{};{};{};{};{};{};{}".format('TRADE', _action, _type,
                                                        _symbol, _price,
                                                        _sl, _tp, _comment,
                                                        _lot, _magic,
                                                        _ticket)

        # Send via PUSH Socket
        return self._remote_send(self._PUSH_SOCKET, msg)

        """
         compArray[0] = TRADE or DATA
         compArray[1] = ACTION (e.g. OPEN, MODIFY, CLOSE)
         compArray[2] = TYPE (e.g. OP_BUY, OP_SELL, etc - only used when ACTION=OPEN)
         
         For compArray[0] == DATA, format is: 
             DATA|SYMBOL|TIMEFRAME|START_DATETIME|END_DATETIME
         
         // ORDER TYPES: 
         // https://docs.mql4.com/constants/tradingconstants/orderproperties
         
         // OP_BUY = 0
         // OP_SELL = 1
         // OP_BUYLIMIT = 2
         // OP_SELLLIMIT = 3
         // OP_BUYSTOP = 4
         // OP_SELLSTOP = 5
         
         compArray[3] = Symbol (e.g. EURUSD, etc.)
         compArray[4] = Open/Close Price (ignored if ACTION = MODIFY)
         compArray[5] = SL
         compArray[6] = TP
         compArray[7] = Trade Comment
         compArray[8] = Lots
         compArray[9] = Magic Number
         compArray[10] = Ticket Number (MODIFY/CLOSE)
         """
        # pass

    ##########################################################################

    """
    Function to check Poller for new responses (PULL) and market data (SUB)
    """

    def _poll_data_(self,
                    string_delimiter=';',
                    poll_timeout=1000):

        while self._ACTIVE:
            sleep(self._sleep_delay)  # poll timeout is in ms, sleep() is s.
            sockets = dict(self._poller.poll(poll_timeout))
            # Process response to commands sent to MetaTrader
            if self._PULL_SOCKET in sockets and sockets[self._PULL_SOCKET] == zmq.POLLIN:
                if self._PULL_SOCKET_STATUS['state']:
                    try:
                        msgx= self._PULL_SOCKET.recv_string(zmq.DONTWAIT)
                        print(msgx)

                        msg = self._remote_recv(self._PULL_SOCKET)

                        # If data is returned, store as pandas Series
                        if msg != '' and msg is not None:
                            try:
                                _data = eval(msg)
                                if '_action' in _data and _data['_action'] == 'HIST':
                                    _symbol = _data['_symbol']
                                    if '_data' in _data.keys():
                                        if _symbol not in self._History_DB.keys():
                                            self._History_DB[_symbol] = {}
                                        self._History_DB[_symbol] = _data['_data']
                                        self.history_db[_symbol] = pd.DataFrame(self._History_DB[_symbol])
                                    else:
                                        print(
                                            'No data found. MT4 often needs multiple requests when accessing data of '
                                            'symbols without open charts.')
                                        print('message: ' + msg)
                                        
                                        self.server_status = "No data found. MT4 often needs multiple requests when accessing data"
                                    
                                # Handling of Account Information messages
                                elif '_action' in _data and _data['_action'] == 'GET_ACCOUNT_INFORMATION':
                                    account_number = _data[
                                        'account_number']  # Use Account Number than Key in Account_info_DB dict
                                    if '_data' in _data.keys():
                                        if account_number not in self.account_info_DB.keys():
                                            self.account_info_DB[account_number] = []
                                        self.account_info_DB[account_number] += _data['_data']

                                        # invokes data handlers on pull port
                                for hnd in self._pulldata_handlers:
                                    hnd.onPullData(_data)

                                self._thread_data_output = _data
                                if self._verbose:
                                    print(_data)  # default logic

                            except Exception as ex:
                                _ex = "Exception Type {0}. Args:\n{1!r}"
                                msg = _ex.format(type(ex).__name__, ex.args)
                                self.server_status = msg
                                print(msg)

                    except zmq.error.Again:
                        pass  # resource temporarily unavailable, nothing to print
                    except ValueError:
                        pass  # No data returned, passing iteration.
                    except UnboundLocalError:
                        pass  # _symbol may sometimes get referenced before being assigned.

                else:
                    print('\r[KERNEL] NO HANDSHAKE on PULL SOCKET.. Cannot READ data.', end='', flush=True)
                    self.server_status = '[KERNEL] NO HANDSHAKE on PULL SOCKET.. Cannot READ data.'
            # Receive new market data from MetaTrader
            if self._SUB_SOCKET in sockets and sockets[self._SUB_SOCKET] == zmq.POLLIN:

                try:
                    msg = self._SUB_SOCKET.recv_string(zmq.DONTWAIT)

                    if msg != "":

                        _timestamp = str(Timestamp.now('UTC'))[:-6]
                        _symbol, _data = msg.split(self._main_string_delimiter)
                        if len(_data.split(string_delimiter)) == 2:
                            _bid, _ask = _data.split(string_delimiter)

                            if self._verbose:
                                print("\n[" + _symbol + "] " + _timestamp + " (" + _bid + "/" + _ask + ") BID/ASK")

                                self._Market_Data_DB[_symbol][_timestamp][_bid] = (float(_bid), float)
                                self._Market_Data_DB[_symbol][_timestamp][_ask] = (float(_ask), float)

                                # Update Market Data DB
                            if _symbol not in self._Market_Data_DB.keys():
                                self._Market_Data_DB[_symbol] = {}

                            self._Market_Data_DB[_symbol][_timestamp] = (float(_bid), float(_ask))

                        elif len(_data.split(string_delimiter)) == 8:
                            _time, _open, _high, _low, _close, _tick_vol, _spread, _real_vol = _data.split(
                                string_delimiter)
                            if self._verbose:
                                print(
                                    "\n[" + _symbol + "] " + _timestamp + " (" + _time + "/" + _open + "/" + _high + "/" + _low + "/" + _close + "/" + _tick_vol + "/" + _spread + "/" + _real_vol + ") TIME/OPEN/HIGH/LOW/CLOSE/TICKVOL/SPREAD/VOLUME")

                                self.market_data.append((_symbol, _timestamp, _time, _open, _high, _low,
                                                         _close, _tick_vol, _spread, _real_vol))
                                # Update Market Rate DB
                            if _symbol not in self._Market_Data_DB.keys():
                                self._Market_Data_DB[_symbol] = {}
                            self._Market_Data_DB[_symbol][_timestamp] = (
                                int(_time), float(_open), float(_high), float(_low), float(_close), int(_tick_vol),
                                int(_spread), int(_real_vol))

                        # invokes data handlers on sub port
                        for hnd in self._sub_data_handlers:
                            hnd.onSubData(msg)

                except zmq.error.Again:
                    pass  # resource temporarily unavailable, nothing to print
                except ValueError:
                    pass  # No data returned, passing iteration.
                except UnboundLocalError:
                    pass  # _symbol may sometimes get referenced before being assigned.

        print("\n++ [KERNEL] _DWX_ZMQ_Poll_Data_() Signing Out ++")
        self.server_status = "\n++ [KERNEL] _DWX_ZMQ_Poll_Data_() Signing Out ++"

    ##########################################################################

    """
    Function to subscribe to given Symbol's BID/ASK feed from MetaTrader
    """

    def _subscribe_marketdata_(self,
                               _symbol='EURUSD'):
        # Subscribe to SYMBOL first.
        self._SUB_SOCKET.setsockopt_string(zmq.SUBSCRIBE, _symbol)

        print("[KERNEL] Subscribed to {} BID/ASK updates. See self._Market_Data_DB.".format(_symbol))
        self.server_status = "[KERNEL] Subscribed to {} BID/ASK updates. See self._Market_Data_DB.".format(_symbol)

        if _symbol not in self._Market_Data_DB.keys():
            self._Market_Data_DB[_symbol] = {}
            self._Market_Data_DB[_symbol][str(Timestamp.now('UTC'))] = (0.0, 0.0)

    """
    Function to unsubscribe to given Symbol's BID/ASK feed from MetaTrader
    """

    def _unsubscribe_marketdata_(self, _symbol):

        self._SUB_SOCKET.setsockopt_string(zmq.UNSUBSCRIBE, _symbol)
        print("\n**\n[KERNEL] Unsubscribing from " + _symbol + "\n**\n")
        self.server_status = "[KERNEL] Unsubscribing from " + _symbol

    """
    Function to unsubscribe from ALL MetaTrader Symbols
    """

    def _unsubscribe_all_marketdata_requests_(self):

        # 31-07-2019 12:22 CEST
        for _symbol in self._Market_Data_DB.keys():
            self._unsubscribe_marketdata_(_symbol=_symbol)

    ##########################################################################
    def _event_monitor_(self,
                        socket_name: str,
                        monitor_socket:
                        str) -> None:

        # 05-08-2019 11:21 CEST
        while self._ACTIVE:

            sleep(self._sleep_delay)  # poll timeout is in ms, sleep() is s.

            # while monitor_socket.poll():
            while monitor_socket.poll(self._poll_timeout):

                try:
                    evt = recv_monitor_message(monitor_socket, zmq.DONTWAIT)
                    evt.update(dict(description=self._MONITOR_EVENT_MAP[evt['event']]))

                    # print(f"\r[{socket_name} Socket] >> {evt['description']}", end='', flush=True)
                    print(f"\n[{socket_name} Socket] >> {evt['description']}")
                    self.server_status = f"\n[{socket_name} Socket] >> {evt['description']}"

                    # Set socket status on HANDSHAKE
                    if evt['event'] == 4096:  # EVENT_HANDSHAKE_SUCCEEDED

                        if socket_name == "PUSH":
                            self._PUSH_SOCKET_STATUS['state'] = True
                            self._PUSH_SOCKET_STATUS['latest_event'] = 'EVENT_HANDSHAKE_SUCCEEDED'

                        elif socket_name == "PULL":
                            self._PULL_SOCKET_STATUS['state'] = True
                            self._PULL_SOCKET_STATUS['latest_event'] = 'EVENT_HANDSHAKE_SUCCEEDED'

                            print(f"\n[{socket_name} Socket] >> ..ready for action!\n")
                            self.server_status = f"\n[{socket_name} Socket] >>..ready for action!\n"
                            self.zone_status = True

                    else:
                        # Update 'latest_event'
                        if socket_name == "PUSH":
                            self._PUSH_SOCKET_STATUS['state'] = False
                            self._PUSH_SOCKET_STATUS['latest_event'] = evt

                        elif socket_name == "PULL":
                            self._PULL_SOCKET_STATUS['state'] = False
                            self._PULL_SOCKET_STATUS['latest_event'] = evt

                    if evt['event'] == zmq.EVENT_MONITOR_STOPPED:

                        # Reinitialize the socket
                        if socket_name == "PUSH":
                            monitor_socket = self._PUSH_SOCKET.get_monitor_socket()
                        elif socket_name == "PULL":
                            monitor_socket = self._PULL_SOCKET.get_monitor_socket()

                except Exception as ex:
                    _ex = "Exception Type {0}. Args:\n{1!r}"
                    _msg = _ex.format(type(ex).__name__, ex.args)
                    print(_msg)
                    self.server_status = _msg

        # Close Monitor Socket
        monitor_socket.close()

        print(f"\n++ [KERNEL] {socket_name} _DWX_ZMQ_EVENT_MONITOR_() Signing Out ++")
        self.server_status = f"\n++ [KERNEL] {socket_name} _DWX_ZMQ_EVENT_MONITOR_() Signing Out ++"

    ##########################################################################

    def _get_candle_list_(self, symbol: str = 'EURUSD') -> object:
        """
        Function to get Candle List from MetaTrader
        """

        print("\n++ [KERNEL] _DWX_ZMQ_GET_CANDLE_LIST_() Signing Out ++")
        self.server_status = "\n++ [KERNEL] _DWX_ZMQ_GET_CANDLE_LIST_() Signing Out ++"

        # Subscribe to SYMBOL first.
        self._SUB_SOCKET.setsockopt_string(zmq.SUBSCRIBE, symbol)

        print("[KERNEL] Subscribed to {} Candle List updates. See self._Candle_List_DB.".format(symbol))
        # Subscribe to SYMBOL first.
        self._subscribe_marketdata_(_symbol=symbol)
        return self._Candle_List_DB

    def _get_price(self, symbol: str = 'EURUSD'):
        """
        Function to get Price from MetaTrader
        """

        print("\n++ [KERNEL] _DWX_ZMQ_GET_PRICE_() Signing Out ++")

        # Subscribe to SYMBOL first.
        self._SUB_SOCKET.setsockopt_string(zmq.SUBSCRIBE, symbol)

        print("[KERNEL] Subscribed to {} Price updates. See self._Price_DB.".format(symbol))

    def _get_timeframe_(self, symbol: str = 'EURUSD'):
        """
        Function to get Timeframe from MetaTrader
        """

        print("\n++ [KERNEL] _DWX_ZMQ_GET_Timeframe_() Signing Out ++")

        # Subscribe to SYMBOL first.
        self._SUB_SOCKET.setsockopt_string(zmq.SUBSCRIBE, symbol)

        print("[KERNEL] Subscribed to {} Timeframe updates. See self._Timeframe_DB.".format(symbol))
        self.server_status = "[KERNEL] Subscribed to {} Timeframe updates. See self._Timeframe_DB"

        # Subscribe to SYMBOL first.
        return self._subscribe_marketdata_()

    def run(self):

        get_logger().info('DWX_ZeroMQ_Connector started')

        self._send_tracksides_request_()
        self._heartbeat()
        self._get_candle_list_(symbol='EURUSD')

    def _heartbeat(self):
        self._remote_send(self._PUSH_SOCKET, "HEARTBEAT;")

    ##########################################################################
    ##########################################################################

    # GET ACCOUNT INFORMATION
    def _get_account_info_(self):

        try:
            self.temp_order_dict['_action'] = 'GET_ACCOUNT_INFO'

            # Execute
            self._send_command_(**self.temp_order_dict)

        except Exception as ex:
            _ex = "Exception Type {0}. Args:\n{1!r}"
            msg = _ex.format(type(ex).__name__, ex.args)
            self.server_status = msg
            print(msg)

        return self._thread_data_output

    def _get_all_trades_(self):
        try:
            self.temp_order_dict['_action'] = 'GET_ALL_TRADES'

            # Execute
            self._send_command_(**self.temp_order_dict)

        except Exception as ex:
            _ex = "Exception Type {0}. Args:\n{1!r}"
            msg = _ex.format(type(ex).__name__, ex.args)
            self.server_status = msg
            print(msg)

    def get_price(self, symbol: str = 'EURUSD'):
        try:
            self.temp_order_dict['_action'] = 'GET_CURRENT_PRICE'
            self.temp_order_dict['_symbol'] = symbol
            self._subscribe_book_ticker(symbol=symbol)
            # Execute
            self._send_command_(**self.temp_order_dict)
        except Exception as ex:
            _ex = "Exception Type {0}. Args:\n{1!r}"
            msg = _ex.format(type(ex).__name__, ex.args)
            self.server_status = msg
            print(msg)

        return self._get_response_

    def _order_close_by_ticket_(self, trade_id):
        try:
            self.temp_order_dict['_action'] = 'ORDER_CLOSE_BY_TICKET'
            self.temp_order_dict['_trade_id'] = trade_id

            # Execute
            return self._send_command_(**self.temp_order_dict)

        except Exception as ex:
            _ex = "Exception Type {0}. Args:\n{1!r}"
            _msg = _ex.format(type(ex).__name__, ex.args)
            self.server_status = _msg
            print(_msg)

    ##############################################################################

    def _clean_up(self, _name='DWX_ZeroMQ_Connector',
                  _globals=None,
                  _locals=None):

        _msg: str = ''
        if _locals is None:
            _locals = locals()
            if _globals is None:
                _globals = globals()
                print(
                    '\n++ [KERNEL] Initializing ZeroMQ Cleanup.. if nothing appears below, no cleanup is necessary, '
                    'otherwise please wait..')
                try:
                    classe = _globals[_name]
                    _locals = list(_locals.items())
                    for _func, _instance in _locals:

                        if isinstance(_instance=_instance, _class=classe):
                            print(f'\n++ [KERNEL] Found & Destroying {_func} object 4werttr22before __init__()')
                            eval(_func)._zmq_shutdown_()
                            print(
                                '\n++ [KERNEL] Cleanup Complete -> OK to initialize DWX_ZeroMQ_Connector if NETSTAT diagnostics ' '== True. ++\n')
                            self.server_status = f"\n++ [KERNEL] Cleanup Complete -> OK to initialize"

                except Exception as es:
                    _e = "Exception Type {0}. Args:\n{1!r}"
                    _msg = _e.format(type(_e).__name__, es.args)
                    self.server_status = _msg

                if 'KeyError' in _msg:
                    print('\n++ [KERNEL] Cleanup Complete -> OK to initialize DWX_ZeroMQ_Connector. ++\n')
                else:
                    print(_msg)

    def _subscribe_book_ticker(self, symbol):
        try:
            self.temp_order_dict['_action'] = 'SUBSCRIBE_BOOK_TICKER'
            self.temp_order_dict['_symbol'] = symbol

            # Execute
            self._send_command_(**self.temp_order_dict)

        except Exception as ex:
            _ex = "Exception Type {0}. Args:\n{1!r}"
            msg = _ex.format(type(ex).__name__, ex.args)
            print(msg)
            self.server_status = msg

        return self._thread_data_output

    def _get_instrument_list(self):
        try:
            self.temp_order_dict['_action'] = 'GET_INSTRUMENT_LIST'

            # Execute
            self._send_command_(**self.temp_order_dict)

        except Exception as ex:
            _ex = "Exception Type {0}. Args:\n{1!r}"
            msg = _ex.format(type(ex).__name__, ex.args)
            print(msg)

        return self._get_response_

    def _get_market_info_(self):
        try:
            self.temp_order_dict['_action'] = 'GET_MARKET_INFO'

            # Execute
            self._send_command_(**self.temp_order_dict)

        except Exception as ex:
            _ex = "Exception Type {0}. Args:\n{1!r}"
            msg = _ex.format(type(ex).__name__, ex.args)
            print(msg)

        return self._thread_data_output

    def get_server_status(self):
        try:
            self.temp_order_dict['_action'] = 'GET_ZONES_SERVER_STATUS'

            # Execute
            self._send_command_(**self.temp_order_dict)

        except Exception as ex:
            _ex = "Exception Type {0}. Args:\n{1!r}"
            msg = _ex.format(type(ex).__name__, ex.args)
            print(msg)

        return self._thread_data_output

    def get_data(self):
        try:
            self.temp_order_dict['_action'] = 'GET_DATA'

            # Execute
            self._send_command_(**self.temp_order_dict)

            return self.temp_order_dict

        except Exception as ex:
            _ex = "Exception Type {0}. Args:\n{1!r}"
            msg: str = _ex.format(type(ex).__name__, ex.args)
            print(msg)
            self.server_status = msg

        return msg

        ##############################################################################
