from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from sqlalchemy import Index
import enum

db = SQLAlchemy()

class UserStatus(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"

class CreditType(enum.Enum):
    FREE = "free"
    PURCHASED = "purchased"
    EARNED = "earned"
    BONUS = "bonus"

class CreditSource(enum.Enum):
    REGISTRATION = "registration"
    INVITE = "invite"
    PURCHASE = "purchase"
    ADMIN_GRANT = "admin_grant"
    REFUND = "refund"

class TransactionType(enum.Enum):
    PURCHASE = "purchase"
    REFUND = "refund"
    CHARGEBACK = "chargeback"

class PaymentMethod(enum.Enum):
    TELEGRAM_STARS = "telegram_stars"
    UPI = "upi"

class TransactionStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class JobType(enum.Enum):
    IMAGE = "image"
    VIDEO = "video"

class JobStatus(enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class InviteStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"

class AdminRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MODERATOR = "moderator"

class ConfigType(enum.Enum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    JSON = "json"

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.BigInteger, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    language_code = db.Column(db.String(10), default='en')
    is_premium = db.Column(db.Boolean, default=False)
    status = db.Column(db.Enum(UserStatus), default=UserStatus.ACTIVE)
    registration_date = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    last_activity = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    total_credits_earned = db.Column(db.Integer, default=1)
    total_credits_spent = db.Column(db.Integer, default=0)
    total_invites_sent = db.Column(db.Integer, default=0)
    total_invites_accepted = db.Column(db.Integer, default=0)
    agreed_to_terms = db.Column(db.Boolean, default=False)
    terms_agreed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    credits = db.relationship('Credit', backref='user', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    face_swap_jobs = db.relationship('FaceSwapJob', backref='user', lazy=True, cascade='all, delete-orphan')
    sent_invites = db.relationship('Invite', foreign_keys='Invite.inviter_user_id', backref='inviter', lazy=True)
    received_invites = db.relationship('Invite', foreign_keys='Invite.invitee_user_id', backref='invitee', lazy=True)
    
    def __repr__(self):
        return f'<User {self.telegram_user_id}>'
    
    def get_active_credits(self):
        """Get total active credits for the user"""
        return sum(credit.balance for credit in self.credits if credit.is_active)
    
    def can_perform_job(self):
        """Check if user has enough credits to perform a face swap job"""
        return self.get_active_credits() >= 1

class Credit(db.Model):
    __tablename__ = 'credits'
    
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False)
    credit_type = db.Column(db.Enum(CreditType), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance = db.Column(db.Integer, nullable=False, default=0)
    source = db.Column(db.Enum(CreditSource), nullable=False)
    source_reference = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Credit {self.id}: {self.balance}/{self.amount}>'

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False)
    transaction_type = db.Column(db.Enum(TransactionType), nullable=False)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=False)
    amount_local = db.Column(db.Numeric(10, 2), nullable=False)
    currency_code = db.Column(db.String(3), nullable=False)
    credits_purchased = db.Column(db.Integer, nullable=False)
    external_transaction_id = db.Column(db.String(255), unique=True)
    payment_gateway_response = db.Column(db.JSON)
    status = db.Column(db.Enum(TransactionStatus), default=TransactionStatus.PENDING)
    processed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Transaction {self.id}: {self.credits_purchased} credits>'

class FaceSwapJob(db.Model):
    __tablename__ = 'face_swap_jobs'
    
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False)
    job_type = db.Column(db.Enum(JobType), nullable=False)
    status = db.Column(db.Enum(JobStatus), default=JobStatus.QUEUED)
    credits_consumed = db.Column(db.Integer, default=1)
    source_file_path = db.Column(db.String(500))
    target_file_path = db.Column(db.String(500))
    result_file_path = db.Column(db.String(500))
    file_size_bytes = db.Column(db.BigInteger)
    processing_time_seconds = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    processing_metadata = db.Column(db.JSON)
    telegram_message_id = db.Column(db.BigInteger)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<FaceSwapJob {self.id}: {self.status.value}>'

class Invite(db.Model):
    __tablename__ = 'invites'
    
    id = db.Column(db.BigInteger, primary_key=True)
    inviter_user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False)
    invitee_user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'))
    invite_code = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.Enum(InviteStatus), default=InviteStatus.PENDING)
    credits_awarded = db.Column(db.Integer, default=1)
    invited_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    accepted_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Invite {self.invite_code}: {self.status.value}>'

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    
    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(AdminRole), default=AdminRole.ADMIN)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime(timezone=True))
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<AdminUser {self.username}>'

class SystemConfiguration(db.Model):
    __tablename__ = 'system_configuration'
    
    id = db.Column(db.BigInteger, primary_key=True)
    config_key = db.Column(db.String(100), unique=True, nullable=False)
    config_value = db.Column(db.Text, nullable=False)
    config_type = db.Column(db.Enum(ConfigType), default=ConfigType.STRING)
    description = db.Column(db.Text)
    is_sensitive = db.Column(db.Boolean, default=False)
    updated_by = db.Column(db.BigInteger, db.ForeignKey('admin_users.id'))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<SystemConfiguration {self.config_key}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'))
    admin_user_id = db.Column(db.BigInteger, db.ForeignKey('admin_users.id'))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.BigInteger)
    old_values = db.Column(db.JSON)
    new_values = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<AuditLog {self.id}: {self.action}>'

# Create indexes for performance optimization
Index('idx_users_telegram_id', User.telegram_user_id)
Index('idx_users_status', User.status)
Index('idx_credits_user_active_type', Credit.user_id, Credit.is_active, Credit.credit_type)
Index('idx_transactions_user_status', Transaction.user_id, Transaction.status)
Index('idx_face_swap_jobs_user_status', FaceSwapJob.user_id, FaceSwapJob.status)
Index('idx_invites_code', Invite.invite_code)
Index('idx_audit_logs_user_action', AuditLog.user_id, AuditLog.action)

