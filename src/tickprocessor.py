from sklearn.discriminant_analysis import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import confusion_matrix, classification_report
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta, date
from os.path import join
import random
import numpy as np
import pandas as pd
from numpy.random import random
from src.DwxClient import DwxClient



class TickProcessor:
    """
     TickProcessor class.

     Attributes:
     X_train: object
     y_train: object
     X_test: object
     y_test: object
     model = None
    
     Constructor for TickProcessor class.
     Parameters:
            sleep_delay (float): Delay in seconds for time.sleep().
            max_retry_command_seconds (int): Maximum time to retry sending a command if not successful.
            verbose (bool): Flag to indicate verbose logging.
            db: Database object (if applicable).
            metatrader_dir_path (str): Path to the MetaTrader directory.
    """
        # Initialization code goes here
    def __init__(self,
                 sleep_delay=0.005,  # 5 ms for time.sleep()
                 max_retry_command_seconds=10,  # retry to send to commend for 10 seconds if not successful.
                 verbose=True, db=None, metatrader_dir_path: str = ''
                 ,start_time=  "3:59" 
                 ,stop_time="23:59"
                 
                 ):
        self.start_time = start_time
        self.stop_time = stop_time

        self.time = None
        self.open_test_trades = True
        self.trade_day = None
        self.use_trade_day = True
        self.symbols = ['EURUSD', 'USDJPY', 'USDCAD', 'USDCHF', 'USDNOK', 'USDSEK', 'USDTRY']
        self.metatrader_dir_path = metatrader_dir_path
        self.takeprofit = 0.011
        self.signal = 0
        self.stoploss = 0.013

        self.orderprofit_ = 0
        self.profits = 0
     
        self.magic_number = 3041990

        self.order_id = 0
        self.history_data_df = pd.DataFrame({
            
        })
        self.signal_on_tick = 0
        self.historic_trades = None
        self.historic_trades_df = None
        self.lot =   self.calculate_lot_size(data_size=100,min_lot_size=0.0100000, max_lot_size=1)
        self.bar_data_count = 0
        self.metatrader_dir_path: str = metatrader_dir_path
        self.tick_data = None
        self.symbol = 'EURUSD'

        self.bid = 0.0
       
        self.ask = 0.0
        self.db = db
        self.da = None
        self.bar_data_df = pd.DataFrame(columns=['time', 'symbol', 'time_frame', 'open', 'high', 'low', 'close',
                                                 'volume'])
        self.verbose = verbose
        self.sleep_delay = sleep_delay
        self.max_retry_command_seconds = max_retry_command_seconds

        self.last_open_time =   datetime.now().utcnow()
        self.last_modification_time= datetime.now().utcnow()

        self.dwx = DwxClient(self, metatrader_dir_path=self.metatrader_dir_path, verbose=verbose, db=self.db,
                             time_frame='H1',
                             symbols=self.symbols)

        self.dwx.subscribe_symbols(self.symbols)
        self.time_frame = 'H1'
        for i in self.symbols:
            symbo = [i, self.time_frame]
            self.dwx.subscribe_symbols_bar_data([symbo])

            start: int = int(str((datetime.utcnow() - timedelta(days=30)).timestamp()).split('.')[0])
            end: int = int(datetime.utcnow().timestamp())

            # last 60 days
            self.dwx.get_historic_data(i, self.time_frame, start, end)

        # account information is stored in self.dwx.account_info.
        print("Account info:", self.dwx.account_info.__str__())

        # Start DWX server
        self.dwx.start()

        # wait for stop event

    def on_bar_data(self,

                    symbol,
                    time_frame,
                    time: [] = None,
                    open: [float] = None,
                    high: [float] = None,
                    low: [float] = None,
                    close: [float] = None,
                    volume: [int] = None
                    ):
        """
        Handles logic when new bar data is received.

        Parameters:
            symbol (str): Trading symbol.
            time_frame (str): Time frame of the bar data.
            time (list): List of timestamp data.
            open_ (list): List of open prices.
            high (list): List of high prices.
            low (list): List of low prices.
            close (list): List of close prices.
            volume (list): List of trading volumes.
        """
        # Handle bar data logic

        
    
        print(f'on_bar_data: {symbol}, {time_frame}, {time}', end='\r')
        if self.verbose:
           
          self.bar_data_count += 1

    def on_historic_data(self, symbol: str = '', time_frame: str = '', data: list = None):

        
        """
        Handles logic when historic market data is received.

        Parameters:
            symbol (str): Trading symbol.
            time_frame (str): Time frame of the historic data.
            data (list): List of historic market data.
        """
        # Handle historic data logic
        history = pd.DataFrame(data, columns=['time', 'symbol', 'time_frame', 'open', 'high', 'low', 'close', 'volume'])

        if self.verbose:
            history['symbol'] = symbol
            history['time_frame'] = time_frame
            history.to_csv(self.dwx.path_historic_data, index=True,
                           header=True)
            print('historic number' + str(self.bar_data_count) + " " + str(history))

    def on_historic_trades(self, symbol: str = 'AUDUSD', time_frame: str = 'H1', trades: list = None):
        """
        Handles logic when historic trades data is received.

        Parameters:
            symbol (str): Trading symbol.
            time_frame (str): Time frame of the historic trades.
            trades (list): List of historic trades data.
        """
        # Handle historic trades logic

        print(f'historic_trades: {len(self.dwx.historic_trades)}')
        self.dwx.historic_trades = pd.DataFrame(trades, columns=['time', 'time_frame', 'symbol', 'order_id',
                                                                 'price', 'amount', 'comment', 'expiration',
                                                                 'order_type', 'stoploss', 'takeprofit'])
        if self.verbose:
            self.dwx.historic_trades['symbol'].values = symbol
            self.dwx.historic_trades['time_frame'].values = time_frame
            self.dwx.historic_trades.to_csv(join(self.dwx.path_historic_trades),

                                            index=False, header=True)

            print('historic_trades number' + str(self.bar_data_count) + " " + str(self.dwx.historic_trades))

    def on_message(self, message):
        """
        Handles logic when a message is received.

        Parameters:
            message (dict): Received message data.
        """
        # Handle incoming messages
        if message['type'] == 'ERROR':
            print(message['type'], '|', message['error_type'], '|', message['description'])
            self.dwx.server_status['server_status'] = 'ERROR'
            self.dwx.server_status['error_type'] = message['error_type']
            self.dwx.server_status['description'] = message['description']
        elif message['type'] == 'INFO':
            print(message['type'], '|', message['message'])
            self.dwx.server_status['server_status'] = 'OK'
            self.dwx.server_status['message'] = message['message']

    # triggers when an order is added or removed, not when only modified.
    def on_order_event(self):
        """
        Handles logic when an order event occurs.
        """
        # Handle order events

        print(f'on_order_event. open_orders: {len(self.dwx.open_orders)} open orders')
        self.dwx.server_status['open_orders'] = len(self.dwx.open_orders)
        self.dwx.server_status['server_status'] = 'OK'

    def get_lot_size(self):
        """
        Calculates lot size.

        Returns:
            float: Calculated lot size.
        """
        # Calculate lot size logic
        i = 0.001 + random() * 0.010
        while True:
            i += 0.001 + random() * 0.019
            if i > 100:
                i -= 100
            break

        return 0.02 + i

    
    def trade_days(self, set_trading_days='yes', ea_start_day='Monday', ea_stop_day='Friday', ea_start_time='00:00',
                   ea_stop_time='23:59'):
        """
        Checks if it's a trading day based on the specified parameters.

        Parameters:
            set_trading_days (str): Flag to set trading days.
            ea_start_day (str): Start day for EA trading.
            ea_stop_day (str): Stop day for EA trading.
            ea_start_time (str): Start time for EA trading.
            ea_stop_time (str): Stop time for EA trading.

        Returns:
            bool: True if it's a trading day, False otherwise.
        """
        # Check if it's a trading day logic
        
        if set_trading_days == 'no':
            return True
        star_day = 0
        stop_day = 0
        if ea_start_day == 'Monday':
            star_day = 1

        elif ea_start_day == 'Tuesday':
            star_day = 2

        elif ea_start_day == 'Wednesday':
            star_day = 3

        elif ea_start_day == 'Thursday':
            star_day = 4

        elif ea_start_day == 'Friday':
            star_day = 5

        elif ea_start_day == 'Saturday':
            star_day = 6

        elif ea_start_day == 'Sunday':
            star_day = 7

        if ea_stop_day == 'Monday':
            stop_day = 1

        if ea_stop_day == 'Tuesday':
            stop_day = 2

        if ea_stop_day == 'Wednesday':
            stop_day = 3

        if ea_stop_day == 'Thursday':
            stop_day = 4

        if ea_stop_day == 'Friday':
            stop_day = 5

        if ea_stop_day == 'Saturday':
            stop_day = 6

        if ea_stop_day == 'Sunday':
            stop_day = 7

        today = datetime.today().weekday()

        self.start_time = datetime.strptime(ea_start_time, "%H:%M:%S").time()
        self.stop_time = datetime.strptime(ea_stop_time, "%H:%M:%S").time()

        current_time = datetime.now().time()

        if star_day < stop_day:
            if star_day < today < stop_day:
                return True
            elif today == star_day:
                if current_time >=self. start_time:
                    return True
                else:
                    return False
            elif today == stop_day:
                if current_time < self.stop_time:
                    return True
                else:
                    return False
        elif star_day > stop_day:
            if star_day < today or today < stop_day:
                return True
            elif today == star_day:
                if current_time >= self.start_time:
                    return True
                else:
                    return False
            elif today == stop_day:
                if current_time < self.stop_time:
                    return True
                else:
                    return False
        elif star_day == stop_day:
            start_datetime = datetime.combine(datetime.today().date(), self.start_time)
            stop_datetime = datetime.combine(datetime.today().date(), self.stop_time)

            if self.start_time < self.stop_time:
                if start_datetime <= datetime.now() <= stop_datetime:
                    return True
                else:
                    return False
            else:
             
             if start_datetime <= datetime.now() or datetime.now() <= stop_datetime:
                    return True
             else:
                    return False

        return False

 
    def get_signal(self, time=[0], open_=[0], high=[0], low=[0], close=[0], volume=[0]):
      """
     Generates trading signals based on market data.

     Args:
        time (list): List of time values.
        open_ (list): List of open prices.
        high (list): List of high prices.
        low (list): List of low prices.
        close (list): List of close prices.
        volume (list): List of volume values.

    Returns:
        float: Accuracy score of the machine learning model.

     """
    # Create a DataFrame for input data
      df = pd.DataFrame({
        'time': time,
        'close': close,
        'open': open_,
        'high': high,
        'low': low,
        'tick_volume': volume  # Assuming this is tick volume data
    })
    
      if df.empty:
          self.dwx.server_status['server_status'] = 'ERROR'
          self.dwx.server_status['error_type'] = 'NO_DATA'
          self.dwx.server_status['description'] = 'No valid data'
          self.handle_no_valid_data()
          return 0
    
    # Create buy or sell signals (1 for buy, -1 for sell)
      buy_or_sell_signal = np.where(df['close'] > df['open'], 1, -1)
      print('buy_or_sell_signal:', buy_or_sell_signal[0]
            )
    
