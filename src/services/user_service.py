from datetime import datetime, timezone
from src.models.database import db, User, Credit, CreditType, CreditSource, UserStatus
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)

class UserService:
    """Service for managing user operations"""
    
    def get_user_by_telegram_id(self, telegram_user_id: int) -> User:
        """Get user by Telegram user ID"""
        return User.query.filter_by(telegram_user_id=telegram_user_id).first()
    
    def get_user_by_id(self, user_id: int) -> User:
        """Get user by internal ID"""
        return User.query.get(user_id)
    
    def get_or_create_user(self, telegram_user_id: int, username: str = None, 
                          first_name: str = None, last_name: str = None, 
                          language_code: str = 'en') -> User:
        """Get existing user or create new one"""
        user = self.get_user_by_telegram_id(telegram_user_id)
        
        if user:
            # Update user information if it has changed
            updated = False
            if user.username != username:
                user.username = username
                updated = True
            if user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if user.language_code != language_code:
                user.language_code = language_code
                updated = True
            
            if updated:
                user.last_activity = datetime.now(timezone.utc)
                db.session.commit()
                logger.info(f"Updated user information for {telegram_user_id}")
            
            return user
        
        # Create new user
        try:
            user = User(
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                registration_date=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc)
            )
            
            db.session.add(user)
            db.session.flush()  # Get the user ID
            
            # Give free registration credit
            self._give_registration_credit(user.id)
            
            db.session.commit()
            logger.info(f"Created new user {telegram_user_id} with ID {user.id}")
            
            return user
            
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Error creating user {telegram_user_id}: {e}")
            # Try to get the user again in case of race condition
            return self.get_user_by_telegram_id(telegram_user_id)
    
    def _give_registration_credit(self, user_id: int):
        """Give free credit to new user"""
        credit = Credit(
            user_id=user_id,
            credit_type=CreditType.FREE,
            amount=1,
            balance=1,
            source=CreditSource.REGISTRATION,
            source_reference='registration_bonus'
        )
        db.session.add(credit)
        logger.info(f"Gave registration credit to user {user_id}")
    
    def agree_to_terms(self, user_id: int) -> bool:
        """Mark user as having agreed to terms"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.agreed_to_terms = True
        user.terms_agreed_at = datetime.now(timezone.utc)
        user.last_activity = datetime.now(timezone.utc)
        
        db.session.commit()
        logger.info(f"User {user_id} agreed to terms")
        return True
    
    def update_last_activity(self, user_id: int):
        """Update user's last activity timestamp"""
        user = self.get_user_by_id(user_id)
        if user:
            user.last_activity = datetime.now(timezone.utc)
            db.session.commit()
    
    def suspend_user(self, user_id: int, reason: str = None) -> bool:
        """Suspend a user account"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.status = UserStatus.SUSPENDED
        db.session.commit()
        logger.warning(f"Suspended user {user_id}. Reason: {reason}")
        return True
    
    def ban_user(self, user_id: int, reason: str = None) -> bool:
        """Ban a user account"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.status = UserStatus.BANNED
        db.session.commit()
        logger.warning(f"Banned user {user_id}. Reason: {reason}")
        return True
    
    def reactivate_user(self, user_id: int) -> bool:
        """Reactivate a suspended or banned user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.status = UserStatus.ACTIVE
        db.session.commit()
        logger.info(f"Reactivated user {user_id}")
        return True
    
    def get_user_stats(self, user_id: int) -> dict:
        """Get comprehensive user statistics"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        return {
            'user_id': user.id,
            'telegram_user_id': user.telegram_user_id,
            'username': user.username,
            'first_name': user.first_name,
            'registration_date': user.registration_date,
            'last_activity': user.last_activity,
            'status': user.status.value,
            'total_credits_earned': user.total_credits_earned,
            'total_credits_spent': user.total_credits_spent,
            'current_credits': user.get_active_credits(),
            'total_invites_sent': user.total_invites_sent,
            'total_invites_accepted': user.total_invites_accepted,
            'total_face_swap_jobs': len(user.face_swap_jobs),
            'completed_jobs': len([job for job in user.face_swap_jobs if job.status.value == 'completed']),
            'agreed_to_terms': user.agreed_to_terms,
            'terms_agreed_at': user.terms_agreed_at
        }
    
    def search_users(self, query: str = None, status: UserStatus = None, 
                    limit: int = 50, offset: int = 0) -> list:
        """Search users with filters"""
        query_obj = User.query
        
        if query:
            query_obj = query_obj.filter(
                db.or_(
                    User.username.ilike(f'%{query}%'),
                    User.first_name.ilike(f'%{query}%'),
                    User.last_name.ilike(f'%{query}%')
                )
            )
        
        if status:
            query_obj = query_obj.filter(User.status == status)
        
        return query_obj.order_by(User.registration_date.desc()).offset(offset).limit(limit).all()
    
    def get_user_count(self) -> dict:
        """Get user count statistics"""
        total_users = User.query.count()
        active_users = User.query.filter_by(status=UserStatus.ACTIVE).count()
        suspended_users = User.query.filter_by(status=UserStatus.SUSPENDED).count()
        banned_users = User.query.filter_by(status=UserStatus.BANNED).count()
        
        return {
            'total': total_users,
            'active': active_users,
            'suspended': suspended_users,
            'banned': banned_users
        }

