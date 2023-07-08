import tkinter

from src.News.news import NewsEvent


class News(tkinter.Frame):
    def __init__(self, controller):

        # Get News
        super().__init__()

        self.news = NewsEvent()
        self.news.get_next_x_news_items(5)
        self.parent = self.master
        self.controller = controller

        self.news_label = tkinter.Label(self.parent, text="News", bg="white")

        self.news_frame = tkinter.Frame(self.parent, bg="white")

        self.title_label = tkinter.Label(self.news_frame, text="Title  " + self.news.titles[0], bg="white")

        self.description_label = tkinter.Label(self.news_frame, text="Description", bg="white")

        self.date_label = tkinter.Label(self.news_frame, text="Date " + self.news.dates[0], bg="white")

        self.country_label = tkinter.Label(self.news_frame, text="Country " + self.news.countries[0], bg="white")
        self.impact_label = tkinter.Label(self.news_frame, text="Importance " + self.news.impacts[0], bg="white")

        self.previous_label = tkinter.Label(self.news_frame, text="Previous ", bg="white")

        self.forecast_label = tkinter.Label(self.news_frame, text="Forecast ", bg="white")
