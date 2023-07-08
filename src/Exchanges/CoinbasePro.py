import requests
from requests.adapters import HTTPAdapter


class Coinbase:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_url = "https://api.pro.coinbase.com"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/91.0.4472.124 Safari/537.36",
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.auth = (self.api_key, self.api_secret)
        self.session.verify = False
        self.session.mount("https://", HTTPAdapter(max_retries=3))
        self.session.mount("http://", HTTPAdapter(max_retries=3))
        self.session.mount("https://api.pro.coinbase.com", HTTPAdapter(max_retries=3))
        self.session.mount("http://api.pro.coinbase.com", HTTPAdapter(max_retries=3))
