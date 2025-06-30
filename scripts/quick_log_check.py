#!/usr/bin/env python3
"""
Quick log monitoring script - can be run via cron
This is a basic version before building the full AI monitoring
"""

import os
import sys
from datetime import datetime, timedelta
import re

def check_recent_errors(log_file='/app/logs/errors.log', minutes=5):
    """Check for errors in the last N minutes"""
    if not os.path.exists(log_file):
        print(f"Log file {log_file} not found")
        return []
    
    errors = []
    cutoff_time = datetime.now() - timedelta(minutes=minutes)
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                # Parse timestamp from log format: ERROR 2025-06-30 12:34:56
                match = re.search(r'ERROR (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                    if timestamp > cutoff_time:
                        errors.append(line.strip())
    except Exception as e:
        print(f"Error reading log file: {e}")
    
    return errors

def send_alert(errors):
    """Send alert if errors found (placeholder for email/slack)"""
    if not errors:
        return
    
    print(f"🚨 ALERT: {len(errors)} errors in last 5 minutes!")
    print("\nRecent errors:")
    for error in errors[:5]:  # Show first 5
        print(f"  - {error[:100]}...")
    
    # TODO: Add email/Slack notification here
    # For now, just log to Docker output

def main():
    """Main monitoring loop"""
    print(f"🔍 Checking logs at {datetime.now()}")
    
    # Check for recent errors
    errors = check_recent_errors()
    
    if errors:
        send_alert(errors)
    else:
        print("✅ No recent errors found")
    
    # Could add more checks here:
    # - Database connectivity
    # - Disk space
    # - Memory usage
    # - Response times

if __name__ == "__main__":
    main()