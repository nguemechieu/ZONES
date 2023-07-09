import datetime
import tkinter
from tkinter import ttk


from src.News.news import NewsEvent


class News(tkinter.Frame):
    def __init__(self, parent, controller):

        self.item = None
        self.record = None
        self.scrollbar = None
        self.tree = None
        self.current_time = datetime.datetime.now()
        self.news = NewsEvent()
        self.news.get_next_x_news_items(7)
        self.parent = parent
        self.controller = controller

        tkinter.Frame.__init__(self, parent)
        self.go_back = tkinter.Button(parent, text="Go Back", command=lambda: self.controller.show_pages("Home"))
        self.go_back.pack(side=tkinter.LEFT)

        self.after(1000, self.update)
        # define columns news and treeview
        columns = ('Title', 'Date', 'Country', 'Impact', 'Forecast', 'Previous')

        self.tree = ttk.Treeview(self.parent, columns=columns, show='headings',style='Treeview.Heading')

        self.tree.bind('<<TreeviewSelect>>', self.item_selected)
        self.tree.pack(side=tkinter.LEFT)

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
                                 56

                             ))

    def item_selected(self, event):

        self.current_time = datetime.datetime.now()
        for selected_item in self.tree.selection():
            self.item = self.tree.item(selected_item)
            self.record = self.item['values']

            # show a message

            # add a scrollbar
            self.scrollbar = ttk.Scrollbar(self.parent, orient=tkinter.VERTICAL, command=self.tree.yview)
            self.tree.configure( selectmode='browse', yscrollcommand=self.scrollbar.set)
