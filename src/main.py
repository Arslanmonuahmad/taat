import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify
from src.models.database import db
from src.routes.user import user_bp
from src.routes.admin import admin_bp
from src.routes.webhook import webhook_bp
from src.services.telegram_bot import TelegramBotService
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Register blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(webhook_bp, url_prefix='/webhook')

# Initialize Telegram bot
telegram_bot = None
if os.getenv('TELEGRAM_BOT_TOKEN'):
    telegram_bot = TelegramBotService(
        token=os.getenv('TELEGRAM_BOT_TOKEN'),
        app_context=app.app_context
    )
    logger.info("Telegram bot service initialized")
else:
    logger.warning("TELEGRAM_BOT_TOKEN not found in environment variables")

# Create database tables
with app.app_context():
    try:
        # Ensure database directory exists
        import os
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        db.create_all()
        logger.info("Database tables created")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        # Continue without database for testing

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Serve static files and handle SPA routing"""
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'telegram_bot_configured': telegram_bot is not None,
        'database_connected': True
    })

@app.route('/api/bot/info')
def bot_info():
    """Get bot information"""
    if not telegram_bot:
        return jsonify({'error': 'Bot not configured'}), 500
    
    return jsonify({
        'bot_configured': True,
        'webhook_configured': bool(os.getenv('TELEGRAM_WEBHOOK_URL'))
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Development mode - run with polling
    if os.getenv('FLASK_ENV') == 'development' and telegram_bot:
        import threading
        
        def run_bot():
            logger.info("Starting Telegram bot in polling mode")
            telegram_bot.run_polling()
        
        # Start bot in a separate thread
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        logger.info("Bot thread started")
    
    # Start Flask app
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=os.getenv('DEBUG', 'False').lower() == 'true')

