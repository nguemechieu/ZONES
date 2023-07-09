import datetime
import os
import sys
import time
import tkinter
import tkinter.ttk as ttk

import PIL
import pyautogui
import pygetwindow

from src.trade import Trade


class Home(tkinter.Frame):
    def __init__(self, parent, controller):
        self.trades = Trade()
        tkinter.Frame.__init__(self, parent)
        self.user_profile_username_entry = None
        self.user_profile_button = None
        self.user_profile_phone = None
        self.user_profile_email_entry = None
        self.user_profile_email = None
        self.login_window = None
        self.login_window_username_entry = None
        self.user_profile_username = None
        self.win = self
        self.login_window_password_entry = None
        self.user_profile_label = None
        self.user_profile_password_entry = None
        self.login_window_username = None
        self.login_window_button = None
        self.user_profile = None
        self.user_profile_phone_entry = None
        self.user_profile_password = None
        self.login_window_password = None

        self.canvas = tkinter.Canvas(self, width=800, height=600, bg='black')
        self.tools_menu = tkinter.Menu(parent, tearoff=0)
        self.insert_menu = tkinter.Menu(parent, tearoff=0)
        self.tab_7 = None
        self.tab_6 = None
        self.controller = controller
        self.master = parent
        self.zmq = Trade()
        self.config(bg='lightblue', relief=tkinter.RAISED, borderwidth=3, highlightthickness=3, padx=10,
                               pady=20
                               )

        # create tab pane
        self.tab_pane = tkinter.ttk.Notebook(parent, padding=10, takefocus=2)
        self.tab_pane.pack(fill=tkinter.BOTH, expand=1)
        # create tab
        self.tab_1 = tkinter.Frame(self.tab_pane, background='yellow')
        self.tab_1.pack(fill=tkinter.BOTH, expand=1)

        # create tab
        self.tab_2 = tkinter.Frame(self.tab_pane, background='orange', relief=tkinter.RAISED, borderwidth=1)
        self.tab_2.pack(fill=tkinter.BOTH, expand=1)

        # create tab
        self.tab_3 = tkinter.Frame(self.tab_pane, background='green', relief=tkinter.RAISED)
        self.tab_3.pack(fill=tkinter.BOTH, expand=1)

        # create tab
        self.tab_4 = tkinter.Frame(self.tab_pane, background='blue', relief=tkinter.RAISED, borderwidth=1,
                                   bg='black',
                                   highlightthickness=1)
        self.tab_4.pack(fill=tkinter.BOTH, expand=1)
        self.data = self.zmq.zones_connect.get_data()
        print(self.data)
        self.tab_5 = tkinter.Frame(self.tab_pane, background='red', relief=tkinter.RAISED, borderwidth=1)

        self.tab_5.pack(fill=tkinter.BOTH, expand=1)
        # create tab
        self.tab_6 = tkinter.Frame(self.tab_pane, background='green', relief=tkinter.RAISED, borderwidth=1)
        self.tab_6.pack(fill=tkinter.BOTH, expand=1)

        self.tab_pane.pack(fill=tkinter.BOTH, expand=1, padx=10, pady=10)

        # Inserting pages into the tab pane

        self.tab_pane.add(self.tab_1, text="Zones Server")
        self.tab_pane.add(self.tab_2, text="Trading ")
        self.tab_pane.add(self.tab_3, text="News ")
        self.tab_pane.add(self.tab_4, text="Account")
        self.tab_pane.add(self.tab_5, text="Statistics")
        self.tab_pane.add(self.tab_6, text="Settings")

        # create Menu Bar
        self.menu_bar = tkinter.Menu(parent, tearoff=0, background='gold', relief=tkinter.RIDGE, borderwidth=4
                                )
        self.controller.config(menu=self.menu_bar, background="#004d99", relief=tkinter.RAISED, borderwidth=3,
                               highlightthickness=3, padx=10, pady=20)
        # create file menu
        self.file_menu = tkinter.Menu(self.menu_bar, tearoff=0, background='lightblue', relief=tkinter.RIDGE,
                                      borderwidth=3,font=34,border=23)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open file", command=lambda: self.controller.open_file())
        self.file_menu.add_command(label="Save file", command=lambda: self.controller.save_file())
        self.file_menu.add_command(label="Save as", command=lambda: self.controller.save_as())
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Login To Trade", command=lambda: self.login_to_trade())
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Profile", command=lambda: self.profile())
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Save As Picture", command=lambda: self.save_as_picture())
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Close", command=lambda: sys.exit(0))
        self.file_menu.add_command(label="Exit", command=lambda: sys.exit(0))
        # create edit menu
        self.edit_menu = tkinter.Menu(self.menu_bar, tearoff=0, background='blue', relief=tkinter.RIDGE, borderwidth=3)
        self.menu_bar.add_cascade(label="Edit", menu=self.edit_menu)
        self.edit_menu.add_command(label="Undo", command=lambda: self.undo())
        self.edit_menu.add_command(label="Redo", command=lambda: self.redo())
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Cut", command=lambda: self.cut())
        self.edit_menu.add_command(label="Copy", command=lambda: self.copy())
        self.edit_menu.add_command(label="Paste", command=lambda: self.paste())
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Select All", command=lambda: self.select_all())
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Delete", command=lambda: self.delete())
        self.edit_menu.add_separator()
        # create view menu
        self.view_menu = tkinter.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="View", menu=self.view_menu)
        self.view_menu.add_checkbutton(label="Show candlesticks", command=lambda: self.show_candlesticks())
        self.view_menu.add_checkbutton(label="Show trades")
        self.view_menu.add_separator()
        self.view_menu.add_checkbutton(label="Show volume", command=lambda: self.show_volume())
        self.view_menu.add_separator()
        self.view_menu.add_checkbutton(label="Show price", command=lambda: self.show_price())
        self.view_menu.add_separator()
        self.view_menu.add_checkbutton(label="Show time", command=lambda: self.show_time())
        self.view_menu.add_separator()
        self.menu_bar.add_cascade(label="Insert", menu=self.insert_menu)
        self.insert_menu.add_command(label="Charts", command=lambda: self.chart())
        self.insert_menu.add_separator()
        self.insert_menu.add_command(label="Trades", command=lambda: self.controller.insert_trade())
        self.menu_bar.add_cascade(label='Tools', menu=self.tools_menu)
        self.tools_menu.add_command(label="Exit", command=lambda: sys.exit(1))
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label="About", command=lambda: self.controller.about())
        self.tools_menu.add_separator()
        # create help menu
        self.help_menu = tkinter.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="About", command=lambda: self.controller.show_pages(param="About"))

        self.account_data = [
            '2020-01-01 00:00:00',
            '<NAME>', 10000, 10000,
            10000, 10000, 10000, 10000, 10000, 10000, 10000
        ]
        print("mydata " + str(self.data))
        self.profile_data = [
            {'_action': 'OPEN_TRADES', '_trades': {
                317733340: {'_magic': 123, '_symbol': 'USDCAD', '_lots': 1.0, '_type': 0, '_open_price': 1.35112,
                            '_open_time': datetime.datetime.now(), '_SL': 0.0, '_TP': 0.0, '_pnl': -1780.05,
                            '_comment': 'BUY LIMIT ORDER'}}}
        ]

        for i in range(len(self.profile_data)):
            if self.profile_data[i]['_action'].startswith('OPEN_TRADES'):
                self.profile_data[i]['_trades'] = self.profile_data[i]['_trades'][317733340]
                self.trade_data = self.profile_data[i]['_trades']

    def undo(self):

        pass

    def redo(self):

        pass

    def cut(self):

        pass

    def copy(self):

        pass

    def paste(self):

        pass

    def select_all(self):
        pass

    def delete(self):
        pass

    def show_price(self):
        pass

    def show_candlesticks(self):
        pass

    def chart(self):
        pass

    def show_volume(self):
        pass

    def show_time(self):


        pass

    def save_as_picture(self):
        # Taking screenshot of the window and saving it as a picture
        self.win.screenshot()
        self.screenshot.show()

    def login_to_trade(self):
        self.login_window = tkinter.Toplevel()
        self.login_window.title("MT4 Account Login")
        self.login_window.geometry("500x500")
        self.login_window.resizable(0, 0)
        self.login_window.grab_set()
        self.login_window.focus_set()
        self.login_window_label = tkinter.Label(self.login_window, text="MT4 Account Login")
        self.login_window_label.grid(row=0, column=0, padx=10, pady=10)
        self.login_window_username = tkinter.Label(self.login_window, text="username")
        self.login_window_username.grid(row=1, column=0, padx=
        10, pady=10)
        self.login_window_username_entry = tkinter.Entry(self.login_window)
        self.login_window_username_entry.grid(row=1, column=1, padx=10, pady=10)
        self.login_window_password = tkinter.Label(self.login_window, text="password")
        self.login_window_password.grid(row=2, column=0, padx=10, pady=10)
        self.login_window_password_entry = tkinter.Entry(self.login_window)
        self.login_window_password_entry.grid(row=2, column=1, padx=10, pady=10)

        self.login_window_button = tkinter.Button(self.login_window, text="Cancel",
                                                  command=lambda: self.controller.show_pages('Login'))
        self.login_window_button.grid(row=3, column=0, padx=10, pady=10)
        self.login_window_button = tkinter.Button(self.login_window, text="Login", command=lambda: self.mt4login())
        self.login_window_button.grid(row=3, column=1, padx=10, pady=10)

        pass

    def profile(self):
        # Create user profile interface

        self.user_profile = tkinter.Toplevel()
        self.user_profile.title("User Profile")
        self.user_profile.geometry("500x500")
        self.user_profile.resizable(0, 0)
        self.user_profile.grab_set()
        self.user_profile.focus_set()
        self.user_profile.focus_force()

        self.user_profile_label = tkinter.Label(self.user_profile, text="User Profile")
        self.user_profile_label.grid(row=0, column=0, padx=10, pady=10)

        self.user_profile_username = tkinter.Label(self.user_profile, text="username")
        self.user_profile_username.grid(row=1, column=0, padx=10, pady=10)
        self.user_profile_username_entry = tkinter.Entry(self.user_profile)
        self.user_profile_username_entry.grid(row=1, column=1, padx=10, pady=10)

        self.user_profile_password = tkinter.Label(self.user_profile, text="password")
        self.user_profile_password.grid(row=2, column=0, padx=10, pady=10)
        self.user_profile_password_entry = tkinter.Entry(self.user_profile)
        self.user_profile_password_entry.grid(row=2, column=1, padx=10, pady=10)
        self.user_profile_email = tkinter.Label(self.user_profile, text="email")
        self.user_profile_email.grid(row=3, column=0, padx=10, pady=10)
        self.user_profile_email_entry = tkinter.Entry(self.user_profile)
        self.user_profile_email_entry.grid(row=3, column=1, padx=10, pady=10)
        self.user_profile_phone = tkinter.Label(self.user_profile, text="phone")
        self.user_profile_phone.grid(row=4, column=0, padx=10, pady=10)
        self.user_profile_phone_entry = tkinter.Entry(self.user_profile)
        self.user_profile_phone_entry.grid(row=4, column=1, padx=10, pady=10)

        self.user_profile_button = tkinter.Button(self.user_profile, text="OK",
                                                  command=lambda: self.user_profile.destroy())

        self.user_profile_button.grid(row=3, column=0, padx=10, pady=10)

    def quit(self):
        self.controller.close()

    def screenshot(self):

        # get screensize
        x, y = pyautogui.size()
        print(f"width={x}\theight={y}")

        x2, y2 = pyautogui.size()
        x2, y2 = int(str(x2)), int(str(y2))
        print(x2 // 2)
        print(y2 // 2)

        # find new window title
        z1 = pygetwindow.getAllTitles()
        time.sleep(1)
        print(len(z1))
        # test with pictures folder

        time.sleep(1)
        z2 = pygetwindow.getAllTitles()
        print(len(z2))
        time.sleep(1)
        z3 = [x for x in z2 if x not in z1]
        z3 = ''.join(z3)
        time.sleep(3)
        # also able to edit z3 to specified window-title string like: "Sublime Text (UNREGISTERED)"
        my = pygetwindow.getWindowsWithTitle(z3)[0]
        # quarter of screen screensize
        x3 = x2 // 2
        y3 = y2 // 2
        my.resizeTo(x3, y3)
        # top-left
        my.moveTo(0, 0)
        time.sleep(3)
        my.activate()
        time.sleep(1)

        # save screenshot
        p = pyautogui.screenshot()
        p.save(
            r"C:\\Users\\nguem\\Desktop\\MT4_Trading_Bot\\Pictures\\screenshot.png"
        )

        # close window
        time.sleep(1)
        my.close()

    def mt4login(self):
        self.login_window.destroy()
        self.controller.show_pages('Home')