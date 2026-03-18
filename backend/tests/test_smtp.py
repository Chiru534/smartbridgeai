import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv

load_dotenv()

smtp_user = os.getenv("SMTP_USER")
smtp_pass = os.getenv("SMTP_PASS")

print(f"Testing SMTP login for: {smtp_user}")

try:
    msg = EmailMessage()
    msg.set_content("This is a test email to verify SMTP configuration is working correctly for the Smartbridge platform.")
    msg["Subject"] = "[Smartbridge] SMTP Configuration Test"
    msg["From"] = smtp_user
    msg["To"] = smtp_user

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.set_debuglevel(1)  # Enable debug output
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    print("\nSUCCESS: SMTP login and email dispatch worked perfectly!")
except Exception as e:
    print(f"\nERROR: SMTP test failed. Details: {e}")
