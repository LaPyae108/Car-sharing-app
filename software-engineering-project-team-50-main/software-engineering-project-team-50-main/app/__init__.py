from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, send, emit
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from api_key import *
from datetime import datetime, date, timezone, timedelta
from sqlalchemy.orm import joinedload
from flask_migrate import Migrate
import os
from app.extensions import db
from app.models import *
import stripe

stripe.api_key = "sk_test_51RB0HZCLTjEo5aWBRjo9jiFuYAVUDbAloWrWuxX4AmwI0SVLshlRYqpb4a4XE0r5LGLcWbk9p7NHbJehWnacPWSJ004D5KXxzx"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///carsharing.db'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_PERMANENT'] = False
app.config['SERVER_NAME'] = 'glowing-space-guacamole-v6v4ggj496w4269x5-5000.app.github.dev/'
app.config['PREFERRED_URL_SCHEME'] = 'https'

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=GOOGLE_ID,
    client_secret=GOOGLE_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid profile email'}
)

socketio = SocketIO(app)

from app.models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Login page and handler
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('user_dashboard'))

    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if not user:
            flash('No account found with that email.', 'danger')
        elif not check_password_hash(user.password, request.form.get('password')):
            flash('Incorrect password.', 'danger')
        else:
            login_user(user)
            session.permanent = False  # Optional: force logout on browser close
            if session.pop('journey_claimed', False):
                flash("Journey successfully claimed and booking created!", "success")
            if user.role == UserRole.superadmin:
                return redirect(url_for('superadmin'))
            elif user.role == UserRole.passenger:
                return redirect(url_for('user_dashboard'))
            elif user.role == UserRole.manager:
                return redirect(url_for('manager_dashboard'))
            else:
                return redirect(url_for('driver_dashboard'))
            
    return render_template('login.html')



# Superadmin dashboard
@app.route('/superadmin')
@login_required
def superadmin():
    if current_user.role != UserRole.superadmin:
        flash("Access denied.", "danger")
        return redirect(url_for('index'))
    users = User.query.all()
    journeys = Journey.query.all()
    return render_template('superadmin_dashboard.html', users=users, UserRole=UserRole, journeys=journeys)

# Update user roles
@app.route('/update_roles', methods=['POST'])
@login_required
def update_roles():
    if current_user.role != UserRole.superadmin:
        flash("Unauthorized", "danger")
        return redirect(url_for('superadmin'))
    for key, value in request.form.items():
        if key.startswith("role_"):
            user_id = key.split("_")[1]
            user = User.query.get(int(user_id))
            if user and user.role != UserRole.superadmin:
                user.role = UserRole(value)
    db.session.commit()
    flash("User roles updated successfully", "success")
    return redirect(url_for('superadmin'))

# User registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('user_dashboard'))

    if request.method == 'POST':
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash("Passwords do not match.", 'danger')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.", 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(
            firstname=firstname,
            lastname=lastname,
            email=email,
            password=hashed_password,
            role='passenger'
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful. You can now log in.", 'success')
        return redirect(url_for('login'))

    return render_template('register.html')



# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Google login
@app.route('/login/google')
def google_login():
    try:
        redirect_uri = url_for('authorize_google', _external=True)
        return google.authorize_redirect(redirect_uri)
    except Exception as e:
        app.logger.error(f"Error during login: {str(e)}")
        return "Error occurred during login", 500

# Google authorization callback
@app.route('/authorize/google')
def authorize_google():
    try:
        token = google.authorize_access_token()
        userinfo_endpoint = google.server_metadata['userinfo_endpoint']
        resp = google.get(userinfo_endpoint)
        user_info = resp.json()
        email = user_info['email']
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(username=email, email=email)
            db.session.add(user)
            db.session.commit()
        login_user(user)
        return redirect(url_for('dashboard'))
    except Exception as e:
        app.logger.error(f"Error during Google authorization: {str(e)}")
        return "Error occurred during authorization", 500

