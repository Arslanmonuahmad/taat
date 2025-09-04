import uuid
from datetime import datetime, timezone, timedelta
from src.models.database import db, User, Invite, InviteStatus, CreditType, CreditSource
from src.services.credit_service import CreditService
import logging

logger = logging.getLogger(__name__)

class InviteService:
    """Service for managing user invitations"""
    
    def __init__(self):
        self.credit_service = CreditService()
    
    def create_invite(self, inviter_user_id: int, expires_in_days: int = 30) -> str:
        """Create a new invite code for a user"""
        try:
            # Generate unique invite code
            invite_code = str(uuid.uuid4())[:8].upper()
            
            # Ensure uniqueness
            while Invite.query.filter_by(invite_code=invite_code).first():
                invite_code = str(uuid.uuid4())[:8].upper()
            
            # Create invite record
            invite = Invite(
                inviter_user_id=inviter_user_id,
                invite_code=invite_code,
                expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            )
            
            db.session.add(invite)
            
            # Update user's total invites sent
            user = User.query.get(inviter_user_id)
            if user:
                user.total_invites_sent += 1
            
            db.session.commit()
            logger.info(f"Created invite code {invite_code} for user {inviter_user_id}")
            
            return invite_code
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating invite for user {inviter_user_id}: {e}")
            raise
    
    def process_invite(self, invite_code: str, invitee_user_id: int) -> dict:
        """Process an invite when a new user joins"""
        try:
            # Find the invite
            invite = Invite.query.filter_by(invite_code=invite_code).first()
            
            if not invite:
                return {'success': False, 'reason': 'Invalid invite code'}
            
            if invite.status != InviteStatus.PENDING:
                return {'success': False, 'reason': 'Invite already used or expired'}
            
            if invite.expires_at < datetime.now(timezone.utc):
                invite.status = InviteStatus.EXPIRED
                db.session.commit()
                return {'success': False, 'reason': 'Invite has expired'}
            
            # Check if invitee is the same as inviter
            if invite.inviter_user_id == invitee_user_id:
                return {'success': False, 'reason': 'Cannot invite yourself'}
            
            # Check if user already exists (shouldn't happen in normal flow)
            invitee = User.query.get(invitee_user_id)
            if not invitee:
                return {'success': False, 'reason': 'Invitee user not found'}
            
            # Process the invite
            invite.invitee_user_id = invitee_user_id
            invite.status = InviteStatus.ACCEPTED
            invite.accepted_at = datetime.now(timezone.utc)
            
            # Award credits to inviter
            self.credit_service.add_credits(
                user_id=invite.inviter_user_id,
                amount=invite.credits_awarded,
                credit_type=CreditType.EARNED,
                source=CreditSource.INVITE,
                source_reference=f"invite_{invite_code}"
            )
            
            # Award bonus credits to invitee
            self.credit_service.add_credits(
                user_id=invitee_user_id,
                amount=1,  # Bonus credit for joining via invite
                credit_type=CreditType.BONUS,
                source=CreditSource.INVITE,
                source_reference=f"invited_by_{invite_code}"
            )
            
            # Update inviter's successful invites count
            inviter = User.query.get(invite.inviter_user_id)
            if inviter:
                inviter.total_invites_accepted += 1
            
            db.session.commit()
            
            logger.info(f"Processed invite {invite_code}: inviter {invite.inviter_user_id} -> invitee {invitee_user_id}")
            
            return {
                'success': True,
                'credits_awarded': invite.credits_awarded,
                'inviter_id': invite.inviter_user_id
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error processing invite {invite_code}: {e}")
            return {'success': False, 'reason': 'Internal error processing invite'}
    
    def get_user_invites(self, user_id: int, status: InviteStatus = None) -> list:
        """Get invites created by a user"""
        query = Invite.query.filter_by(inviter_user_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(Invite.created_at.desc()).all()
    
    def get_invite_by_code(self, invite_code: str) -> Invite:
        """Get invite by code"""
        return Invite.query.filter_by(invite_code=invite_code).first()
    
    def expire_old_invites(self) -> int:
        """Expire old invites that have passed their expiration date"""
        try:
            expired_count = Invite.query.filter(
                Invite.expires_at < datetime.now(timezone.utc),
                Invite.status == InviteStatus.PENDING
            ).update({'status': InviteStatus.EXPIRED})
            
            db.session.commit()
            logger.info(f"Expired {expired_count} old invites")
            
            return expired_count
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error expiring old invites: {e}")
            return 0
    
    def get_invite_statistics(self) -> dict:
        """Get system-wide invite statistics"""
        try:
            total_invites = Invite.query.count()
            pending_invites = Invite.query.filter_by(status=InviteStatus.PENDING).count()
            accepted_invites = Invite.query.filter_by(status=InviteStatus.ACCEPTED).count()
            expired_invites = Invite.query.filter_by(status=InviteStatus.EXPIRED).count()
            
            # Top inviters
            from sqlalchemy import func
            top_inviters = db.session.query(
                User.telegram_user_id,
                User.first_name,
                User.username,
                func.count(Invite.id).label('invite_count')
            ).join(Invite, User.id == Invite.inviter_user_id).filter(
                Invite.status == InviteStatus.ACCEPTED
            ).group_by(User.id).order_by(func.count(Invite.id).desc()).limit(10).all()
            
            return {
                'total_invites': total_invites,
                'pending_invites': pending_invites,
                'accepted_invites': accepted_invites,
                'expired_invites': expired_invites,
                'acceptance_rate': (accepted_invites / total_invites * 100) if total_invites > 0 else 0,
                'top_inviters': [
                    {
                        'telegram_user_id': inviter.telegram_user_id,
                        'name': inviter.first_name or inviter.username or 'Unknown',
                        'invite_count': inviter.invite_count
                    } for inviter in top_inviters
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting invite statistics: {e}")
            return {}
    
    def validate_invite_code(self, invite_code: str) -> dict:
        """Validate an invite code without processing it"""
        invite = self.get_invite_by_code(invite_code)
        
        if not invite:
            return {'valid': False, 'reason': 'Invalid invite code'}
        
        if invite.status != InviteStatus.PENDING:
            return {'valid': False, 'reason': 'Invite already used or expired'}
        
        if invite.expires_at < datetime.now(timezone.utc):
            return {'valid': False, 'reason': 'Invite has expired'}
        
        return {
            'valid': True,
            'inviter_id': invite.inviter_user_id,
            'credits_awarded': invite.credits_awarded,
            'expires_at': invite.expires_at
        }
    
    def get_user_invite_stats(self, user_id: int) -> dict:
        """Get invite statistics for a specific user"""
        user = User.query.get(user_id)
        if not user:
            return None
        
        invites = self.get_user_invites(user_id)
        pending_invites = [inv for inv in invites if inv.status == InviteStatus.PENDING]
        accepted_invites = [inv for inv in invites if inv.status == InviteStatus.ACCEPTED]
        expired_invites = [inv for inv in invites if inv.status == InviteStatus.EXPIRED]
        
        return {
            'total_sent': len(invites),
            'pending': len(pending_invites),
            'accepted': len(accepted_invites),
            'expired': len(expired_invites),
            'acceptance_rate': (len(accepted_invites) / len(invites) * 100) if invites else 0,
            'credits_earned_from_invites': len(accepted_invites) * 1  # Assuming 1 credit per invite
        }
    
    def cancel_invite(self, invite_code: str, user_id: int) -> bool:
        """Cancel a pending invite (only by the inviter)"""
        try:
            invite = Invite.query.filter_by(
                invite_code=invite_code,
                inviter_user_id=user_id,
                status=InviteStatus.PENDING
            ).first()
            
            if not invite:
                return False
            
            invite.status = InviteStatus.EXPIRED
            db.session.commit()
            
            logger.info(f"Cancelled invite {invite_code} by user {user_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error cancelling invite {invite_code}: {e}")
            return False

