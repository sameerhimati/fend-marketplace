from apps.notifications.models import Notification
from apps.users.models import User
from apps.pilots.models import Pilot, PilotBid

def create_notification(recipient, notification_type, title, message, related_pilot=None, related_bid=None):
    """
    Create a notification for a recipient if they have notifications enabled
    """
    # Check if user has notifications enabled
    preferences = getattr(recipient, 'notification_preferences', None)
    if preferences and not preferences.enabled:
        return None
    
    notification = Notification.objects.create(
        recipient=recipient,
        type=notification_type,
        title=title,
        message=message,
        related_pilot=related_pilot,
        related_bid=related_bid
    )
    return notification

def create_pilot_notification(pilot, notification_type, title, message, related_bid=None):
    """
    Create notifications for all members of the organization that owns the pilot
    """
    organization = pilot.organization
    recipients = User.objects.filter(organization=organization)
    
    notifications = []
    for recipient in recipients:
        notification = create_notification(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            related_pilot=pilot,
            related_bid=related_bid
        )
        notifications.append(notification)
    
    return notifications

def create_bid_notification(bid, notification_type, title, message):
    """
    Create notification for a bid - notifies both the pilot owner and bid submitter
    """
    # Notify pilot owner's organization
    pilot_notifications = create_pilot_notification(
        pilot=bid.pilot,
        notification_type=notification_type,
        title=title,
        message=message,
        related_bid=bid
    )
    
    # Notify bid submitter if not already notified (in case they're from a different org)
    submitter_org = bid.startup
    if submitter_org != bid.pilot.organization:
        submitter_notifications = User.objects.filter(organization=submitter_org)
        for recipient in submitter_notifications:
            notification = create_notification(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                related_pilot=bid.pilot,
                related_bid=bid
            )
            pilot_notifications.append(notification)
    
    return pilot_notifications

def mark_as_read(notification_id, user):
    """
    Mark a notification as read if it belongs to the user
    """
    try:
        notification = Notification.objects.get(id=notification_id, recipient=user)
        notification.read = True
        notification.save()
        return True
    except Notification.DoesNotExist:
        return False

def mark_all_as_read(user):
    """
    Mark all notifications as read for a user
    """
    Notification.objects.filter(recipient=user, read=False).update(read=True)
    return True

def get_unread_count(user):
    """
    Get count of unread notifications for a user
    """
    return Notification.objects.filter(recipient=user, read=False).count()

