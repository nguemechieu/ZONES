# -*- coding: utf-8 -*-
"""
    DWX_ZMQ_Reporting.py
    --
    @author: Darwinex Labs (www.darwinex.com)
    
    Copyright (c) 2019 onwards, Darwinex. All rights reserved.
    
    Licensed under the BSD 3-Clause License, you may not use this file except 
    in compliance with the License. 
    
    You may obtain a copy of the License at:    
    https://opensource.org/licenses/BSD-3-Clause
"""

from time import sleep

from pandas import DataFrame, to_datetime


class DwxZmqReporting(object):

    def __init__(self, _zmq):
        self._zmq = _zmq

    ##########################################################################

    def _get_open_trades_(self, _trader='Trader_SYMBOL',
                          _delay=0.1, _wbreak=10):

        # Reset data output
        self._zmq._set_response_(None)

        # Get open trades from MetaTrader
        self._zmq._DWX_MTX_GET_ALL_OPEN_TRADES_()

        # While loop start time reference            
        _ws = to_datetime('now')

        # While data not received, sleep until timeout
        while not self._zmq._valid_response_('zmq'):

            sleep(_delay)

            if (to_datetime('now') - _ws).total_seconds() > (_delay * _wbreak):
                break

        # If data received, return DataFrame
        if self._zmq._valid_response_('zmq'):

            _response = self._zmq._get_response_

            if ('_trades' in _response.keys()
                    and len(_response['_trades']) > 0):
                _df = DataFrame(data=_response['_trades'].values(),
                                index=_response['_trades'].keys())
                return _df[_df['_comment'] == _trader]

        # Default
        return DataFrame()



    def get_data(self):


        pass

    def get_signal(self, symbol):

        # Reset data output

        # While loop start time reference
        _ws = to_datetime('now')

        # While data not received, sleep until timeout
        while not self._zmq._valid_response_('zmq'):

            sleep(0.1)

            if (to_datetime('now') - _ws).total_seconds() > (0.1 * 10):
                break

        # If data received, return DataFrame
        if self._zmq._valid_response_('zmq'):

            _response = self._zmq._get_response_

            if ('_signals' in _response.keys()
                    and len(_response['_signals']) > 0):
                _df = DataFrame(data=_response['_signals'].values(),
                                index=_response['_signals'].keys())
                return _df[_df['_symbol'] == symbol]

        # Default
        return DataFrame()

