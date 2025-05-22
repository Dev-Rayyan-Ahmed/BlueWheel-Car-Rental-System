import mysql.connector #type: ignore [Using SQL Query Via Python]
from mysql.connector import Error # type: ignore [Error Handling]
from abc import ABC, abstractmethod
from datetime import datetime
import pytz #type: ignore  [ #for current Pakistan Time Zone ] 
import random
import os
from dotenv import load_dotenv


# User-Defined Error Class
class DatabaseConnectionError(Exception):
    def __init__(self, message="Failed to connect to the database"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"[DatabaseConnectionError] {self.message}"

def write_to_booking_history(customer_name,customer_license,car_name,date,total_amount,days):

    filename = "C:\\Coding (VScode)\\Codes\\CEP - OOP\\booking_history.txt"

    if not os.path.exists(filename):
        with open(filename, "w") as file:
            file.write("BlueWheels Booking History\n")
            file.write("==========================\n")
    
    with open(filename,"a") as file:

        print("HAPPY - ")

        file.write(f"Customer Name: {customer_name}\n")
        file.write(f"Customer License: {customer_license}\n")
        file.write(f"Car Booked: {car_name}\n")
        file.write(f"Booking Date: {str(date)[0:11]}\n") #Slicing to get only the Date-M-Year
        file.write(f"Booked for: {days} Days\n")
        file.write(f"Total Amount: ${total_amount}\n")
        file.write(f"================================>\n")
        file.flush()

# Database connector ~
def get_db_connection():
    try:
        load_dotenv()
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "cs138"),
            database=os.getenv("DB_NAME", "bluewheelsdb"),
            port=int(os.getenv("DB_PORT", 3306))
        )
        
        if conn.is_connected():
            return conn
        else:
            raise DatabaseConnectionError("Connection object was not established.")
    except Error as e:
        raise DatabaseConnectionError(f"MySQL Error: {str(e)}")

    except DatabaseConnectionError as e:
        print(str(e))
        return None

# Abstract User class with common interface
class User(ABC):
    def __init__(self, data):
        self.id = data.get(self._id_field)
        self.username = data.get('username')
        self.password = data.get('password')
        self.email = data.get('email_id')
        self.address = data.get('address')

    @property
    @abstractmethod
    def _id_field(self):
        """Database field name for user ID"""
        pass

    @abstractmethod
    def authenticate(self, *args, **kwargs):
        """Check credentials and return user instance if valid"""
        pass

# Admin user, inherits from User
class Admin(User):
    _id_field = 'admin_id'

    def __init__(self, data):
        super().__init__(data)
        self.admin_code = data.get('admin_code')

    @classmethod
    def authenticate(cls, admin_code, password):
        # check admin credentials
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        sql = "SELECT * FROM admins WHERE admin_code = %s"
        cur.execute(sql, (admin_code,))
        data = cur.fetchone()
        db.close()
        if data and data['password'] == password:
            return cls(data)
        return None

# Customer user, inherits from User
class Customer(User):
    _id_field = 'customer_id'

    def __init__(self, data):
        super().__init__(data)
        self.license_no = data.get('license_no') or data.get('lisense_no')
        self.balance = float(data.get('balance', 0))

    @classmethod
    def authenticate(cls, license_no, password):
        # check customer login
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        sql = "SELECT * FROM customers WHERE license_no = %s"
        cur.execute(sql, (license_no,))
        data = cur.fetchone()
        db.close()
        if data and data['password'] == password:
            return cls(data)
        return None

    @classmethod
    def signup(cls, username, password, license_no, email_id, address):
        # register new customer
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        sql = ("INSERT INTO customers "
               "(username, password, license_no, email_id, address) "
               "VALUES (%s, %s, %s, %s, %s)")
        cur.execute(sql, (username, password, license_no, email_id, address))
        db.commit()
        # fetch inserted record
        cur.execute("SELECT * FROM customers WHERE customer_id = %s", (cur.lastrowid,))
        data = cur.fetchone()
        db.close()
        return cls(data)

    def add_balance(self, amount):
        # increase customer's balance
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        sql = "UPDATE customers SET balance = balance + %s WHERE customer_id = %s"
        cur.execute(sql, (amount, self.id))
        db.commit()
        # update object balance
        self.balance += amount
        db.close()

    @classmethod
    def get_all_customers(cls):
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM customers")
        customers = cur.fetchall()
        customers_obj = [cls(c) for c in customers]
        return customers_obj
        


