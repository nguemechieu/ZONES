import tkinter


class About(tkinter.Frame):
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)
        self.controller = controller
        self.parent = parent

        self.label = tkinter.Label(parent, text="About")
        self.label.pack(side=tkinter.TOP)
        self.text_box = tkinter.Text(parent, width=500, height=500)
        self.text_box.pack(fill=tkinter.BOTH, expand=1)
        self.text_box.insert(tkinter.END, "This is ZONES! ZONES is a powerful ai trading software used for"
                                          "professional investment and trading \n\n\n")