# User dashboard
@app.route('/user_dashboard')
@login_required
def user_dashboard():
    today = date.today()
    now_time = datetime.now().time()
    user_bookings = Booking.query.join(Journey).filter(
        Booking.user_id == current_user.id
    ).order_by(Journey.journey_date, Journey.journey_time).all()
    upcoming_paid_bookings = Booking.query.join(Journey).filter(
        Booking.user_id == current_user.id,
        Booking.booking_status != 'cancelled',
        Booking.payment_status == BookingPaymentStatus.paid,
        (Journey.journey_date > today) |
        ((Journey.journey_date == today) & (Journey.journey_time >= now_time))
    ).order_by(Journey.journey_date, Journey.journey_time).all()
    past_booking_ids = [
        b.id for b in user_bookings
        if (b.journey.journey_date < today) or
        (b.journey.journey_date == today and b.journey.journey_time < now_time)
    ]
    user_journeys = Journey.query.filter_by(
        creator_id=current_user.id,
        journey_status='active',
    ).filter(Journey.driver_id == None).all()
    trips = Booking.trips_last_week(current_user.id)
    return render_template(
        "user_dashboard.html",
        user_bookings=user_bookings,
        upcoming_paid_bookings=upcoming_paid_bookings,
        user_journeys=user_journeys,
        past_booking_ids=past_booking_ids,
        trips=trips,
        current_date=date.today()
    )

# Create a new journey
@app.route('/create_journey', methods=['GET', 'POST'])
@login_required
def create_journey():
    if request.method == 'POST':
        start_location = request.form.get('start_location')
        end_location = request.form.get('end_location')
        departure_date_str = request.form.get('departure_date')
        departure_time_str = request.form.get('departure_time')
        is_recurring = bool(request.form.get('recurring'))
        recurring_days = request.form.getlist('recurring_days')
        available_seats = int(request.form.get('available_seats'))
        try:
            departure_datetime = datetime.strptime(
                f"{departure_date_str}T{departure_time_str}", '%Y-%m-%dT%H:%M'
            )
            journey_date = departure_datetime.date()
            journey_time = departure_datetime.time()
        except ValueError:
            flash("Invalid departure date/time format.", "danger")
            return redirect(url_for('create_journey'))
        new_journey = Journey(
            start_location=start_location,
            end_location=end_location,
            journey_date=journey_date,
            journey_time=journey_time,
            is_recurring=is_recurring,
            recurring_days=", ".join(recurring_days),
            available_seats=available_seats,
            creator_id=current_user.id
        )
        db.session.add(new_journey)
        db.session.commit()
        return redirect(url_for('journey_summary', journey_id=new_journey.id))
    start_prefill = request.args.get('start_location', '')
    end_prefill = request.args.get('end_location', '')
    return render_template(
        'create_journey.html',
        start_prefill=start_prefill,
        end_prefill=end_prefill
    )

# Driver dashboard
@app.route('/driver_dashboard')
@login_required
def driver_dashboard():
    if current_user.role != UserRole.driver:
        flash("Access denied.", "danger")
        return redirect(url_for('index'))
    journeys = Journey.query.filter_by(driver_id=current_user.id).all()
    confirmed_bookings = Booking.query.options(
        joinedload(Booking.user), joinedload(Booking.journey)
    ).join(Journey).filter(
        Journey.driver_id == current_user.id,
        Booking.booking_status == 'confirmed'
    ).all()
    pending_bookings = Booking.query.options(
        joinedload(Booking.user), joinedload(Booking.journey)
    ).join(Journey).filter(
        Journey.driver_id == current_user.id,
        Booking.booking_status == 'pending'
    ).all()
    return render_template(
        'driver.html',
        journeys=journeys,
        confirmed_bookings=confirmed_bookings,
        pending_bookings=pending_bookings
    )

# Confirm a booking (driver)
@app.route('/confirm_booking/<int:booking_id>', methods=['POST'])
@login_required
def confirm_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if not booking.journey or booking.journey.driver_id != current_user.id:
        flash("Unauthorized booking confirmation.", "danger")
        return redirect(url_for('driver_dashboard'))
    action = request.form.get('action')
    if action == 'accept':
        booking.booking_status = 'confirmed'
        flash("Booking accepted.", "success")
    elif action == 'reject':
        booking.booking_status = 'rejected'
        flash("Booking rejected.", "warning")
    else:
        flash("Invalid action.", "danger")
    db.session.commit()
    return redirect(url_for('driver_dashboard'))

