import tkinter.messagebox
import MySQLdb
from configparser import ConfigParser


class Db(object):
    def __init__(self):
        self.config = ConfigParser()
        self.config.read("config.ini")
        self.host = self.config.get('mysql', 'host')
        self.user = self.config.get('mysql', 'user')
        self.password = self.config.get('mysql', 'password')
        self.database = self.config.get('mysql', 'database')
        self.port = self.config.get('mysql', 'port')

        try:
            self.conn = MySQLdb.connect(
                host=self.host,
                user=self.user,
                passwd=self.password,
                db=self.database,
                port=int(self.port)
            )
            self.cur = self.conn.cursor()

            self.cur.execute("CREATE DATABASE IF NOT EXISTS " + self.database)
            self.cur.execute("USE " + self.database)

            self.cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255),
                    username VARCHAR(255),
                    password VARCHAR(255),
                    phone VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255)
                )
            ''')

            self.cur.execute('''
                CREATE TABLE IF NOT EXISTS countries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    country VARCHAR(255)
                )
            ''')

            self.cur.execute('''
                CREATE TABLE IF NOT EXISTS states (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    state VARCHAR(255)
                )
            ''')

            self.cur.execute('''
                CREATE TABLE IF NOT EXISTS cities (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    city VARCHAR(255)
                )
            ''')

            self.cur.execute('INSERT INTO countries (country) VALUES ("United States of America")')
            self.cur.execute('INSERT INTO states (state) VALUES ("Alabama")')
            self.cur.execute('INSERT INTO cities (city) VALUES ("Montgomery")')
            self.cur.execute('INSERT INTO states (state) VALUES ("Alaska")')
            self.cur.execute('INSERT INTO states (state) VALUES ("Arizona")')
            self.cur.execute('INSERT INTO states (state) VALUES ("Arkansas")')

            self.conn.commit()

        except MySQLdb.Error:
            tkinter.messagebox.showerror("Error", "Error: unable to connect to MySQL server.")

    def verify(self, username: str, password: str) -> bool:
        try:
            self.cur.execute('SELECT * FROM users WHERE username=%s AND password=%s', (username, password))
            user = self.cur.fetchone()

            if user:
                return True
            else:
                tkinter.messagebox.showerror("Error", "Username or password incorrect")
                return False

        except MySQLdb.Error:
            tkinter.messagebox.showerror("Error", "Database error occurred.")
            return False
