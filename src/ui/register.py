import tkinter
from tkinter import Label, Entry, Button, messagebox


class Register(tkinter.Frame):
    def __init__(self, controller):

        super().__init__()
        self.controller = controller
        self.config(bg="#6699ff", relief=tkinter.RIDGE, borderwidth=1, highlightthickness=1)


        self.master = self.winfo_toplevel()

        self.label = Label(self.master, text=" Registration ", bg="#6699ff")
        self.label.grid(row=0, column=0, padx=100, pady=10)
        self.usernames = tkinter.StringVar()
        self.usernames.set("Enter Username")
        self.password = tkinter.StringVar()
        self.password.set("<PASSWORD>")
        self.confirm_password = tkinter.StringVar()
        self.confirm_password.set("<PASSWORD>")
        self.first_name = tkinter.StringVar()
        self.first_name.set("Enter First Name")
        self.last_name = tkinter.StringVar()
        self.last_name.set("Enter Last Name")
        self.email = tkinter.StringVar()
        self.email.set("Enter Email")
        self.phone_number = tkinter.StringVar()
        self.phone_number.set("Enter Phone Number")
        self.address = tkinter.StringVar()
        self.address.set("Enter Address")
        self.city = tkinter.StringVar()
        self.city.set("Enter City")
        self.state = tkinter.StringVar()
        self.state.set("Enter State")
        self.country = tkinter.StringVar()
        self.country.set("Enter Country")
        self.zip_code = tkinter.StringVar()
        self.zip_code.set("Enter Zip Code")
        self.username_label = Label(self.master, text="Username", bg="#6699ff", fg="white")
        self.username_label.grid(row=0, column=0, padx=10, pady=10)
        self.username_entry = Entry(self.master, textvariable=self.usernames)
        self.username_entry.grid(row=0, column=1, padx=10, pady=10)
        self.password_label = Label(self.master, text="Password", bg="#6699ff", fg="white")
        self.password_label.grid(row=1, column=0, padx=10, pady=10)
        self.password_entry = Entry(self.master, textvariable=self.password, show="*")
        self.password_entry.grid(row=1, column=1, padx=10, pady=10)
        self.confirm_password_label = Label(self.master, text="Confirm Password", bg="#6699ff", fg="white")
        self.confirm_password_label.grid(row=2, column=0, padx=10, pady=10)
        self.confirm_password_entry = Entry(self.master, textvariable=self.confirm_password, show="*")
        self.confirm_password_entry.grid(row=2, column=1, padx=10, pady=10)
        self.first_name_label = Label(self.master, text="First Name", bg="#6699ff", fg="white")
        self.first_name_label.grid(row=3, column=0, padx=10, pady=10)
        self.first_name_entry = Entry(self.master, textvariable=self.first_name)
        self.first_name_entry.grid(row=3, column=1, padx=10, pady=10)
        self.last_name_label = Label(self.master, text="Last Name", bg="#6699ff", fg="white")
        self.last_name_label.grid(row=4, column=0, padx=10, pady=10)
        self.last_name_entry = Entry(self.master, textvariable=self.last_name)
        self.last_name_entry.grid(row=4, column=1, padx=10, pady=10)
        self.email_label = Label(self.master, text="Email", bg="#6699ff", fg="white")
        self.email_label.grid(row=5, column=0, padx=10, pady=10)
        self.email_entry = Entry(self.master, textvariable=self.email)
        self.email_entry.grid(row=5, column=1, padx=10, pady=10)
        self.phone_number_label = Label(self.master, text="Phone Number", bg="#6699ff", fg="white")
        self.phone_number_label.grid(row=6, column=0, padx=10, pady=10)
        self.phone_number_entry = Entry(self.master, textvariable=self.phone_number)
        self.phone_number_entry.grid(row=6, column=1, padx=10, pady=10)
        self.address_label = Label(self.master, text="Address", bg="#6699ff", fg="white")
        self.address_label.grid(row=7, column=0, padx=10, pady=10)
        self.address_entry = Entry(self.master, textvariable=self.address)
        self.address_entry.grid(row=7, column=1, padx=10, pady=10)
        self.city_label = Label(self.master, text="City", bg="#6699ff", fg="white")
        self.city_label.grid(row=8, column=0, padx=10, pady=10)
        self.city_entry = Entry(self.master, textvariable=self.city)
        self.city_entry.grid(row=8, column=1, padx=10, pady=10)
        self.state_label = Label(self.master, text="State", bg="#6699ff", fg="white")
        self.state_label.grid(row=9, column=0, padx=10, pady=10)
        self.state_entry = Entry(self.master, textvariable=self.state)
        self.state_entry.grid(row=9, column=1, padx=10, pady=10)
        self.zip_code_label = Label(self.master, text="Zip Code", bg="#6699ff", fg="white")
        self.zip_code_label.grid(row=10, column=0, padx=10, pady=10)
        self.zip_code_entry = Entry(self.master, textvariable=self.zip_code)
        self.zip_code_entry.grid(row=10, column=1, padx=10, pady=10)
        self.country_label = Label(self.master, text="Country", bg="#6699ff", fg="white")
        self.country_label.grid(row=11, column=0, padx=10, pady=10)
        self.country_entry = Entry(self.master, textvariable=self.country)
        self.country_entry.grid(row=11, column=1, padx=10, pady=10)
        self.register_button = Button(self.master, text="Register", bg="#6699ff", fg="white",
                                      command=self.register_user)
        self.register_button.grid(row=12, column=0, padx=10, pady=10)

        self.back_button = Button(self.master, text="Back", bg="#6699ff", fg="white",
                                  command=lambda: self.controller.show_pages("Login"))
        self.back_button.grid(row=12, column=2, padx=10, pady=10)

    def register_user(self):

        username = self.username_entry.get()
        password = self.password_entry.get()
        first_name = self.first_name_entry.get()
        last_name = self.last_name_entry.get()
        email = self.email_entry.get()
        phone = self.phone_number_entry.get()
        confirm_password = self.confirm_password_entry.get()
        address = self.address_entry.get()
        city = self.city_entry.get()
        state = self.state_entry.get()
        zip_code = self.zip_code_entry.get()
        country = self.country_entry.get()

        if username == "" or password == "" or first_name == "" or last_name == "" or email == "" or phone == "":
            messagebox.showerror("Error", "All fields are required{0}".format((
                "" if username == "" else "\nUsername"
                                          "" if password == "" else "\nPassword"
                                                                    "" if first_name == "" else '\nFirst Name'
                                                                                                '' if last_name == "" else "\nLast Name"

                                                                                                                           "" if email == "" else "\nEmail" + " if phone == "" else ""\nPhone Number"" if confirm_password == "" else ""\nConfirm Password""" if address == "" else "\nAddress"
                                                                                                                                                                                                                                                                                    "" if city == "" else "\nCity"
                                                                                                                                                                                                                                                                                                          "" if state == "" else "\nState"
                                                                                                                                                                                                                                                                                                                                 "" if zip_code == "" else "\nZip Code"
                                                                                                                                                                                                                                                                                                                                                           "" if country == "" else "\nCountry"

            ))

                                 )
            return
        if confirm_password != password:
            messagebox.showerror("Error", "Passwords do not match")
        try:

            # Create table users if it doesn't exist'

            self.controller.db.cur.execute("USE " + self.controller.db.database)

            self.controller.db.cur.execute("CREATE TABLE IF NOT EXISTS users (username VARCHAR(255),"
                                           "password VARCHAR(255), firstname VARCHAR(255),"
                                           "last_name VARCHAR(255),email VARCHAR(255),"
                                           

                                           "phone VARCHAR(255) ,"
                                           "_id INTEGER PRIMARY KEY AUTO_INCREMENT),"
                                           "FOREIGN KEY (username) REFERENCES users(username) ON")

            result = self.controller.db.cur.execute(
                "INSERT INTO users (username, password, firstname, last_name, email, phone) VALUES (%s, %s, %s, %s, "
                "%s, %s)",
                (username, password, first_name, last_name, email, phone)
            )

            self.controller.db.conn.commit()

            if result > 0:

                # Get the id of the new user

                self.controller.db.cur.execute("SELECT _id FROM users WHERE username = %s", (username,
                                                                                             ))
                user_id = self.controller.db.cur.fetchone()
                user_id = user_id[0]
                username = self.controller.db.cur.fetchone()
                username = username[0]
                first_name = self.controller.db.cur.fetchone()
                first_name = first_name[0]
                last_name = self.controller.db.cur.fetchone()
                last_name = last_name[0]
                email = self.controller.db.cur.fetchone()
                email = email[0]
                phone = self.controller.db.cur.fetchone()
                phone = phone[0]
                messagebox.showinfo("Success", "User registered successfully  " +
                                    " \n Username: " + username + "  " + user_id +
                                    " \n First Name: " + first_name +
                                    " \n Last Name: " + last_name +
                                    " \n Email: " + email +
                                    " \n Phone Number: " + phone)
                self.controller.show_pages('Login')

                return
            else:
                messagebox.showerror("Error", "User already exists")
                return

        except Exception as e:
            messagebox.showerror("Error", e.args[0])
