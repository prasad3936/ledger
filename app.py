from flask import Flask, render_template, request, redirect, url_for, flash, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os
import threading
import webview
import pywhatkit as kit

app = Flask(__name__)

# Secret key for session management
app.secret_key = os.urandom(24)

# Configuration for SQLite Database
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///customer_db.sqlite'
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

import os
import sys
from dotenv import load_dotenv
#load_dotenv()  # only needed if you're using a .env file locally
if getattr(sys, 'frozen', False):
    dotenv_path = os.path.join(sys._MEIPASS, '.env')
else:
    dotenv_path = '.env'

load_dotenv(dotenv_path)


db_user = os.environ.get('DB_USER')
db_password = os.environ.get('DB_PASSWORD')
db_host = os.environ.get('DB_HOST')
db_port = os.environ.get('DB_PORT', '14627')
db_name = 'ledgerdb'

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False



db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Redirect unauthorized users to the login page
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    customers = db.relationship('Customer', backref='user', lazy=True)


# Other models
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'credit' or 'debit'
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    remark = db.Column(db.String(255), nullable=True)


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), nullable=False)
    amount = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', cascade="all, delete-orphan", backref='customer')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_click_to_chat_url(customer_name, customer_mobile, reminder_details, amount, user):
    """
    Generates a WhatsApp Click-to-Chat URL with a pre-filled reminder message.
    """
    # Prepare the message text
    message_body = (
        f"Dear {customer_name},\n\n"
        f"You have the following unpaid bills:\n{reminder_details}\n\n"
        f"Total Amount Due: {amount}\n\n"
        f"Please make the payment at your earliest convenience.\n\n"
        f"Regards,\n {user}.\n"
        f"Powered By Ledger"
    )
    
    # Encode the message for the URL
    encoded_message = message_body.replace(' ', '%20').replace('\n', '%0A')
    
    # Generate the WhatsApp Click-to-Chat URL
    whatsapp_url = f"https://wa.me/{customer_mobile}?text={encoded_message}"
    return whatsapp_url



# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            flash("Login successful!", "success")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash("Invalid username or password. Please try again.", "danger")

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash("Username already exists. Please choose a different username.", "danger")
        else:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for('login'))

    return render_template('setup.html')


@app.route('/')
@login_required
def index():
    user = current_user
    username = user.username if user else 'Guest'
    page = request.args.get('page', 1, type=int)
    customers = Customer.query.filter_by(user_id=user.id).paginate(page=page, per_page=7, error_out=False)
    total_amount = db.session.query(db.func.sum(Customer.amount)).filter_by(user_id=user.id).scalar() or 0

    return render_template('index.html', customers=customers.items, total_amount=total_amount, username=username, pagination=customers)


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        amount = request.form['amount']

        new_customer = Customer(name=name, mobile=mobile, amount=amount, user_id=current_user.id)
        db.session.add(new_customer)
        db.session.commit()

        return redirect(url_for('index'))
    return render_template('add_customer.html')


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    customer = Customer.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        customer.name = request.form['name']
        customer.mobile = request.form['mobile']
        customer.amount = request.form['amount']
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('edit_customer.html', customer=customer)


@app.route('/delete/<int:id>')
@login_required
def delete_customer(id):
    customer = Customer.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/transaction/<int:id>', methods=['POST'])
@login_required
def transaction(id):
    customer = Customer.query.get_or_404(id)
    amount = float(request.form['amount'])
    remark = request.form['remark']
    action = request.form['action']  # Get the action (credit or debit) from the clicked button

    if action == 'credit':
        customer.amount += amount
        transaction = Transaction(customer_id=id, type='credit', amount=amount, remark=remark)

    elif action == 'debit':
        if customer.amount >= amount:
            customer.amount -= amount
            transaction = Transaction(customer_id=id, type='debit', amount=amount, remark=remark)
        else:
            error_message = "Insufficient balance. Please check your account and try again."
            return render_template('error.html', error_message=error_message), 400

    db.session.add(transaction)
    db.session.commit()

    return redirect(url_for('index'))



@app.route('/send_reminder/<int:customer_id>', methods=['GET'])
@login_required
def send_reminder(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    user = current_user.username
    reminder_details = f"Unpaid bills for {customer.name}"
    amount = customer.amount

    whatsapp_url = generate_click_to_chat_url(customer.name, customer.mobile, reminder_details,amount,user)

    # Render a page with a link that opens WhatsApp in a new tab
    return render_template("sent_reminder.html", whatsapp_url=whatsapp_url, customer_name=customer.name,user=user)

@app.route('/print_invoice/<int:id>')
@login_required
def print_invoice(id):
    customer = Customer.query.get_or_404(id)
    transactions = Transaction.query.filter_by(customer_id=id).order_by(Transaction.date.desc()).all()
    current_datetime = datetime.utcnow()
    return render_template('invoice.html', customer=customer, transactions=transactions, current_datetime=current_datetime)


@app.route('/print_customers')
@login_required
def print_customers():
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    total_amount = sum(customer.amount for customer in customers)
    current_datetime = datetime.utcnow()
    return render_template('print.html', customers=customers, total_amount=total_amount, total_customers=len(customers), current_datetime=current_datetime)


@app.route('/search')
@login_required
def search():
    query = request.args.get('query')
    page = request.args.get('page', 1, type=int)

    if query:
        customers = Customer.query.filter(
            (Customer.name.ilike(f"%{query}%") | Customer.mobile.ilike(f"%{query}%")) & (Customer.user_id == current_user.id)
        ).paginate(page=page, per_page=7, error_out=False)

        total_amount = db.session.query(db.func.sum(Customer.amount)).filter(
            (Customer.name.ilike(f"%{query}%") | Customer.mobile.ilike(f"%{query}%")) & (Customer.user_id == current_user.id)
        ).scalar() or 0
    else:
        flash("No Matching Records Found", "info")
        customers = None
        total_amount = 0

    return render_template('index.html', customers=customers.items if customers else [], total_amount=total_amount, query=query, pagination=customers)


# Function to run Flask in a separate thread
def run_flask():
    app.run(debug=False, use_reloader=False)


if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    webview.create_window('Ledger - Rakho Pai Pai Ka Hisaab', 'http://127.0.0.1:5000', width=1000, height=600, background_color="#F0F0F0")
    webview.start()
