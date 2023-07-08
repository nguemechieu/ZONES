import smtplib
import tkinter

from datetime import datetime
from email.mime.text import MIMEText
from tkinter import filedialog, RAISED, BOTTOM
# NOEL M NGUEMECHIEU
# https://github.com/nguemechieu/telegramMt4Trader
from src.db import Db
from src.trade import Trade
from src.ui.News import News
from src.ui.about import About
from src.ui.forgot_password import ForgotPassword
from src.ui.home import Home
from src.ui.login import Login
from src.ui.register import Register
from src.ui.reset_password import ResetPassword
from src.ui.services import Service


def send_email(subject: str = "", body: str = "", sender: str = "",
               recipients=None, password: str = ""):
    if recipients is None:
        recipients = ["r@gmail.com", "recipient2@gmail.com"]
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        smtp_server.login(sender, password)
        smtp_server.sendmail(sender, recipients, msg.as_string())
        print("Message sent!")


class App(tkinter.Tk):
    trades: Trade

    def __init__(self):
        tkinter.Tk.__init__(self)
        self.controller = self
        self.parent = self.master
        self.frames = {}
        self.filename = None
        self.Messagebox = None
        self.geometry("1530x780")
        self.title("ZONES EA   |MT4 Trader " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.resizable(width=True, height=True)
        self.iconbitmap(r"src\Images\zones_ea.ico")
        self.configure(background="lightblue", relief=RAISED, border=2, bg="lightblue")

        self.db = Db()
        self.trades = Trade()

        self.menubar = tkinter.Menu(self.master)
        self.file_menu = tkinter.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open", command=lambda: self.open_file())
        self.file_menu.add_command(label="Save", command=lambda: self.save_file())
        self.file_menu.add_separator()
        self.file_menu.add_command(label="open an account", command=lambda :self.show_pages("Login"))
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.quit)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="connect", command=lambda: self.connect())
        self.login = tkinter.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Login", menu=self.login)
        self.login.add_command(label="Login", command=lambda: self.show_pages("Login"))
        self.login.add_command(label="Register", command=lambda: self.show_pages("Register"))
        self.service_menu = tkinter.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Services", menu=self.service_menu)
        self.service_menu.add_command(label="Service", command=lambda: self.show_pages("Service"))
        self.service_menu.add_separator()
        self.trade_menu = tkinter.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Trade", menu=self.trade_menu)
        self.trade_menu.add_command(label="Trade", command=lambda: self.show_pages("Trade"))

        self.trade_menu.add_separator()

        self.news_menu = tkinter.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="News", menu=self.news_menu)
        self.news_menu.add_command(label="News", command=lambda: self.controller.show_pages("News"))


        self.trade_menu.add_separator()


        self.help_menu = tkinter.Menu(self.menubar, tearoff=0)

        self.menubar.add_cascade(label="Help", menu=self.help_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.quit)
        self.config(menu=self.menubar)

        self.frame = tkinter.Frame(self.master, relief=RAISED, border=2, bg="lightblue")
        self.iconbitmap(r"src\images\zones_ea.ico")
        # self.master.iconphoto(True, tkinter.PhotoImage(file=r"src\images\zones_ea.ico"))
        self.frame.pack(fill=tkinter.BOTH, expand=1)
        self.mainloop()

    def show_pages(self, param):

        self.delete_frame()
        for _frame in self.winfo_children():
            _frame.destroy()

        self.title(
            "ZONES EA  |       AI POWERED MT4 Trader |    " + param + " Copyright " + datetime.strftime(datetime.now(),
                                                                                                        "%Y")
            + ", NGUEMECHIEU NOEL  MARTIAL")
        if param in ['Login', 'Register', 'ForgotPassword', 'ResetPassword', 'Home', 'About', 'News']:
            frames = [Service, Login, Register, ForgotPassword, ResetPassword, Home, About, News
                      ]
            for frame in frames:
                if param == frame.__name__:
                    frame = frame( self,self.controller)
                    frame.tkraise()

    def delete_frame(self):
        for _frame in self.winfo_children():
            _frame.destroy()

    def connect(self):
        self.delete_frame()
        for _frame in self.winfo_children():
            _frame.destroy()
        self.frame = Login(self, self.controller)

    def show_error(self, param):
        if param is not None:
            self.Messagebox = tkinter.Message(self.master, text=param, width=300)
            print(param)
            self.Messagebox.pack(side=BOTTOM)
            self.Messagebox.after(3000, self.Messagebox.destroy)

    def open_file(self):
        filename = filedialog.askopenfilename()
        if filename:
            try:
                self.trades.load_from_file(filename)
                self.show_pages("Home")
            except Exception as e:
                self.show_error(str(e))

    def save_file(self):
        self.filename = filedialog.asksaveasfilename()
        if self.filename is not None:
            try:
                self.trades.save_to_file(self.filename)
                self.show_pages("Login")
            except Exception as e:
                self.show_error(str(e))


if __name__ == '__main__':
    App()
else:
    exit(1)
