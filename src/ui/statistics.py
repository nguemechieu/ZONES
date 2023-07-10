import tkinter


class Statistics(tkinter.Frame):
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)
        self.controller = controller
        self.parent = parent

        self.label_name = tkinter.Label(parent, text="Name:")
        self.label_name.grid(row=0, column=0, padx=5, pady=5)
        self.label_name_entry = tkinter.Entry(parent, textvariable=tkinter.StringVar())
        self.label_name_entry.grid(row=0, column=1, padx=5, pady=5)

        self.label_age = tkinter.Label(parent, text="Age:")
        self.label_age.grid(row=1, column=0, padx=5, pady=5)
        self.label_age_entry = tkinter.Entry(parent, textvariable=tkinter.StringVar())
        self.label_age_entry.grid(row=1, column=1, padx=5, pady=5)

        self.label_gender = tkinter.Label(parent, text="Gender:")
        self.label_gender.grid(row=2, column=0, padx=5, pady=5)
        self.label_gender_entry = tkinter.Entry(parent, textvariable=tkinter.StringVar())
        self.label_gender_entry.grid(row=2, column=1, padx=5, pady=5)