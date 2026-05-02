"""
User Activity API Routes
Handles user activity tracking and retrieval
"""
from flask import Blueprint, jsonify, request
from pathlib import Path
import json
from .utils.app_logger_standard import get_error_logger

# Create activity blueprint
activity_bp = Blueprint('activity', __name__)

# Get logger
error_logger = get_error_logger()

# Activity log file path
ACTIVITY_LOG_PATH = Path("logs/activity/afm_activity.log")


def get_afm_activities(user_id=None, limit=100):
    """
    Read AFM-specific activities from structured log file
    
    Args:
        user_id: Filter by specific user
        limit: Maximum activities to return
    """
    activities = []
    
    # Get log files
    log_files = []
    if ACTIVITY_LOG_PATH.exists():
        log_files.append(ACTIVITY_LOG_PATH)
    
    # Check for rotated files
    log_dir = ACTIVITY_LOG_PATH.parent
    if log_dir.exists():
        rotated_files = sorted(log_dir.glob(f"{ACTIVITY_LOG_PATH.name}.*"), reverse=True)
        log_files.extend(rotated_files[:5])
    
    if not log_files:
        return activities
    
    try:
        collected_count = 0
        
        for log_file in log_files:
            if collected_count >= limit:
                break
                
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                # Parse each line (most recent first)
                for line in reversed(lines):
                    if collected_count >= limit:
                        break
                        
                    try:
                        log_entry = json.loads(line.strip())
                        
                        # Filter for AFM activities
                        if (log_entry.get('message', '').startswith('AFM ') and 
                            log_entry.get('level', '').upper() == 'INFO'):
                            
                            log_user = log_entry.get('user', 'anonymous')
                            
                            # Apply user filter if specified
                            if user_id is None or log_user == user_id:
                                # Transform log entry to activity format
                                activity = {
                                    'timestamp': log_entry.get('time', log_entry.get('timestamp', '')),
                                    'user': log_user,
                                    'action': log_entry.get('action', ''),
                                    'tool': log_entry.get('tool', '')
                                }
                                
                                # Add action-specific data
                                if log_entry.get('action') == 'list_files':
                                    activity['files_count'] = log_entry.get('files_count', 0)
                                elif log_entry.get('action') == 'get_detail':
                                    activity['filename'] = log_entry.get('filename', '')
                                    activity['summary_count'] = log_entry.get('summary_count', 0)
                                    activity['detail_count'] = log_entry.get('detail_count', 0)
                                
                                activities.append(activity)
                                collected_count += 1
                                
                    except json.JSONDecodeError:
                        continue
                        
            except Exception as e:
                error_logger.warning(f"Failed to read log file {log_file}", extra={
                                   'error': str(e),
                                   'file': str(log_file)})
                continue
                
    except Exception as e:
        error_logger.error("Failed to read AFM activities", extra={
                         'error': str(e),
                         'user_id': user_id,
                         'limit': limit})
    
    return activities


