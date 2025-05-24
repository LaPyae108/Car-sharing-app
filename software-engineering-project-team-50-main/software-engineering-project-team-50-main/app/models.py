from flask_login import UserMixin
from app.extensions import db
from datetime import datetime, date, timedelta
import enum
from sqlalchemy.sql import func
class UserRole(enum.Enum):
    passenger = "passenger"
    admin = "admin"
    driver = "driver"
    manager = "manager"
    superadmin = "superadmin"

class BookingPaymentStatus(enum.Enum):
    unpaid = "unpaid"
    pending = "pending"
    paid = "paid"
    refunded = "refunded"

class PaymentMethod(enum.Enum):
    card = "card"
    google_pay = "google pay"
    other = "other"

class PaymentStatus(enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(50))
    lastname = db.Column(db.String(50))
    email = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    phone_number = db.Column(db.String)
    role = db.Column(db.Enum(UserRole), nullable=False)
    rating = db.Column(db.Float)

    journeys_created = db.relationship('Journey', foreign_keys='Journey.creator_id', backref='creator', lazy=True)
    journeys_driven = db.relationship('Journey', foreign_keys='Journey.driver_id', backref='driver', lazy=True)
    bookings = db.relationship('Booking', backref='user', lazy=True)
    ratings_given = db.relationship('Rating', foreign_keys='Rating.rater_id', backref='rater', lazy=True)
    ratings_received = db.relationship('Rating', foreign_keys='Rating.rated_user_id', backref='rated', lazy=True)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy=True)
    support_issues = db.relationship('SupportIssue', back_populates='user', lazy=True)

    payments = db.relationship('Payment', backref='user', lazy=True)
    stored_cards = db.relationship('StoredCard', backref='user', lazy=True)

    saved_routes = db.relationship(
        'SavedRoute',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan'
    )

class Journey(db.Model):
    __tablename__ = 'journeys'
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    start_location = db.Column(db.String(100), nullable=False)
    end_location = db.Column(db.String(100), nullable=False)
    journey_date = db.Column(db.Date, nullable=False)
    journey_time = db.Column(db.Time, nullable=False)
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_days = db.Column(db.String(100))  # comma-separated days
    available_seats = db.Column(db.Integer, nullable=False, default=1)
    journey_status = db.Column(db.String(20), default='active')
    support_issues = db.relationship('SupportIssue', back_populates='journey', lazy=True)

    bookings = db.relationship('Booking', backref='journey', lazy=True)
    messages = db.relationship('Message', backref='journey', lazy=True)

class DiscountRule(db.Model):
    __tablename__ = 'discount_rules'
    id = db.Column(db.Integer, primary_key=True)
    rule_name = db.Column(db.String)
    min_trips = db.Column(db.Integer)
    discount_percentage = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)

    bookings = db.relationship('Booking', backref='discount_rule', lazy=True)

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    journey_id = db.Column(db.Integer, db.ForeignKey('journeys.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    booking_date = db.Column(db.Date)
    passenger_count = db.Column(db.Integer)
    total_cost = db.Column(db.Float)
    booking_status = db.Column(db.String)
    cancellation_reason = db.Column(db.String)
    discount_id = db.Column(db.Integer, db.ForeignKey('discount_rules.id'), nullable=True)
    discount_amount = db.Column(db.Float, nullable=True)
    payment_status = db.Column(db.Enum(BookingPaymentStatus), nullable=False)
    passenger_notes = db.Column(db.String, nullable=True)

    ratings = db.relationship('Rating', backref='booking', lazy=True)
    support_issues = db.relationship('SupportIssue', back_populates='booking', lazy=True)

    payments = db.relationship('Payment', backref='booking', lazy=True)

    @classmethod
    def trips_last_week(cls, user_id):
        """Return how many bookings this user made in the past 7 days."""
        cutoff = date.today() - timedelta(days=7)
        return (
            cls.query
               .filter(cls.user_id == user_id,
                       cls.booking_date >= cutoff)
               .count()
        )

class StoredCard(db.Model):
    __tablename__ = 'stored_cards'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_type = db.Column(db.String)
    card_num = db.Column(db.Integer)
    cvv_num = db.Column(db.Integer)
    cardholder_name = db.Column(db.String)
    expiry_month = db.Column(db.Integer)
    expiry_year = db.Column(db.Integer)
    is_default = db.Column(db.Boolean, default=False)

    payments = db.relationship('Payment', backref='stored_card', lazy=True)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float)
    payment_date = db.Column(db.Date)
    payment_time = db.Column(db.Time)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=False)
    transaction_id = db.Column(db.String, unique=True, nullable=False)
    payment_status = db.Column(db.Enum(PaymentStatus), nullable=False)
    refund_amount = db.Column(db.Float)
    refund_date = db.Column(db.Date)
    refund_reason = db.Column(db.String)
    stored_card_id = db.Column(db.Integer, db.ForeignKey('stored_cards.id'))

class Rating(db.Model):
    __tablename__ = 'ratings'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    rater_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rated_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating_score = db.Column(db.Integer)
    rating_comment = db.Column(db.String)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    journey_id = db.Column(db.Integer, db.ForeignKey('journeys.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message_content = db.Column(db.String)
    sent_date = db.Column(db.Date)
    sent_time = db.Column(db.Time)
    read_status = db.Column(db.Boolean, default=False)

from datetime import datetime

class SupportIssue(db.Model):
    __tablename__ = 'support_issues'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=True)
    journey_id = db.Column(db.Integer, db.ForeignKey('journeys.id'), nullable=True)

    issue_type = db.Column(db.String, nullable=False)
    issue_description = db.Column(db.String, nullable=False)
    issue_status = db.Column(db.String, default='open')
    created_date = db.Column(db.DateTime, default=func.now())
    resolved_date = db.Column(db.DateTime, nullable=True)
    booking = db.relationship('Booking', back_populates='support_issues')
    journey = db.relationship('Journey', back_populates='support_issues')
    user = db.relationship('User', back_populates='support_issues')



class CarDetail(db.Model):
    __tablename__ = 'car_details'
    id = db.Column(db.Integer, primary_key=True)
    plate_id = db.Column(db.String, unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    brand = db.Column(db.String)
    model = db.Column(db.String)
    capacity = db.Column(db.Integer)

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    booking = db.relationship(
        'Booking',
        backref=db.backref(
            'chat_messages',
            lazy=True,
            cascade="all, delete-orphan",
            passive_deletes=True
        )
    )
    sender = db.relationship('User', backref=db.backref('chat_chat_messages', lazy=True))


class SavedRoute(db.Model):
    __tablename__ = 'saved_routes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_location = db.Column(db.String(100), nullable=False)
    end_location   = db.Column(db.String(100), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class ChangeRequest(db.Model):
    __tablename__   = 'change_requests'
    id              = db.Column(db.Integer, primary_key=True)
    target_type     = db.Column(db.String(20), nullable=False)    # 'journey' or 'booking'
    target_id       = db.Column(db.Integer, nullable=False)
    requester_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    field           = db.Column(db.String(50), nullable=False)    # e.g. 'journey_time'
    old_value       = db.Column(db.String,   nullable=False)
    new_value       = db.Column(db.String,   nullable=False)
    status          = db.Column(db.String(20), nullable=False, default='pending')  # pending/accepted/rejected
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at    = db.Column(db.DateTime, nullable=True)

    requester       = db.relationship('User', backref='change_requests')
