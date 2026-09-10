from transformers.agents import Tool, HfApiEngine, ReactJsonAgent
import tensorflow as tf
from flask import Flask, render_template, request, redirect, flash, url_for, session, make_response, jsonify
from flask_session import Session
from datetime import datetime, timedelta
import random
import pdfkit
import mysql.connector
from mysql.connector import Error
import os
import json
from groq import Groq
from huggingface_hub import login

# Replace with your Hugging Face API token
login(token="Your Huggingface API Key")

llm_engine = HfApiEngine("Qwen/Qwen2.5-72B-Instruct")
os.environ['GROQ_API_KEY'] = "Your Groq API Key"
llm=Groq()

app = Flask(__name__)
app.config["CACHE_TYPE"] = "null"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
app.secret_key = "your_secret_key"  # Necessary for flash messages

path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="password",
        database="train"
    )

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/")
def index():
    if (not session.get('user')):
        return redirect(url_for('login'))
    return redirect(url_for('home'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    session.clear()
    if request.method == "POST":
        user = request.form['userId']
        password = request.form['password']

        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            login_query = """
            SELECT Pwd
            FROM Login
            WHERE UserId = %s
            """
            try:
                cursor.execute(login_query, (user,))
                details = cursor.fetchall()
                if details and password == details[0][0]:
                    session['user'] = user
                    return redirect(url_for('loading'))
                flash("Password Incorrect")
            except Error as err:
                flash(f"Error during login: {err}")
            finally:
                connection.close()
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    session.clear()
    if request.method == "POST":
        user = request.form['userId']
        password = request.form['password']
        mobile_no = request.form['mobileNumber']
        email = request.form['email']

        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()

            user_query = """
            SELECT UserId, Email
            FROM Login
            """
            try:
                cursor.execute(user_query)
                users = cursor.fetchall()
                for u in users:
                    if (user==u[0]):
                        return render_template('register.html', message="User already exists")
                    if (email==u[1]):
                        return render_template('register.html', message="Email already exists")
            except Error as err:
                connection.rollback()
                flash(f"Error during registration: {err}")

            register_query = """
            INSERT INTO Login (UserId, Pwd, Mobile_no, Email)
            VALUES (%s, %s, %s, %s)
            """
            try:
                cursor.execute(register_query, (user, password, mobile_no, email))
                connection.commit()
                flash("Registration successful")
                return redirect(url_for('login'))
            except Error as err:
                connection.rollback()
                flash(f"Error during registration: {err}")
                return render_template('register.html')
            finally:
                connection.close()
    return render_template('register.html')

@app.route("/logout")
def logout():
    session.clear()
    return render_template('login.html')

@app.route("/loading")
def loading():
    if (not session.get('user')):
        return redirect(url_for('login'))
    return render_template('loading.html')

@app.route("/home")
def home():
    if (not session.get('user')):
        return redirect(url_for('login'))
    flash(session['user'])

    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            cursor.execute("""UPDATE Login SET User_Status = 'active' WHERE UserId = %s""", (session['user'],))
            connection.commit()
        except Error as err:
            flash(f"Error updating login status: {err}")
        finally:
            connection.close()

    return render_template('index.html', username=session['user'])

@app.route("/about")
def about():
    if (not session.get('user')):
        return redirect(url_for('login'))
    return render_template('about.html')

@app.route("/booktrain")
def booktrain():
    if (not session.get('user')):
        return redirect(url_for('login'))
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            cursor.execute("""
            SELECT station_name, min_order
            FROM (
            SELECT station_name, MIN(order_in_route) AS min_order
            FROM stations
            GROUP BY station_name) AS unique_stations
            ORDER BY min_order;
            """)
            stations = [row for row in cursor.fetchall()]
            min_date = datetime.now().date() + timedelta(days=1)
            max_date = min_date + timedelta(days=7)
            flash(max_date)
        except Error as err:
            flash(f"Error fetching station data: {err}")
        finally:
            connection.close()
        return render_template('booktrain.html', stations=stations, min_date=min_date, max_date=max_date)

@app.route("/bookings")
def bookings():
    if (not session.get('user')):
        return redirect(url_for('login'))
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()

        today = datetime.today().date()
        now = datetime.now().time()
        flash(now)

        try:
            current_bookings_query = """
            SELECT DISTINCT tr.train_number, tr.train_name, t.ticket_cluster, t.ticket_type, t.departure_date, t.arrival_date, t.departure_time, t.arrival_time, t.ticket_source, t.ticket_destination
            FROM MyTickets mt
            JOIN tickets t ON mt.ticket_ID = t.ticket_ID
            JOIN booking b ON b.ticket_ID = t.ticket_ID
            JOIN reservation r ON r.ticket_ID = t.ticket_ID
            JOIN trains tr ON tr.train_number = r.train_number
            JOIN passengers p ON p.adhaar_number = b.adhaar_number
            WHERE mt.UserId = %s AND (t.departure_date > %s OR (t.departure_date = %s AND t.departure_time > %s))
            ORDER BY t.departure_date ASC, t.departure_time ASC, t.ticket_cluster ASC
            """
            cursor.execute(current_bookings_query, (session['user'], today, today, now))
            current_cluster_details = cursor.fetchall()
            flash(current_cluster_details)

            past_bookings_query = """
            SELECT DISTINCT tr.train_number, tr.train_name, t.ticket_cluster, t.ticket_type, t.departure_date, t.arrival_date, t.departure_time, t.arrival_time, t.ticket_source, t.ticket_destination
            FROM MyTickets mt
            JOIN tickets t ON mt.ticket_ID = t.ticket_ID
            JOIN booking b ON b.ticket_ID = t.ticket_ID
            JOIN reservation r ON r.ticket_ID = t.ticket_ID
            JOIN trains tr ON tr.train_number = r.train_number
            JOIN passengers p ON p.adhaar_number = b.adhaar_number
            WHERE mt.UserId = %s AND (t.departure_date < %s OR (t.departure_date = %s AND t.departure_time <= %s))
            ORDER BY t.departure_date ASC, t.departure_time ASC, t.ticket_cluster ASC
            """
            cursor.execute(past_bookings_query, (session['user'], today, today, now))
            past_cluster_details = cursor.fetchall()
            flash(past_cluster_details)
        except Error as err:
            flash(f"Error fetching booking data: {err}")
        finally:
            connection.close()

        return render_template('bookings.html', current_tickets=current_cluster_details, past_tickets=past_cluster_details)

@app.route('/printTicket/ticket<filename>', methods=['POST'])
def printTicket(filename):
    if (not session.get('user')):
        return redirect(url_for('login'))
    
    cluster = request.form['ticket_cluster']
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        
        try:
            print_query = """
            SELECT DISTINCT tr.train_number, tr.train_name, t.ticket_cluster, t.ticket_type, t.departure_date, t.arrival_date, t.departure_time, t.arrival_time, t.ticket_source, t.ticket_destination, t.amount
            FROM MyTickets mt
            JOIN tickets t ON mt.ticket_ID = t.ticket_ID
            JOIN booking b ON b.ticket_ID = t.ticket_ID
            JOIN reservation r ON r.ticket_ID = t.ticket_ID
            JOIN trains tr ON tr.train_number = r.train_number
            JOIN passengers p ON p.adhaar_number = b.adhaar_number
            WHERE ticket_cluster = %s
            """
            cursor.execute(print_query, (cluster, ))
            ticket_details = cursor.fetchone()

            passenger_query = """
            SELECT p.passenger_name, p.age, p.sex, t.coach_no, t.berth_no, t.ticket_ID
            FROM tickets t
            JOIN booking b ON b.ticket_ID = t.ticket_ID
            JOIN passengers p ON p.adhaar_number = b.adhaar_number
            WHERE ticket_cluster = %s
            """
            cursor.execute(passenger_query, (cluster, ))
            passenger_details = cursor.fetchall()

            rendered = render_template('ticket.html', train_number=ticket_details[0], train_name=ticket_details[1], train_departure=ticket_details[6], train_arrival=ticket_details[7], source=ticket_details[8], destination=ticket_details[9], travel_date=ticket_details[4],
            arrival_date=ticket_details[5], ticket_type=ticket_details[3], amount=ticket_details[10], passengers=passenger_details)
            
            options = {
                'page-size': 'A3',
                'orientation': 'portrait',
                'margin-top': '0.5in',
                'margin-right': '0.5in',
                'margin-bottom': '0.5in',
                'margin-left': '0.5in',
                'encoding': "UTF-8",
                'custom-header': [
                    ('Accept-Encoding', 'gzip')
                ],
                'no-outline': None
            }

            ticket = pdfkit.from_string(rendered, False, configuration=config, options=options)
            response = make_response(ticket)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'inline; filename=ticket{filename}.pdf'
            return response
        except Error as err:
            flash(f"Error printing ticket: {err}")
        finally:
            connection.close()

@app.route("/trainlist", methods=['POST'])
def trainlist():
    if (not session.get('user')):
        return redirect(url_for('login'))
    session['source'] = request.form['source'][2:]
    session['destination'] = request.form['destination'][2:]
    src = request.form['source'][0:1]
    dst = request.form['destination'][0:1]
    travel_date = request.form['journey_date']
    session['travel_date'] = travel_date
    travel_day = datetime.strptime(travel_date, "%Y-%m-%d").strftime('%A')
    flash(f"{travel_date}{travel_day}")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        if src<dst:
            query = """
            SELECT t.train_name, t.train_number, ta.available_ac_seats, ta.available_gen_seats, sd.departure_time, sa.arrival_time, t.price_per_ticket 
            FROM trains t
            JOIN stations sd on sd.station_name = %s
            JOIN stations sa on sa.station_name = %s
            JOIN stations sa_src ON t.src = sa_src.station_name
            JOIN stations sa_dest ON t.destination = sa_dest.station_name
            JOIN train_availability ta ON t.train_number = ta.train_number
            WHERE (sa_src.order_in_route <= (SELECT order_in_route FROM stations WHERE stations.station_name = %s) AND 
            sa_dest.order_in_route >= (SELECT order_in_route FROM stations WHERE stations.station_name = %s))
            AND ta.day_of_week = %s
            AND (ta.available_ac_seats > 0
            OR ta.available_gen_seats > 0)
            """
        else:
            query = """
            SELECT t.train_name, t.train_number, ta.available_ac_seats, ta.available_gen_seats, sa.departure_time, sd.arrival_time, t.price_per_ticket 
            FROM trains t
            JOIN stations sd on sd.station_name = %s
            JOIN stations sa on sa.station_name = %s
            JOIN stations sa_src ON t.src = sa_src.station_name
            JOIN stations sa_dest ON t.destination = sa_dest.station_name
            JOIN train_availability ta ON t.train_number = ta.train_number
            WHERE (sa_src.order_in_route > sa_dest.order_in_route AND 
            sa_src.order_in_route >= (SELECT order_in_route FROM stations WHERE stations.station_name = %s) AND sa_dest.order_in_route <= (SELECT order_in_route FROM stations WHERE stations.station_name = %s))
            AND ta.day_of_week = %s
            AND (ta.available_ac_seats > 0
            OR ta.available_gen_seats > 0)
            """
        cursor.execute(query, (session['source'], session['destination'], session['source'], session['destination'], travel_day))
        trains = cursor.fetchall()
        if not trains:
            flash("No trains available for the selected route and date.")
            return redirect(url_for('booktrain'))

        flash(trains)
        session['train_departure']=trains[0][4]
        session['train_arrival']=trains[0][5]
        
        if session['train_departure']>session['train_arrival']:
            arrival_date = datetime.strptime(travel_date, "%Y-%m-%d") + timedelta(days=1)
            session['journey_time']=timedelta(hours=24)-(session['train_departure']-session['train_arrival'])
        else:
            arrival_date = datetime.strptime(travel_date, "%Y-%m-%d")
            session['journey_time']=session['train_arrival']-session['train_departure']
        
        arrival_date= arrival_date.strftime("%Y-%m-%d")
        session['arrival_date']=arrival_date

        return render_template('trainlist.html', trains=trains, travel_date=travel_date, arrival_date=arrival_date, source=session['source'], destination=session['destination'], journey_time=session['journey_time'])
    except Exception as e:
        flash(f"Error while fetching train list: {str(e)}")
        return redirect(url_for('booktrain'))
    finally:
        connection.close()


@app.route("/passengers", methods=['POST'])
def passengers():
    if (not session.get('user')):
        return redirect(url_for('login'))
    try:
        session['train_number'] = request.form['train_number']
        session['train_name'] = request.form['train_name']
        session['ticket_type'] = request.form['ticket_type']
        session['amount'] = request.form['amount']
        if session['ticket_type']=="General":
            session['amount'] = int(session['amount'])/2
        flash(request.form)
        return render_template('passengers.html')
    except Exception as e:
        flash(f"Error processing passenger details: {str(e)}")
        return redirect(url_for('booktrain'))


@app.route("/payment", methods=['POST'])
def payment():
    if (not session.get('user')):
        return redirect(url_for('login'))
    try:
        session['passenger_name'] = request.form.getlist('passenger_name')
        session['age'] = request.form.getlist('age')
        session['mobile_no'] = request.form.getlist('mobile_no')
        session['adhaar_number'] = request.form.getlist('adhaar_number')
        session['sex'] = request.form.getlist('sex')
        amount = 0
        for i in range(len(session['passenger_name'])):
            if(session['passenger_name'][i]):
                amount = amount + int(session['amount'])
        flash(request.form)
        return render_template('payment.html', amount=amount)
    except Exception as e:
        flash(f"Error processing payment details: {str(e)}")
        return redirect(url_for('booktrain'))

@app.route('/success', methods=['POST'])
def success():
    if (not session.get('user')):
        return redirect(url_for('login'))
    
    session['ticket_cluster'] = random.randint(1000, 9999)

    for i in range(len(session['passenger_name'])):
        flash(session['passenger_name'][i])
        if(session['passenger_name'][i]):
            try:
                ticket_id = random.randint(100000, 999999)
                flash(f"{ticket_id}")
                connection = get_db_connection()
                cursor = connection.cursor()

                # Insert passenger details
                passenger_query = """
                INSERT IGNORE INTO passengers (passenger_name, age, mobile_no, adhaar_number, sex)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(passenger_query, (session['passenger_name'][i], session['age'][i], session['mobile_no'][i], session['adhaar_number'][i], session['sex'][i]))

                 # Fetch current version and available seats
                version_query = """
                SELECT available_ac_seats, available_gen_seats, version_number
                FROM train_availability
                WHERE train_number = %s AND day_of_week = %s FOR UPDATE
                """
                cursor.execute(version_query, (session['train_number'], datetime.strptime(session['travel_date'], "%Y-%m-%d").strftime('%A')))
                availability = cursor.fetchone()

                if not availability:
                    flash("Train or availability details not found.")
                    connection.rollback()
                    return redirect(url_for('booktrain'))
                
                if session['ticket_type'] == "AC":
                    available_seats = availability[0]
                elif session['ticket_type'] == "General":
                    available_seats = availability[1]

                current_version = availability[2]

                if available_seats <= 0:
                    flash("No seats available for the selected train.")
                    connection.rollback()
                    return redirect(url_for('booktrain'))

                # Update available seats
                new_version = current_version + 1

                if session['ticket_type']=="AC":
                    update_seats_query = """
                    UPDATE train_availability 
                    SET available_ac_seats = available_ac_seats - 1, version_number = %s 
                    WHERE train_number = %s AND day_of_week = %s AND version_number = %s AND available_ac_seats > 0
                    """
                    
                    berth_query = """
                    SELECT ts.ac_seats, ta.available_ac_seats
                    FROM train_seats ts, train_availability ta  
                    WHERE ts.train_number = %s AND ta.train_number = %s AND day_of_week = %s
                    """
                elif session['ticket_type']=="General":
                    update_seats_query = """
                    UPDATE train_availability 
                    SET available_gen_seats = available_gen_seats - 1, version_number = %s 
                    WHERE train_number = %s AND day_of_week = %s AND version_number = %s AND available_gen_seats > 0
                    """

                    berth_query = """
                    SELECT ts.gen_seats, ta.available_gen_seats
                    FROM train_seats ts, train_availability ta  
                    WHERE ts.train_number = %s AND ta.train_number = %s AND day_of_week = %s
                    """
                cursor.execute(update_seats_query, (new_version, session['train_number'], datetime.strptime(session['travel_date'], "%Y-%m-%d").strftime('%A'), current_version))

                if cursor.rowcount == 0:
                    flash("Booking failed due to concurrent updates. Please try again.")
                    connection.rollback()
                    return redirect(url_for('booktrain'))

                cursor.execute(berth_query, (session['train_number'], session['train_number'], datetime.strptime(session['travel_date'], "%Y-%m-%d").strftime('%A')))
                seats = cursor.fetchone()
                flash(seats)

                berth_no = seats[0]-seats[1]
                if session['ticket_type']=="AC":
                    coach_no = "A" + str(int(((berth_no-1)/50)+1))
                elif session['ticket_type']=="General":
                    coach_no = "G" + str(int(((berth_no-1)/50)+1))
                flash(coach_no)

                # Insert ticket details
                ticket_query = """
                INSERT INTO tickets (ticket_type, confirmation_status, departure_date, arrival_date, departure_time, arrival_time, ticket_ID, ticket_cluster, amount, coach_no, berth_no, ticket_source, ticket_destination)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                cursor.execute(ticket_query, (session['ticket_type'], 'Confirmed', session['travel_date'], session['arrival_date'], session['train_departure'], session['train_arrival'], ticket_id, session['ticket_cluster'], session['amount'], coach_no, berth_no, session['source'], session['destination']))

                # Insert MyTicket details
                myticket_query = """
                INSERT INTO MyTickets (UserId, ticket_ID)
                VALUES (%s, %s)
                """
                cursor.execute(myticket_query, (session['user'], ticket_id))

                # Insert booking details
                booking_query = """
                INSERT INTO booking (adhaar_number, ticket_ID)
                VALUES (%s, %s)
                """
                cursor.execute(booking_query, (session['adhaar_number'][i], ticket_id))

                # Insert reservation details
                reservation_query = """
                INSERT INTO reservation (ticket_ID, train_number)
                VALUES (%s, %s)
                """
                cursor.execute(reservation_query, (ticket_id, session['train_number']))

                connection.commit()
                flash(f"Booking successful! Your Ticket ID is {ticket_id}.")
            except Exception as e:
                connection.rollback()  # Rollback changes if there's an error
                flash(f"Booking failed: {str(e)}")  # Display error message
            finally:
                connection.close()

    return render_template('success.html', filename=session['ticket_cluster'])

@app.route('/ticket/ticket<filename>')
def ticket(filename):
    if (not session.get('user')):
        return redirect(url_for('login'))
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        passenger_query = """
        SELECT p.passenger_name, p.age, p.sex, t.coach_no, t.berth_no, t.ticket_ID
        FROM tickets t
        JOIN booking b ON b.ticket_ID = t.ticket_ID
        JOIN passengers p ON p.adhaar_number = b.adhaar_number
        WHERE ticket_cluster = %s
        """
        cursor.execute(passenger_query, (session['ticket_cluster'], ))
        passenger_details = cursor.fetchall()

        if not passenger_details:
            flash("No passenger details found for the provided ticket cluster.")
            return redirect(url_for('booktrain'))
        
        rendered = render_template('ticket.html', train_number=session['train_number'], train_name=session['train_name'], train_departure=session['train_departure'], train_arrival=session['train_arrival'], source=session['source'], destination=session['destination'], travel_date=session['travel_date'],
        arrival_date=session['arrival_date'], ticket_type=session['ticket_type'], amount=session['amount'], passengers=passenger_details)

        options = {
            'page-size': 'A3',
            'orientation': 'portrait',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8",
            'custom-header': [
                ('Accept-Encoding', 'gzip')
            ],
            'no-outline': None
        }

        ticket = pdfkit.from_string(rendered,False, configuration=config, options=options)

        response = make_response(ticket)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=ticket{filename}.pdf'

        return response
    
    except Exception as e:
        flash(f"Error generating ticket: {str(e)}")
        return redirect(url_for('booktrain'))

    finally:
        connection.close()
    
class Retriever(Tool):
    name = "Retriever"
    description = (
        "This tool retrieves the train data from the database."
    )

    inputs = {"query": {"type": "string", "description": "It should have 3 terms seperated by commas, the 2 stations in between which retrieval needs to be done and the keyword on which ordering needs to be done."}}
    output_type = 'string'

    def forward(self, query: str):  # Accept keyword arguments to receive inputs
        terms = query.split(',')
        source=terms[0]
        destination=terms[1].strip()
        queryindex=0
        if(terms[2].strip()=='fastest'):
            queryindex=1
        elif terms[2].strip()=='cheapest':
            queryindex=2
        elif terms[2].strip()=='costliest':
            queryindex=3
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            query="""
            SELECT t.order_in_route
            FROM stations t
            WHERE t.station_name= %s
            """
            cursor.execute(query, (source,))
            src= cursor.fetchall()
            cursor.execute(query, (destination,))
            dst= cursor.fetchall()
            if src<dst:
                query = """
                SELECT t.train_name, t.train_number, sd.departure_time, sa.arrival_time, t.price_per_ticket 
                FROM trains t
                JOIN stations sd on sd.station_name = %s
                JOIN stations sa on sa.station_name = %s
                JOIN stations sa_src ON t.src = sa_src.station_name
                JOIN stations sa_dest ON t.destination = sa_dest.station_name
                JOIN train_availability ta ON t.train_number = ta.train_number
                WHERE (sa_src.order_in_route <= (SELECT order_in_route FROM stations WHERE stations.station_name = %s) AND 
                sa_dest.order_in_route >= (SELECT order_in_route FROM stations WHERE stations.station_name = %s))
                """
            else:
                query = """
                SELECT t.train_name, t.train_number, sa.departure_time, sd.arrival_time, t.price_per_ticket 
                FROM trains t
                JOIN stations sd on sd.station_name = %s
                JOIN stations sa on sa.station_name = %s
                JOIN stations sa_src ON t.src = sa_src.station_name
                JOIN stations sa_dest ON t.destination = sa_dest.station_name
                JOIN train_availability ta ON t.train_number = ta.train_number
                WHERE (sa_src.order_in_route > sa_dest.order_in_route AND 
                sa_src.order_in_route >= (SELECT order_in_route FROM stations WHERE stations.station_name = %s) AND sa_dest.order_in_route <= (SELECT order_in_route FROM stations WHERE stations.station_name = %s))
                """
            cursor.execute(query, (source, destination, source, destination))
            trains = cursor.fetchall()
            #print(len(trains))
            #print(trains)
            
            # List to store train info with journey time
            journey_times = []
            # Calculate journey time for each train and store in journey_times list
            for train in trains:
                session['train_departure']=train[2]
                session['train_arrival']=train[3]
                if session['train_departure']>session['train_arrival']:
                    session['journey_time']=timedelta(hours=24)-(session['train_departure']-session['train_arrival'])
                else:
                    session['journey_time']=session['train_arrival']-session['train_departure']
                print("Moveon")
                journey_time = session['journey_time']

                # Append to journey_times with train details and calculated journey time
                journey_times.append({
                    'train_name': train[0],
                    'train_number': train[1],
                    'journey_time': journey_time,
                    'departure_time': train[2],
                    'arrival_time': train[3],
                    'price_per_ticket': train[4]
                })
            if queryindex==1:
                journey_times.sort(key=lambda x: x['journey_time'])
                top_train_name = journey_times[0]['train_name']
                return f"the fastest train is {top_train_name}"
            elif queryindex==2:
                journey_times.sort(key=lambda x: (x['journey_time'], x['price_per_ticket']))
                top_train_name = journey_times[0]['train_name']
                return f"the cheapest train is {top_train_name}"
            elif queryindex==3:
                journey_times.sort(key=lambda x: x['price_per_ticket'], reverse=True)
                top_train_name = journey_times[0]['train_name']
                return f"the most expensive train is {top_train_name}"
        except Exception as e:
            flash(f"Error while fetching train list: {str(e)}")
            return redirect(url_for('booktrain'))
        finally:
            connection.close()
    

@app.route('/chatbot', methods=['POST'])
def chatbot_response():
    user_message = request.json.get('message')
    prompt = user_message + "\n" + "Extract station names and one the three keywords 'fastest', 'costliest', 'cheapest' (one of them will be present in the query) from the following query and return them as 'station1,station2,keyword'. Be accurate to the point and act only to rephrase the query in the format needed as 'station1,station2,keyword', do not try to answer it. The keyword is also important and the rephrased query should contain one of the following words: fastest, costliest, cheapest based on which of them is present in the query."
    chat_completion = llm.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="llama-3.1-70b-versatile",
        stream=False,
    )
    query = chat_completion.choices[0].message.content
    retriever_tool = Retriever(query=query)
    agent = ReactJsonAgent(tools=[retriever_tool], llm_engine=llm_engine, max_iterations=4, verbose=2)
    agent_output = agent.run(query)
    return jsonify({'response': agent_output})

if __name__ == '__main__':
    app.run(debug=True)
