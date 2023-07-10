import smtplib
import sys
import tkinter
from datetime import datetime
from email.mime.text import MIMEText
from tkinter import filedialog, RAISED, BOTTOM
# NOEL M NGUEMECHIEU
# https://github.com/nguemechieu/zones
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
        self.frames = {

        }
        self.pages = {}
        self.filename = None
        self.Messagebox = None
        self.geometry("1530x800")
        self.title("ZONES   |MT4 Trader " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.resizable(width=True, height=True)
        self.iconbitmap(r"src\Images\zones_ea.ico")
        self.image = tkinter.PhotoImage(file=r"src\Images\zones_ea.png")
        self.background_label = tkinter.Label(self, image=self.image, bg="#004d99")
        self.background_label.place(x=0, y=0, relwidth=1, relheight=1,bordermode=
                                    tkinter.OUTSIDE, anchor=tkinter.NW)
        self.configure(background="gray", relief=RAISED, border=9, bg="#004d99")
        self.db = Db()
        self.iconbitmap(r"src\images\zones_ea.ico")
        self.frame = Login(self, self.controller)

        self.mainloop()

    def show_pages(self, param):
        self.delete_frame()
        for _frame in self.winfo_children():
            _frame.destroy()
        self.title(
            "ZONES     |     AI POWERED MT4 Trader |    -->" + param + " | " + datetime.strftime(datetime.now(),
                                                                                                 "%Y")
            + ", NGUEMECHIEU NOEL  MARTIAL")
        if param in ['Login', 'Register', 'ForgotPassword', 'ResetPassword', 'Home', 'About', 'News', 'Service']:
            frames = [ Login, Register, ForgotPassword, ResetPassword, Home, About, News, Service]
            for frame in frames:
                if param == frame.__name__:
                    frame = frame(self, self.controller)
                    frame.tkraise()

    def delete_frame(self):
        for _frame in self.winfo_children():
            _frame.destroy()

    def connect(self):
        self.delete_frame()
        for _frame in self.winfo_children():
            _frame.destroy()
        self.frame = Login(self.parent, self.controller)

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

    def exit(self):
        sys.exit(0)


if __name__ == '__main__':
    App()
else:
    sys.exit(0)
