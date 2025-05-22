from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from functools import wraps
from Class_Models import Car, Customer, Admin, Booking, get_db_connection

# To WebPage Directly.
import webbrowser
import threading
import os

# --> App

app = Flask(__name__)
app.secret_key = 'CS_138'
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400
)

# --- Helpers and decorators ---
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page','error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_user():
    return {'current_user': session.get('user')}

# --- Public routes --- -- -- ----------------------------
@app.route('/')
def home():
    cars = Car.all_available()
    featured_cars = Car.get_3_random_cars()
    return render_template('home.html', cars=cars,featured_cars= featured_cars)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact',methods = ["GET","POST"])
def contact():
    if request.method == "POST":
        flash("Message Sent!","success")
        return redirect(url_for('contact'))
    return render_template('contact.html')

# --- Cars ---
@app.route('/cars')
def cars():
    cars = Car.all_available()
    return render_template('cars.html', cars=cars)

@app.route('/car_details/<int:car_id>')
def car_details(car_id):
    car = Car.get_by_id(car_id)
    if not car:
        abort(404)
    # fetching 
    db = get_db_connection()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT username, rating, comment, review_date FROM reviews WHERE car_id=%s ORDER BY review_date DESC", (car_id,))
    reviews = cur.fetchall()
    db.close()
    return render_template('car_details.html', car=car, reviews=reviews)

# --- Authentication ---
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        license_no = request.form['license']
        password = request.form['password']
        user = Customer.authenticate(license_no, password)
        if user:
            session['user'] = {
                'id': user.id,
                'name': user.username,
                'license': user.license_no,
                'email': user.email,
                'address': user.address,
                'balance': user.balance,
                'user_type': 'customer'
            }
            session.permanent = True
            flash('Login successful!','success')
            return redirect(url_for('account'))
        flash('Invalid credentials','error')
    return render_template('auth.html', mode='login')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        data = {
            'username': request.form['name'],
            'password': request.form['password'],
            'license_no': request.form['license'],
            'email_id': request.form['email'],
            'address': request.form['address']
        }
        user = Customer.signup(**data)
        session['user'] = {
            'id': user.id,
            'name': user.username,
            'license': user.license_no,
            'email': user.email,
            'address': user.address,
            'balance': user.balance,
            'user_type': 'customer'
        }
        flash('Account created!','success')
        return redirect(url_for('account'))
    return render_template('auth.html', mode='signup')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out','error')
    return redirect(url_for('home'))

# --- Account & Booking ---
@app.route('/account')
def account():
    if 'user' not in session:
        return redirect(url_for('login'))
    uid = session['user']['id']
    booking = Booking.active_for_customer(uid)
    rented_car = booking.get_rented_car() if booking else None
    return render_template('account.html', user=session['user'], booking=booking,rented_car = rented_car)

@app.route('/add_balance', methods=['POST'])
@login_required
def add_balance():
    amount = float(request.form['amount'])
    user = Customer({'customer_id': session['user']['id'],
                     'username': session['user']['name'],
                     'password': '',
                     'email_id': session['user']['email'],
                     'address': session['user']['address'],
                     'balance': session['user']['balance']})
    user.add_balance(amount)
    session['user']['balance'] = user.balance
    flash(f'Added {amount} to balance','success')
    return redirect(url_for('account'))

