import datetime
import requests
import tkinter
import tkinter.ttk as ttk
from tkinter import TOP, RAISED, LEFT

from src.News.news import NewsEvent

from src.ui.account import Account
from src.ui.statistics import Statistics
from src.ui.trading import Trading


def screen_shot():
    # Taking screenshot of the window and saving it as a picture
    print("screen shot")


def save_as_picture():
    # Taking screenshot of the window and saving it as a picture
    screen_shot()


class Home(tkinter.Frame):
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller
        self.data = {}
        self.login_window_label = None

        tkinter.Frame.__init__(self, parent, bg='lightblue', relief=tkinter.RAISED, borderwidth=3,
                               highlightthickness=3, padx=10, pady=20, width=1500, height=730)
        self.user_profile_username_entry = None
        self.user_profile_button = None
        self.user_profile_phone = None
        self.user_profile_email_entry = None
        self.user_profile_email = None
        self.login_window = None
        self.login_window_username_entry = None
        self.user_profile_username = None

        self.login_window_password_entry = None
        self.user_profile_label = None
        self.user_profile_password_entry = None
        self.login_window_username = None
        self.login_window_button = None
        self.user_profile = None
        self.user_profile_phone_entry = None
        self.user_profile_password = None
        self.login_window_password = None

        self.tools_menu = tkinter.Menu(parent, tearoff=0)
        self.insert_menu = tkinter.Menu(parent, tearoff=0)
        self.tab_7 = None
        self.tab_6 = None
        self.controller = controller
        self.master = parent

        self.news = NewsEvent()

        self.config(bg='lightblue', relief=tkinter.RAISED, borderwidth=3, highlightthickness=3, padx=10,
                    pady=20
                    )

        # create tab pane
        self.tab_pane =ttk.Notebook(parent, takefocus=2)
        self.tab_pane.pack(fill=tkinter.BOTH, expand=1, side=LEFT, padx=10, pady=10)
        # create tab
        self.tab_1 = tkinter.Frame(self.tab_pane)
        self.tab_1.pack(fill=tkinter.BOTH, expand=1)

        self.tab_1_server_status_label = tkinter.Text(self.tab_1, width=1500, height=300, bg='black', fg="yellow")
        self.tab_1_server_status_label.place(x=1, y=0)
        self.tab_1_server_status_label.config(bg='black', fg='white')
        self.tab_1_server_status_label.config(relief=tkinter.RAISED, borderwidth=1)
        self.tab_1_server_status_label.config(highlightthickness=1)

        self.tab_1_server_status_label.insert(0.0, "Server Time  :" +
                                              self.controller.zmq.dwx.server_status['server_time'].__str__() +\
                                              "\nSTATUS :" +


                                              self.controller.zmq.dwx.server_status['server_status'].__str__() + \
                                              "\nINFO :" +
                                              self.controller.zmq.dwx.server_status['info'].__str__()+"\nACCOUNT INFO:"
                                              +

                                              self.controller.zmq.dwx.server_status['account_info'].__str__()


                                              )

        self.tab_1_server_status_label = tkinter.Text(self.tab_1, bg='black', fg='lightgreen', relief=tkinter.RAISED,
                                                      borderwidth=1, highlightthickness=1)
        self.tab_1_server_status_label.place(x=2, y=120, width=1500, height=600)

        self.tab_1_server_status_label.config(font=("Arial", 13), bg='black', fg='lightgreen')

        self.tab_1_server_status_label.insert(0.0, str(
            self.controller.zmq.dwx.server_status))

        self.tab_2 = tkinter.Frame(self.tab_pane, background='lightblue', relief=tkinter.RAISED, borderwidth=1)
        self.tab_2.pack(fill=tkinter.BOTH, expand=1)

        # create tab
        self.tab_3 = tkinter.Frame(self.tab_pane, background='green', relief=tkinter.RAISED, borderwidth=1)
        self.tab_3.pack(fill=tkinter.BOTH, expand=1)
        self.news_label = tkinter.Label(self.tab_3, text="FOREX MARKET NEWS",
                                        bg='black', border=2, relief=RAISED,
                                        fg='green', font=
                                        ("Arial", 12))
        self.news_label.pack(fill=tkinter.BOTH, expand=1, side=TOP)
        news_tree = tkinter.ttk.Treeview(self.tab_3, height=17, selectmode=tkinter.EXTENDED)
        news_text = tkinter.Text(self.tab_3, width=1500, height=150, bg='black', fg="yellow")
        news_text.place(x=1, y=0, width=1500, height=100)
        news_text.config(relief=tkinter.RAISED, borderwidth=1)
        news_text.insert(0.0, "Upcoming News\n\n" + str(self.news.get_upcoming_news )+"\n\n")

        self.current_time = datetime.datetime.now()

        columns = ('date', 'title', 'country', 'impact', 'forecast', 'previous')
        news_tree['columns'] = columns
        news_tree['show'] = 'headings'
        for title in self.news.titles:
            i = self.news.titles.index(title)
            news_tree.insert('', tkinter.END,
                             values=(
                                 self.news.titles[i],
                                 self.news.dates[i],
                                 self.news.countries[i],
                                 self.news.impacts[i],
                                 self.news.forecast[i],
                                 self.news.previous[i]

                             ))
            news_text.insert(0.0,
                             title.__str__() + "\n" + str(self.news.dates[i]) + "\n" + str(self.news.countries[i]) + "\n" + str(
                                 self.news.impacts[i]) + "\n" + str(self.news.forecast[i]) + "\n" + str(
                                 self.news.previous[i]))

        news_tree.pack(fill=tkinter.BOTH, expand=1)

        # create tab
        self.tab_4 = tkinter.Frame(self.tab_pane, background='blue', relief=tkinter.RAISED, borderwidth=1,
                                   bg='black',
                                   highlightthickness=1)
        self.tab_4.pack(fill=tkinter.BOTH, expand=1)
        Account(self.tab_4, self.controller).grid(sticky=tkinter.NSEW)

        # create tab

       
        self.tab_5 = tkinter.Frame(self.tab_pane, background='red', relief=tkinter.RAISED, borderwidth=1)

        self.tab_5.pack(fill=tkinter.BOTH, expand=1)
        # create tab
        self.tab_6 = tkinter.Frame(self.tab_pane, relief=tkinter.RAISED, borderwidth=1)
        self.tab_6.pack(fill=tkinter.BOTH, expand=1)

        self.tab_pane.pack(fill=tkinter.BOTH, expand=1, padx=10, pady=10)

        # Inserting pages into the tab pane
        self.news_tab = tkinter.Frame(self.tab_pane, relief=tkinter.RAISED)
        self.trading_tab = Trading(self.tab_2, self.controller)
        self.statistics_tab = Statistics(self.tab_5, self.controller)
        self.statistics_tab.grid(sticky=tkinter.NSEW)
        self.tab_pane.add(self.tab_1, text="Server ")
        self.tab_pane.add(self.tab_2, text=" Trading ")
        self.tab_pane.add(self.tab_3, text=" News ")
        self.tab_pane.add(self.tab_4, text=" Account ")
        self.tab_pane.add(self.tab_5, text=" Statistics  ")
        self.tab_pane.add(self.tab_6, text=" Settings ")

        self.update_server_status()

    def update_server_status(self):
        self.after(5000, self.tab_pane)
    
