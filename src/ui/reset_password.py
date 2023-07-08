import tkinter


class ResetPassword(tkinter.Frame):
    def __init__(self,parent, controller):
        super().__init__()
        self.master = parent
        self.back = None
        self.reset = None
        self.parent = self.master
        self.controller = controller

        self.email = tkinter.StringVar()
        self.password = tkinter.StringVar()
        self.confirm_password = tkinter.StringVar()
        self.error = tkinter.StringVar()
        self.error.set("")
        self.error_label = tkinter.Label(self.parent, textvariable=self.error, bg="white", fg="red")

        self.email_label = tkinter.Label(self.parent, text="Email", bg="white", fg="black")

        self.email_entry = tkinter.Entry(self.parent, textvariable=self.email, bg="white", fg="black")

        self.password_label = tkinter.Label(self.parent, text="Password", bg="white", fg="black")

        self.password_entry = tkinter.Entry(self.parent, textvariable=self.password, show="*", bg="white", fg="black")

        self.confirm_password_label = tkinter.Label(self.parent, text="Confirm Password", bg="white", fg="black")

        self.confirm_password_entry = tkinter.Entry(self.parent, textvariable=self.confirm_password, show="*",
                                                    bg="white", fg="black")

        self.reset_button = tkinter.Button(self.parent, text="Reset", bg="white", fg="black",
                                           command=lambda: self.reset)

        self.back_button = tkinter.Button(self.parent, text="Back", bg="white", fg="black", command=lambda: self.back)
