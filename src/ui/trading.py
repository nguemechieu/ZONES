
import random
import tkinter
import tkinter as tk

import matplotlib.dates as mpdates
import matplotlib.dates as mpl_dates
import pandas as pd






class Trading(tkinter.Frame):
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.start_trading = None
        self.stop_trading = None
        self.trading_Label = tkinter.Label(parent, text="Session  :", font=("Arial", 20, "bold"),
                                           border=10,
                                           highlightthickness=2,
                                           background="black",
                                           foreground="white")
        self.trading_Label.pack(
            side=tkinter.TOP, padx=10, pady=10, ipady=10,
            ipadx=10
        )
        self.canvas = tkinter.Canvas(parent, width=1300, height=700,
                                     confine=True, border=20, background="black", highlightthickness=2, bd=2
                                     )
        self.canvas.pack(
            side=tkinter.LEFT, padx=10, pady=10, ipady=10, ipadx=10
        )
        self.canvas.create_rectangle(0, 0, 1300, 690, fill="white")
        self.canvas.create_rectangle(0, 0, 1300, 690, fill="black")

        self.navigator_bar = tkinter.Button(parent, text="Navigator", font=("Arial", 15, "bold"),
                                            command=lambda: self.controller.show_pages("Navigator"))
        self.navigator_bar.pack(
            side=tkinter.RIGHT, padx=10, pady=10, ipady=10,
            ipadx=10
        )

        self.start_button = tkinter.Button(parent, text="Start", font=("Arial", 15, "bold"), fg="lightgreen",
                                           command=lambda: self.start_trading)
        self.start_button.pack(side=tkinter.TOP, padx=10, pady=10, ipady=10)

        self.stop_button = tkinter.Button(parent, text="Stop", font=("Arial", 15, "bold"), fg="lightgreen",
                                          command=lambda: self.stop_trading)
        self.stop_button.pack(side=tkinter.TOP, padx=10, pady=10, ipady=10)

