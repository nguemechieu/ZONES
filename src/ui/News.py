import datetime
import tkinter
from tkinter import ttk

from src.News.news import NewsEvent
class News(tkinter.Frame):
    def __init__(self, parent, controller):
        tkinter.Frame.__init__(parent, bg="black", border=7, relief=tkinter.RIDGE, padx=10, pady=10
                               , highlightbackground="black", highlightcolor="black", container=True)
        self.parent = parent
        self.title_label = tkinter.Label(self.parent, text="Forex Market News", justify="center",
                                         background="lightblue")
        self.title_label.pack(side=tkinter.TOP, fill=tkinter.X)

        self.item = None
        self.record = None
        self.scrollbar = None
        self.tree = None
        self.current_time = datetime.datetime.now()
        self.news = NewsEvent()
        self.news.get_next_x_news_items(7)

        self.controller = controller

        # define columns news and treeview
        self.columns = ('Title', 'Date', 'Country', 'Impact', 'Forecast', 'Previous')
        self.tree = ttk.Treeview(self.parent, columns=self.columns, selectmode="browse", show='headings',
                                 style='Treeview.Heading', yscrollcommand=lambda: self.scrollbar)

        self.tree.pack(side=tkinter.RIGHT, fill=tkinter.BOTH)

        # define headings
        self.tree.heading(
            'Title', text='Title'
        )
        self.tree.heading(
            'Date', text='Date'
        )
        self.tree.heading(
            'Country', text='Country'
        )
        self.tree.heading(
            'Impact', text='Impact'
        )
        self.tree.heading(
            'Forecast', text='Forecast'
        )
        self.tree.heading(
            'Previous', text='Previous'
        )

        for title in self.news.titles:
            i = self.news.titles.index(title)
            self.tree.insert('', tkinter.END,
                             values=(
                                 self.news.titles[i],
                                 self.news.dates[i],
                                 self.news.countries[i],
                                 self.news.impacts[i],

                                 0,
                                 0

                             ))

    def item_selected(self, event):
        self.tree.delete(*self.tree.get_children())
        self.item = None
        self.record = None
        self.current_time = datetime.datetime.now()
        if event is not None:
            self.tree.insert('', tkinter.END,
                             values=(
                                 self.news.titles[event],
                                 self.news.dates[event],
                                 self.news.countries[event],
                                 self.news.impacts[event],
                                 self.news.forecasts[event],

                                 self.news.previous[event]

                             ))

            self.after(1000, self.update)
            self.tree.selection_set(event)

        elif event is None:
            self.after(1000, self.update)

            for title in self.news.titles:
                i = self.news.titles.index(title)
                self.tree.insert('', tkinter.END,
                                 values=(
                                     self.news.titles[i],
                                     self.news.dates[i],
                                     self.news.countries[i],
                                     self.news.impacts[i],
                                     self.news.forecasts[i],
                                     self.news.previous[i]


                                 ))

            self.scrollbar = ttk.Scrollbar(self.parent, orient=tkinter.VERTICAL, command=self.tree.yview)
            self.tree.configure(selectmode='browse')