# Journey summary for the creator
@app.route('/journey_summary')
@login_required
def journey_summary():
    latest_journey = Journey.query.filter_by(creator_id=current_user.id).order_by(Journey.id.desc()).first()
    if not latest_journey:
        flash("No journeys found.", "warning")
        return redirect(url_for('user_dashboard'))

    base_price = 25.00

    rule = DiscountRule.query.filter_by(rule_name="Weekly Commuter", is_active=True).first()
    if rule:
        discount_amount = base_price * (rule.discount_percentage / 100)
    else:
        discount_amount = 0.0

    final_price = base_price - discount_amount

    return render_template(
        'summary.html',
        summary=latest_journey,
        base_price=base_price,
        discount_amount=discount_amount,
        final_price=final_price
    )


# Manager dashboard
@app.route('/manager_dashboard')
@login_required
def manager_dashboard():
    if current_user.role != UserRole.manager:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    users = User.query.all()
    bookings = Booking.query.filter(Booking.payment_status.in_(['paid', 'refunded'])).all()
    journeys = Journey.query.all()
    support_issues = SupportIssue.query.all()

    total_income = sum(b.total_cost for b in bookings)
    platform_fee = total_income * 0.005

    # Income chart
    income_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    income_data = [round(total_income / 7, 2)] * 7  # Split evenly (for now)

    return render_template('manager_dashboard.html',
                           users=users,
                           bookings=bookings,
                           support_issues=support_issues,
                           journeys=journeys,
                           total_income=total_income,
                           platform_fee=platform_fee,
                           income_labels=income_labels,
                           income_data=income_data)


# Create a Stripe checkout session
@app.route('/create_checkout_session', methods=['POST'])  # Changed route name to match JS call
@login_required
def create_checkout_session():
    data = request.get_json()
    
    # Get price from frontend and validate
    try:
        item_price = float(data.get('price', 25.00))
        amount = int(item_price * 100)  # Convert to cents
    except (TypeError, ValueError) as e:
        return jsonify(error=f"Invalid price format: {str(e)}"), 400

    passenger_notes = data.get('notes', '').strip()
    session['passenger_notes'] = passenger_notes

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {
                        'name': 'Journey Booking',
                        'description': passenger_notes[:100] if passenger_notes else "Standard journey booking"
                    },
                    'unit_amount': amount,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('cancel', _external=True),
        )
        return jsonify({'sessionId': checkout_session.id})
    except Exception as e:
        return jsonify(error=str(e)), 500


# Payment success handler
@app.route('/success')
@login_required
def success():
    session_id = request.args.get('session_id')
    if not session_id:
        flash("Missing session ID.", "danger")
        return redirect(url_for('user_dashboard'))
    
    # Retrieve session WITH line_items expansion
    checkout_session = stripe.checkout.Session.retrieve(
        session_id,
        expand=['line_items']  # <-- THIS IS CRUCIAL
    )
    
    # Get line items safely
    if not checkout_session.line_items or not checkout_session.line_items.data:
        flash("Payment details unavailable.", "danger")
        return redirect(url_for('user_dashboard'))
    
    amount_paid = checkout_session.line_items.data[0].amount_total / 100
    passenger_notes = session.pop('passenger_notes', '')
    latest_journey = Journey.query.filter_by(creator_id=current_user.id).order_by(Journey.id.desc()).first()
    if not latest_journey:
        flash("No journey found to attach the booking to.", "danger")
        return redirect(url_for('user_dashboard'))
    new_booking = Booking(
        journey_id=latest_journey.id,
        user_id=current_user.id,
        booking_date=datetime.today().date(),
        passenger_count=1,
        total_cost=amount_paid,
        booking_status='confirmed',
        payment_status=BookingPaymentStatus.paid,
        passenger_notes=passenger_notes
    )
    trips = Booking.trips_last_week(current_user.id)
    if trips >= 4:
        rule = (
            DiscountRule.query
            .filter_by(is_active=True)
            .filter(DiscountRule.min_trips <= trips)
            .order_by(DiscountRule.min_trips.desc())
            .first()
        )
        if rule:
            new_booking.discount_id = rule.id
            new_booking.discount_amount = new_booking.total_cost * (rule.discount_percentage / 100.0)
    db.session.add(new_booking)
    db.session.commit()
    flash("Booking confirmed and payment successful!", "success")
    return render_template('success.html')

# Payment cancelled handler
@app.route('/cancel')
@login_required
def cancel():
    return "Payment cancelled."

