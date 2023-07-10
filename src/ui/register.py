import tkinter
from tkinter import Label, Entry, Button, messagebox

class Register(tkinter.Frame):
    def __init__(self, parent, controller):

        tkinter.Frame.__init__(self, parent,
                               highlightbackground="#6699ff",
                               relief=tkinter.RIDGE, borderwidth=1530)
        self.controller = controller
        self.master = parent
        self.grid(padx=400, pady=50)
        self.label = Label(parent, text="Registration", font=("Times New Roman", 60, "bold"), bg="#6699ff",
                           fg="white", justify="center",highlightbackground="#6699ff")
        self.label.grid(row=0, column=0, columnspan=2, sticky="nsew")

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
        self.username_label = Label(self.master, text="Username", bg="#6699ff", fg="white")
        self.username_label.grid(row=2, column=0)
        self.username_entry = Entry(self.master, textvariable=self.usernames)
        self.username_entry.grid(row=2, column=1)
        self.password_label = Label(self.master, text="Password", bg="#6699ff", fg="white")
        self.password_label.grid(row=3, column=0)
        self.password_entry = Entry(self.master, textvariable=self.password, show="*")
        self.password_entry.grid(row=3, column=1)
        self.confirm_password_label = Label(self.master, text="Confirm Password", bg="#6699ff", fg="white")
        self.confirm_password_label.grid(row=4, column=0)
        self.confirm_password_entry = Entry(self.master, textvariable=self.confirm_password, show="*")
        self.confirm_password_entry.grid(row=4, column=1)
        self.first_name_label = Label(self.master, text="First Name", bg="#6699ff", fg="white")
        self.first_name_label.grid(row=5, column=0)
        self.first_name_entry = Entry(self.master, textvariable=self.first_name)
        self.first_name_entry.grid(row=5, column=1)
        self.last_name_label = Label(self.master, text="Last Name", bg="#6699ff", fg="white")
        self.last_name_label.grid(row=6, column=0)
        self.last_name_entry = Entry(self.master, textvariable=self.last_name)
        self.last_name_entry.grid(row=6, column=1)
        self.email_label = Label(self.master, text="Email", bg="#6699ff", fg="white")
        self.email_label.grid(row=7, column=0)
        self.email_entry = Entry(self.master, textvariable=self.email)
        self.email_entry.grid(row=7, column=1)
        self.phone_number_label = Label(self.master, text="Phone Number", bg="#6699ff", fg="white")
        self.phone_number_label.grid(row=8, column=0)
        self.phone_number_entry = Entry(self.master, textvariable=self.phone_number)
        self.phone_number_entry.grid(row=8, column=1)
        self.register_button = Button(self.master, text="SUBMIT",
                                      command=self.register_user(self.usernames.get(), self.password.get(),
                                                                 self.first_name.get(), self.last_name.get(),
                                                                 self.email.get(), self.phone_number.get()))
        self.register_button.grid(row=10, column=2)

        self.back_button = Button(self.master, text="GO BACK",
                                  command=lambda: self.controller.show_pages("Login"))
        self.back_button.grid(row=13, column=0)

    def register_user(
            self, username, password, first_name, last_name, email, phone
    ):

        if username == "" or password == "" or first_name == "" or last_name == "" or email == "" or phone == "":
            messagebox.showerror("Error", "All fields are required{0}".format([
                "" if username == "" else "\nPassword"
                                          "" if first_name == "" else '\nFirst Name'
                                                                      '' if last_name == "" else "\nLast Name"

                                                                                                 "" if email == "" else "\nEmail" + " if phone == ",
                " else ""\nPhone Number"
            ])

                                 )
            return
        if self.confirm_password != password:
            messagebox.showerror("Error", "Passwords do not match")
        try:

            # Create table users if it doesn't exist

            result = self.controller.db.cur.execute(
                "INSERT INTO " + self.controller.db.database + "_users (username, password, first_name, last_name, "
                                                               "email, phone,"
                                                               " ) VALUES (%s, %s, %s, %s,"
                                                               "%s, %s)",
                (username, password, first_name, last_name, email, phone
                 )
            )

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
