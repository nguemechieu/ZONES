import datetime
import tkinter

from src.News.news import NewsEvent


class News(tkinter.Frame):
    def __init__(self, parent, controller):
        self.close = None
        self.current_time = datetime.datetime.now()
        self.news = NewsEvent()
        self.news.get_next_x_news_items(5)
        self.parent = parent
        self.controller = controller
        tkinter.Frame.__init__(self, parent)


        self.info_label = tkinter.Label(self.parent, text="News", bg="lightblue", fg="white", font=("Arial", 12),width=70)
        self.info_label.pack(side=tkinter.TOP)

        self.news_label = tkinter.Label(self.parent, text="News", bg="white")
        self.news_label.pack(side=tkinter.TOP)
        self.title_label = tkinter.Label(self.parent, text="Title  " + self.news.titles[0], bg="white")
        self.title_label.pack(side=tkinter.TOP)

        self.description_label = tkinter.Label(self.parent, text="Description", bg="white")
        self.description_label.pack(side=tkinter.TOP)

        self.date_label = tkinter.Label(self.parent, text="Date " + self.news.dates[0], bg="white")
        self.date_label.pack(side=tkinter.TOP)

        self.country_label = tkinter.Label(self.parent, text="Country " + self.news.countries[0], bg="white")
        self.country_label.pack(side=tkinter.TOP)
        self.impact_label = tkinter.Label(self.parent, text="Importance " + self.news.impacts[0], bg="white")
        self.impact_label.pack(side=tkinter.TOP)

        self.previous_label = tkinter.Label(self.parent, text="Previous ", bg="white")
        self.previous_label.pack(side=tkinter.TOP)

        self.forecast_label = tkinter.Label(self.parent, text="Forecast ", bg="white")
        self.forecast_label.pack(side=tkinter.TOP)

        self.Listbox = tkinter.Listbox(self.parent, selectmode=tkinter.SINGLE, bg="black", fg="white", height=500,
                                       width=800)
        self.Listbox.pack(side=tkinter.TOP)
        if len(self.news.titles) > 1 and len(self.news.countries):
            for i in range(len(self.news.titles)):
                self.Listbox.insert(tkinter.END, self.news.titles[i])
                self.Listbox.insert(tkinter.END, self.news.dates[i])
                self.Listbox.insert(tkinter.END, self.news.countries[i])
                self.Listbox.insert(tkinter.END, self.news.impacts[i])
        #     self.Listbox.insert(tkinter.END, self.news.forecast[i])
        #    self.Listbox.insert(tkinter.END, self.news.previous[i])
        else:
            self.Listbox.insert(tkinter.END, self.news.titles[0])
            self.Listbox.insert(tkinter.END, self.news.dates[0])
            self.Listbox.insert(tkinter.END, self.news.countries[0])
            self.Listbox.insert(tkinter.END, self.news.impacts[0])
            #    self.Listbox.insert(tkinter.END, self.news.forecast[0])
            #    self.Listbox.insert(tkinter.END, self.news.previous[0])
        self.Listbox.pack(side=tkinter.TOP)
        self.button = tkinter.Button(self.parent, text="Close", command=lambda: self.controller.show_page('Home'))
        self.button.pack(side=tkinter.BOTTOM)
