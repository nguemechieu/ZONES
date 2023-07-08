import json
import urllib3


class TelegramBot(object):
    def __init__(self, _token: str):
        self.token = _token
        self.url = 'https://api.telegram.org/bot' + _token
        self.http = urllib3.PoolManager()
        self.http.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.http.headers.update({'Content-Type': 'application/json'})
        self.http.headers.update({'Authorization': 'Bearer' + self.token})
        self.http.headers.update({'Accept': 'application/json'})
        self.http.headers.update({'Connection': 'close'})
        self.http.headers.update({'Cache-Control': 'no-cache'})
        self.http.headers.update({'Pragma': 'no-cache'})
        self.http.headers.update({'Cache-Control': 'no-cache'})

        response = self.http.request('GET', self.url + '/getMe')
        self.me = json.loads(response.data.decode('utf-8'))
        print(self.me)

        response = self.http.request('GET', self.url + '/getUpdates')
        self.data = [json.loads(response.data.decode('utf-8'))]
        print(self.data)

    def send_chat_action(self, chat_id: int, action: str):
        data = {
            'chat_id': chat_id,
            'action': action,
            'message_thread_id': None
        }
        response = self.http.request('POST', self.url + '/sendChatAction', data=json.dumps(data))
        print(response.data.decode('utf-8'))

    def send_message(self, chat_id: int, message_text: str):
        parse_mode = 'markdown'

        reply_markup = None

        data = {
            'chat_id': chat_id,
            'text': message_text,
            'message_thread_id': None,
            'parse_mode': parse_mode,
            'reply_markup': reply_markup
        }
        response = self.http.request('POST', self.url + '/sendMessage', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def get_message(self, chat_id: int = None, message_id=None):
        data = {
            'chat_id': chat_id,
            'message_id': message_id
        }
        response = self.http.request('POST', self.url + '/getMessage', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def get_updates(self, offset=None, limit=None):
        data = {
            'offset': offset,
            'limit': limit
        }
        response = self.http.request('GET', self.url + '/getUpdates', body=json.dumps(data))
        print(json.loads(response.data.decode('utf-8')))

        return json.loads(response.data.decode('utf-8'))

    def get_me(self):
        response = self.http.request('POST', self.url + '/getMe')
        return json.loads(response.data.decode('utf-8'))

    def get_chat(self, chat_id):
        data = {
            'chat_id': chat_id
        }
        response = self.http.request('POST', self.url + '/getChat', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def get_user(self, user_id):
        data = {
            'user_id': user_id
        }
        response = self.http.request('POST', self.url + '/getUser', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def get_chat_administrators(self, chat_id):
        data = {
            'chat_id': chat_id
        }
        response = self.http.request('POST', self.url + '/getChatAdministrators', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def get_chat_members_count(self, chat_id):
        data = {
            'chat_id': chat_id
        }
        response = self.http.request('POST', self.url + '/getChatMembersCount', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def get_chat_member(self, chat_id, user_id):
        data = {
            'chat_id': chat_id,
            'user_id': user_id
        }
        response = self.http.request('POST', self.url + '/getChatMember', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def leave_chat(self, chat_id):
        data = {
            'chat_id': chat_id
        }
        response = self.http.request('POST', self.url + '/leaveChat', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def get_user_profile_photos(self, user_id, offset=None, limit=None):
        data = {
            'user_id': user_id,
            'offset': offset,
            'limit': limit
        }
        response = self.http.request('POST', self.url + '/getUserProfilePhotos', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def get_file(self, file_id):
        data = {
            'file_id': file_id
        }
        response = self.http.request('POST', self.url + '/getFile', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def send_photo(self, chat_id, photo, caption=None, reply_markup=None, reply_to_message_id=None,
                   reply_to_message=None, reply_to_message_text=None, reply_to_message_html=None):
        data = {
            'chat_id': chat_id,
            'photo': photo,
            'caption': caption,
            'reply_markup': reply_markup,
            'reply_to_message_id': reply_to_message_id,
            'reply_to_message': reply_to_message,
            'reply_to_message_text': reply_to_message_text,
            'reply_to_message_html': reply_to_message_html
        }
        response = self.http.request('POST', self.url + '/sendPhoto', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def send_audio(self, chat_id, audio, caption=None, reply_markup=None, reply_to_message_id=None,
                   reply_to_message=None, reply_to_message_text=None, reply_to_message_html=None):
        data = {
            'chat_id': chat_id,
            'audio': audio,
            'caption': caption,
            'reply_markup': reply_markup,
            'reply_to_message_id': reply_to_message_id,
            'reply_to_message': reply_to_message,
            'reply_to_message_text': reply_to_message_text,
            'reply_to_message_html': reply_to_message_html}
        response = self.http.request('POST', self.url + '/sendAudio', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))

    def send_document(self, chat_id, document, caption=None, reply_markup=None, reply_to_message_id=None,
                      reply_to_message=None, reply_to_message_text=None, reply_to_message_html=None):
        data = {
            'chat_id': chat_id,
            'document': document,
            'caption': caption,
            'reply_markup': reply_markup,
            'reply_to_message_id': reply_to_message_id,
            'reply_to_message': reply_to_message,
            'reply_to_message_text': reply_to_message_text,
            'reply_to_message_html': reply_to_message_html}
        response = self.http.request('POST', self.url + '/sendDocument', body=json.dumps(data))
        return json.loads(response.data.decode('utf-8'))
