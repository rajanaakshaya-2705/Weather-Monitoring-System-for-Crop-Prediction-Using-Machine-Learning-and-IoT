from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_apscheduler import APScheduler
import joblib
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
import os
from collections import Counter
import logging  # Add this for logging
import requests
from datetime import datetime

app = Flask(_name_)
app.secret_key = os.urandom(24)  # Replace with a secure random key

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load the trained model and label encoder
model = joblib.load('crop_type_prediction_model.pkl')
le = joblib.load('label_encoder.pkl')

# MySQL connection
db = pymysql.connect(host='localhost',
                     user='root',
                     password='',
                     database='crop_prediction')

# Ensure the tables exist
with db.cursor() as cursor:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        year INT,
        day_of_year INT,
        temperature FLOAT,
        humidity FLOAT,
        rainfall FLOAT,
        soil_moisture FLOAT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE,
        password_hash VARCHAR(255)
    )
    """)
    db.commit()

# APScheduler Configuration
class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Function to collect data from NodeMCU
def collect_data_from_nodemcu():
    try:
        # NodeMCU endpoint for getting sensor data
        nodemcu_url = "http:/192.168.255.4/nodemcu/data"  # Update this URL if needed

        response = requests.get(nodemcu_url)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Data received from NodeMCU: {data}")

            # Extract sensor data from JSON payload
            temperature = data['temperature']
            humidity = data['humidity']
            soil_moisture = data['soil']
            rainfall = data['rain']

            # Get the current year and day of the year
            now = datetime.now()
            year = now.year
            day_of_year = now.timetuple().tm_yday

            # Insert sensor data into database
            with db.cursor() as cursor:
                sql = """
                INSERT INTO sensor_data (year, day_of_year, temperature, humidity, rainfall, soil_moisture)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (year, day_of_year, temperature, humidity, rainfall, soil_moisture))
                db.commit()

            logging.info("Data collected and stored in the database.")
        else:
            logging.error(f"Failed to get data from NodeMCU. Status code: {response.status_code}")

    except Exception as e:
        logging.error(f"Error while collecting data: {str(e)}")

# Schedule the data collection every 2 minutes
scheduler.add_job(id='collect_data_job', func=collect_data_from_nodemcu, trigger='interval', minutes=2)

@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with db.cursor() as cursor:
            cursor.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user[1], password):
                session['username'] = username
                return redirect(url_for('index'))
        return "Login failed. Please try again."
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = generate_password_hash(password)
        try:
            with db.cursor() as cursor:
                cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
                db.commit()
            return redirect(url_for('login'))
        except pymysql.err.IntegrityError:
            return "Username already exists. Please choose a different username."
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/predict_crop_type', methods=['GET'])
def predict_crop_type():
    try:
        # Get the last 50 sensor data entries from the database
        with db.cursor() as cursor:
            cursor.execute("""
            SELECT year,day_of_year,temperature, humidity, rainfall, soil_moisture
            FROM sensor_data
            ORDER BY timestamp DESC
            LIMIT 100
            """)
            recent_data = cursor.fetchall()

        if not recent_data:
            return jsonify({"status": "error", "message": "No sensor data found"}), 404

        # Initialize a counter for the predicted crop types
        crop_counter = Counter()

        for data in recent_data:
            # Prepare data for prediction
            features = [[data[0], data[1], data[2], data[3],data[4],data[5]]] 

            # Make prediction
            predicted_num = model.predict(features)[0]
            predicted_label = le.inverse_transform([predicted_num])[0]

            # Update the counter for the predicted crop type
            crop_counter[predicted_label] += 1

        # Get the crop type with the highest count
        most_common_crop = crop_counter.most_common(1)[0][0]

        return jsonify({"predicted_crop_type": most_common_crop}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/nodemcu/data', methods=['POST'])
def nodemcu_data():
    try:
        data = request.get_json()
        logging.info(f"Data received from NodeMCU: {data}")
        
        # Check if all required fields are present in the received JSON payload
        required_fields = ['temperature', 'humidity', 'soil', 'rain']
        if not all(field in data for field in required_fields):
            return jsonify({"status": "error", "message": "Incomplete data"}), 400
        
        # Extract sensor data from JSON payload
        temperature = data['temperature']
        humidity = data['humidity']
        soil_moisture = data['soil']
        rainfall = data['rain']
        
        # Get the current year and day of the year
        now = datetime.now()
        year = now.year
        day_of_year = now.timetuple().tm_yday
        
        # Insert sensor data into the database
        with db.cursor() as cursor:
            sql = """
            INSERT INTO sensor_data (year, day_of_year, temperature, humidity, rainfall, soil_moisture)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (year, day_of_year, temperature, humidity, rainfall, soil_moisture))
            db.commit()
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logging.error(f"Error while processing POST request: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
if _name_ == '_main_':
    app.run(debug=True, host='0.0.0.0', port=5000)