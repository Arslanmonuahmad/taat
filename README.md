# 🤖 Telegram Face Swap Bot

A complete Telegram bot for face swapping using FaceFusion, with credit system, invite rewards, payment integration, and admin panel.

## ✨ Features

### 🎭 Face Swap Capabilities
- **Image Face Swap**: Swap faces between two images
- **Video Face Swap**: Swap face from image to video
- **High Quality**: Powered by FaceFusion (industry-leading face manipulation platform)
- **Fast Processing**: Optimized for quick results

### 💳 Credit System
- **Free Credits**: 1 free credit on registration
- **Invite Rewards**: Earn 1 credit per successful invite
- **Purchase Options**: Telegram Stars (100 stars = 70 credits) or UPI (₹59 = 23 credits)
- **Anti-Glitch**: Robust credit validation and refund system

### 🎁 Invite System
- **Referral Links**: Generate unique invite codes
- **Automatic Rewards**: Credits awarded when friends join
- **Tracking**: Monitor invite success rates

### 💰 Payment Integration
- **Telegram Stars**: Native Telegram payment system
- **UPI**: Indian payment system (GPay, PhonePe, Paytm, etc.)
- **Webhook Verification**: Secure payment processing
- **Transaction History**: Complete payment tracking

### 🛡️ User Guidelines & Safety
- **Legal Compliance**: Clear guidelines against illegal use
- **Consent Requirements**: Emphasis on ethical usage
- **Account Protection**: Suspension/ban system for violations

### 📊 Admin Panel
- **Real-time Dashboard**: Monitor users, credits, transactions
- **User Management**: Suspend, ban, reactivate accounts
- **Credit Management**: Grant credits, view balances
- **System Cleanup**: Expire old data automatically
- **Data Export**: Export system statistics

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Telegram Bot Token (from @BotFather)
- PostgreSQL database (for production)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd telegram_face_swap_bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Setup environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Initialize database**
```bash
python -c "from src.main import app; from src.models.database import db; app.app_context().push(); db.create_all()"
```

5. **Run the bot**
```bash
python src/main.py
```

## 🌐 Deployment

### Vercel Deployment

1. **Install Vercel CLI**
```bash
npm install -g vercel
```

2. **Deploy to Vercel**
```bash
vercel --prod
```

3. **Set Environment Variables**
- Go to Vercel dashboard
- Add all environment variables from `.env.example`
- Set `DATABASE_URL` to your PostgreSQL connection string

4. **Set Telegram Webhook**
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://your-app.vercel.app/webhook/telegram"}'
```

### Alternative Deployment Options

- **Heroku**: Use `Procfile` and set environment variables
- **Railway**: Connect GitHub repo and deploy
- **DigitalOcean**: Use App Platform or Droplets
- **AWS**: Use Elastic Beanstalk or Lambda

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | ✅ |
| `DATABASE_URL` | Database connection string | ✅ |
| `SECRET_KEY` | Flask secret key | ✅ |
| `ADMIN_API_KEY` | Admin panel authentication | ✅ |
| `TELEGRAM_WEBHOOK_URL` | Webhook URL for Telegram | ✅ |
| `WEBHOOK_SECRET_TOKEN` | Webhook security token | ⚠️ |
| `MAX_FILE_SIZE_MB` | Max upload size (default: 50) | ❌ |

### Database Setup

**Development (SQLite)**
```python
DATABASE_URL=sqlite:///database/app.db
```

**Production (PostgreSQL)**
```python
DATABASE_URL=postgresql://username:password@host:port/database
```

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start bot and show guidelines |
| `/help` | Show help message |
| `/credits` | Check credit balance |
| `/invite` | Generate invite link |
| `/buy` | Purchase credits |
| `/stats` | View user statistics |
| `/history` | View transaction history |

## 📱 Usage Flow

1. **Registration**: User starts bot and agrees to guidelines
2. **Face Upload**: User sends source image (face to swap)
3. **Target Upload**: User sends target image or video
4. **Processing**: Bot processes face swap using FaceFusion
5. **Result**: Bot sends swapped image/video back to user

## 🛠️ Admin Panel

Access the admin panel at `/admin/` with the following features:

- **Dashboard**: Real-time statistics and system overview
- **User Management**: View, suspend, ban, reactivate users
- **Credit Management**: Grant credits, view balances
- **Transaction Monitoring**: Payment history and status
- **System Maintenance**: Cleanup expired data
- **Data Export**: Export system reports

### Admin Authentication
```bash
Authorization: Bearer <ADMIN_API_KEY>
```

## 🔒 Security Features

- **Input Validation**: File type and size validation
- **Credit Protection**: Anti-glitch credit system
- **Payment Verification**: Webhook signature validation
- **User Guidelines**: Legal compliance enforcement
- **Rate Limiting**: Prevent abuse (implement as needed)

## 📊 API Endpoints

### Public Endpoints
- `GET /health` - Health check
- `POST /webhook/telegram` - Telegram webhook
- `POST /webhook/payment/telegram-stars` - Telegram Stars payment
- `POST /webhook/payment/upi` - UPI payment

### Admin Endpoints
- `GET /admin/` - Admin dashboard
- `GET /admin/api/stats` - System statistics
- `GET /admin/api/users` - User list
- `POST /admin/api/grant-credits` - Grant credits
- `POST /admin/api/suspend-user` - Suspend user

## 🧪 Testing

### Local Testing
```bash
# Run the Flask app
python src/main.py

# Test webhook endpoints
curl -X POST http://localhost:5000/health

# Test admin panel
open http://localhost:5000/admin/
```

### Bot Testing
1. Start the bot locally
2. Use ngrok for webhook testing:
```bash
ngrok http 5000
# Set webhook to ngrok URL
```

## 📁 Project Structure

```
telegram_face_swap_bot/
├── src/
│   ├── main.py                 # Flask application entry point
│   ├── models/
│   │   └── database.py         # Database models
│   ├── services/
│   │   ├── telegram_bot.py     # Telegram bot service
│   │   ├── user_service.py     # User management
│   │   ├── credit_service.py   # Credit system
│   │   ├── invite_service.py   # Invite system
│   │   ├── face_swap_service.py # Face swap processing
│   │   ├── file_handler.py     # File management
│   │   └── payment_service.py  # Payment processing
│   └── routes/
│       ├── admin.py            # Admin panel routes
│       ├── user.py             # User API routes
│       └── webhook.py          # Webhook routes
├── external/
│   └── facefusion/             # FaceFusion integration
├── uploads/                    # User uploaded files
├── outputs/                    # Generated face swaps
├── temp/                       # Temporary files
├── database/                   # SQLite database (development)
├── requirements.txt            # Python dependencies
├── vercel.json                 # Vercel configuration
├── runtime.txt                 # Python version
├── .env.example               # Environment variables template
└── README.md                  # This file
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Legal Notice

This software is designed for legitimate, consensual, and legal use only. Users are responsible for:

- Obtaining proper consent for all images/videos used
- Complying with local laws and regulations
- Using the service ethically and responsibly
- Not creating content for harassment or deception

The developers are not responsible for misuse of this software.

## 🆘 Support

- **Issues**: Create a GitHub issue
- **Documentation**: Check this README
- **Admin Panel**: Use `/admin/` for system management

## 🔄 Updates

- **v1.0.0**: Initial release with FaceFusion integration
- **Features**: Face swap, credit system, payments, admin panel
- **Deployment**: Vercel-ready with comprehensive documentation

---

**Made with ❤️ for the AI community**

