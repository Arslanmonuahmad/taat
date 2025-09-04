import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.models.database import db, Transaction, TransactionType, PaymentMethod, TransactionStatus
from src.services.credit_service import CreditService
from src.models.database import CreditType, CreditSource
import hashlib
import hmac
import json

logger = logging.getLogger(__name__)

class PaymentService:
    """Service for handling payments via Telegram Stars and UPI"""
    
    def __init__(self):
        self.credit_service = CreditService()
        
        # Payment configurations
        self.telegram_stars_rate = 100  # 100 stars = 70 credits
        self.telegram_stars_credits = 70
        
        self.upi_rate_inr = 59  # 59 INR = 23 credits
        self.upi_credits = 23
        
        # Webhook secrets for verification
        self.telegram_webhook_secret = os.getenv('TELEGRAM_WEBHOOK_SECRET')
        self.upi_webhook_secret = os.getenv('UPI_WEBHOOK_SECRET')
    
    def create_transaction(self, user_id: int, transaction_type: TransactionType,
                          payment_method: PaymentMethod, amount_local: float,
                          currency_code: str, credits_purchased: int,
                          external_transaction_id: str = None) -> Transaction:
        """Create a new transaction record"""
        try:
            transaction = Transaction(
                user_id=user_id,
                transaction_type=transaction_type,
                payment_method=payment_method,
                amount_local=amount_local,
                currency_code=currency_code,
                credits_purchased=credits_purchased,
                external_transaction_id=external_transaction_id,
                status=TransactionStatus.PENDING
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            logger.info(f"Created transaction {transaction.id} for user {user_id}")
            return transaction
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating transaction: {e}")
            raise
    
    def process_telegram_stars_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process Telegram Stars payment"""
        try:
            # Verify payment authenticity
            if not self._verify_telegram_payment(payment_data):
                return {'success': False, 'error': 'Invalid payment verification'}
            
            # Extract payment details
            user_id = payment_data.get('user_id')
            stars_amount = payment_data.get('total_amount')  # Amount in stars
            payment_id = payment_data.get('telegram_payment_charge_id')
            
            if not all([user_id, stars_amount, payment_id]):
                return {'success': False, 'error': 'Missing payment data'}
            
            # Calculate credits based on stars
            if stars_amount == self.telegram_stars_rate:
                credits_to_add = self.telegram_stars_credits
            else:
                # Calculate proportionally
                credits_to_add = int((stars_amount / self.telegram_stars_rate) * self.telegram_stars_credits)
            
            # Create transaction record
            transaction = self.create_transaction(
                user_id=user_id,
                transaction_type=TransactionType.PURCHASE,
                payment_method=PaymentMethod.TELEGRAM_STARS,
                amount_local=stars_amount,
                currency_code='STARS',
                credits_purchased=credits_to_add,
                external_transaction_id=payment_id
            )
            
            # Add credits to user account
            credit = self.credit_service.add_credits(
                user_id=user_id,
                amount=credits_to_add,
                credit_type=CreditType.PURCHASED,
                source=CreditSource.PURCHASE,
                source_reference=f"telegram_stars_{transaction.id}"
            )
            
            # Update transaction status
            transaction.status = TransactionStatus.COMPLETED
            transaction.completed_at = datetime.now(timezone.utc)
            transaction.credit_id = credit.id
            
            db.session.commit()
            
            logger.info(f"Processed Telegram Stars payment: {credits_to_add} credits for user {user_id}")
            
            return {
                'success': True,
                'transaction_id': transaction.id,
                'credits_added': credits_to_add,
                'stars_amount': stars_amount
            }
            
        except Exception as e:
            logger.error(f"Error processing Telegram Stars payment: {e}")
            return {'success': False, 'error': str(e)}
    
    def process_upi_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process UPI payment"""
        try:
            # Verify payment authenticity
            if not self._verify_upi_payment(payment_data):
                return {'success': False, 'error': 'Invalid payment verification'}
            
            # Extract payment details
            user_id = payment_data.get('user_id')
            amount_inr = float(payment_data.get('amount'))
            payment_id = payment_data.get('transaction_id')
            upi_id = payment_data.get('upi_id')
            
            if not all([user_id, amount_inr, payment_id]):
                return {'success': False, 'error': 'Missing payment data'}
            
            # Calculate credits based on INR amount
            if amount_inr == self.upi_rate_inr:
                credits_to_add = self.upi_credits
            else:
                # Calculate proportionally
                credits_to_add = int((amount_inr / self.upi_rate_inr) * self.upi_credits)
            
            # Create transaction record
            transaction = self.create_transaction(
                user_id=user_id,
                transaction_type=TransactionType.PURCHASE,
                payment_method=PaymentMethod.UPI,
                amount_local=amount_inr,
                currency_code='INR',
                credits_purchased=credits_to_add,
                external_transaction_id=payment_id
            )
            
            # Add credits to user account
            credit = self.credit_service.add_credits(
                user_id=user_id,
                amount=credits_to_add,
                credit_type=CreditType.PURCHASED,
                source=CreditSource.PURCHASE,
                source_reference=f"upi_{transaction.id}"
            )
            
            # Update transaction status
            transaction.status = TransactionStatus.COMPLETED
            transaction.completed_at = datetime.now(timezone.utc)
            transaction.credit_id = credit.id
            
            db.session.commit()
            
            logger.info(f"Processed UPI payment: {credits_to_add} credits for user {user_id}")
            
            return {
                'success': True,
                'transaction_id': transaction.id,
                'credits_added': credits_to_add,
                'amount_inr': amount_inr,
                'upi_id': upi_id
            }
            
        except Exception as e:
            logger.error(f"Error processing UPI payment: {e}")
            return {'success': False, 'error': str(e)}
    
    def _verify_telegram_payment(self, payment_data: Dict[str, Any]) -> bool:
        """Verify Telegram payment authenticity"""
        try:
            if not self.telegram_webhook_secret:
                logger.warning("Telegram webhook secret not configured")
                return True  # Skip verification if not configured
            
            # Implement Telegram payment verification logic
            # This would typically involve checking the payment signature
            # For now, we'll do basic validation
            
            required_fields = ['user_id', 'total_amount', 'telegram_payment_charge_id']
            return all(field in payment_data for field in required_fields)
            
        except Exception as e:
            logger.error(f"Error verifying Telegram payment: {e}")
            return False
    
    def _verify_upi_payment(self, payment_data: Dict[str, Any]) -> bool:
        """Verify UPI payment authenticity"""
        try:
            if not self.upi_webhook_secret:
                logger.warning("UPI webhook secret not configured")
                return True  # Skip verification if not configured
            
            # Implement UPI payment verification logic
            # This would typically involve checking the payment gateway signature
            # For now, we'll do basic validation
            
            required_fields = ['user_id', 'amount', 'transaction_id']
            return all(field in payment_data for field in required_fields)
            
        except Exception as e:
            logger.error(f"Error verifying UPI payment: {e}")
            return False
    
    def get_payment_options(self, user_id: int) -> Dict[str, Any]:
        """Get available payment options for a user"""
        return {
            'telegram_stars': {
                'amount': self.telegram_stars_rate,
                'currency': 'STARS',
                'credits': self.telegram_stars_credits,
                'description': f'{self.telegram_stars_rate} Telegram Stars = {self.telegram_stars_credits} Credits'
            },
            'upi': {
                'amount': self.upi_rate_inr,
                'currency': 'INR',
                'credits': self.upi_credits,
                'description': f'₹{self.upi_rate_inr} = {self.upi_credits} Credits'
            }
        }
    
    def get_transaction_history(self, user_id: int, limit: int = 10) -> list:
        """Get transaction history for a user"""
        transactions = Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                'id': tx.id,
                'type': tx.transaction_type.value,
                'payment_method': tx.payment_method.value,
                'amount': float(tx.amount_local),
                'currency': tx.currency_code,
                'credits': tx.credits_purchased,
                'status': tx.status.value,
                'created_at': tx.created_at.isoformat(),
                'completed_at': tx.completed_at.isoformat() if tx.completed_at else None
            }
            for tx in transactions
        ]
    
    def get_transaction_by_id(self, transaction_id: int) -> Optional[Transaction]:
        """Get transaction by ID"""
        return Transaction.query.get(transaction_id)
    
    def get_transaction_by_external_id(self, external_id: str) -> Optional[Transaction]:
        """Get transaction by external transaction ID"""
        return Transaction.query.filter_by(external_transaction_id=external_id).first()
    
    def mark_transaction_failed(self, transaction_id: int, error_message: str = None) -> bool:
        """Mark a transaction as failed"""
        try:
            transaction = self.get_transaction_by_id(transaction_id)
            if not transaction:
                return False
            
            transaction.status = TransactionStatus.FAILED
            transaction.error_message = error_message
            transaction.completed_at = datetime.now(timezone.utc)
            
            db.session.commit()
            logger.info(f"Marked transaction {transaction_id} as failed")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking transaction as failed: {e}")
            return False
    
    def get_payment_statistics(self) -> Dict[str, Any]:
        """Get payment statistics"""
        try:
            total_transactions = Transaction.query.count()
            completed_transactions = Transaction.query.filter_by(status=TransactionStatus.COMPLETED).count()
            failed_transactions = Transaction.query.filter_by(status=TransactionStatus.FAILED).count()
            pending_transactions = Transaction.query.filter_by(status=TransactionStatus.PENDING).count()
            
            # Revenue by payment method
            from sqlalchemy import func
            revenue_by_method = db.session.query(
                Transaction.payment_method,
                func.sum(Transaction.amount_local).label('total_amount'),
                func.count(Transaction.id).label('transaction_count')
            ).filter_by(status=TransactionStatus.COMPLETED).group_by(Transaction.payment_method).all()
            
            return {
                'total_transactions': total_transactions,
                'completed_transactions': completed_transactions,
                'failed_transactions': failed_transactions,
                'pending_transactions': pending_transactions,
                'success_rate': (completed_transactions / total_transactions * 100) if total_transactions > 0 else 0,
                'revenue_by_method': {
                    item.payment_method.value: {
                        'total_amount': float(item.total_amount),
                        'transaction_count': item.transaction_count
                    } for item in revenue_by_method
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting payment statistics: {e}")
            return {}
    
    def create_payment_invoice(self, user_id: int, payment_method: str) -> Dict[str, Any]:
        """Create a payment invoice for the user"""
        try:
            payment_options = self.get_payment_options(user_id)
            
            if payment_method not in payment_options:
                return {'success': False, 'error': 'Invalid payment method'}
            
            option = payment_options[payment_method]
            
            # Create pending transaction
            transaction = self.create_transaction(
                user_id=user_id,
                transaction_type=TransactionType.PURCHASE,
                payment_method=PaymentMethod.TELEGRAM_STARS if payment_method == 'telegram_stars' else PaymentMethod.UPI,
                amount_local=option['amount'],
                currency_code=option['currency'],
                credits_purchased=option['credits']
            )
            
            return {
                'success': True,
                'transaction_id': transaction.id,
                'amount': option['amount'],
                'currency': option['currency'],
                'credits': option['credits'],
                'description': option['description']
            }
            
        except Exception as e:
            logger.error(f"Error creating payment invoice: {e}")
            return {'success': False, 'error': str(e)}

