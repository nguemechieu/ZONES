import tkinter
from tkinter import messagebox


class ForgotPassword(tkinter.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)

        self.controller = controller
        self.parent = parent

        self.title = tkinter.Label(self.parent, text="Forgot Password")
        self.email_label = tkinter.Label(self.parent, text="Email")
        self.email_label.grid(row=0, column=0)
        self.email_entry = tkinter.Entry(self.parent, background='lightblue')
        self.email_entry.grid(row=0, column=1)
        self.email_button = tkinter.Button(self.parent, text="SUBMIT", command=lambda: self.submit())
        self.email_button.grid(row=3, column=2)
        self.go_back_button = tkinter.Button(self.parent, text="GO BACK",
                                             command=lambda: self.controller.show_pages('Login'))
        self.go_back_button.grid(row=3, column=0)
        self.go_back_button.focus()

    def submit(self):
        email = self.email_entry.get()
        if not email:
            messagebox.showerror(title="Error", message="Please enter an email")
            return False
        try:
            self.controller.db.cur.execute(
                "SELECT * FROM users WHERE email =?", (email
                                                       )
            )
            user = self.controller.cur.fetchone()
            if user:

                # Send email to user
                self.controller.send_email(
                    email=email,
                    subject="Password Reset Request",
                    message="Please click on the link below to reset your password",
                    link=f"http://localhost:5000/reset_password/{user['id']}",

                )

                self.email_entry.delete(0, tkinter.END)
                self.email_entry.focus()
                messagebox.showinfo(title="Success", message="Check your email for a password reset link")
                self.controller.show_page("Login")
                return True
            else:
                messagebox.showerror(title="Error", message="Invalid email")
                self.controller.show_page("Login")
                return False

        except Exception as e:
            messagebox.showerror(title="Error", message=str(e))
            return False
