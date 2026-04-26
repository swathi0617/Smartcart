# config.py
# ------------------------------------
# This file holds all configurations
# like Secret Key, Database connection
# details, Email settings, Razorpay keys etc.
# ------------------------------------

SECRET_KEY = "your_secret_key_here"   # used for sessions

# MySQL Database Configuration
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "Swathi@123"  # keep empty if no password
DB_NAME = "smartcart"

# Email SMTP Settings
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'swathisampatam68@gmail.com'
MAIL_PASSWORD = 'kokm gvqu lbpj tkbv'   # Gmail App Password

RAZORPAY_KEY_ID = "rzp_test_ShE5m1yXJddi8o"
RAZORPAY_KEY_SECRET = "88Rf7VbQJDl9wyj6puOh1oTl"
