import tkinter


from configparser import ConfigParser

from tkinter import Message


class Db:
    def __init__(self):
        # Create mysql connection
        self.users = None
        self.config = ConfigParser()
        self.config.add_section('mysql')
        self.config.read(filenames="config.ini")
        self.host = self.config.get(section='mysql', option='host')
        self.user = self.config.get(section='mysql', option='user')
        self.password = self.config.get(section='mysql', option='password')
        self.database = self.config.get(section='mysql', option='database')
        self.port = self.config.get(section='mysql', option='port')
        self.conn = MySQLdb.connect(host=self.host, user=self.user, passwd=self.password, db='')

        if self.conn is None:
            print("Error: unable to connect to MySQL server.")
            tkinter.Message(text="Error: unable to connect to MySQL server.")

            return
        self.cur = self.conn.cursor()
        self.cur.execute("CREATE  DATABASE IF NOT EXISTS " + self.database)
        self.cur.execute("USE " + self.database)
        self.cur.execute('CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(255)'
                         ',username VARCHAR(255), password VARCHAR(255), phone VARCHAR(255),'
                         'first_name VARCHAR(255), last_name VARCHAR(255))')

        self.conn.commit()

        self.cur.execute(
            'CREATE TABLE IF NOT EXISTS countries (id INT AUTO_INCREMENT PRIMARY KEY, country VARCHAR(255))')
        self.conn.commit()
        self.cur.execute('CREATE TABLE IF NOT EXISTS states (id INT AUTO_INCREMENT PRIMARY KEY, state VARCHAR(255))')
        self.conn.commit()
        self.cur.execute('CREATE TABLE IF NOT EXISTS cities (id INT AUTO_INCREMENT PRIMARY KEY, city VARCHAR(255))')
        self.conn.commit()
        self.cur.execute('INSERT INTO countries (country) VALUES ("United States of America")')
        self.conn.commit()
        self.cur.execute('INSERT INTO states (state) VALUES ("Alabama")')
        self.conn.commit()
        self.cur.execute('INSERT INTO cities (city) VALUES ("Montgomery")')
        self.conn.commit()
        self.cur.execute('INSERT INTO states (state) VALUES ("Alaska")')
        self.conn.commit()
        self.cur.execute('INSERT INTO states (state) VALUES ("Arizona")')
        self.conn.commit()
        self.cur.execute('INSERT INTO states (state) VALUES ("Arkansas")')
        self.conn.commit()

        self.conn.close()

    def get_all_users(self):
        self.cur.execute('SELECT * FROM ' + self.database + '_users ORDER BY id ASC')
        self.users = self.cur.fetchall()
        return self.users

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

    def get_countries(self):
        self.cur.execute('SELECT * FROM countries ORDER BY id ASC')
        [countries] = self.cur.fetchall()
        self.cur.close()

        return countries

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
        self.conn = MySQLdb.connect(db_name)
        self.cur = self.conn.cursor()
        self.cur.execute(statement, data)
        self.conn.commit()
        self.cur.close()

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
