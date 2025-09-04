import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
from src.models.database import db, User, Credit, CreditType, CreditSource, UserStatus
from src.services.user_service import UserService
from src.services.credit_service import CreditService
from src.services.invite_service import InviteService
from src.services.face_swap_service import FaceSwapService
from src.services.file_handler import FileHandler
from src.services.payment_service import PaymentService
from src.models.database import JobType
import uuid
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramBotService:
    """Telegram bot service for face swap bot"""
    
    def __init__(self, token: str, app_context):
        self.token = token
        self.app_context = app_context
        self.application = None
        
        # Initialize services
        self.user_service = UserService()
        self.credit_service = CreditService()
        self.invite_service = InviteService()
        self.face_swap_service = FaceSwapService()
        self.file_handler = FileHandler()
        self.payment_service = PaymentService()
        
        # User state tracking
        self.user_states = {}
        
        # Guidelines text
        self.guidelines_text = """
🤖 **Face Swap Bot - User Guidelines**

⚠️ **IMPORTANT LEGAL NOTICE:**

**WE DO NOT PROMOTE OR SUPPORT:**
• Illegal activities of any kind
• Non-consensual face swapping
• Creating deepfakes for harassment
• Impersonation for fraud or deception
• Adult content or inappropriate material
• Violation of privacy rights
• Any form of cyberbullying

**ACCEPTABLE USE:**
• Entertainment and creative content
• Personal projects with consent
• Educational purposes
• Art and creative expression

**YOUR RESPONSIBILITIES:**
• Only use images/videos you own or have permission to use
• Respect others' privacy and consent
• Follow local laws and regulations
• Use the service ethically and responsibly

**CONSEQUENCES:**
• Violation of these guidelines will result in immediate account suspension
• We reserve the right to ban users who misuse the service
• Legal action may be taken for serious violations

By continuing, you agree to these terms and confirm you will use this service responsibly and legally.

Do you agree to these guidelines?
        """
    
    def setup_handlers(self):
        """Setup bot command and message handlers"""
        if not self.application:
            return
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("credits", self.credits_command))
        self.application.add_handler(CommandHandler("invite", self.invite_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("buy", self.buy_command))
        self.application.add_handler(CommandHandler("history", self.history_command))
        
        # Callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.VIDEO, self.handle_video))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            telegram_user = update.effective_user
            
            # Check for invite code in the command
            invite_code = None
            if context.args:
                invite_code = context.args[0]
            
            with self.app_context():
                # Get or create user
                user = self.user_service.get_or_create_user(
                    telegram_user_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                    language_code=telegram_user.language_code
                )
                
                # Check if user has agreed to terms
                if not user.agreed_to_terms:
                    # Show guidelines
                    keyboard = [
                        [InlineKeyboardButton("✅ I Agree", callback_data="agree_terms")],
                        [InlineKeyboardButton("❌ I Disagree", callback_data="disagree_terms")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        self.guidelines_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                # Process invite code if provided
                if invite_code and not hasattr(user, '_invite_processed'):
                    invite_result = self.invite_service.process_invite(invite_code, user.id)
                    if invite_result['success']:
                        await update.message.reply_text(
                            f"🎉 Welcome! You've been invited and received bonus credits!\n"
                            f"💳 Credits earned: {invite_result['credits_awarded']}"
                        )
                    user._invite_processed = True
                
                # Show main menu
                await self.show_main_menu(update, user)
                
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    
    async def show_main_menu(self, update: Update, user: User):
        """Show the main menu to the user"""
        credits = self.credit_service.get_active_credit_balance(user.id)
        
        welcome_text = f"""
🤖 **Welcome to Face Swap Bot!**

👋 Hello {user.first_name or 'User'}!
💳 Your Credits: **{credits}**

**How to use:**
1. Send me a photo of a face (source)
2. Send me a target image or video
3. I'll swap the faces for you!

**Commands:**
/credits - Check your credit balance
/invite - Get invite link to earn credits
/buy - Purchase more credits
/stats - View your statistics
/help - Show this help message

Ready to start? Send me your first image! 📸
        """
        
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()
        
        try:
            with self.app_context():
                telegram_user = update.effective_user
                user = self.user_service.get_user_by_telegram_id(telegram_user.id)
                
                if not user:
                    await query.edit_message_text("❌ User not found. Please use /start")
                    return
                
                if query.data == "agree_terms":
                    # User agreed to terms
                    self.user_service.agree_to_terms(user.id)
                    await query.edit_message_text(
                        "✅ Thank you for agreeing to our guidelines!\n\n"
                        "🎉 You've received 1 free credit to get started!\n\n"
                        "Use /help to see available commands."
                    )
                    await self.show_main_menu(update, user)
                
                elif query.data == "disagree_terms":
                    await query.edit_message_text(
                        "❌ You must agree to our guidelines to use this service.\n\n"
                        "Use /start to try again when you're ready to agree to our terms."
                    )
                
                elif query.data.startswith("buy_"):
                    payment_method = query.data.replace("buy_", "")
                    await self.handle_payment_selection(query, user, payment_method)
                
        except Exception as e:
            logger.error(f"Error in button callback: {e}")
            await query.edit_message_text("❌ An error occurred. Please try again.")
    
    async def handle_payment_selection(self, query, user: User, payment_method: str):
        """Handle payment method selection"""
        try:
            invoice = self.payment_service.create_payment_invoice(user.id, payment_method)
            
            if not invoice['success']:
                await query.edit_message_text(f"❌ Error: {invoice['error']}")
                return
            
            if payment_method == "telegram_stars":
                text = f"""
💫 **Telegram Stars Payment**

💰 Amount: {invoice['amount']} Stars
💳 Credits: {invoice['credits']}
📝 Description: {invoice['description']}

To complete payment:
1. Use Telegram's built-in payment system
2. Pay {invoice['amount']} Stars
3. Credits will be added automatically

Transaction ID: {invoice['transaction_id']}
                """
            else:  # UPI
                text = f"""
💳 **UPI Payment**

💰 Amount: ₹{invoice['amount']}
💳 Credits: {invoice['credits']}
📝 Description: {invoice['description']}

To complete payment:
1. Use any UPI app (GPay, PhonePe, Paytm, etc.)
2. Pay ₹{invoice['amount']} to our UPI ID
3. Send payment screenshot here
4. Credits will be added after verification

Transaction ID: {invoice['transaction_id']}
                """
            
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Error handling payment selection: {e}")
            await query.edit_message_text("❌ Payment error. Please try again.")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads"""
        try:
            with self.app_context():
                telegram_user = update.effective_user
                user = self.user_service.get_user_by_telegram_id(telegram_user.id)
                
                if not user or not user.agreed_to_terms:
                    await update.message.reply_text("❌ Please use /start first and agree to our guidelines.")
                    return
                
                # Download the photo
                photo = update.message.photo[-1]  # Get highest resolution
                file = await photo.get_file()
                
                download_result = await self.file_handler.download_telegram_file(file, 'image')
                
                if not download_result['success']:
                    await update.message.reply_text(f"❌ Error downloading image: {download_result['error']}")
                    return
                
                # Validate the image
                validation = self.file_handler.validate_image_file(download_result['local_path'])
                if not validation['valid']:
                    self.file_handler.cleanup_file(download_result['local_path'])
                    await update.message.reply_text(f"❌ Invalid image: {validation['error']}")
                    return
                
                # Store user state
                user_state = self.user_states.get(user.id, {})
                
                if 'source_image' not in user_state:
                    # This is the source image (face to swap)
                    user_state['source_image'] = download_result['local_path']
                    self.user_states[user.id] = user_state
                    
                    await update.message.reply_text(
                        "✅ Source image received! Now send me the target image or video where you want to swap the face."
                    )
                else:
                    # This is the target image
                    target_path = download_result['local_path']
                    source_path = user_state['source_image']
                    
                    # Check credits
                    credits = self.credit_service.get_active_credit_balance(user.id)
                    if credits < 1:
                        await update.message.reply_text(
                            "❌ Insufficient credits! You need at least 1 credit for face swapping.\n"
                            "Use /buy to purchase more credits."
                        )
                        return
                    
                    # Create face swap job
                    job = self.face_swap_service.create_face_swap_job(
                        user_id=user.id,
                        job_type=JobType.IMAGE,
                        source_file_path=source_path,
                        target_file_path=target_path,
                        telegram_message_id=update.message.message_id
                    )
                    
                    await update.message.reply_text(
                        f"🔄 Processing your face swap...\n"
                        f"Job ID: {job.id}\n"
                        f"This may take a few minutes. I'll send you the result when it's ready!"
                    )
                    
                    # Process the job (in a real deployment, this would be async)
                    result = self.face_swap_service.process_face_swap_job(job.id)
                    
                    if result['success']:
                        # Send the result
                        with open(result['output_path'], 'rb') as photo_file:
                            await update.message.reply_photo(
                                photo=photo_file,
                                caption=f"✅ Face swap completed!\nJob ID: {job.id}"
                            )
                    else:
                        await update.message.reply_text(f"❌ Face swap failed: {result['error']}")
                    
                    # Clear user state
                    self.user_states.pop(user.id, None)
                    
                    # Cleanup files
                    self.file_handler.cleanup_file(source_path)
                    self.file_handler.cleanup_file(target_path)
                
        except Exception as e:
            logger.error(f"Error handling photo: {e}")
            await update.message.reply_text("❌ An error occurred processing your image.")
    
    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video uploads"""
        try:
            with self.app_context():
                telegram_user = update.effective_user
                user = self.user_service.get_user_by_telegram_id(telegram_user.id)
                
                if not user or not user.agreed_to_terms:
                    await update.message.reply_text("❌ Please use /start first and agree to our guidelines.")
                    return
                
                user_state = self.user_states.get(user.id, {})
                
                if 'source_image' not in user_state:
                    await update.message.reply_text(
                        "❌ Please send a source image (face) first, then the target video."
                    )
                    return
                
                # Download the video
                video = update.message.video
                file = await video.get_file()
                
                download_result = await self.file_handler.download_telegram_file(file, 'video')
                
                if not download_result['success']:
                    await update.message.reply_text(f"❌ Error downloading video: {download_result['error']}")
                    return
                
                # Validate the video
                validation = self.file_handler.validate_video_file(download_result['local_path'])
                if not validation['valid']:
                    self.file_handler.cleanup_file(download_result['local_path'])
                    await update.message.reply_text(f"❌ Invalid video: {validation['error']}")
                    return
                
                # Check credits
                credits = self.credit_service.get_active_credit_balance(user.id)
                if credits < 1:
                    await update.message.reply_text(
                        "❌ Insufficient credits! You need at least 1 credit for face swapping.\n"
                        "Use /buy to purchase more credits."
                    )
                    return
                
                # Create face swap job
                source_path = user_state['source_image']
                target_path = download_result['local_path']
                
                job = self.face_swap_service.create_face_swap_job(
                    user_id=user.id,
                    job_type=JobType.VIDEO,
                    source_file_path=source_path,
                    target_file_path=target_path,
                    telegram_message_id=update.message.message_id
                )
                
                await update.message.reply_text(
                    f"🔄 Processing your video face swap...\n"
                    f"Job ID: {job.id}\n"
                    f"This may take several minutes. I'll send you the result when it's ready!"
                )
                
                # Process the job
                result = self.face_swap_service.process_face_swap_job(job.id)
                
                if result['success']:
                    # Send the result
                    with open(result['output_path'], 'rb') as video_file:
                        await update.message.reply_video(
                            video=video_file,
                            caption=f"✅ Video face swap completed!\nJob ID: {job.id}"
                        )
                else:
                    await update.message.reply_text(f"❌ Video face swap failed: {result['error']}")
                
                # Clear user state
                self.user_states.pop(user.id, None)
                
                # Cleanup files
                self.file_handler.cleanup_file(source_path)
                self.file_handler.cleanup_file(target_path)
                
        except Exception as e:
            logger.error(f"Error handling video: {e}")
            await update.message.reply_text("❌ An error occurred processing your video.")
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        text = update.message.text.strip()
        
        # Check if it's an invite code
        if len(text) == 8 and text.isupper():
            with self.app_context():
                telegram_user = update.effective_user
                user = self.user_service.get_user_by_telegram_id(telegram_user.id)
                
                if user:
                    invite_result = self.invite_service.process_invite(text, user.id)
                    if invite_result['success']:
                        await update.message.reply_text(
                            f"🎉 Invite code accepted!\n"
                            f"💳 You received {invite_result['credits_awarded']} credits!"
                        )
                    else:
                        await update.message.reply_text(f"❌ Invalid invite code: {invite_result['reason']}")
                else:
                    await update.message.reply_text("❌ Please use /start first.")
        else:
            await update.message.reply_text(
                "🤖 I understand images and videos for face swapping!\n\n"
                "Send me:\n"
                "1. A photo with the face you want to use\n"
                "2. A target image or video\n\n"
                "Use /help for more commands."
            )
    
    async def credits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /credits command"""
        try:
            with self.app_context():
                telegram_user = update.effective_user
                user = self.user_service.get_user_by_telegram_id(telegram_user.id)
                
                if not user:
                    await update.message.reply_text("❌ Please use /start first.")
                    return
                
                credits = self.credit_service.get_active_credit_balance(user.id)
                credit_history = self.credit_service.get_credit_history(user.id, limit=5)
                
                text = f"💳 **Your Credits: {credits}**\n\n"
                
                if credit_history:
                    text += "📊 **Recent Activity:**\n"
                    for credit in credit_history:
                        status = "✅" if credit.is_active else "❌"
                        text += f"{status} {credit.amount} credits - {credit.source.value}\n"
                
                text += "\n💰 Use /buy to purchase more credits"
                
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                
        except Exception as e:
            logger.error(f"Error in credits command: {e}")
            await update.message.reply_text("❌ An error occurred.")
    
    async def invite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /invite command"""
        try:
            with self.app_context():
                telegram_user = update.effective_user
                user = self.user_service.get_user_by_telegram_id(telegram_user.id)
                
                if not user:
                    await update.message.reply_text("❌ Please use /start first.")
                    return
                
                # Create invite code
                invite_code = self.invite_service.create_invite(user.id)
                bot_username = context.bot.username
                
                invite_link = f"https://t.me/{bot_username}?start={invite_code}"
                
                text = f"""
🎁 **Your Invite Link**

📋 Invite Code: `{invite_code}`
🔗 Invite Link: {invite_link}

💰 **Earn 1 credit for each friend who joins!**

Share this link with friends to earn credits when they sign up and agree to our guidelines.
                """
                
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                
        except Exception as e:
            logger.error(f"Error in invite command: {e}")
            await update.message.reply_text("❌ An error occurred.")
    
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /buy command"""
        try:
            with self.app_context():
                telegram_user = update.effective_user
                user = self.user_service.get_user_by_telegram_id(telegram_user.id)
                
                if not user:
                    await update.message.reply_text("❌ Please use /start first.")
                    return
                
                payment_options = self.payment_service.get_payment_options(user.id)
                
                text = "💰 **Purchase Credits**\n\nChoose your payment method:\n\n"
                
                keyboard = []
                
                for method, option in payment_options.items():
                    text += f"💳 **{method.replace('_', ' ').title()}**\n"
                    text += f"   {option['description']}\n\n"
                    
                    keyboard.append([InlineKeyboardButton(
                        f"{option['description']}", 
                        callback_data=f"buy_{method}"
                    )])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    text, 
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                
        except Exception as e:
            logger.error(f"Error in buy command: {e}")
            await update.message.reply_text("❌ An error occurred.")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            with self.app_context():
                telegram_user = update.effective_user
                user = self.user_service.get_user_by_telegram_id(telegram_user.id)
                
                if not user:
                    await update.message.reply_text("❌ Please use /start first.")
                    return
                
                stats = self.user_service.get_user_stats(user.id)
                invite_stats = self.invite_service.get_user_invite_stats(user.id)
                
                text = f"""
📊 **Your Statistics**

👤 **Account Info:**
• Registration: {stats['registration_date'].strftime('%Y-%m-%d')}
• Status: {stats['status']}

💳 **Credits:**
• Current Balance: {stats['current_credits']}
• Total Earned: {stats['total_credits_earned']}
• Total Spent: {stats['total_credits_spent']}

🎁 **Invites:**
• Sent: {invite_stats['total_sent']}
• Accepted: {invite_stats['accepted']}
• Success Rate: {invite_stats['acceptance_rate']:.1f}%

🔄 **Face Swaps:**
• Total Jobs: {stats['total_face_swap_jobs']}
• Completed: {stats['completed_jobs']}
                """
                
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text("❌ An error occurred.")
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command"""
        try:
            with self.app_context():
                telegram_user = update.effective_user
                user = self.user_service.get_user_by_telegram_id(telegram_user.id)
                
                if not user:
                    await update.message.reply_text("❌ Please use /start first.")
                    return
                
                transactions = self.payment_service.get_transaction_history(user.id)
                
                if not transactions:
                    await update.message.reply_text("📝 No transaction history found.")
                    return
                
                text = "📝 **Transaction History**\n\n"
                
                for tx in transactions:
                    status_emoji = "✅" if tx['status'] == 'completed' else "❌" if tx['status'] == 'failed' else "⏳"
                    text += f"{status_emoji} **{tx['type'].title()}**\n"
                    text += f"   Amount: {tx['amount']} {tx['currency']}\n"
                    text += f"   Credits: {tx['credits']}\n"
                    text += f"   Date: {tx['created_at'][:10]}\n\n"
                
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                
        except Exception as e:
            logger.error(f"Error in history command: {e}")
            await update.message.reply_text("❌ An error occurred.")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🤖 **Face Swap Bot Help**

**How to use:**
1. Send a photo with the face you want to use (source)
2. Send a target image or video
3. I'll swap the faces and send you the result!

**Commands:**
/start - Start the bot and see main menu
/help - Show this help message
/credits - Check your credit balance
/invite - Get invite link to earn credits
/buy - Purchase more credits
/stats - View your statistics
/history - View transaction history

**Credit System:**
• 1 credit = 1 face swap (image or video)
• Get 1 free credit when you join
• Earn credits by inviting friends
• Purchase credits with Telegram Stars or UPI

**Supported Files:**
• Images: JPG, PNG, WebP
• Videos: MP4, MOV, AVI, MKV
• Max file size: 50MB

**Need help?** Contact support or check our guidelines with /start
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    def run_polling(self):
        """Run the bot in polling mode"""
        try:
            self.application = Application.builder().token(self.token).build()
            self.setup_handlers()
            
            logger.info("Starting Telegram bot in polling mode...")
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
    
    def run_webhook(self, webhook_url: str, port: int = 8443):
        """Run the bot in webhook mode"""
        try:
            self.application = Application.builder().token(self.token).build()
            self.setup_handlers()
            
            logger.info(f"Starting Telegram bot in webhook mode on port {port}")
            self.application.run_webhook(
                listen="0.0.0.0",
                port=port,
                webhook_url=webhook_url
            )
            
        except Exception as e:
            logger.error(f"Error running bot webhook: {e}")

