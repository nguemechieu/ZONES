from configparser import ConfigParser
from sqlite3 import connect
from tkinter import Message

import MySQLdb


class Db(object):
    def __init__(self):
        # Create mysql connection
        self.config = ConfigParser()
        self.config.add_section('mysql')
        self.config.read(filenames="config.ini")
        self.host = self.config.get(section='mysql', option='host')
        self.user = self.config.get(section='mysql', option='user')
        self.password = self.config.get(section='mysql', option='password')
        self.database = self.config.get(section='mysql', option='database')
        self.port = self.config.get(section='mysql', option='port')
        self.conn = MySQLdb.connect(host=self.host, user=self.user, passwd=self.password, db='')
        self.cur = self.conn.cursor()
        self.cur.execute("CREATE  DATABASE IF NOT EXISTS "+self.database)
        self.cur.execute("USE "+self.database)
        self.cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTO_INCREMENT, username TEXT, '
                         'email TEXT, phone TEXT, password TEXT)')
        self.cur.execute('CREATE TABLE IF NOT EXISTS zones (id INTEGER PRIMARY KEY AUTO_INCREMENT, name TEXT, '
                         'latitude REAL, longitude REAL)')

    def get_all_users(self):
        self.cur.execute('SELECT * FROM users ORDER BY id ASC')
        users = self.cur.fetchall()
        self.cur.close()
        self.conn.close()
        return users

    def find_user_by_password(self, password):
        self.cur.execute('SELECT * FROM users WHERE password=?', password)
        user = self.cur.fetchone()
        self.cur.close()
        return user

    def find_user_by_email(self, email):
        self.cur.execute('SELECT * FROM users WHERE email=?', email)
        user = self.cur.fetchone()
        self.cur.close()

        return user

    def find_user_by_phone(self, phone):
        self.cur.execute('SELECT * FROM users WHERE phone=?', phone)
        user = self.cur.fetchone()
        self.cur.close()
        self.conn.close()
        return user

    def create_user(
            self, db_name,
            statement: str, data: str

    ) -> None:
        self.conn = connect(db_name)
        self.cur = self.conn.cursor()
        self.cur.execute(statement, data)
        self.conn.commit()

    def get_user_by_email(self, email: str):
        self.cur.execute('SELECT * FROM users WHERE email=?', email)
        user = self.cur.fetchone()
        if user:
            self.cur.close()
            return user
        else:
            self.cur.close()
            message = "User not found"
            Message(text=message)
            return None

    def verify(self, username: str = "", password: str = ""):

        self.cur.execute(
            'SELECT * FROM users WHERE username=? AND password=?',
            (username, password)
        )
        user = self.cur.fetchone()
        if user:
            self.cur.close()
            print('Checking password')
            self.cur.execute('SELECT * FROM users WHERE  username=? AND password=?', (username, password))
            user[2] = self.cur.fetchone()
            if user[2]:
                self.cur.close()
                return True
            else:
                self.cur.close()
                message = "Wrong password"
                Message(text=message)

        else:
            self.cur.close()
            message = "username or password incorrect"
            Message(text=message)

        return False
