import tkinter
from configparser import ConfigParser
import tkinter.filedialog
import mysql.connector 
class Db:
    def __init__(self):
        # Initialize the users dictionary with default values
        self.users: dict = {
            "id": 0,
            "email": "",
            "username": "",
            "password": "",
            "phone": "",
            "first_name": "",
            "last_name": "",
            "created_at": "",
            "updated_at": ""
        }

        # Read MySQL configuration from config.ini file
        self.config = ConfigParser()
        self.config.read(filenames="config.ini")
        self.host = self.config.get(section='mysql', option='host')
        self.user = self.config.get(section='mysql', option='user')
        self.password = self.config.get(section='mysql', option='password')
        self.database = self.config.get(section='mysql', option='database')
        self.port = self.config.get(section='mysql', option='port')

        # Create a MySQL engine and connection
        
#         self.engine = mysql.connector.connect(
#     user=self.user,
#     password=self.password,
#     host=self.host,
#     port=self.port,
#     database=self.database
# )
#         self.conn = self.engine.connect()
#         self.cur = self.conn.cursor()

#         # Check if the connection is successful, if not, print an error message
#         if self.conn is None:
#             print("Error: unable to connect to MySQL server.")
#             tkinter.Message(text="Error: unable to connect to MySQL server.")

#         # Create the database if it does not exist
#         self.cur.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")

#         # Create the users table if it does not exist
#         self.cur.execute(
#             'CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(255), '
#             'username VARCHAR(255), password VARCHAR(255), phone VARCHAR(255), '
#             'first_name VARCHAR(255), last_name VARCHAR(255), created_at DATETIME, updated_at DATETIME)')

#     def verify(self, username: str = "", password: str = ""):
#         # Execute a SQL query to select a user with the given username and password
#         self.cur.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
#         user = self.cur.fetchone()

#         if user:
#             # If the user is found, update the users dictionary and return True
#             self.users = dict(zip(["id", "email", "username", "password", "phone", "first_name", "last_name",
#                                    "created_at", "updated_at"], user))
#             return True
#         else:
#             # If the user is not found, display an appropriate message and return False
#             message = "Username or password incorrect"
#             tkinter.Message(message)
# #             return False

#     def insert_data(self, table: str = '', data=None):
#         # Insert data into the specified table
#         self.cur.execute(
#             f"INSERT INTO {table} (time, symbol, time_frame, open, high, low, close, volume) "
#             "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
#             (
#                 data['time'],
#                 data['symbol'],
#                 data['time_frame'],
#                 data['open'],
#                 data['high'],
#                 data['low'],
#                 data['close'],
#                 data['volume']
#             ))
#         # Commit the changes to the database
#         self.conn.commit()
