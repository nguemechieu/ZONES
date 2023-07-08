import tkinter


class About(tkinter.Frame):
    def __init__(self, parent, controller):
        super().__init__()
        self.controller = controller
        self.parent = parent
        self.label = tkinter.Label(self.master, text="ZONES EA   |MT4 Trader | Version 1.0.0| About")
        self.label.pack(fill=tkinter.X)
        self.label2 = tkinter.Label(self.master, text="Developed by NGUEMECHIEU NOEL MARTIAL  in 2021")
        self.label2.pack(fill=tkinter.X)
        self.label3 = tkinter.Label(self.master, text="Contact: +1 302-317-6610")
        self.label3.pack(fill=tkinter.X)
        self.label4 = tkinter.Label(self.master, text="Email: nguemechieu@live.com")
        self.label4.pack(fill=tkinter.X)
        self.label5 = tkinter.Label(self.master, text="Github: https://github.com/nguemechieu/ZONES_EA")
        self.label5.pack(fill=tkinter.X)
        self.label6_description = tkinter.Label(self.master, text="Description:")
        self.label6_description.pack(fill=tkinter.X)
        self.label6 = tkinter.Label(self.master, text="ZONES EA is a trading platform based on MT4. It allows you to "
                                                      "trade on the basis of your strategy."
                                                      "The platform is based on the MT4 Trader, which is a trading "
                                                      "platform based on the MetaTrader."
                                                      "The application also enable you to send emails, message ,"
                                                      "photos and videos to your friends. and telegram channel.")



