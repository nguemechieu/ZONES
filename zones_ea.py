import smtplib
import tkinter
from datetime import datetime
from email.mime.text import MIMEText
from tkinter import filedialog, RAISED, BOTTOM

from src.Trade import Trades
# NOEL M NGUEMECHIEU
# https://github.com/nguemechieu/telegramMt4Trader
from src.db import Db
from src.ui.News import News
from src.ui.forgot_password import ForgotPassword
from src.ui.home import Home
from src.ui.login import Login
from src.ui.register import Register
from src.ui.reset_password import ResetPassword


def send_email(subject: str = "", body: str = "", sender: str = "",
               recipients=None, password: str = ""):
    if recipients is None:
        recipients = ["recipient1@gmail.com", "recipient2@gmail.com"]
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        smtp_server.login(sender, password)
        smtp_server.sendmail(sender, recipients, msg.as_string())
        print("Message sent!")


class About(tkinter.Frame):
    def __init__(self, master):
        tkinter.Frame.__init__(self, master)
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


class App(object):

    def __init__(self):
        self.controller = self
        self.frames = {}

        self.filename = None
        self.Messagebox = None
        self.master = tkinter.Tk()

        self.master.geometry("1530x780")
        self.master.title("ZONES EA   |MT4 Trader " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.master.resizable(width=True, height=True)
        self.master.iconbitmap(r"src\Images\zones_ea.ico")
        self.master.config(bg="gray")
        self.db = Db()
        self.trades = Trades()
        self.trades.strategy('EURUSD')
        self.menubar = tkinter.Menu(self.master)

        self.file_menu = tkinter.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open", command=lambda: self.open_file())
        self.file_menu.add_command(label="Save", command=lambda: self.save_file())
        self.file_menu.add_separator()
        self.file_menu.add_command(label="connect", command=lambda: self.connect())
        self.login = tkinter.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Login", menu=self.login)
        self.login.add_command(label="Login", command=lambda: self.show_pages("Login"))
        self.login.add_command(label="Register", command=lambda: self.show_pages("Register"))
        self.help_menu = tkinter.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.master.quit)
        self.master.config(menu=self.menubar)

        self.frame = tkinter.Frame(self.master, relief=RAISED)
        self.master.iconbitmap(r"src\images\zones_ea.ico")
        # self.master.iconphoto(True, tkinter.PhotoImage(file=r"src\images\zones_ea.ico"))
        self.db = Db()
        self.trades = Trades()
        self.trades.strategy('EURUSD')

        #self.frame.pack(fill=tkinter.BOTH, expand=1)
        self.master.protocol("WM_DELETE_WINDOW", self.master.quit)
        self.master.mainloop()

    def delete_frame(self):
        for _frame in self.master.winfo_children():
            _frame.destroy()

    def show_pages(self, page: str):
        self.delete_frame()
        for _frame in self.master.winfo_children():
            _frame.destroy()

        self.master.title(
            "ZONES EA  |AI POWERED MT4 Trader |    " + page + " copyright " + datetime.strftime(datetime.now(), "%Y")
            + ", NGUEMECHIEU NOEL  MARTIAL")
        if page in ['Login', 'Register', 'ForgotPassword', 'ResetPassword', 'Home', 'About', 'News']:
            frames = [Login, Register, ForgotPassword, ResetPassword, Home, About, News
                      ]
            for frame in frames:
                if page == frame.__name__:
                    frame = frame(self)
                    frame.tkraise()

    def connect(self):
        self.delete_frame()
        for _frame in self.master.winfo_children():
            _frame.destroy()
        self.frame = Login(self)

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
                self.trades.save_to_file(self)
                self.show_pages("Login")
            except Exception as e:
                self.show_error(str(e))
        self.master.protocol("WM_DELETE_WINDOW", self.master.quit)
        self.show_pages("Login")

    def mainloop(self):
        self.master.mainloop()


if __name__ == '__main__':
    App()