# List available journeys for drivers
@app.route('/available_journeys')
@login_required
def available_journeys():
    if current_user.role != UserRole.driver:
        flash("Only drivers can view available journeys.", "danger")
        return redirect(url_for('index'))
    
    journeys = Journey.query.filter(
        Journey.driver_id == None,            # Unclaimed
        Journey.journey_status == 'active'    # Only active journeys
    ).order_by(Journey.journey_date.asc()).all()  # Optional: show soonest first

    return render_template('available_journeys.html', journeys=journeys)


# Claim a journey (driver)
@app.route('/claim_journey/<int:journey_id>', methods=['POST'])
@login_required
def claim_journey(journey_id):
    if current_user.role != UserRole.driver:
        flash("Only drivers can claim journeys.", "danger")
        return redirect(url_for('index'))

    journey = Journey.query.get_or_404(journey_id)
    if journey.driver_id is not None:
        flash("This journey has already been claimed.", "warning")
    else:
        journey.driver_id = current_user.id
        new_booking = Booking(
            journey_id=journey.id,
            user_id=journey.creator_id,
            booking_date=datetime.today().date(),
            passenger_count=1,
            total_cost=25.00,
            booking_status='confirmed',
            payment_status=BookingPaymentStatus.paid
        )
        db.session.add(new_booking)
        session['journey_claimed'] = True
        db.session.commit()

    return redirect(url_for('available_journeys'))


# Waiting page
@app.route('/waiting')
@login_required
def waiting():
    summary = session.get('journey_summary', {})
    journey_id = summary.get('journey_id')  # Add this to session when creating journey
    return render_template('waiting.html', summary=summary, journey_id=journey_id)

# Cancel a booking
@app.route('/cancel_journey/<int:journey_id>', methods=['POST'])
@login_required
def cancel_journey(journey_id):
    journey = Journey.query.get_or_404(journey_id)

    if current_user.id != journey.creator_id and current_user.role not in [UserRole.admin, UserRole.superadmin]:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    driver_claimed = journey.driver_id is not None

    # Cancel the journey
    journey.journey_status = 'cancelled'

    # Cancel all related bookings
    for booking in journey.bookings:
        if booking.booking_status != 'cancelled':
            booking.booking_status = 'cancelled'
            payment = Payment.query.filter_by(booking_id=booking.id).first()

            if driver_claimed:
                # 75% refund if driver was assigned
                booking.total_cost = round(booking.total_cost * 0.75, 2)
                if payment:
                    payment.payment_status = PaymentStatus.refunded
                    payment.refund_amount = booking.total_cost
                    payment.refund_date = datetime.utcnow()
                    payment.refund_reason = "Journey cancelled after driver assigned."
            else:
                # Full refund (free) if no driver assigned
                booking.total_cost = 0.0
                if payment:
                    payment.payment_status = PaymentStatus.refunded
                    payment.refund_amount = 0.0
                    payment.refund_date = datetime.utcnow()
                    payment.refund_reason = "Journey cancelled before driver assigned."

    db.session.commit()

    flash('Journey cancelled successfully.', 'success')
    return redirect(url_for('user_dashboard'))


# Send a chat message
@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        booking_id = data.get('booking_id')
        journey_id = data.get('journey_id')
        message_text = data.get('message')
        if not message_text:
            return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400
        if booking_id:
            new_message = ChatMessage(
                booking_id=booking_id,
                sender_id=current_user.id,
                message_text=message_text,
                timestamp=datetime.utcnow()
            )
        elif journey_id:
            return jsonify({'success': False, 'error': 'Journey messaging not implemented'}), 400
        else:
            return jsonify({'success': False, 'error': 'No booking or journey specified'}), 400
        db.session.add(new_message)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': {
                'sender_id': current_user.id,
                'text': message_text,
                'timestamp': new_message.timestamp.strftime('%H:%M')
            }
        })
    except Exception as e:
        app.logger.error(f"Message send error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# Manage a journey (creator)
@app.route('/manage_journey/<int:journey_id>')
@login_required
def manage_journey(journey_id):
    journey = Journey.query.get_or_404(journey_id)
    if journey.creator_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('user_dashboard'))
    now = datetime.now()
    journey_datetime = datetime.combine(journey.journey_date, journey.journey_time)
    can_edit = now < (journey_datetime - timedelta(minutes=15))
    bookings = Booking.query.filter_by(journey_id=journey_id).all()
    return render_template(
        'manage_journey.html',
        journey=journey,
        bookings=bookings,
        can_edit=can_edit
    )

