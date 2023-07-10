import tkinter
from tkinter import RAISED, RIDGE


class Account(tkinter.Frame):
    def __init__(self, parent, controller, _account_info_DB):

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

        account_info_text = tkinter.Label(self, text="Account Information")
        account_info_text.grid(row=0, column=0, padx=10, pady=10, sticky=tkinter.W)
        account_info_text = tkinter.Text(
            self, height=10, width=500,background='lightblue',border=3,state=
            tkinter.DISABLED
            ,font=("Arial", 12)
        )
        account_info_text.grid(row=1, column=0, padx=10, pady=10, sticky=tkinter.W)
        account_info_text.insert(tkinter.END, _account_info_DB)
