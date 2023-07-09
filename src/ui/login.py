import tkinter
from tkinter import messagebox


class Login(tkinter.Frame):
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(self, parent)
        self.controller = controller
        self.parent = parent

        self.frames = {}
        self.grid(padx=300, pady=100)
        self.error = tkinter.StringVar()

        self.username_label = tkinter.Label(self.master, text="Username")
        self.username_label.grid(row=1, column=0)
        self.username = tkinter.StringVar()
        self.username_entry = tkinter.Entry(self.master, textvariable=self.username, background='lightblue')
        self.username_entry.grid(row=1, column=1)
        self.password_label = tkinter.Label(self.master, text="Password")
        self.password_label.grid(row=2, column=0)
        self.password = tkinter.StringVar()
        self.password_entry = tkinter.Entry(self.master, textvariable=self.password, show="*", bg="lightblue")
        self.password_entry.grid(row=2, column=1)

        self.remember_me = tkinter.BooleanVar()
        self.remember_me.set(True)
        self.remember_me_label = tkinter.Checkbutton(self.master, text="Remember Me", variable=self.remember_me)
        self.remember_me_label.grid(row=3, column=2)

        self.login_button = tkinter.Button(self.master, text="Login",
                                           command=lambda: self.controller.show_pages(param="Home"))
        self.login_button.grid(row=4, column=2)

        self.register_button = tkinter.Button(self.master, text="Register",
                                              command=lambda: self.controller.show_pages(param='Register'))
        self.register_button.grid(row=4, column=0)

        self.forgot_password_button = tkinter.Button(self.master, text="Forgot Password",
                                                     command=lambda: self.controller.show_pages(
                                                         param='ForgotPassword'))
        self.forgot_password_button.grid(row=5, column=1)

        self.username_entry.focus_set()
        self.password_entry.focus_set()
        self.master.bind("<Return>", lambda e: self.login())

    def login(self):
        username = self.username.get()
        password = self.password.get()

        if username == "" or password == "":
            messagebox.showerror("Error", "Please enter username and password")
            return False

        try:
            self.controller.db.cur.execute("USE " + self.controller.db.database)
            self.controller.db.cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username,
                                                                                                         password))
            result = self.controller.db.cur.fetchone()
            if result and username == self.controller.username.get() and password == self.controller.passwordx.get():
                self.controller.username.set(username)
                self.controller.passwordx.set(password)
                self.controller.show_pages(page='Home')

                return True
            else:
                messagebox.showerror("Error", "Invalid username or password")
                return False

        except Exception as e:
            messagebox.showerror("Error", e.args[0])
        return False
