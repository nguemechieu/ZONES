import tkinter
class Service(tkinter.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.parent = parent
        self.label = tkinter.Label(self.master, text="ZONES EA   |MT4 Trader | Version 1.0.0| Service")
        self.label.pack(fill=tkinter.X)
        self.label2 = tkinter.Label(self.master, text="Developed by NGUEMECHIEU NOEL MARTIAL  in 2021")
        self.label2.pack(fill=tkinter.X)
        self.label3 = tkinter.Label(self.master, text="Contact: +1 302-317-6610")
        self.label3.pack(fill=tkinter.X)
        self.label4 = tkinter.Label(self.master, text="Email: nguemechieu@live.com")
        self.label4.pack(fill=tkinter.X)