def get_user_analytics(days=7):
    """
    Get user analytics with session-based deduplication
    
    Returns daily unique users and session counts
    """
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    analytics = {
        'daily_stats': [],
        'total_unique_users': set(),
        'summary': {}
    }
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get all activities for the period
    all_activities = get_afm_activities(limit=10000)
    
    # Group by date and user
    daily_users = defaultdict(lambda: defaultdict(list))
    
    for activity in all_activities:
        try:
            # Parse timestamp
            timestamp_str = activity.get('timestamp', '')
            if 'T' in timestamp_str:
                activity_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                continue
                
            # Skip if outside date range
            if activity_time < start_date:
                continue
                
            date_key = activity_time.date().isoformat()
            user = activity.get('user', 'anonymous')
            
            # Store activity time for session calculation
            daily_users[date_key][user].append(activity_time)
            analytics['total_unique_users'].add(user)
            
        except Exception:
            continue
    
    # Calculate daily stats with sessions
    for date_key in sorted(daily_users.keys()):
        users_data = daily_users[date_key]
        daily_stat = {
            'date': date_key,
            'unique_users': len(users_data),
            'total_sessions': 0,
            'total_actions': 0,
            'avg_actions_per_session': 0
        }
        
        # Calculate sessions per user
        for user, timestamps in users_data.items():
            # Sort timestamps
            sorted_times = sorted(timestamps)
            sessions = 1
            
            # Count sessions (new session if gap > 30 minutes)
            for i in range(1, len(sorted_times)):
                time_gap = (sorted_times[i] - sorted_times[i-1]).total_seconds() / 60
                if time_gap > 30:  # 30 minute session timeout
                    sessions += 1
            
            daily_stat['total_sessions'] += sessions
            daily_stat['total_actions'] += len(timestamps)
        
        if daily_stat['total_sessions'] > 0:
            daily_stat['avg_actions_per_session'] = round(
                daily_stat['total_actions'] / daily_stat['total_sessions'], 1
            )
        
        analytics['daily_stats'].append(daily_stat)
    
    # Calculate summary
    if analytics['daily_stats']:
        analytics['summary'] = {
            'period_days': days,
            'total_unique_users': len(analytics['total_unique_users']),
            'avg_daily_users': round(
                sum(d['unique_users'] for d in analytics['daily_stats']) / len(analytics['daily_stats']), 1
            ),
            'avg_daily_sessions': round(
                sum(d['total_sessions'] for d in analytics['daily_stats']) / len(analytics['daily_stats']), 1
            )
        }
    
    return analytics


@activity_bp.route('/user-activities', methods=['GET'])
def get_activities():
    """Get AFM access activities"""
    try:
        # Get optional user filter from query params
        user_id = request.args.get('user')
        limit = int(request.args.get('limit', 100))
        
        activities = get_afm_activities(user_id, limit)
        
        return jsonify({
            'success': True,
            'data': activities,
            'count': len(activities),
            'message': f'Retrieved {len(activities)} AFM activities'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to retrieve activities'
        }), 500


@activity_bp.route('/my-activities', methods=['GET'])
def get_my_activities():
    """Get current user's AFM activities"""
    try:
        # Get current user from cookie
        current_user = request.cookies.get('LAST_USER')
        if not current_user:
            return jsonify({
                'success': False,
                'error': 'No user identified',
                'message': 'LAST_USER cookie not found'
            }), 400
        
        activities = get_afm_activities(current_user, 50)
        
        return jsonify({
            'success': True,
            'user': current_user,
            'data': activities,
            'count': len(activities),
            'message': f'Retrieved {len(activities)} AFM activities for {current_user}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to retrieve user activities'
        }), 500


@activity_bp.route('/current-user', methods=['GET'])
def get_current_user_endpoint():
    """Get current user from cookie"""
    try:
        current_user = request.cookies.get('LAST_USER')
        
        if not current_user:
            return jsonify({
                'success': False,
                'error': 'No user identified',
                'message': 'LAST_USER cookie not found'
            }), 400
        
        return jsonify({
            'success': True,
            'user': current_user,
            'message': f'Current user: {current_user}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to get current user'
        }), 500


@activity_bp.route('/user-analytics', methods=['GET'])
def get_analytics():
    """Get user analytics with session-based metrics"""
    try:
        # Get days parameter (default 7 days)
        days = int(request.args.get('days', 7))
        
        analytics = get_user_analytics(days)
        
        return jsonify({
            'success': True,
            'data': analytics,
            'message': f'User analytics for the last {days} days'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to generate analytics'
        }), 500


@activity_bp.route('/debug/cookies', methods=['GET'])
def debug_cookies():
    """Debug endpoint to see all cookies"""
    cookies = {}
    for cookie_name, cookie_value in request.cookies.items():
        cookies[cookie_name] = cookie_value
    
    return jsonify({
        'success': True,
        'cookies': cookies,
        'count': len(cookies),
        'message': 'All cookies received by server'
    })