# Submit a rating
@app.route('/submit_rating', methods=['POST'])
@login_required
def submit_rating():
    data = request.get_json()
    booking_id = data.get('booking_id')
    rating_score = data.get('rating_score')
    rating_comment = data.get('rating_comment', '')
    current_time = datetime.now()
    if not booking_id or not rating_score:
        return jsonify({'success': False, 'error': 'Missing data'}), 400
    existing_rating = Rating.query.filter_by(booking_id=booking_id, rater_id=current_user.id).first()
    if existing_rating:
        return jsonify({'success': False, 'error': 'Rating already submitted'}), 400
    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({'success': False, 'error': 'Booking not found'}), 404
    if not booking.journey or not booking.journey.driver_id:
        return jsonify({'success': False, 'error': 'Driver not found'}), 400
    new_rating = Rating(
        booking_id=booking_id,
        rater_id=current_user.id,
        rated_user_id=booking.journey.driver_id,
        rating_score=rating_score,
        rating_comment=rating_comment.strip()
    )
    db.session.add(new_rating)
    db.session.commit()
    return jsonify({'success': True})

# Update journey details (creator)
@app.route('/update_journey/<int:journey_id>', methods=['POST'])
@login_required
def update_journey(journey_id):
    journey = Journey.query.get_or_404(journey_id)
    if journey.creator_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('user_dashboard'))
    now = datetime.now()
    journey_datetime = datetime.combine(journey.journey_date, journey.journey_time)
    if now >= (journey_datetime - timedelta(minutes=15)):
        flash("Edits are not allowed within 15 minutes of journey time.", "warning")
        return redirect(url_for('manage_journey', journey_id=journey.id))
    try:
        journey.start_location = request.form['start_location']
        journey.end_location = request.form['end_location']
        journey.journey_date = datetime.strptime(request.form['journey_date'], "%Y-%m-%d").date()
        journey.journey_time = datetime.strptime(request.form['journey_time'], "%H:%M").time()
        journey.available_seats = int(request.form['available_seats'])
        journey.notes = request.form.get('notes', '').strip()
        db.session.commit()
        flash("Journey updated successfully!", "success")
        return redirect(url_for('user_dashboard'))
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating journey: {e}", "danger")
        return redirect(url_for('manage_journey', journey_id=journey.id))

# Update journey notes (creator)
@app.route('/update_journey_notes/<int:journey_id>', methods=['POST'])
@login_required
def update_journey_notes(journey_id):
    journey = Journey.query.get_or_404(journey_id)
    if journey.creator_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('user_dashboard'))
    journey_dt = datetime.combine(journey.journey_date, journey.journey_time)
    if datetime.now() >= (journey_dt - timedelta(minutes=15)):
        flash("You can’t edit notes within 15 minutes of departure.", "warning")
        return redirect(url_for('manage_journey', journey_id=journey_id))
    new_notes = request.form.get('notes', '').strip()
    journey.notes = new_notes
    db.session.commit()
    flash("Notes saved successfully!", "success")
    return redirect(url_for('manage_journey', journey_id=journey_id))



# Submit a support issue
@app.route('/submit_support_issue', methods=['POST'])
@login_required
def submit_support_issue():
    subject = request.form.get('subject', '').strip()
    description = request.form.get('description', '').strip()
    if not subject or not description:
        return jsonify({'success': False, 'error': 'All fields are required.'}), 400
    issue = SupportIssue(
        user_id=current_user.id,
        booking_id=None,
        issue_type=subject,
        issue_description=description,
        issue_status='open',
        created_date=datetime.today().date()
    )
    db.session.add(issue)
    db.session.commit()
    return jsonify({'success': True}), 200

# SocketIO: handle modal chat messages
@socketio.on('send_modal_message')
def handle_modal_message(data):
    booking_id = data.get('booking_id')
    message = data.get('message')
    if not message or not booking_id:
        return
    new_message = ChatMessage(
        booking_id=booking_id,
        sender_id=current_user.id,
        message_text=message,
        timestamp=datetime.utcnow()
    )
    db.session.add(new_message)
    db.session.commit()
    emit('receive_modal_message', {
        'booking_id': booking_id,
        'sender_id': current_user.id,
        'message_text': message,
        'timestamp': new_message.timestamp.strftime('%H:%M')
    }, broadcast=True)

# List recurring routes
@app.route('/recurring_routes')
@login_required
def list_recurring_routes():
    return render_template(
        'recurring_routes.html',
        routes=current_user.recurring_routes
    )