# Car model
class Car:
    def __init__(self, data):
        # map fields from DB to attributes
        self.car_id = data['car_id']
        self.name = data['name']
        self.brand = data['brand']
        self.price_per_day = data['price_per_day']
        self.seating_capacity = data['seating_capacity']
        self.fuel_type = data['fuel_type']
        self.cc = data['cc']
        self.hp = data['hp']
        self.top_speed = data['top_speed']
        self.dimension = data['dimension']
        self.year = data['year']
        self.air_conditioned = bool(data['air_conditioned'])
        self.is_available = bool(data['is_available'])
        self.img_link = data['img_link']

    @classmethod
    def get_3_random_cars(cls):
        all_cars = cls.all_available() 
        if len(all_cars) < 3:
            return all_cars 
        return random.sample(all_cars, 3)

    @classmethod
    def all_available(cls):
        # get all cars that are available
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM cars WHERE is_available = 1")
        rows = cur.fetchall()
        db.close()
        return [cls(r) for r in rows]

    @classmethod
    def get_by_id(cls, car_id):
        # get single car by id
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM cars WHERE car_id = %s", (car_id,))
        data = cur.fetchone()
        db.close()
        return cls(data) if data else None

    def save(self):
        # insert or update car record
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        if self.car_id:
            sql = ("UPDATE cars SET name=%s, brand=%s, price_per_day=%s, seating_capacity=%s, "
                   "fuel_type=%s, cc=%s, hp=%s, top_speed=%s, dimension=%s, year=%s, "
                   "air_conditioned=%s, is_available=%s, img_link=%s WHERE car_id=%s")
            params = (self.name, self.brand, self.price_per_day, self.seating_capacity,
                      self.fuel_type, self.cc, self.hp, self.top_speed,
                      self.dimension, self.year, int(self.air_conditioned),
                      int(self.is_available), self.img_link, self.car_id)
        else:
            sql = ("INSERT INTO cars (name, brand, price_per_day, seating_capacity, "
                   "fuel_type, cc, hp, top_speed, dimension, year, air_conditioned, is_available, img_link) "
                   "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
            params = (self.name, self.brand, self.price_per_day, self.seating_capacity,
                      self.fuel_type, self.CC, self.Hp, self.Top_Speed,
                      self.Dimension, self.Year, int(self.Air_conditioned),
                      int(self.is_available), self.Img_link)
        cur.execute(sql, params)
        db.commit()

        if not self.car_id:
            self.car_id = cur.lastrowid # to overide AutoIncrement of car_id,
        db.close()

    def delete(self):
        # remove car from DB
        if not self.car_id:
            return
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("DELETE FROM cars WHERE car_id = %s", (self.car_id,))
        db.commit()
        db.close()
    
    def to_dict(self):
        return {
            'id': self.car_id,
            'name': self.name,
            'brand': self.brand,
            'image_url': self.img_link,
            'specs': {
                'Top Speed': f"{self.top_speed} km/h",
                'Horsepower': f"{self.hp} HP",
                'Engine': f"{self.cc} cc",
                'Passengers': self.seating_capacity,
                'Year': self.year,
                'Fuel': self.fuel_type,
                'A/C': "Yes" if self.air_conditioned else "No",
                'Dimensions': self.dimension,
                'Price': f"{self.price_per_day}$/day",
                'Status': self.is_available
            }
        }

# Booking (Rental) model
class Booking:
    def __init__(self, data):
        self.rental_id = data['rental_id']
        self.customer_id = data['customer_id']
        self.car_id = data['car_id']
        self.no_of_days = data['no_of_days']
        self.total_price = data['total_price']
        self.rental_date = data['rental_date']

    @classmethod
    def create(cls, customer_id, car_id, days, total_price):
        db = get_db_connection()
        cur = db.cursor(dictionary=True)

        #Get current date in Pakistan time
        pakistan_time = datetime.now(pytz.timezone("Asia/Karachi"))

        #Inserting into rentals Table 
        cur.execute("""
            INSERT INTO rentals (customer_id, car_id, no_of_days, total_price, rental_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (customer_id, car_id, days, total_price, pakistan_time))

        db.commit()
        cur.execute("SELECT * FROM rentals WHERE rental_id = %s", (cur.lastrowid,))
        data = cur.fetchone()

        cur.execute("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
        customer = Customer(cur.fetchone())
        customer_name = customer.username
        customer_license = customer.license_no

        cur.execute("SELECT * FROM cars WHERE car_id = %s", (car_id,))
        car = Car(cur.fetchone())
        car_name = car.name


        write_to_booking_history(customer_name,customer_license,car_name,pakistan_time,total_price,days)
        db.close()
        return cls(data)

    @classmethod
    def active_for_customer(cls, customer_id):
        # get active rental (if any) for customer
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM rentals WHERE customer_id = %s", (customer_id,))
        data = cur.fetchone()
        db.close()
        return cls(data) if data else None

    @classmethod
    def all_bookings(cls):
        # list all bookings joined with customer and car info
        db = get_db_connection()
        cur = db.cursor(dictionary=True)
        cur.execute(
            """
            SELECT r.rental_id, r.customer_id, r.car_id, r.no_of_days, r.total_price,r.rental_date,
                   c.name as car_name,c.img_link, cust.username as customer_name, cust.license_no
            FROM rentals r
            JOIN cars c ON r.car_id = c.car_id
            JOIN customers cust ON r.customer_id = cust.customer_id
            """
        )
        rows = cur.fetchall()
        db.close()
        return rows

    def mark_returned(self):
        # remove rental and free car
        db = get_db_connection()
        cur = db.cursor()
        # delete rental
        cur.execute("DELETE FROM rentals WHERE rental_id = %s", (self.rental_id,))
        # mark car available
        cur.execute("UPDATE cars SET is_available = 1 WHERE car_id = %s", (self.car_id,))
        db.commit()
        db.close()

    def get_rented_car(self):
        """Fetch and return the Car object associated with this booking."""
        return Car.get_by_id(self.car_id)

