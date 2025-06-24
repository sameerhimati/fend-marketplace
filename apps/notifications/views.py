from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from apps.notifications.models import Notification, NotificationPreferences
from apps.notifications.services import mark_as_read, mark_all_as_read, get_unread_count

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    paginator = Paginator(notifications, 20)  # Show 20 notifications per page
    
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    unread_count = get_unread_count(request.user)
    
    return render(request, 'notifications/list.html', {
        'page_obj': page_obj,
        'unread_count': unread_count
    })

@login_required
def notification_detail(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    
    # Automatically mark as read when viewed
    if not notification.read:
        notification.read = True
        notification.save(update_fields=['read'])
    
    context = {
        'notification': notification
    }
    
    # Add related objects to context if they exist
    if notification.related_pilot:
        context['pilot'] = notification.related_pilot
    
    if notification.related_bid:
        context['bid'] = notification.related_bid
    
    return render(request, 'notifications/detail.html', context)

@login_required
def mark_notification_read(request, notification_id):
    success = mark_as_read(notification_id, request.user)
    
    if request.headers.get('HX-Request'):
        if success:
            return JsonResponse({'success': True})
        return JsonResponse({'success': False}, status=404)
    
    return redirect('notifications:list')

@login_required
def mark_all_notifications_read(request):
    mark_all_as_read(request.user)
    
    if request.headers.get('HX-Request'):
        return JsonResponse({'success': True, 'count': 0})
    
    return redirect('notifications:list')

@login_required
def get_notification_count(request):
    count = get_unread_count(request.user)
    return JsonResponse({'count': count})


@login_required
def delete_notification(request, notification_id):
    """Delete a notification"""
    if request.method != 'POST':
        return redirect('notifications:list')
    
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.delete()
    
    messages.success(request, "Notification deleted successfully")
    return redirect('notifications:list')

@login_required
def toggle_notifications(request):
    """Toggle notification preferences"""
    if request.method != 'POST':
        return redirect('notifications:list')
    
    # Get or create notification preferences 
    preferences, created = NotificationPreferences.objects.get_or_create(
        user=request.user,
        defaults={'enabled': True}
    )
    
    # Toggle the enabled state
    preferences.enabled = not preferences.enabled
    preferences.save()
    
    status = "enabled" if preferences.enabled else "disabled"
    messages.success(request, f"Notifications {status}")
    
    return redirect('notifications:list')