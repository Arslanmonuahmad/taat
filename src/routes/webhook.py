from flask import Blueprint, request, jsonify
from telegram import Update
import json
import logging
import os

webhook_bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)

@webhook_bp.route('/telegram', methods=['POST'])
def telegram_webhook():
    """Handle Telegram webhook updates"""
    try:
        # Verify webhook secret token if configured
        secret_token = os.getenv('WEBHOOK_SECRET_TOKEN')
        if secret_token:
            received_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
            if received_token != secret_token:
                logger.warning("Invalid webhook secret token")
                return jsonify({'error': 'Unauthorized'}), 401
        
        # Get the update data
        update_data = request.get_json()
        
        if not update_data:
            logger.warning("No update data received")
            return jsonify({'error': 'No data'}), 400
        
        # Create Telegram Update object
        update = Update.de_json(update_data, None)
        
        if not update:
            logger.warning("Invalid update format")
            return jsonify({'error': 'Invalid update'}), 400
        
        # Get the bot service from the app context
        from src.main import telegram_bot
        
        if not telegram_bot:
            logger.error("Telegram bot not initialized")
            return jsonify({'error': 'Bot not configured'}), 500
        
        # Process the update
        # Note: In production, this should be handled asynchronously
        # For now, we'll log the update and return success
        logger.info(f"Received update: {update.update_id}")
        
        # TODO: Process the update with the bot
        # This would typically involve calling the bot's update handler
        # telegram_bot.process_update(update)
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'error': 'Internal error'}), 500

@webhook_bp.route('/telegram/set', methods=['POST'])
def set_webhook():
    """Set Telegram webhook URL"""
    try:
        data = request.get_json()
        webhook_url = data.get('webhook_url')
        
        if not webhook_url:
            return jsonify({'error': 'webhook_url is required'}), 400
        
        # Get the bot service
        from src.main import telegram_bot
        
        if not telegram_bot:
            return jsonify({'error': 'Bot not configured'}), 500
        
        # Set the webhook
        # Note: This is a simplified implementation
        # In production, you'd use the Telegram Bot API to set the webhook
        
        return jsonify({
            'status': 'success',
            'message': f'Webhook set to {webhook_url}'
        })
        
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({'error': str(e)}), 500

@webhook_bp.route('/telegram/info', methods=['GET'])
def webhook_info():
    """Get webhook information"""
    try:
        # Get the bot service
        from src.main import telegram_bot
        
        if not telegram_bot:
            return jsonify({'error': 'Bot not configured'}), 500
        
        # Return webhook status
        return jsonify({
            'webhook_configured': bool(os.getenv('TELEGRAM_WEBHOOK_URL')),
            'webhook_url': os.getenv('TELEGRAM_WEBHOOK_URL'),
            'secret_token_configured': bool(os.getenv('WEBHOOK_SECRET_TOKEN'))
        })
        
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return jsonify({'error': str(e)}), 500

@webhook_bp.route('/payment/telegram-stars', methods=['POST'])
def telegram_stars_webhook():
    """Handle Telegram Stars payment webhook"""
    try:
        # Verify the payment webhook
        update_data = request.get_json()
        
        if not update_data:
            return jsonify({'error': 'No data'}), 400
        
        # Process Telegram Stars payment
        # This would integrate with Telegram's payment system
        logger.info(f"Received Telegram Stars payment webhook: {update_data}")
        
        # TODO: Implement payment processing
        # 1. Verify payment authenticity
        # 2. Extract payment details (user_id, amount, etc.)
        # 3. Add credits to user account
        # 4. Update transaction record
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Error processing Telegram Stars payment: {e}")
        return jsonify({'error': 'Internal error'}), 500

@webhook_bp.route('/payment/upi', methods=['POST'])
def upi_payment_webhook():
    """Handle UPI payment webhook"""
    try:
        # Verify the payment webhook
        update_data = request.get_json()
        
        if not update_data:
            return jsonify({'error': 'No data'}), 400
        
        # Process UPI payment
        # This would integrate with a UPI payment gateway
        logger.info(f"Received UPI payment webhook: {update_data}")
        
        # TODO: Implement payment processing
        # 1. Verify payment authenticity with payment gateway
        # 2. Extract payment details (user_id, amount, transaction_id, etc.)
        # 3. Add credits to user account
        # 4. Update transaction record
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Error processing UPI payment: {e}")
        return jsonify({'error': 'Internal error'}), 500

@webhook_bp.route('/health', methods=['GET'])
def webhook_health():
    """Webhook health check"""
    return jsonify({
        'status': 'healthy',
        'endpoints': {
            'telegram': '/webhook/telegram',
            'telegram_stars': '/webhook/payment/telegram-stars',
            'upi': '/webhook/payment/upi'
        }
    })