# Generate sample candlestick and moving average data
      np.random.seed(42)
      num_samples = 1000

      data = {
    'open': np.random.rand(num_samples) * 10 + 50,
    'high': np.random.rand(num_samples) * 5 + 60,
    'low': np.random.rand(num_samples) * 5 + 45,
    'close': np.random.rand(num_samples) * 10 + 50,
    'moving_average': np.random.rand(num_samples) * 5 + 55,
    'target': np.random.choice([-1, 1], size=num_samples)}
      
      print('data:', data)

      df = pd.DataFrame(data)

    # Feature engineering
      df['candle_body'] = np.where(df['close'] > df['open'], 1, -1)
      df['upper_shadow'] = df['high'] - np.maximum(df['open'], df['close'])
      df['lower_shadow'] = np.minimum(df['open'], df['close']) - df['low']

# Drop unnecessary columns
      df = df.drop(['open', 'high', 'low', 'close'], axis=1)

# Fill missing values with mean
      imputer = SimpleImputer(strategy='mean')
      df = pd.DataFrame(imputer.fit_transform(df), columns=df.columns)

# Split the data into features (X) and target variable (y)
      X = df.drop('target', axis=1)
      y = df['target']

# Split the data into training and testing sets
      X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Standardize the features
      scaler = StandardScaler()
      X_train_scaled = scaler.fit_transform(X_train)
      X_test_scaled = scaler.transform(X_test)

