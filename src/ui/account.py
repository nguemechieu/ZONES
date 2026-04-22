import tkinter


class Account(tkinter.Frame):
    def __init__(self, parent, controller):
        self.account_info_DB = {}
        self.account_profit = tkinter.StringVar()
        self.submit_lots = None
        self.balance = 0
        self.transactions = []
        tkinter.Frame.__init__(self, parent)
        self.controller = controller
        self.parent = parent

        # {ACCOUNT_NUMBER:[{'current time': 'CURRENT_TIME', 'account_name': 'ACCOUNT_NAME',
        # 'account_balance': ACCOUNT_BALANCE, 'account_equity': ACCOUNT_EQUITY,
        # 'account_profit': ACCOUNT_PROFIT, 'account_free_margin': ACCOUNT_FREE_MARGIN,
        # 'account_leverage': ACCOUNT_LEVERAGE}]}

        account_info_text0 = tkinter.Label(self.parent, text="ACCOUNT INFO", font=("Arial", 10))
        account_info_text0.grid(row=1, column=1, padx=10, pady=10, sticky=tkinter.W)

        self.account_info_text = tkinter.Text(
            self.parent,

            wrap=tkinter.WORD,
            font=("Arial", 10), background='black', foreground='lightgreen')

        self.account_info_text.grid(row=1, column=2, padx=500, pady=50)

        self.account_info_text.insert(tkinter.END, "ACCOUNT NUMBER " + str(controller.zmq.dwx.account_info) + "\n")