# Create new recurring route
@app.route('/recurring_routes/new', methods=['GET','POST'])
@login_required
def new_recurring_route():
    if request.method == 'POST':
        start = request.form['start_location']
        end = request.form['end_location']
        days = request.form.getlist('days_of_week')
        time = request.form['time']
        route = RecurringRoute(
            user_id=current_user.id,
            start_location=start,
            end_location=end,
            days_of_week=','.join(days),
            time=time
        )
        db.session.add(route)
        db.session.commit()
        flash("Recurring route created!", "success")
        return redirect(url_for('list_recurring_routes'))
    return render_template('recurring_route_form.html')

# Edit recurring route
@app.route('/recurring_routes/<int:id>/edit', methods=['GET','POST'])
@login_required
def edit_recurring_route(id):
    route = RecurringRoute.query.get_or_404(id)
    if route.user_id != current_user.id:
        flash("Not authorized to edit that route.", "danger")
        return redirect(url_for('list_recurring_routes'))
    if request.method == 'POST':
        route.start_location = request.form['start_location']
        route.end_location = request.form['end_location']
        route.days_of_week = ','.join(request.form.getlist('days_of_week'))
        route.time = request.form['time']
        db.session.commit()
        flash("Recurring route updated!", "success")
        return redirect(url_for('list_recurring_routes'))
    return render_template(
        'recurring_route_form.html',
        route=route
    )

# Delete recurring route
@app.route('/recurring_routes/<int:id>/delete', methods=['POST'])
@login_required
def delete_recurring_route(id):
    route = RecurringRoute.query.get_or_404(id)
    if route.user_id == current_user.id:
        db.session.delete(route)
        db.session.commit()
        flash("Recurring route deleted.", "warning")
    else:
        flash("Not authorized to delete that route.", "danger")
    return redirect(url_for('list_recurring_routes'))

# Save a route
@app.route('/save_route', methods=['POST'])
@login_required
def save_route():
    is_json = request.is_json
    data = request.get_json(silent=True) if is_json else request.form

    start = data.get('start_location')
    end = data.get('end_location')

    if not start or not end:
        if is_json:
            return jsonify(success=False, error="Both start_location and end_location are required"), 400
        else:
            flash("Start and end locations are required.", "danger")
            return redirect(url_for('user_dashboard'))

    # Check for duplicate route
    existing = SavedRoute.query.filter_by(
        user_id=current_user.id,
        start_location=start,
        end_location=end
    ).first()

    if existing:
        if is_json:
            return jsonify(success=False, error="This route is already saved."), 409
        else:
            flash("This route is already saved to your dashboard.", "warning")
            return redirect(url_for('user_dashboard'))

    # Save new route
    new_route = SavedRoute(
        user_id=current_user.id,
        start_location=start,
        end_location=end
    )
    db.session.add(new_route)
    db.session.commit()

    if is_json:
        return jsonify(
            success=True,
            route={
                'id': new_route.id,
                'start_location': new_route.start_location,
                'end_location': new_route.end_location
            }
        ), 201
    else:
        flash("Journey saved to your dashboard!", "success")
        return redirect(url_for('user_dashboard'))


# One-click rebook from a saved route
@app.route('/rebook/<int:route_id>', methods=['GET'])
@login_required
def rebook(route_id):
    route = SavedRoute.query.filter_by(id=route_id, user_id=current_user.id).first_or_404()
    return redirect(url_for(
        'create_journey',
        start_location=route.start_location,
        end_location=route.end_location
    ))

def apply_change(req):
    Model = Journey if req.target_type == 'journey' else Booking
    obj = Model.query.get(req.target_id)
    setattr(obj, req.field, req.new_value)
    db.session.commit()

# Request a change to a journey or booking
@app.route('/request_change', methods=['POST'])
@login_required
def request_change():
    ttype = request.form['target_type']
    tid = int(request.form['target_id'])
    field = request.form['field']
    new_val = request.form['new_value']
    Target = Journey if ttype == 'journey' else Booking
    target_obj = Target.query.get_or_404(tid)
    old_val = str(getattr(target_obj, field))
    if (ttype == 'journey' and target_obj.creator_id == current_user.id) or \
       (ttype == 'booking' and target_obj.user_id == current_user.id):
        status = 'accepted'
    else:
        status = 'pending'
    req = ChangeRequest(
        target_type=ttype,
        target_id=tid,
        requester_id=current_user.id,
        field=field,
        old_value=old_val,
        new_value=new_val,
        status=status
    )
    db.session.add(req)
    db.session.flush()
    if status == 'accepted':
        apply_change(req)
        flash("Your change was applied immediately.", "success")
    else:
        flash("Your change request is pending approval.", "info")
    db.session.commit()
    return redirect(request.referrer or url_for('user_dashboard'))

