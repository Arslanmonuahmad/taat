from datetime import datetime, timezone, timedelta
from src.models.database import db, User, Credit, CreditType, CreditSource
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

class CreditService:
    """Service for managing user credits"""
    
    def get_user_credits(self, user_id: int) -> list:
        """Get all credits for a user"""
        return Credit.query.filter_by(user_id=user_id, is_active=True).all()
    
    def get_active_credit_balance(self, user_id: int) -> int:
        """Get total active credit balance for a user"""
        result = db.session.query(func.sum(Credit.balance)).filter_by(
            user_id=user_id, 
            is_active=True
        ).scalar()
        return result or 0
    
    def add_credits(self, user_id: int, amount: int, credit_type: CreditType, 
                   source: CreditSource, source_reference: str = None, 
                   expires_at: datetime = None) -> Credit:
        """Add credits to a user account"""
        try:
            credit = Credit(
                user_id=user_id,
                credit_type=credit_type,
                amount=amount,
                balance=amount,
                source=source,
                source_reference=source_reference,
                expires_at=expires_at
            )
            
            db.session.add(credit)
            
            # Update user's total credits earned
            user = User.query.get(user_id)
            if user:
                user.total_credits_earned += amount
            
            db.session.commit()
            logger.info(f"Added {amount} credits to user {user_id} from {source.value}")
            
            return credit
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding credits to user {user_id}: {e}")
            raise
    
    def consume_credits(self, user_id: int, amount: int = 1) -> bool:
        """Consume credits from user account (FIFO - oldest first)"""
        try:
            # Get active credits ordered by creation date (FIFO)
            credits = Credit.query.filter_by(
                user_id=user_id, 
                is_active=True
            ).filter(Credit.balance > 0).order_by(Credit.created_at).all()
            
            total_available = sum(credit.balance for credit in credits)
            
            if total_available < amount:
                logger.warning(f"Insufficient credits for user {user_id}. Available: {total_available}, Required: {amount}")
                return False
            
            remaining_to_consume = amount
            
            for credit in credits:
                if remaining_to_consume <= 0:
                    break
                
                if credit.balance >= remaining_to_consume:
                    # This credit has enough balance
                    credit.balance -= remaining_to_consume
                    remaining_to_consume = 0
                else:
                    # Consume all of this credit and move to next
                    remaining_to_consume -= credit.balance
                    credit.balance = 0
                
                # Deactivate credit if balance is zero
                if credit.balance == 0:
                    credit.is_active = False
            
            # Update user's total credits spent
            user = User.query.get(user_id)
            if user:
                user.total_credits_spent += amount
            
            db.session.commit()
            logger.info(f"Consumed {amount} credits from user {user_id}")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error consuming credits for user {user_id}: {e}")
            return False
    
    def refund_credits(self, user_id: int, amount: int, reason: str = None) -> Credit:
        """Refund credits to a user account"""
        return self.add_credits(
            user_id=user_id,
            amount=amount,
            credit_type=CreditType.BONUS,
            source=CreditSource.REFUND,
            source_reference=reason
        )
    
    def grant_admin_credits(self, user_id: int, amount: int, admin_id: int, reason: str = None) -> Credit:
        """Grant credits by admin"""
        return self.add_credits(
            user_id=user_id,
            amount=amount,
            credit_type=CreditType.BONUS,
            source=CreditSource.ADMIN_GRANT,
            source_reference=f"admin_{admin_id}_{reason}" if reason else f"admin_{admin_id}"
        )
    
    def expire_old_credits(self) -> int:
        """Expire old credits that have passed their expiration date"""
        try:
            expired_count = Credit.query.filter(
                Credit.expires_at < datetime.now(timezone.utc),
                Credit.is_active == True
            ).update({'is_active': False})
            
            db.session.commit()
            logger.info(f"Expired {expired_count} old credits")
            
            return expired_count
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error expiring old credits: {e}")
            return 0
    
    def get_credit_history(self, user_id: int, limit: int = 50, offset: int = 0) -> list:
        """Get credit history for a user"""
        return Credit.query.filter_by(user_id=user_id).order_by(
            Credit.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    def get_credit_statistics(self) -> dict:
        """Get system-wide credit statistics"""
        try:
            total_credits_issued = db.session.query(func.sum(Credit.amount)).scalar() or 0
            total_credits_active = db.session.query(func.sum(Credit.balance)).filter_by(is_active=True).scalar() or 0
            total_credits_consumed = total_credits_issued - total_credits_active
            
            # Credits by type
            credits_by_type = db.session.query(
                Credit.credit_type,
                func.sum(Credit.amount).label('total'),
                func.sum(Credit.balance).label('remaining')
            ).filter_by(is_active=True).group_by(Credit.credit_type).all()
            
            # Credits by source
            credits_by_source = db.session.query(
                Credit.source,
                func.sum(Credit.amount).label('total')
            ).group_by(Credit.source).all()
            
            return {
                'total_issued': total_credits_issued,
                'total_active': total_credits_active,
                'total_consumed': total_credits_consumed,
                'by_type': {item.credit_type.value: {'total': item.total, 'remaining': item.remaining} for item in credits_by_type},
                'by_source': {item.source.value: item.total for item in credits_by_source}
            }
            
        except Exception as e:
            logger.error(f"Error getting credit statistics: {e}")
            return {}
    
    def validate_credit_transaction(self, user_id: int, amount: int) -> dict:
        """Validate if a credit transaction can be performed"""
        user = User.query.get(user_id)
        if not user:
            return {'valid': False, 'reason': 'User not found'}
        
        if user.status.value != 'active':
            return {'valid': False, 'reason': 'User account is not active'}
        
        current_balance = self.get_active_credit_balance(user_id)
        if current_balance < amount:
            return {
                'valid': False, 
                'reason': f'Insufficient credits. Available: {current_balance}, Required: {amount}'
            }
        
        return {'valid': True, 'current_balance': current_balance}
    
    def get_expiring_credits(self, days_ahead: int = 7) -> list:
        """Get credits that will expire within specified days"""
        expiry_date = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        
        return Credit.query.filter(
            Credit.expires_at <= expiry_date,
            Credit.expires_at > datetime.now(timezone.utc),
            Credit.is_active == True,
            Credit.balance > 0
        ).all()
    
    def transfer_credits(self, from_user_id: int, to_user_id: int, amount: int, reason: str = None) -> bool:
        """Transfer credits between users (admin function)"""
        try:
            # Validate source user has enough credits
            validation = self.validate_credit_transaction(from_user_id, amount)
            if not validation['valid']:
                return False
            
            # Consume from source user
            if not self.consume_credits(from_user_id, amount):
                return False
            
            # Add to destination user
            self.add_credits(
                user_id=to_user_id,
                amount=amount,
                credit_type=CreditType.BONUS,
                source=CreditSource.ADMIN_GRANT,
                source_reference=f"transfer_from_{from_user_id}_{reason}" if reason else f"transfer_from_{from_user_id}"
            )
            
            logger.info(f"Transferred {amount} credits from user {from_user_id} to user {to_user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error transferring credits: {e}")
            return False

