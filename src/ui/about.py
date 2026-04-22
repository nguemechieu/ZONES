import tkinter


class About(tkinter.Frame):
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)
        self.controller = controller

        self.label = tkinter.Label(parent, text="About", background="black", foreground="white",
                                   font=("Arial", 20, "bold"),
                                   padx=10, pady=10, relief=tkinter.RIDGE)

        self.label.config(font=("Arial", 20, "bold"))
        self.label.config(background="black")
        self.label.config(foreground="white")
        self.label.config(padx=10)
        self.label.config(pady=10)
        self.label.config(relief=tkinter.RIDGE)
        self.label.pack(fill=tkinter.BOTH, expand=1)
        self.go_back_button = tkinter.Button(parent, text="Go Back", command=lambda: self.controller.show_pages("Home"))
        self.go_back_button.pack()
        self.text_box = tkinter.Text(parent, width=500, height=500, background="black", foreground="white")
        self.text_box.pack(fill=tkinter.BOTH, expand=1)
        self.text_box.insert(tkinter.END,
                             "Welcome to ZONES! \n"
                             "\nZONES is a powerful AI trading system that allows you to train your own neural network "
                             "to predict the price of a stock. \n"
                             "\nZONES is developed by    Nguemechieu Noel Martial  since 2022. \n and is based on the "
                             "MT4 Metatrader software and zeromq connector protocol. \n"
                             "\nZONES is license under apache2 and require you to follow all requirements before "
                             "using or . \n"
                             "\n upgrading the project."
                             "It is a combination of the following software: \nMT4 Metatrader  \nZeromq Python \n "
                             "Telegram \n"
                             "Tensorflow \n Keras \n Python >=3.11 \nOanda \nCoinbase Pro \n Binance.us \n ChatGpt \n"

                             )

