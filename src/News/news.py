import os
import threading
import tkinter
import xml.etree.ElementTree as ET

import requests

from Telegram import TelegramBot

sUrl = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml?version=bf0e35a327e8c9cd0b0ffdbae2dae029"  # ForexFactory NEWS URL (XML)


def impact_to_color(param):
    if param == 'Low':
        return 'green'
    elif param == 'Medium':
        return 'orange'
    elif param == 'High':
        return 'red'
    pass


def set_alerts(param):
    tkinter.Message(text=param, font=('Helvetica',))
    pass


class NewsEvent:
    def __init__(self,
                 url: str = 'https://nfs.faireconomy.media/ff_calendar_thisweek.xml?version'
                            '=45f4bf06b3af96b68bf3dd03db821ab6',
                 update_in_minutes: int = 240,
                 minutes_before_news: int = 480,
                 minutes_after_news: int = 60,
                 gmt_offset: int = -6):

        self.newsfile = "ff_calendar_thisweek.xml"


        self.channel = 'tradeexpert_infos'
        self.titles = []
        self.countries = []
        self.impacts = []
        self.forecast = []
        self.previous = []
        self.dates = []
        self.times = []
        self.news_items = []
        self.get_upcoming_news = None
        self.events = []

        self.url = url
        self.minutes_before_news = minutes_before_news
        self.minutes_after_news = minutes_after_news
        self.update_in_minutes = update_in_minutes
        self.gmt_offset = gmt_offset
        # Download the XML file

        self.download_xml(url=self.url)
        # Parse the XML data

        tree = ET.parse(self.newsfile)
        root = tree.getroot()

        news_thread = threading.Thread(target=self.xml_update, args=(self.url,
                                                                     self.newsfile))
        news_thread.start()

        # Extract data from the XML

        for text in root.iter('title'):
            self.titles.append(text.text)
        for text in root.iter('country'):
            self.countries.append(text.text)
        for text in root.iter('date'):
            self.dates.append(text.text)
        # for tex in root.iter('time'):
        #     self.times.append(tex.text)
        #
        #     self.date_time = [tex- relativedelta(hours=-self.gmt_offset)]
        #     print("time " + tex.text)
        for text in root.iter('impact'):
            self.impacts.append(text.text)
        for text in root.iter('forecast'):
            self.forecast.append(text.text)

        for text in root.iter('previous'):
            self.previous.append(text.text)
            print("previous " + str(text.text))

        self.number_of_items = len(self.titles)
        self.lastUpdate = 0

        for event in root.findall('event'):
            title = event.find('title').text
            country = event.find('country').text
            date = event.find('date').text
            time = event.find('time').text
            impact = event.find('impact').text
            forecast = event.find('forecast').text
            previous = event.find('previous').text

            self.events.append({
                'title': title,
                'country': country,
                'date': date,
                'time': time,
                'impact': impact,
                'forecast': forecast,
                'previous': previous
            })

        news_thread.join()

    def get_upcoming_news(self) -> str:

        return self.draw_events(
            ShowPanel=True,
            ShowPanelBG=True,
            eTitle=self.events[0]['title'],
            eCountry=self.events[0]['country'],
            eMinutes=self.events[0]['date'],
            eImpact=self.events[0]['impact'],
            Pbgc='white',
            Corner='black',
            x0=0,
            ePrevious=self.events[0]['previous'],
            eForecast=self.events[0]['forecast'],
            Alert1Minutes=self.minutes_before_news,
            Alert2Minutes=self.minutes_after_news

        )

    def url_download_to_file(self, url, file_path):
        response = requests.get(url)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"File downloaded successfully: {file_path}")
        else:
            print(f"Failed to download file. HTTP Error {response.status_code}")

    def xml_read(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
                print(f"Read news: {data.decode('utf-8')}")
        except FileNotFoundError:
            print(f"File not found: {file_path}")
        except Exception as e:
            print(f"Error reading file: {e}")

    def xml_update(self, url, file_path):
        if os.path.exists(file_path):
            os.remove(file_path)
            print("Old file deleted.")
        self.url_download_to_file(url, file_path)
        self.xml_read(file_path)

    def draw_events(self, ShowPanel=True, ShowPanelBG=True, eTitle='', eCountry='', eMinutes='', eImpact='', Pbgc=None,
                    Corner=None, x0=None, ePrevious=None, eForecast=None, Alert1Minutes=None, Alert2Minutes=None):


        # draw objects / alert functions
        for i in range(5):
            event_tool_tip = f"{eTitle[i]}\nCurrency: {eCountry[i]}\nTime left: {str(eMinutes[i])} Minutes\nImpact: {eImpact[i]}"
            print("Out: " + event_tool_tip)

            # impact color
            event_color = impact_to_color(eImpact[i])
            print("Color: " + event_color)

            alert_message = f"{str(eMinutes[i])} Minutes until [{eTitle[i]}] Event on {eCountry[i]}\nImpact: {eImpact[i]}\nForecast: {eForecast[i]}\nPrevious: {ePrevious[i]}"
            first_alert = False
            second_alert = False

            if Alert1Minutes != -1 and eMinutes[i] == Alert1Minutes and not first_alert:
                set_alerts("First Alert! " + alert_message)

                print("First Alert!" + alert_message)
                TelegramBot.send_message(self.channel,message_text= "First Alert! " + alert_message)
                first_alert = True

                return 'First Alert!' + alert_message

                # second alert
            if Alert2Minutes != -1 and eMinutes[i] == Alert2Minutes and not second_alert:
                set_alerts("Second Alert! " + alert_message)

                print("Second Alert!" + alert_message)

                second_alert = True
                TelegramBot.send_message(chat_id=self.channel, message_text="Second Alert! " + alert_message)
                return 'Second Alert!' + alert_message

                # break if no more data
            if eTitle[i] == eTitle[i + 1]:
                print("NO MORE EVENTS! GET SOME REST. ")

                TelegramBot.send_message(chat_id=self.channel, message_text="NO MORE EVENTS! GET SOME REST")

                return 'NO MORE EVENTS! GET SOME REST'

    def download_xml(self, url):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                with open(self.newsfile, 'wb') as f:
                    f.write(response.content)
                print(f"File downloaded successfully: {self.newsfile}")
            else:
                print(f"Failed to download file. HTTP Error {response.status_code}")
        except Exception as e:
            print(f"Error downloading file: {e}")
        pass
