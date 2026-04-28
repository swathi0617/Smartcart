from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify, make_response
from flask_mail import Mail, Message
import sqlite3
import bcrypt
import random
import config
import os
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer
import razorpay
import traceback
from utils.pdf_generator import generate_pdf

app = Flask(__name__)

razorpay_client = razorpay.Client(
    auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)
)
app.secret_key = config.SECRET_KEY
serializer = URLSafeTimedSerializer(app.secret_key)
app.config['MAIL_SERVER'] = config.MAIL_SERVER
app.config['MAIL_PORT'] = config.MAIL_PORT
app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = config.MAIL_USERNAME

mail = Mail(app)

# -------------------- SQLITE3 DB CONNECTION --------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "smartcart.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            profile_image TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            profile_image TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            category TEXT,
            original_price REAL,
            discount_percent INTEGER,
            price REAL,
            coins INTEGER,
            image TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            phone TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            pincode TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            address_id INTEGER,
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT,
            amount REAL,
            payment_status TEXT,
            order_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            product_name TEXT,
            quantity INTEGER,
            price REAL
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, stored_hash):
    if stored_hash is None:
        return False
    if isinstance(stored_hash, bytes):
        stored_hash = stored_hash.decode('utf-8')
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

os.makedirs(os.path.join(BASE_DIR, 'static/uploads/product_images'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static/uploads/admin_profiles'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static/uploads/user_profiles'), exist_ok=True)

# ---------------------------------------------------------
# ROUTE 1: ADMIN SIGNUP (SEND OTP)
# ---------------------------------------------------------
@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():

    # Show form
    if request.method == "GET":
        return render_template("admin/admin_signup.html")

    # POST → Process signup
    name = request.form['name']
    email = request.form['email']

    # 1️⃣ Check if admin email already exists
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id FROM admin WHERE email=?", (email,))
    existing_admin = cursor.fetchone()
    cursor.close()
    conn.close()

    if existing_admin:
        flash("This email is already registered. Please login instead.", "danger")
        return redirect('/admin-signup')

    # 2️⃣ Save user input temporarily in session
    session['signup_name'] = name
    session['signup_email'] = email

    # 3️⃣ Generate OTP and store in session
    otp = random.randint(100000, 999999)
    session['otp'] = otp

    # 4️⃣ Send OTP Email
    message = Message(
        subject="SmartCart Admin OTP",
        sender=config.MAIL_USERNAME,
        recipients=[email]
    )
    message.body = f"Your OTP for SmartCart Admin Registration is: {otp}"
    mail.send(message)

    flash("OTP sent to your email!", "success")
    return redirect('/verify-otp')



# ---------------------------------------------------------
# ROUTE 2: DISPLAY OTP PAGE
# ---------------------------------------------------------
@app.route('/verify-otp', methods=['GET'])
def verify_otp_get():
    return render_template("admin/verify_otp.html")



# ---------------------------------------------------------
# ROUTE 3: VERIFY OTP + SAVE ADMIN
# ---------------------------------------------------------
@app.route('/verify-otp', methods=['POST'])
def verify_otp_post():

    # User submitted OTP + Password
    user_otp = request.form['otp']
    password = request.form['password']

    # Compare OTP
    if str(session.get('otp')) != str(user_otp):
        flash("Invalid OTP. Try again!", "danger")
        return redirect('/verify-otp')

    # Hash password using bcrypt
    hashed_password = hash_password(password)

    # Insert admin into database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO admin (name, email, password) VALUES (?, ?, ?)",
        (session['signup_name'], session['signup_email'], hashed_password)
    )
    conn.commit()
    cursor.close()
    conn.close()

    # Clear temporary session data
    session.pop('otp', None)
    session.pop('signup_name', None)
    session.pop('signup_email', None)

    flash("Admin Registered Successfully!", "success")
    return redirect('/admin-signup')


