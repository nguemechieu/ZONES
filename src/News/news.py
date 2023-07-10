import xml.etree.ElementTree as ET
import datetime
import os

import requests
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta

from src.trade import Trade


class NewsEvent(object):
    def __init__(self,
                 url: str = 'https://nfs.faireconomy.media/ff_calendar_thisweek.xml?version'
                            '=45f4bf06b3af96b68bf3dd03db821ab6',
                 update_in_minutes: int = 240,
                 minutes_before_news: int = 480,
                 minutes_after_news: int = 60,
                 gmt_offset: int = -6):

        """
        Class for checking Forex Factory(FF) news calendar.
            Args:
                url: url string for downloading news calendar from
                update_in_minutes: update interval for retrieving news calendar from FF, every 4 hours isOK
                minutes_before news: start of time window before news happens
                minutes_after_news: end of time window after news happened

            Remarks:
                The FF calendar will be saved in an XML file in subfolder ./News/       !!! take care
                If ./News does not exist, it will be created
        """

        self.date_time = None
        self._dated_1 = None
        self._dated_d = None
        self.previous = 0.0
        self.forecasts = 0.0
        self.number_of_items = 0
        self.url = url
        self.update_in_minutes = update_in_minutes
        self.minutes_before_news = minutes_before_news
        self.minutes_after_news = minutes_after_news
        self.lastUpdate = datetime.datetime.now() + relativedelta(minutes=self.update_in_minutes)
        self.base_date = 0
        self.quote_date = 0
        self.currency_date = 0
        self.titles = []
        self.countries = []
        self.dates = []
        self.times = []
        self.impacts = []
        self.news_items = []
        self.forecast = []
        self.previous = []
        self.gmt_offset = gmt_offset
        self.retrieve_url()

    # this routine will be called internally
    def retrieve_url(self):

        # check if news directory exists

        isdir = os.path.isdir("./News")
        if isdir is False:
            os.makedirs("./News")

        keyfile = requests.get(self.url)
        xml_file = "./News/news_.xml"

        if xml_file in os.listdir("./News"):
            open(xml_file, 'wb').write(keyfile.content)
        else:
            with open(xml_file, 'wb') as f:
                f.write(keyfile.content)
        self.titles.clear()
        self.countries.clear()
        self.dates.clear()
        self.times.clear()
        self.impacts.clear()
        self.forecast.clear()
        self.previous.clear()
        self.news_items.clear()

        tree = ET.parse(xml_file)
        root = tree.getroot()
        for text in root.iter('title'):
            self.titles.append(text.text)
        for text in root.iter('country'):
            self.countries.append(text.text)
        for text in root.iter('date'):
            self.dates.append(text.text)
            for tex in root.iter('time'):
                self.times.append(tex.text)
                date_time = parse(str(text.text) + ' ' + str(tex.text))
                self.date_time = [date_time - relativedelta(hours=-self.gmt_offset)]
                print("time " + text.text)
        for text in root.iter('impact'):
            self.impacts.append(text.text)
        for text in root.iter('forecast'):
            self.forecast.append(text.text)

        for text in root.iter('previous'):
            self.previous.append(text.text)
            print("previous " + str(text.text))

        self.number_of_items = len(self.titles)
        self.lastUpdate = 0

        for index in range(0, len(self.dates), 1):
            # make date first
            _date = parse(self.dates[index] + ' ' + self.times[index])
            _date = _date - relativedelta(hours=-self.gmt_offset)
            self.news_items.append((_date, self.titles[index], self.countries[index],
                                    self.impacts[index],
                                    self.forecast[index], self.previous[index]))
        self.lastUpdate = datetime.datetime.now()

    def get_upcoming_news(self):
        """
            Get upcoming news for a currency.

            Args:
                currency:   currency name to check for
                            AUD|CAD|CHF|EUR|GBP|JPY|NZD|USD
            Returns:
                bool: True(if news in defined period), else False
                title: description of news item
                impact: news impact on currency (high, medium or low)
        """
        # check for updating the calendar`
        diff = datetime.datetime.now() - self.lastUpdate
        diff = diff.total_seconds()
        if diff > self.update_in_minutes * 60:
            self.retrieve_url()
            self.lastUpdate = datetime.datetime.now()
            self.lastUpdate = self.lastUpdate + relativedelta(minutes=self.update_in_minutes)

        for index in range(0, len(self.news_items), 1):
            # check time
            if ((self.news_items[index][
                         0].timestamp() - self.minutes_before_news * 60) < datetime.datetime.now().timestamp() < (
                        self.news_items[index][0].timestamp() + self.minutes_after_news * 60)):
                self.currency_date = self.news_items[index][0].timestamp() - self.minutes_before_news * 60
                return True, str(self.news_items[index][2]), str(self.news_items[index][3])





    def check_currency(self,
                       currency: str = 'EUR'):
        """
            Check upcoming news for a currency.

            Args:
                currency:   currency name to check for
                            AUD|CAD|CHF|EUR|GBP|JPY|NZD|USD
            Returns:
                bool: True(if news in defined period), else False
                title: description of news item
                impact: news impact on currency (high, medium or low)
        """
        # check for updating the calendar`
        diff = datetime.datetime.now() - self.lastUpdate
        diff = diff.total_seconds()
        if diff > self.update_in_minutes * 60:
            self.retrieve_url()

        for index in range(0, len(self.news_items), 1):
            if self.news_items[index][0] == currency:
                # check time
                if ((self.news_items[index][
                         1].timestamp() - self.minutes_before_news * 60) < datetime.datetime.now().timestamp() < (
                        self.news_items[index][1].timestamp() + self.minutes_after_news * 60)):
                    self.currency_date = self.news_items[index][1].timestamp() - self.minutes_before_news * 60
                    return True, str(self.news_items[index][2]), str(self.news_items[index][3])

        return False, '', ''

    def check_instrument(self,
                         instrument: str = 'EURUSD'):
        """
            Check coming news for an instrument.

            Args:
                instrument: instrument name to check for
                            28 basic instruments
            Returns:
                bool: True(if news in defined period), else False
                title: description of news item
                impact: news impact on currency (high, medium or low)
        """
        # check for updating the calendar`
        diff = datetime.datetime.now() - self.lastUpdate
        diff = diff.total_seconds()
        if diff > self.update_in_minutes * 60:
            self.retrieve_url()

        # split instrument in the two currencies
        if len(instrument) < 7:
            return False, '', ''
        if len(instrument) > 7:
            instrument = instrument[0:7]

        currency_1 = instrument[0:3]
        currency_2 = instrument[3:7]

        result_1, title_1, impact_1 = self.check_currency(currency_1)
        self.base_date = self.currency_date
        result_2, title_2, impact_2 = self.check_currency(currency_2)
        self.quote_date = self.currency_date
        if not result_1 and not result_2:
            return False, '', ''

        if result_1 and not result_2:
            return result_1, title_1, impact_1

        if not result_1 and result_2:
            return result_2, title_2, impact_2

        if result_1 and result_2:
            if impact_1 == 'High' and (impact_2 == 'Low' or impact_2 == 'Medium' or impact_2 == 'Holiday'):
                return True, title_1, impact_1
            if impact_1 == 'Medium' and (impact_2 == 'Low' or impact_2 == 'Holiday'):
                return True, title_1, impact_1
            if impact_2 == 'High' and (impact_1 == 'Low' or impact_1 == 'Medium' or impact_1 == 'Holiday'):
                return True, title_2, impact_2
            if impact_2 == 'Medium' and (impact_1 == 'Low' or impact_1 == 'Holiday'):
                return True, title_2, impact_2
            if (self.base_date < self.quote_date) and impact_1 != 'Holiday' and impact_1 != 'Holiday':
                return True, title_1, impact_1
            else:
                return True, title_2, impact_2

        return False, '', ''

    def get_next_x_news_items(self,
                              number_of_items: int = 7) -> dict:

        self.number_of_items = number_of_items
        if self.number_of_items > 10:
            self.number_of_items = 10

        """
            Create dictionary with next x news items.

            Args:
                number_of_items: number of items to retrieve, limited to 10

            Returns:
                dictionary: last x news items, format 'index': ['country', 'date', 'title', 'impact']
                                                        index '0' --> 'number_of_items'
        """
        # check for updating the calendar`
        diff = datetime.datetime.now() - self.lastUpdate
        diff = diff.total_seconds()
        if diff > self.update_in_minutes * 60:
            self.retrieve_url()

        # loop through news_items list
        news_items = {
            '0:': ['', '', '', '', '', '']
        }

        counter = 0
        for index in range(0, len(self.news_items) - 1, 1):
            if counter >= self.number_of_items:
                break

            # convert string to datetime
            self._dated_1 = self.news_items[index][0]
            print("_dated " + str(self._dated_1))
            _dated = parse(str(self._dated_1))

            _datedd = _dated - relativedelta(hours=-self.gmt_offset)
            # check time

            _date = self.news_items[index][0]

            if _datedd > _date:
                news_items[str(counter) + ':'] = [str(self.news_items[index][0]),
                                                  str(self.news_items[index][1]),
                                                  str(self.news_items[index][2]),
                                                  str(self.news_items[index][3]),
                                                  str(self.news_items[index][4]),
                                                  str(self.news_items[index][5]),
                                                  str(self.news_items[index][6])]

                counter = counter + 1

        return news_items