# Update support issue status (manager)
@app.route('/update_support_status/<int:issue_id>', methods=['POST'])
@login_required
def update_support_status(issue_id):
    issue = SupportIssue.query.get_or_404(issue_id)
    new_status = request.form.get('new_status')
    if new_status not in ('open', 'closed'):
        flash('Invalid status.', 'warning')
    else:
        issue.issue_status = new_status
        issue.resolved_date = date.today() if new_status == 'closed' else None
        db.session.commit()
        flash(f'Ticket marked {new_status}.', 'success')
    return redirect(url_for('manager_dashboard'))

# Update booking discount (manager)
@app.route('/update_booking_discount/<int:booking_id>', methods=['POST'])
@login_required
def update_booking_discount(booking_id):
    if current_user.role != UserRole.admin:
        if request.is_json:
            return jsonify({'error': 'Unauthorized'}), 403
        flash("Unauthorized", "danger")
        return redirect(url_for('manager_dashboard'))
    if request.is_json:
        data = request.get_json(silent=True) or {}
        try:
            pct = float(data.get('discount_percentage', 0))
        except ValueError:
            return jsonify({'error': 'Invalid percentage'}), 400
    else:
        try:
            pct = float(request.form['discount_percentage'])
        except (ValueError, KeyError):
            flash("Invalid percentage", "danger")
            return redirect(url_for('manager_dashboard'))
    pct = max(0.0, min(100.0, pct))
    booking = Booking.query.get_or_404(booking_id)
    old_final = booking.total_cost - (booking.discount_amount or 0)
    booking.discount_amount = booking.total_cost * (pct / 100.0)
    db.session.commit()
    new_final = booking.total_cost - booking.discount_amount
    delta = round(new_final - old_final, 2)
    if request.is_json:
        return jsonify({
            'original_subtotal': round(booking.total_cost, 2),
            'new_final': round(new_final, 2),
            'delta': delta
        }), 200
    flash(f"Discount updated to {pct:.1f}%", "success")
    return redirect(url_for('manager_dashboard'))

@app.route('/admin_income')
@login_required
def admin_income():
    if current_user.role not in [UserRole.admin, UserRole.superadmin]:
        return redirect(url_for('index'))

    bookings = Booking.query.filter(Booking.payment_status.in_(['paid', 'refunded'])).all()

    # Total income should include ALL bookings (cancelled ones already have discounted price)
    total_income = sum(b.total_cost for b in bookings)

    platform_fee = total_income * 0.005  # 0.5% company fee
    driver_total_profit = total_income - platform_fee

    # Driver earnings breakdown
    driver_earnings = {}
    for b in bookings:
        if b.journey.driver:
            driver_id = b.journey.driver.id
            if driver_id not in driver_earnings:
                driver_earnings[driver_id] = {
                    'name': f"{b.journey.driver.firstname} {b.journey.driver.lastname}",
                    'total_rides': 0,
                    'total_earnings': 0.0
                }
            driver_earnings[driver_id]['total_rides'] += 1
            driver_earnings[driver_id]['total_earnings'] += b.total_cost

    drivers = list(driver_earnings.values())

    return render_template('admin_income.html',
                           total_income=total_income,
                           platform_fee=platform_fee,
                           driver_total_profit=driver_total_profit,
                           drivers=drivers)

#report&issue
@app.route('/report_issue', methods=['POST'])
@login_required
def report_issue():
    data = request.get_json()
    booking_id = data.get('booking_id')
    message = data.get('message')

    if not booking_id or not message:
        return jsonify(success=False, error="Missing booking_id or message"), 400

    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first()
    if not booking:
        return jsonify(success=False, error="Booking not found"), 404

    issue = SupportIssue(
        user_id=current_user.id,
        journey_id=booking.journey_id,
        booking_id=booking_id,
        issue_type="Complaint",
        issue_description=message,
        issue_status="open"
    )
    db.session.add(issue)
    db.session.commit()

    return jsonify(success=True), 200