# =================================================================
# ROUTE 4: ADMIN LOGIN PAGE (GET + POST)
# =================================================================
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():

    # Show login page
    if request.method == 'GET':
        return render_template("admin/admin_login.html")

    # POST → Validate login
    email = request.form['email']
    password = request.form['password']

    # Step 1: Check if admin email exists
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM admin WHERE email=?", (email,))
    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    if admin is None:
        flash("Email not found! Please register first.", "danger")
        return redirect('/admin-login')

    # Step 2: Compare entered password with hashed password
    if not check_password(password, admin['password']):
        flash("Incorrect password! Try again.", "danger")
        return redirect('/admin-login')

    # Step 5: If login success → Create admin session
    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']
    session['admin_email'] = admin['email']

    flash("Login Successful!", "success")
    return redirect('/admin-dashboard')
#==================================================================
# forgot paaword route
#==================================================================
@app.route('/forgot-password', methods=['GET', 'POST'])
def admin_forgot_password():

    if request.method == 'GET':
        return render_template("admin/forgot_password.html")

    email = request.form.get('email', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM admin WHERE email = ?", (email,))
    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    if not admin:
        flash("Admin email not found!", "danger")
        return redirect('/forgot-password')

    flash("Reset link sent to admin email!", "success")
    return redirect('/forgot-password')
#=============================================================
#reset_password
#===============================================================
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='reset-password', max_age=600)
    except:
        flash("Invalid or expired link", "danger")
        return redirect('/admin-login')

    if request.method == 'POST':
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            flash("Passwords do not match", "danger")
            return redirect(request.url)

        hashed = hash_password(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE admin SET password=? WHERE email=?",
            (hashed, email)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Password updated successfully!", "success")
        return redirect(url_for('admin_login'))

    return render_template('admin/reset_password.html')

# =================================================================
# ROUTE 5: ADMIN DASHBOARD (PROTECTED ROUTE)
# =================================================================
@app.route('/admin-dashboard')
def admin_dashboard():

    # Protect dashboard → Only logged-in admin can access
    if 'admin_id' not in session:
        flash("Please login to access dashboard!", "danger")
        return redirect('/admin-login')

    # Send admin name to dashboard UI
    return render_template("admin/dashboard.html", admin_name=session['admin_name'])



# =================================================================
# ROUTE 6: ADMIN LOGOUT
# =================================================================
@app.route('/admin-logout')
def admin_logout():

    # Clear admin session
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_email', None)

    flash("Logged out successfully.", "success")
    return redirect('/admin-login')

# ------------------- IMAGE UPLOAD PATH -------------------
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads/product_images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# =================================================================
# ROUTE 7: SHOW ADD PRODUCT PAGE (Protected Route)
# =================================================================
@app.route('/admin/add-item', methods=['GET'])
def add_item_page():

    # Only logged-in admin can access
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    return render_template("admin/add_item.html")



# =================================================================
# ROUTE 8: ADD PRODUCT INTO DATABASE
# =================================================================
@app.route('/admin/add-item', methods=['POST'])
def add_item():

    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    name = request.form['name']
    description = request.form['description']
    category = request.form['category']

    original_price = float(request.form['original_price'])
    discount_percent = int(request.form['discount_percent'])

    discount_amount = original_price * discount_percent / 100
    price = original_price - discount_amount

    if price >= 1000:
        coins = 100
    elif price >= 500:
        coins = 50
    else:
        coins = 0

    image_file = request.files['image']

    if image_file.filename == "":
        flash("Please upload a product image!", "danger")
        return redirect('/admin/add-item')

    filename = secure_filename(image_file.filename)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image_file.save(image_path)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products 
        (name, description, category, original_price, discount_percent, price, coins, image)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        description,
        category,
        original_price,
        discount_percent,
        price,
        coins,
        filename
    ))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Product added successfully!", "success")
    return redirect('/admin/add-item')

# =================================================================
# ROUTE 9: DISPLAY ALL PRODUCTS (Admin)
# ===============================================================

#=================================================================
# ROUTE 10: VIEW SINGLE PRODUCT DETAILS
# =================================================================
@app.route('/admin/view-item/<int:item_id>')
def view_item(item_id):

    # Check admin session
    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products WHERE product_id = ?", (item_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/view_item.html", product=product)


# =================================================================
# ROUTE 11: SHOW UPDATE FORM WITH EXISTING DATA
# =================================================================
@app.route('/admin/update-item/<int:item_id>', methods=['GET'])
def update_item_page(item_id):

    # Check login
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    # Fetch product data
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products WHERE product_id = ?", (item_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    return render_template("admin/update_item.html", product=product)

