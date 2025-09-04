from flask import Blueprint, request, jsonify, render_template_string
from src.models.database import db, User, Credit, Transaction, FaceSwapJob, Invite, AdminUser
from src.services.user_service import UserService
from src.services.credit_service import CreditService
from src.services.invite_service import InviteService
from functools import wraps
import os

admin_bp = Blueprint('admin', __name__)

# Simple authentication decorator (in production, use proper JWT or session management)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Simple authentication check - in production, implement proper auth
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f"Bearer {os.getenv('ADMIN_API_KEY', 'admin_secret')}":
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

user_service = UserService()
credit_service = CreditService()
invite_service = InviteService()

@admin_bp.route('/')
def admin_dashboard():
    """Admin dashboard HTML page"""
    dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Face Swap Bot - Admin Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-number { font-size: 2em; font-weight: bold; color: #3498db; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        .section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .section h2 { margin-top: 0; color: #2c3e50; }
        .btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
        .btn:hover { background: #2980b9; }
        .btn-danger { background: #e74c3c; }
        .btn-danger:hover { background: #c0392b; }
        .table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        .table th { background-color: #f8f9fa; }
        .status-active { color: #27ae60; font-weight: bold; }
        .status-suspended { color: #f39c12; font-weight: bold; }
        .status-banned { color: #e74c3c; font-weight: bold; }
        .loading { text-align: center; padding: 20px; color: #7f8c8d; }
        .error { color: #e74c3c; padding: 10px; background: #fdf2f2; border-radius: 4px; margin: 10px 0; }
        .success { color: #27ae60; padding: 10px; background: #f0f9f0; border-radius: 4px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Telegram Face Swap Bot - Admin Dashboard</h1>
            <p>Monitor and manage your bot's operations</p>
        </div>

        <div class="stats-grid" id="statsGrid">
            <div class="loading">Loading statistics...</div>
        </div>

        <div class="section">
            <h2>📊 System Overview</h2>
            <button class="btn" onclick="refreshStats()">🔄 Refresh Stats</button>
            <button class="btn" onclick="exportData()">📥 Export Data</button>
            <button class="btn btn-danger" onclick="cleanupExpired()">🧹 Cleanup Expired</button>
        </div>

        <div class="section">
            <h2>👥 Recent Users</h2>
            <div id="recentUsers">
                <div class="loading">Loading users...</div>
            </div>
        </div>

        <div class="section">
            <h2>💳 Recent Transactions</h2>
            <div id="recentTransactions">
                <div class="loading">Loading transactions...</div>
            </div>
        </div>

        <div class="section">
            <h2>🔧 Admin Actions</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                <div>
                    <h3>Grant Credits</h3>
                    <input type="number" id="grantUserId" placeholder="User ID" style="width: 100%; padding: 8px; margin: 5px 0;">
                    <input type="number" id="grantAmount" placeholder="Credit Amount" style="width: 100%; padding: 8px; margin: 5px 0;">
                    <input type="text" id="grantReason" placeholder="Reason" style="width: 100%; padding: 8px; margin: 5px 0;">
                    <button class="btn" onclick="grantCredits()">Grant Credits</button>
                </div>
                <div>
                    <h3>User Management</h3>
                    <input type="number" id="manageUserId" placeholder="User ID" style="width: 100%; padding: 8px; margin: 5px 0;">
                    <button class="btn" onclick="suspendUser()">Suspend User</button>
                    <button class="btn" onclick="banUser()">Ban User</button>
                    <button class="btn" onclick="reactivateUser()">Reactivate User</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '/admin/api';
        const AUTH_TOKEN = 'Bearer admin_secret'; // In production, implement proper auth

        async function apiCall(endpoint, method = 'GET', data = null) {
            try {
                const options = {
                    method,
                    headers: {
                        'Authorization': AUTH_TOKEN,
                        'Content-Type': 'application/json'
                    }
                };
                
                if (data) {
                    options.body = JSON.stringify(data);
                }
                
                const response = await fetch(API_BASE + endpoint, options);
                const result = await response.json();
                
                if (!response.ok) {
                    throw new Error(result.error || 'API call failed');
                }
                
                return result;
            } catch (error) {
                console.error('API call error:', error);
                showError('Error: ' + error.message);
                throw error;
            }
        }

        function showError(message) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.textContent = message;
            document.body.insertBefore(errorDiv, document.body.firstChild);
            setTimeout(() => errorDiv.remove(), 5000);
        }

        function showSuccess(message) {
            const successDiv = document.createElement('div');
            successDiv.className = 'success';
            successDiv.textContent = message;
            document.body.insertBefore(successDiv, document.body.firstChild);
            setTimeout(() => successDiv.remove(), 3000);
        }

        async function loadStats() {
            try {
                const stats = await apiCall('/stats');
                
                const statsHtml = `
                    <div class="stat-card">
                        <div class="stat-number">${stats.users.total}</div>
                        <div class="stat-label">Total Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${stats.users.active}</div>
                        <div class="stat-label">Active Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${stats.credits.total_issued}</div>
                        <div class="stat-label">Credits Issued</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${stats.credits.total_active}</div>
                        <div class="stat-label">Active Credits</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${stats.invites.total_invites}</div>
                        <div class="stat-label">Total Invites</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${stats.invites.accepted_invites}</div>
                        <div class="stat-label">Accepted Invites</div>
                    </div>
                `;
                
                document.getElementById('statsGrid').innerHTML = statsHtml;
            } catch (error) {
                document.getElementById('statsGrid').innerHTML = '<div class="error">Failed to load statistics</div>';
            }
        }

        async function loadRecentUsers() {
            try {
                const users = await apiCall('/users?limit=10');
                
                let usersHtml = `
                    <table class="table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Name</th>
                                <th>Username</th>
                                <th>Status</th>
                                <th>Credits</th>
                                <th>Registered</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                users.forEach(user => {
                    usersHtml += `
                        <tr>
                            <td>${user.telegram_user_id}</td>
                            <td>${user.first_name || 'N/A'}</td>
                            <td>@${user.username || 'N/A'}</td>
                            <td><span class="status-${user.status}">${user.status}</span></td>
                            <td>${user.current_credits}</td>
                            <td>${new Date(user.registration_date).toLocaleDateString()}</td>
                        </tr>
                    `;
                });
                
                usersHtml += '</tbody></table>';
                document.getElementById('recentUsers').innerHTML = usersHtml;
            } catch (error) {
                document.getElementById('recentUsers').innerHTML = '<div class="error">Failed to load users</div>';
            }
        }

        async function loadRecentTransactions() {
            try {
                const transactions = await apiCall('/transactions?limit=10');
                
                let transactionsHtml = `
                    <table class="table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>User</th>
                                <th>Type</th>
                                <th>Amount</th>
                                <th>Credits</th>
                                <th>Status</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                transactions.forEach(tx => {
                    transactionsHtml += `
                        <tr>
                            <td>${tx.id}</td>
                            <td>${tx.user_id}</td>
                            <td>${tx.transaction_type}</td>
                            <td>${tx.amount_local} ${tx.currency_code}</td>
                            <td>${tx.credits_purchased}</td>
                            <td>${tx.status}</td>
                            <td>${new Date(tx.created_at).toLocaleDateString()}</td>
                        </tr>
                    `;
                });
                
                transactionsHtml += '</tbody></table>';
                document.getElementById('recentTransactions').innerHTML = transactionsHtml;
            } catch (error) {
                document.getElementById('recentTransactions').innerHTML = '<div class="error">Failed to load transactions</div>';
            }
        }

        async function grantCredits() {
            const userId = document.getElementById('grantUserId').value;
            const amount = document.getElementById('grantAmount').value;
            const reason = document.getElementById('grantReason').value;
            
            if (!userId || !amount) {
                showError('Please fill in User ID and Amount');
                return;
            }
            
            try {
                await apiCall('/grant-credits', 'POST', {
                    user_id: parseInt(userId),
                    amount: parseInt(amount),
                    reason: reason
                });
                
                showSuccess(`Granted ${amount} credits to user ${userId}`);
                document.getElementById('grantUserId').value = '';
                document.getElementById('grantAmount').value = '';
                document.getElementById('grantReason').value = '';
                refreshStats();
            } catch (error) {
                // Error already shown by apiCall
            }
        }

        async function suspendUser() {
            const userId = document.getElementById('manageUserId').value;
            if (!userId) {
                showError('Please enter User ID');
                return;
            }
            
            try {
                await apiCall('/suspend-user', 'POST', { user_id: parseInt(userId) });
                showSuccess(`User ${userId} suspended`);
                loadRecentUsers();
            } catch (error) {
                // Error already shown by apiCall
            }
        }

        async function banUser() {
            const userId = document.getElementById('manageUserId').value;
            if (!userId) {
                showError('Please enter User ID');
                return;
            }
            
            try {
                await apiCall('/ban-user', 'POST', { user_id: parseInt(userId) });
                showSuccess(`User ${userId} banned`);
                loadRecentUsers();
            } catch (error) {
                // Error already shown by apiCall
            }
        }

        async function reactivateUser() {
            const userId = document.getElementById('manageUserId').value;
            if (!userId) {
                showError('Please enter User ID');
                return;
            }
            
            try {
                await apiCall('/reactivate-user', 'POST', { user_id: parseInt(userId) });
                showSuccess(`User ${userId} reactivated`);
                loadRecentUsers();
            } catch (error) {
                // Error already shown by apiCall
            }
        }

        async function refreshStats() {
            await Promise.all([loadStats(), loadRecentUsers(), loadRecentTransactions()]);
            showSuccess('Statistics refreshed');
        }

        async function exportData() {
            try {
                const response = await fetch(API_BASE + '/export', {
                    headers: { 'Authorization': AUTH_TOKEN }
                });
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'bot_data_export.json';
                a.click();
                showSuccess('Data exported successfully');
            } catch (error) {
                showError('Export failed: ' + error.message);
            }
        }

        async function cleanupExpired() {
            try {
                const result = await apiCall('/cleanup', 'POST');
                showSuccess(`Cleanup completed: ${result.expired_credits} credits, ${result.expired_invites} invites`);
                refreshStats();
            } catch (error) {
                // Error already shown by apiCall
            }
        }

        // Load initial data
        document.addEventListener('DOMContentLoaded', () => {
            refreshStats();
        });
    </script>
</body>
</html>
    """
    return render_template_string(dashboard_html)

@admin_bp.route('/api/stats')
@admin_required
def get_stats():
    """Get system statistics"""
    try:
        user_stats = user_service.get_user_count()
        credit_stats = credit_service.get_credit_statistics()
        invite_stats = invite_service.get_invite_statistics()
        
        # Get job statistics
        total_jobs = FaceSwapJob.query.count()
        completed_jobs = FaceSwapJob.query.filter_by(status='completed').count()
        
        return jsonify({
            'users': user_stats,
            'credits': credit_stats,
            'invites': invite_stats,
            'jobs': {
                'total': total_jobs,
                'completed': completed_jobs,
                'success_rate': (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/users')
@admin_required
def get_users():
    """Get users list"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        status = request.args.get('status')
        
        users = user_service.search_users(limit=limit, offset=offset)
        
        users_data = []
        for user in users:
            user_stats = user_service.get_user_stats(user.id)
            users_data.append(user_stats)
        
        return jsonify(users_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/transactions')
@admin_required
def get_transactions():
    """Get transactions list"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        transactions = Transaction.query.order_by(
            Transaction.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        transactions_data = []
        for tx in transactions:
            transactions_data.append({
                'id': tx.id,
                'user_id': tx.user_id,
                'transaction_type': tx.transaction_type.value,
                'payment_method': tx.payment_method.value,
                'amount_local': float(tx.amount_local),
                'currency_code': tx.currency_code,
                'credits_purchased': tx.credits_purchased,
                'status': tx.status.value,
                'created_at': tx.created_at.isoformat()
            })
        
        return jsonify(transactions_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/grant-credits', methods=['POST'])
@admin_required
def grant_credits():
    """Grant credits to a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        reason = data.get('reason', 'Admin grant')
        
        if not user_id or not amount:
            return jsonify({'error': 'user_id and amount are required'}), 400
        
        credit = credit_service.grant_admin_credits(
            user_id=user_id,
            amount=amount,
            admin_id=1,  # In production, get from authenticated admin
            reason=reason
        )
        
        return jsonify({
            'success': True,
            'credit_id': credit.id,
            'message': f'Granted {amount} credits to user {user_id}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/suspend-user', methods=['POST'])
@admin_required
def suspend_user():
    """Suspend a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        reason = data.get('reason', 'Admin action')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        success = user_service.suspend_user(user_id, reason)
        
        if success:
            return jsonify({'success': True, 'message': f'User {user_id} suspended'})
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/ban-user', methods=['POST'])
@admin_required
def ban_user():
    """Ban a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        reason = data.get('reason', 'Admin action')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        success = user_service.ban_user(user_id, reason)
        
        if success:
            return jsonify({'success': True, 'message': f'User {user_id} banned'})
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/reactivate-user', methods=['POST'])
@admin_required
def reactivate_user():
    """Reactivate a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        success = user_service.reactivate_user(user_id)
        
        if success:
            return jsonify({'success': True, 'message': f'User {user_id} reactivated'})
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/cleanup', methods=['POST'])
@admin_required
def cleanup_expired():
    """Cleanup expired credits and invites"""
    try:
        expired_credits = credit_service.expire_old_credits()
        expired_invites = invite_service.expire_old_invites()
        
        return jsonify({
            'success': True,
            'expired_credits': expired_credits,
            'expired_invites': expired_invites
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/export')
@admin_required
def export_data():
    """Export system data"""
    try:
        # Get summary statistics for export
        user_stats = user_service.get_user_count()
        credit_stats = credit_service.get_credit_statistics()
        invite_stats = invite_service.get_invite_statistics()
        
        export_data = {
            'export_timestamp': db.func.now(),
            'statistics': {
                'users': user_stats,
                'credits': credit_stats,
                'invites': invite_stats
            }
        }
        
        return jsonify(export_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