@app.route('/payment/<int:car_id>')
def payment(car_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if session['user']['user_type'] == 'admin':
        flash("Admin can't Rent Cars :)","success")
        return redirect(url_for('admin_dashboard'))

    customer_id = session['user']['id']

    existing_booking = Booking.active_for_customer(customer_id)
    if existing_booking:
        flash('You already have a rented car. You can only rent one car at a time.','error')
        return redirect(url_for('account'))

    car = Car.get_by_id(car_id)
    if not car or not car.is_available:
        abort(404)
    return render_template('payment.html', car=car)

@app.route('/process_payment/<int:car_id>', methods=['POST'])
def process_payment(car_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    days = int(request.form['days'])
    uid = session['user']['id']
    car = Car.get_by_id(car_id)
    total = car.price_per_day * days
    if session['user']['balance'] < total:
        flash('Insufficient balance','error')
        return redirect(url_for('payment', car_id=car_id))
    # deduct and book
    user = Customer({'customer_id': uid, 'balance': session['user']['balance']})
    user.add_balance(-total) 
    session['user']['balance'] = user.balance
    car.is_available = False
    car.save()
    Booking.create(uid, car_id, days, total)
    flash('Booking done','success')
    return redirect(url_for('account'))

# --- reviews ---
@app.route('/add_review/<int:car_id>', methods=['GET','POST'])
def add_review(car_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        db = get_db_connection()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO reviews (customer_id, car_id, username, license_no, rating, comment) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (session['user']['id'], car_id, session['user']['name'],
             session['user']['license'], request.form['rating'], request.form['comment'])
        )
        db.commit()
        db.close()
        flash('Review added','success')
        return redirect(url_for('account', car_id=car_id))
    return render_template('add_review.html', car_id=car_id)

# --- Admin ---
@app.route('/admin_login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        admin = Admin.authenticate(request.form['admin_code'], request.form['admin_password'])
        if admin and admin.email == request.form['admin_email']:
            session['user'] = {'id': admin.id, 'name':'Admin', 'user_type':'admin'}
            flash('Welcome Admin','success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin creds','error')
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if session['user']['user_type'] != 'admin':
        flash('Admins only','error')
        return redirect(url_for('home'))

    db = get_db_connection()
    mycursor = db.cursor()
    mycursor.execute("SELECT COUNT(*) FROM rentals")
    rental_count = mycursor.fetchone()[0] 
    mycursor.execute("SELECT COUNT(*) FROM cars")
    total_cars = mycursor.fetchone()[0] 


    return render_template('admin_dashboard.html',rental_count = rental_count,total_cars = total_cars)

@app.route('/manage_cars')
@login_required
def manage_cars():
    cars = Car.all_available() + [c for c in Car.all_available() if not c.is_available]
    return render_template('manage_cars.html', cars=cars)

@app.route('/add_car', methods=['GET','POST'])
def add_car():
    if request.method == 'POST':
        car = Car({
            'car_id': None, 'name': request.form['name'], 'brand':request.form['brand'],
            'price_per_day':request.form['price_per_day'], 'seating_capacity':request.form['seating_capacity'],
            'fuel_type':request.form['fuel_type'], 'cc':request.form['CC'], 'hp':request.form['Hp'],
            'top_speed':request.form['Top_Speed'], 'dimension':request.form['Dimension'],
            'year':request.form['Year'], 'air_conditioned':1 if 'Air_conditioned' in request.form else 0,
            'is_available':1 if 'is_available' in request.form else 0, 'img_link':request.form['Img_link']
        })
        car.save()
        flash('Car added','success')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_car.html')

@app.route('/delete_car_page', methods=['GET', 'POST'])
def delete_car_page():
    return render_template('delete_car.html')

@app.route('/delete_car', methods=['POST'])
def delete_car():
    car_id = request.form['car_id']
    car = Car.get_by_id(car_id)
    if car:

        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        cur.execute('SELECT * FROM rentals WHERE car_id = %s', (car_id,))
        result = cur.fetchone()
        
        if result:
            flash("Car is Currently Booked, Can't be Deleted!","error")
            return redirect(url_for('delete_car_page'))
        
        car.delete()
        flash('Car removed','success')
        
    else:
        flash('Car not found','error')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/bookings')
def manage_bookings():
    rentals = Booking.all_bookings()

    return render_template('manage_bookings.html', rentals=rentals)

@app.route('/mark_returned/<int:rental_id>', methods=['POST'])
def mark_returned(rental_id):

    db = get_db_connection()
    cur = db.cursor(dictionary=True)
    cur.execute('SELECT * FROM rentals WHERE rental_id = %s', (rental_id,))
    result = cur.fetchone()

    if not result:
        flash('Rental not found.', 'error')
        return redirect(url_for('manage_bookings'))

    # b = Booking({'rental_id': rental_id})
    b = Booking(result)
    b.mark_returned()
    flash('Returned','success')
    return redirect(url_for('manage_bookings'))

@app.route('/manage_customers')
def manage_customers():
    customers = Customer.get_all_customers()
    return render_template('manage_customers.html', customers=customers)

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.5, open_browser).start()
    app.run(debug=True,host='0.0.0.0', port=5000)