# =================================================================
# ROUTE-12: UPDATE PRODUCT + OPTIONAL IMAGE REPLACE
# =================================================================
@app.route('/admin/update-item/<int:item_id>', methods=['POST'])
def update_item(item_id):

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    # 1️⃣ Get updated form data
    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    price = request.form['price']

    new_image = request.files['image']

    # 2️⃣ Fetch old product data
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE product_id = ?", (item_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    old_image_name = product['image']

    # 3️⃣ If admin uploaded a new image → replace it
    if new_image and new_image.filename != "":

        # Secure filename
        from werkzeug.utils import secure_filename
        new_filename = secure_filename(new_image.filename)

        # Save new image
        new_image_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        new_image.save(new_image_path)

        # Delete old image file
        old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], old_image_name)
        if os.path.exists(old_image_path):
            os.remove(old_image_path)

        final_image_name = new_filename

    else:
        # No new image uploaded → keep old one
        final_image_name = old_image_name

    # 4️⃣ Update product in the database
    cursor.execute("""
        UPDATE products
        SET name=?, description=?, category=?, price=?, image=?
        WHERE product_id=?
    """, (name, description, category, price, final_image_name, item_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Product updated successfully!", "success")
    return redirect('/admin/item-list')

# =================================================================
# ROUTE 13: UPDATED PRODUCT LIST WITH SEARCH + CATEGORY FILTER
# =================================================================
@app.route('/admin/item-list')
def item_list():

    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append("%" + search + "%")

    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/item_list.html",
        products=products,
        categories=categories
    )
# =================================================================
# ROUTE 14: DELETE PRODUCT
# =================================================================
@app.route('/admin/delete-item/<int:item_id>')
def delete_item(item_id):

    if 'admin_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT image FROM products WHERE product_id=?", (item_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/admin/item-list')

    image_name = product['image']

    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_name)
    if os.path.exists(image_path):
        os.remove(image_path)

    cursor.execute("DELETE FROM products WHERE product_id=?", (item_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Product deleted successfully!", "success")
    return redirect('/admin/item-list')
#==========================================================
# add admin profile
#==========================================================
ADMIN_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads/admin_profiles')
app.config['ADMIN_UPLOAD_FOLDER'] = ADMIN_UPLOAD_FOLDER

# =================================================================
# ROUTE 1: SHOW ADMIN PROFILE DATA
# =================================================================
@app.route('/admin/profile', methods=['GET'])
def admin_profile():

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM admin WHERE admin_id = ?", (admin_id,))
    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("admin/admin_profile.html", admin=admin)


# =================================================================
# ROUTE 2: UPDATE ADMIN PROFILE (NAME, EMAIL, PASSWORD, IMAGE)
# =================================================================
@app.route('/admin/profile', methods=['POST'])
def admin_profile_update():

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    admin_id = session['admin_id']

    # 1️⃣ Get form data
    name = request.form['name']
    email = request.form['email']
    new_password = request.form['password']
    new_image = request.files['profile_image']

    conn = get_db_connection()
    cursor = conn.cursor()

    # 2️⃣ Fetch old admin data
    cursor.execute("SELECT * FROM admin WHERE admin_id = ?", (admin_id,))
    admin = cursor.fetchone()

    old_image_name = admin['profile_image']

    # 3️⃣ Update password only if entered
    if new_password:
        hashed_password = hash_password(new_password)
    else:
        hashed_password = admin['password']  # keep old password

    # 4️⃣ Process new profile image if uploaded
    if new_image and new_image.filename != "":

        from werkzeug.utils import secure_filename
        new_filename = secure_filename(new_image.filename)

        # Save new image
        image_path = os.path.join(app.config['ADMIN_UPLOAD_FOLDER'], new_filename)
        new_image.save(image_path)

        # Delete old image
        if old_image_name:
            old_image_path = os.path.join(app.config['ADMIN_UPLOAD_FOLDER'], old_image_name)
            if os.path.exists(old_image_path):
                os.remove(old_image_path)

        final_image_name = new_filename
    else:
        final_image_name = old_image_name

    # 5️⃣ Update database
    cursor.execute("""
        UPDATE admin
        SET name=?, email=?, password=?, profile_image=?
        WHERE admin_id=?
    """, (name, email, hashed_password, final_image_name, admin_id))

    conn.commit()
    cursor.close()
    conn.close()

    # Update session name for UI consistency
    session['admin_name'] = name  
    session['admin_email'] = email

    flash("Profile updated successfully!", "success")
    return redirect('/admin/profile')

# =================================================================
# ROUTE: USER REGISTRATION
# =================================================================
@app.route('/user-register', methods=['GET', 'POST'])
def user_register():

    if request.method == 'GET':
        return render_template("user/user_register.html")

    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    # Check if user already exists
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        flash("Email already registered! Please login.", "danger")
        return redirect('/user-register')

    # Hash password
    hashed_password = hash_password(password)

    # Insert new user
    cursor.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        (name, email, hashed_password)
    )
    conn.commit()

    cursor.close()
    conn.close()

    flash("Registration successful! Please login.", "success")
    return redirect('/user-login')
# =================================================================
# ROUTE: USER LOGIN
# =================================================================
@app.route('/', methods=['GET', 'POST'])
@app.route('/user-login', methods=['GET', 'POST'])
def user_login():

    # Open login page
    if request.method == 'GET':
        session.pop('_flashes', None)
        return render_template("user/user_login.html")

    # Form values
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    # Empty validation
    if not email or not password:
        flash("Please enter email and password!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    # Email not found
    if not user:
        flash("Email not found! Please register.", "danger")
        return redirect('/user-login')

    # Password wrong
    if not check_password(password, user['password']):
        flash("Incorrect password!", "danger")
        return redirect('/user-login')

    # Clear old session
    session.clear()

    # New session
    session['user_id'] = user['user_id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']

    flash("Login successful!", "success")
    return redirect('/user-dashboard')
#============== forgot password==========
@app.route('/user/forgot-password', methods=['GET', 'POST'])
def user_forgot_password():

    if request.method == 'GET':
        return render_template("user/forgot_password.html")

    email = request.form.get('email')

    flash("User reset link sent!", "success")
    return redirect('/user/forgot-password')

# =================================================================
# ROUTE: USER DASHBOARD
# =================================================================
@app.route('/user-dashboard')
def user_dashboard():

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COALESCE(SUM(quantity),0) AS cart_count
        FROM cart
        WHERE user_id=?
    """, (user_id,))
    cart_count = cursor.fetchone()['cart_count']

    cursor.execute("""
        SELECT COALESCE(SUM(MAX(p.original_price - p.price, 0) * c.quantity),0) AS saved_amount
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id=?
    """, (user_id,))
    saved_amount = cursor.fetchone()['saved_amount']

    cursor.execute("""
        SELECT DISTINCT category
        FROM products
        WHERE category IS NOT NULL AND category!=''
        ORDER BY category ASC
    """)
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "user/user_home.html",
        user_name=session.get("user_name", "User"),
        cart_count=cart_count,
        saved_amount=saved_amount,
        member_since=2026,
        categories=categories
    )
# =================================================================
# ROUTE: USER LOGOUT
# =================================================================
@app.route('/user-logout')
def user_logout():

    # Clear complete session
    session.clear()

    # Remove any pending old flash messages
    session.pop('_flashes', None)

    # Show only logout message
    flash("Logged out successfully!", "success")

    return redirect('/user-login')

# =================================================================
# ROUTE: USER PRODUCT LISTING (SEARCH + FILTER)
# =================================================================
@app.route('/user/products')
def user_products():

    # Optional: restrict only logged-in users
    if 'user_id' not in session:
        flash("Please login to view products!", "danger")
        return redirect('/user-login')

    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch categories for filter dropdown
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = cursor.fetchall()

    # Build dynamic SQL
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append("%" + search + "%")

    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)

    cursor.execute(query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "user/user_products.html",
        products=products,
        categories=categories
    )

# =================================================================
# ROUTE: USER PRODUCT DETAILS PAGE
# =================================================================
@app.route('/user/product/<int:product_id>')
def user_product_details(product_id):

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        flash("Product not found!", "danger")
        return redirect('/user/products')

    return render_template("user/product_details.html", product=product)

# =================================================================
# ADD ITEM TO CART
# =================================================================
@app.route('/user/add-to-cart/<int:product_id>')
def add_to_cart(product_id):

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM cart
        WHERE user_id=? AND product_id=?
    """, (user_id, product_id))

    item = cursor.fetchone()

    if item:
        cursor.execute("""
            UPDATE cart
            SET quantity = quantity + 1
            WHERE user_id=? AND product_id=?
        """, (user_id, product_id))
    else:
        cursor.execute("""
            INSERT INTO cart(user_id, product_id, quantity)
            VALUES(?, ?, 1)
        """, (user_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Item added to cart successfully!", "success")
    return redirect(request.referrer)

# =================================================================
# VIEW CART PAGE
# =================================================================
@app.route('/user/cart')
def user_cart():
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            c.quantity,
            p.product_id,
            p.name,
            p.price,
            p.original_price,
            p.image,
            (p.price * c.quantity) AS total_price
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id = ?
    """, (user_id,))

    cart_items = cursor.fetchall()

    grand_total = sum(item['total_price'] for item in cart_items)
    saved_amount = sum(
        max((item['original_price'] or 0) - item['price'], 0) * item['quantity']
        for item in cart_items
    )

    cursor.close()
    conn.close()

    return render_template(
        "user/cart.html",
        cart_items=cart_items,
        grand_total=grand_total,
        saved_amount=saved_amount
    )
#====================cart increase===================================

@app.route('/user/cart/increase/<int:product_id>')
def increase_cart(product_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE cart
        SET quantity = quantity + 1
        WHERE user_id = ? AND product_id = ?
    """, (user_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/user/cart')
#====================cart decrease===========================

@app.route('/user/cart/decrease/<int:product_id>')
def decrease_cart(product_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE cart
        SET quantity = quantity - 1
        WHERE user_id = ? AND product_id = ? AND quantity > 1
    """, (user_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/user/cart')
#========================cart remove=======================

@app.route('/user/cart/remove/<int:product_id>')
def remove_cart(product_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM cart
        WHERE user_id = ? AND product_id = ?
    """, (user_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/user/cart')
USERS_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads/user_profiles')
app.config['USERS_UPLOAD_FOLDER'] = USERS_UPLOAD_FOLDER
#---------------------checkout select------------------------
@app.route('/checkout-selected', methods=['POST'])
def checkout_selected():

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    selected_products = request.form.getlist('selected_products')

    if not selected_products:
        flash("Please select at least one product!", "warning")
        return redirect('/user/cart')

    # selected ids session lo save
    session['selected_products'] = selected_products

    return redirect('/add-address')
# ==========================================================
# SHOW USER PROFILE
# ==========================================================
@app.route('/user/profile', methods=['GET'])
def user_profile():

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("user/user_profile.html", user=user)


# ==========================================================
# UPDATE USER PROFILE
# ==========================================================
@app.route('/user/profile', methods=['POST'])
def user_profile_update():

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    name = request.form['name']
    email = request.form['email']
    new_password = request.form['password']
    new_image = request.files['profile_image']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    old_image_name = user['profile_image'] if 'profile_image' in user.keys() else ''

    # Password update
    if new_password:
        hashed_password = hash_password(new_password)
    else:
        hashed_password = user['password']

    # Image upload
    if new_image and new_image.filename != "":
        from werkzeug.utils import secure_filename

        filename = secure_filename(new_image.filename)

        image_path = os.path.join(
            app.config['USERS_UPLOAD_FOLDER'],
            filename
        )
        new_image.save(image_path)

        # delete old image
        if old_image_name:
            old_path = os.path.join(
                app.config['USERS_UPLOAD_FOLDER'],
                old_image_name
            )
            if os.path.exists(old_path):
                os.remove(old_path)

        final_image_name = filename
    else:
        final_image_name = old_image_name

    # Update DB
    cursor.execute("""
        UPDATE users
        SET name=?, email=?, password=?, profile_image=?
        WHERE user_id=?
    """, (name, email, hashed_password, final_image_name, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    # Update session
    session['user_name'] = name
    session['user_email'] = email

    flash("Profile updated successfully!", "success")
    return redirect('/user/profile')

# =================================================================
# ROUTE: CREATE RAZORPAY ORDER
# =================================================================
@app.route('/user/pay')
def user_pay():

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.quantity, p.price
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id = ?
    """, (user_id,))
    cart_items = cursor.fetchall()

    cursor.close()
    conn.close()

    if not cart_items:
        flash("Your cart is empty!", "danger")
        return redirect('/user/products')

    total_amount = sum(float(item['price']) * int(item['quantity']) for item in cart_items)
    razorpay_amount = int(total_amount * 100)

    razorpay_order = razorpay_client.order.create({
        "amount": razorpay_amount,
        "currency": "INR",
        "payment_capture": "1"
    })

    session['razorpay_order_id'] = razorpay_order['id']

    return render_template(
        "user/payment.html",
        amount=total_amount,
        key_id=config.RAZORPAY_KEY_ID,
        order_id=razorpay_order['id']
    )

# =================================================================
# TEMP SUCCESS PAGE (Verification in Day 13)
# =================================================================
@app.route('/payment-success')
def payment_success():

    payment_id = request.args.get('payment_id')
    order_id = request.args.get('order_id')

    if not payment_id:
        flash("Payment failed!", "danger")
        return redirect('/user/cart')

    return render_template(
        "user/payment_success.html",
        payment_id=payment_id,
        order_id=order_id
    )

# ================= ADD ADDRESS =================
@app.route('/add-address', methods=['GET', 'POST'])
def add_address():
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        full_name = request.form['full_name']
        phone = request.form['phone']
        address = request.form['address']
        city = request.form['city']
        state = request.form['state']
        pincode = request.form['pincode']

        cursor.execute("""
            INSERT INTO addresses 
            (user_id, full_name, phone, address, city, state, pincode)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session['user_id'],
            full_name,
            phone,
            address,
            city,
            state,
            pincode
        ))

        conn.commit()
        flash("Address added successfully!", "success")
        return redirect('/add-address')

    cursor.execute(
        "SELECT * FROM addresses WHERE user_id=? ORDER BY id DESC",
        (session['user_id'],)
    )
    addresses = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('user/add_address.html', addresses=addresses)


# ================= EDIT ADDRESS =================
@app.route('/edit-address/<int:address_id>', methods=['GET', 'POST'])
def edit_address(address_id):
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM addresses WHERE id=? AND user_id=?",
        (address_id, session['user_id'])
    )
    address = cursor.fetchone()

    if not address:
        cursor.close()
        conn.close()
        flash("Address not found!", "danger")
        return redirect('/add-address')

    if request.method == 'POST':
        full_name = request.form['full_name']
        phone = request.form['phone']
        new_address = request.form['address']
        city = request.form['city']
        state = request.form['state']
        pincode = request.form['pincode']

        cursor.execute("""
            UPDATE addresses
            SET full_name=?, phone=?, address=?, city=?, state=?, pincode=?
            WHERE id=? AND user_id=?
        """, (
            full_name,
            phone,
            new_address,
            city,
            state,
            pincode,
            address_id,
            session['user_id']
        ))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Address updated successfully!", "success")
        return redirect('/add-address')

    cursor.close()
    conn.close()

    return render_template('user/edit_address.html', address=address)


# ================= DELETE ADDRESS =================
@app.route('/delete-address/<int:address_id>')
def delete_address(address_id):

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE orders
            SET address_id = NULL
            WHERE address_id = ? AND user_id = ?
        """, (address_id, user_id))

        cursor.execute("""
            DELETE FROM addresses
            WHERE id = ? AND user_id = ?
        """, (address_id, user_id))

        conn.commit()
        flash("Address deleted successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(str(e), "danger")

    finally:
        cursor.close()
        conn.close()

    return redirect('/add-address')


# ================= CONTINUE TO PAYMENT =================
@app.route('/continue-payment/<int:address_id>')
def continue_payment(address_id):
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    session['address_id'] = address_id
    return redirect(f'/payment/{address_id}')
#================================================
# payment
#====================================================
@app.route('/payment/<int:address_id>')
def payment(address_id):

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    selected_products = session.get('selected_products', [])

    if not selected_products:
        flash("Please select products first!", "warning")
        return redirect('/user/cart')

    selected_products = [int(pid) for pid in selected_products]

    conn = get_db_connection()
    cursor = conn.cursor()

    # address check
    cursor.execute("""
        SELECT *
        FROM addresses
        WHERE id = ? AND user_id = ?
    """, (address_id, user_id))

    address = cursor.fetchone()

    if not address:
        cursor.close()
        conn.close()
        flash("Address not found!", "danger")
        return redirect('/add-address')

    placeholders = ",".join(["?"] * len(selected_products))

    query = f"""
        SELECT 
            c.quantity,
            p.product_id,
            p.name,
            p.price,
            p.image,
            (p.price * c.quantity) AS total_price
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id = ?
        AND p.product_id IN ({placeholders})
    """

    values = [user_id] + selected_products

    cursor.execute(query, values)
    cart_items = cursor.fetchall()

    if not cart_items:
        cursor.close()
        conn.close()
        flash("Selected products not found in cart!", "danger")
        return redirect('/user/cart')

    grand_total = 0
    for item in cart_items:
        grand_total += float(item['total_price'])

    razorpay_order = razorpay_client.order.create({
        "amount": int(grand_total * 100),
        "currency": "INR",
        "payment_capture": 1
    })

    session['razorpay_order_id'] = razorpay_order['id']
    session['address_id'] = address_id

    cursor.close()
    conn.close()

    return render_template(
        'user/payment.html',
        cart_items=cart_items,
        grand_total=grand_total,
        key_id=config.RAZORPAY_KEY_ID,
        order_id=razorpay_order['id'],
        address_id=address_id,
        address=address
    )
# DAY 13: Verify Razorpay Payment & Store Order + Order Items



# Ensure razorpay_client is initialized (from Day 12)
# razorpay_client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))

# ------------------------------
# Route: Verify Payment and Store Order
# ------------------------------
@app.route('/verify-payment', methods=['POST'])
def verify_payment():

    if 'user_id' not in session:
        flash("Please login to complete the payment.", "danger")
        return redirect('/user-login')

    razorpay_payment_id = request.form.get('razorpay_payment_id')
    razorpay_order_id = request.form.get('razorpay_order_id')
    razorpay_signature = request.form.get('razorpay_signature')

    if not razorpay_payment_id or not razorpay_order_id or not razorpay_signature:
        flash("Payment verification failed. Missing payment data.", "danger")
        return redirect('/user/cart')

    payload = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    try:
        razorpay_client.utility.verify_payment_signature(payload)
    except Exception as e:
        print("PAYMENT VERIFY ERROR:", e)
        flash("Payment verification failed. Please try again.", "danger")
        return redirect('/user/cart')

    user_id = session['user_id']
    selected_products = session.get('selected_products', [])
    address_id = session.get('address_id')

    if not selected_products:
        flash("No selected products found.", "danger")
        return redirect('/user/cart')

    if not address_id:
        flash("Please select address first.", "danger")
        return redirect('/add-address')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        selected_products = [int(pid) for pid in selected_products]

        placeholders = ",".join(["?"] * len(selected_products))

        query = f"""
            SELECT 
                c.quantity,
                p.product_id,
                p.name,
                p.price
            FROM cart c
            JOIN products p ON c.product_id = p.product_id
            WHERE c.user_id = ?
            AND p.product_id IN ({placeholders})
        """

        values = [user_id] + selected_products

        cursor.execute(query, values)
        cart_items = cursor.fetchall()

        if not cart_items:
            flash("Selected cart items not found.", "danger")
            return redirect('/user/cart')

        total_amount = 0
        for item in cart_items:
            total_amount += float(item['price']) * int(item['quantity'])

        cursor.execute("""
            INSERT INTO orders 
            (user_id, address_id, razorpay_order_id, razorpay_payment_id, amount, payment_status, order_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            address_id,
            razorpay_order_id,
            razorpay_payment_id,
            total_amount,
            'paid',
            'Confirmed'
        ))

        order_db_id = cursor.lastrowid

        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items 
                (order_id, product_id, product_name, quantity, price)
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_db_id,
                item['product_id'],
                item['name'],
                item['quantity'],
                item['price']
            ))

        delete_query = f"""
            DELETE FROM cart
            WHERE user_id = ?
            AND product_id IN ({placeholders})
        """

        cursor.execute(delete_query, values)

        conn.commit()

        session.pop('selected_products', None)
        session.pop('razorpay_order_id', None)
        session.pop('address_id', None)

        flash("Payment successful and order placed!", "success")
        return redirect(f"/user/order-success/{order_db_id}")

    except Exception as e:
        conn.rollback()
        print("ORDER ERROR:", e)
        flash(str(e), "danger")
        return redirect('/user/cart')

    finally:
        cursor.close()
        conn.close()
#================================================================
# Orders Success
#===============================================================
@app.route('/user/order-success/<int:order_id>')
def order_success(order_id):

    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            o.*,
            a.full_name,
            a.phone,
            a.address,
            a.city,
            a.state,
            a.pincode
        FROM orders o
        LEFT JOIN addresses a ON o.address_id = a.id
        WHERE o.order_id = ? 
        AND o.user_id = ?
    """, (order_id, user_id))

    order = cursor.fetchone()

    if not order:
        cursor.close()
        conn.close()
        flash("Order not found!", "danger")
        return redirect('/user-dashboard')

    cursor.execute("""
        SELECT 
            product_id,
            product_name,
            quantity,
            price,
            (quantity * price) AS total_price
        FROM order_items
        WHERE order_id = ?
    """, (order_id,))

    items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "user/order_success.html",
        order=order,
        items=items
    )
#==========================================================
# my orders
#==========================================================
@app.route('/user/my-orders')
def User_my_orders():

    # Check login
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect('/user-login')

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch user orders latest first
    cursor.execute("""
        SELECT 
            order_id,
            razorpay_order_id,
            amount,
            payment_status,
            created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY order_id DESC
    """, (user_id,))

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'user/my_orders.html',
        orders=orders
    )

# ----------------------------
# GENERATE INVOICE PDF
# ----------------------------
@app.route("/user/download-invoice/<int:order_id>")
def download_invoice(order_id):

    if 'user_id' not in session:
        flash("Please login!", "danger")
        return redirect('/user-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            o.*,
            a.full_name,
            a.phone,
            a.address,
            a.city,
            a.state,
            a.pincode
        FROM orders o
        LEFT JOIN addresses a 
            ON o.address_id = a.id
        WHERE o.order_id = ?
        AND o.user_id = ?
    """, (order_id, session['user_id']))

    order = cursor.fetchone()

    if not order:
        cursor.close()
        conn.close()
        flash("Order not found.", "danger")
        return redirect('/user/my-orders')

    cursor.execute("""
        SELECT 
            product_name,
            quantity,
            price
        FROM order_items
        WHERE order_id = ?
    """, (order_id,))

    items = cursor.fetchall()

    cursor.close()
    conn.close()

    html = render_template(
        "user/invoice.html",
        order=order,
        items=items
    )

    pdf = generate_pdf(order, items)

    if not pdf:
        flash("Error generating PDF", "danger")
        return redirect('/user/my-orders')

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=invoice_{order_id}.pdf"

    return response

# ================================================================
# ADMIN: VIEW ALL ORDERS
# ================================================================
@app.route('/admin/orders')
def admin_orders():

    if 'admin_id' not in session:
        flash("Please login as admin!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT o.order_id, o.user_id, o.amount, 
               o.payment_status, o.order_status, o.created_at,
               u.name AS username
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        ORDER BY o.created_at DESC
    """)

    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin/order_list.html", orders=orders)

# ================================================================
# ADMIN: VIEW ORDER DETAILS
# ================================================================
@app.route('/admin/order/<int:order_id>')
def admin_order_details(order_id):

    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE order_id=?", (order_id,))
    order = cursor.fetchone()

    cursor.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/order_details.html", order=order, items=items)
# ================================================================
# ADMIN: UPDATE ORDER STATUS
# ================================================================
@app.route("/admin/update-order-status/<int:order_id>", methods=['POST'])
def update_order_status(order_id):
    if 'admin_id' not in session:
        flash("Please login!", "danger")
        return redirect('/admin-login')

    new_status = request.form.get('status')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE orders SET order_status=? WHERE order_id=?",
                    (new_status, order_id))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Order status updated successfully!", "success")
    return redirect(f"/admin/order/{order_id}")

# ------------------------ RUN SERVER -----------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
    