# Train a machine learning model (Random Forest Classifier)
      model = RandomForestClassifier(random_state=42, n_estimators=100)
      model.fit(X_train_scaled, y_train)
# Make predictions on the test set
      y_pred = model.predict(X_test_scaled)
# Evaluate the model
      print("Accuracy:", accuracy_score(y_test, y_pred))
      print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))
      print("Classification Report:\n", classification_report(y_test, y_pred))
      self.dwx.server_status['accuracy'] = self.calculate_accuracy(model, X_train, y_train)
      return buy_or_sell_signal[0]


    def handle_no_valid_data(self):
        """ Handle no valid data   
        """
        self.dwx.server_status['server_status'] = 'ERROR'
        self.dwx.server_status['error_type'] = 'NO_VALID_DATA'
  
    def print_evaluation_metrics(self, y_test, y_pred):
        print(confusion_matrix(y_test, y_pred))
        print(classification_report(y_test, y_pred))

    def update_server_status(self):
        # Implement server status update logic here
        
        self.dwx.server_status['server_status'] = 'READY'



    def calculate_accuracy(self, model, x_train, y_train):
        accuracy = model.score(x_train, y_train)
        print("Accuracy:", accuracy)
        scores = cross_val_score(model, x_train, y_train, cv=5)  # 5-fold cross-validation
        print("Cross-validation scores:", scores)
        print("Mean Accuracy:", scores.mean())
        print("Standard Deviation:", scores.std())
        print("Accuracy on Training Set:", scores.mean())
        print("Accuracy on Test Set:", scores.mean())
        print("Accuracy on Training Set:", scores.mean())

        return scores

    # Function to generate random numbers following Benford's Law
    def generate_benfords_numbers(self, size):
        """
        Generate random numbers following Benford's Law
        :param size:
        :return:
        """
       
        numbers = []
        leading_digits = [str(i) for i in range(1, 10)]  # Leading digits 1 to 9
        while len(numbers) < size:
            # Generate random number following Ben-ford's Law
            import random
            number = int(random.choice(leading_digits) + ''.join(random.choices('0123456789', k=random.randint(1, 8))))
            numbers.append(number)
        return numbers
    
    def on_tick(self, symbol='AUDUSD', bid=0.0, ask=0.0, bar_data=None):
        """
         Handles trading logic on each tick.

         Args:
         use_trade_day (bool): Flag indicating whether to check if trading is allowed on the current day.
         market_data (pd.DataFrame): DataFrame containing market data.
         bar_data: Additional bar data for signal generation.

         :param bar_data:
         :param symbol:
         :param bid:
         :param ask:

        """

        self.dwx.server_status['server_status'] = 'OK'

        self.dwx.server_status['last_modification_time'] = datetime.utcnow()
        self.dwx.server_status['last_open_time'] = self.last_open_time

        # Extract symbol from market_data
        use_trade_day = self.use_trade_day

        if use_trade_day:
            # Check if trading is allowed today
            self.trade_day = self.trade_days(ea_stop_day='Friday',
                                             ea_start_day='Sunday',
                                             ea_start_time='09:00:00',
                                             ea_stop_time='23:30:00'

                                             )
            if not self.trade_day:
                print('Trading is not allowed today: ' + date.today().strftime('%Y-%m-%d %H:%M:%S'))
                self.dwx.server_status['server_status'] = 'ERROR'
                self.dwx.server_status['error_type'] = 'TRADE_NOT_ALLOWED today ' + date.today().strftime(   '%Y-%m-%d' '%H:%M:%S')
            else:
                print('Trading is allowed today!')
                self.dwx.server_status['server_status'] = 'OK'
                self.dwx.server_status['info'] = 'Trading is allowed today!'

            dat = pd.DataFrame(bar_data, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume'])

            self.signal_on_tick=self.get_signal(

                time=dat['time'],
                open_=dat['open'],
                high=dat['high'],
                low=dat['low'],
                close=dat['close'],
                volume=dat['tick_volume']

            )



            now = datetime.utcnow()

            print('on_tick:', now, symbol, bid, ask)

            # to test trading.
            # this will randomly try to open and close orders every few seconds.
         
            if self.signal_on_tick == 1:
                order_type = 'buystop'
                price = ask
                self.dwx.open_order(symbol=symbol, order_type=order_type,
                                    price=price, lots=self.lot,
                                    magic=self.magic_number,
                                    stop_loss=price - self.stoploss,
                                    take_profit=price + self.takeprofit,
                                    comment='ZONES @' + order_type.__str__() + 'TRADE ' + now.__str__())
            elif self.signal_on_tick == -1:
                    order_type = 'sellstop'
                    price = ask
                    self.dwx.open_order(symbol=symbol, order_type=order_type,
                                            price=price, lots=self.lot,
                                            magic=self.magic_number,
                                            stop_loss= price + self.stoploss,
                                            take_profit= price- self.takeprofit,
                                            comment='ZONES @' + order_type + 'TRADE ' + now.__str__())

            if now > self.last_modification_time + timedelta(seconds=60):
                self.last_modification_time = now
                for ticket in self.dwx.open_orders.keys():
                  self.dwx.close_order(ticket, lots= self.lot)
            if len(self.dwx.open_orders) >= 50 and now > self.last_modification_time + timedelta(seconds=3600) and self.calculate_profitability(
                entry_price=self.dwx.open_orders[self.dwx.open_orders.keys()[0]]['open_price'],
                exit_price=self.dwx.open_orders[self.dwx.open_orders.keys()[0]]['close_price'],
                quantity=self.dwx.open_orders[self.dwx.open_orders.keys()[0]]['lots'],
                transaction_costs=self.dwx.open_orders[self.dwx.open_orders.keys()[0]]['transaction_costs'] or 0
            ) <= 10:
                #self.dwx.close_all_orders()
                self.dwx.close_orders_by_symbol(symbol)
            # self.dwx.close_orders_by_magic(0)

    def calculate_profitability(self,entry_price=0.0, exit_price=0.0, quantity=0.0, transaction_costs=0.0):
        """
             Calculate trade profitability.

         Parameters:
         - entry_price: The price at which the trade was entered.
         - exit_price: The price at which the trade was exited.
         - quantity: The quantity of the traded asset.
         - transaction_costs: Any transaction costs associated with the trade (default is 0).

         Returns:
          - profit: The calculated profit.
           """

           # Calculate the total cost of the trade (entry cost + transaction costs)
        total_cost = entry_price * quantity + transaction_costs
    # Calculate the total revenue from the trade (exit price * quantity)
        total_revenue = exit_price * quantity

    # Calculate the profit (total revenue - total cost)
        profit = total_revenue - total_cost
        self.dwx.server_status['profitability'] = '' + str(profit) + '%'
        return profit
    

    def generate_benfords_numbers(self,size=0):
        """
         Generate random numbers following Benford's Law
         :param size:
         :return:
        """
        leading_digits = [int(str(i)[0]) for i in range(1, 10)]  # Leading digits 1 to 9
        numbers = []
        import random
        while len(numbers) < size:
            # Generate random number following Benford's Law
            number = int(str(random.choice(leading_digits)) + ''.join(str(random.randint(0, 9)) for _ in range(random.randint(1, 8))))
            numbers.append(number)

        return numbers
    
    def calculate_lot_size(self,data_size, min_lot_size=0.01, max_lot_size=10.0):

     # Generate random numbers following Benford's Law
       benfords_numbers = self.generate_benfords_numbers(data_size)
       lot_sizes = np.interp(benfords_numbers, (min(benfords_numbers), max(benfords_numbers)), (min_lot_size, max_lot_size))
       
       print('benfords_numbers' , benfords_numbers)
       print('lot_sizes', lot_sizes)
       
       if lot_sizes[0] > max_lot_size:
            lot_sizes[-1] = max_lot_size/2
       elif lot_sizes[-1] < min_lot_size:
            lot_sizes[-1] += min_lot_size
    
       if lot_sizes[-1] > max_lot_size:
            lot_sizes[-1] = max_lot_size/2
       elif lot_sizes[-1] < min_lot_size:
            lot_sizes[-1] += min_lot_size/0.01
       print('lot_sizes', lot_sizes)
       return lot_sizes[-1]
       

