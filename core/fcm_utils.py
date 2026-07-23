import logging
import firebase_admin
from firebase_admin import messaging
from apps.accounts.models import UserDeviceToken
from apps.students.models import StudentDeviceToken

logger = logging.getLogger(__name__)

def send_push_notification(tokens, title, body, data=None):
    """
    Sends a push notification to a list of FCM tokens.
    """
    if not tokens:
        return
    
    if not firebase_admin._apps:
        logger.error("Firebase app is not initialized. Cannot send push notification.")
        return

    # Ensure all data values are strings as required by Firebase API
    str_data = {}
    if data:
        for k, v in data.items():
            str_data[k] = str(v)

    # Create the message payload
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=str_data,
        tokens=tokens,
    )
    
    try:
        response = messaging.send_multicast(message)
        logger.info(f"Successfully sent {response.success_count} messages; {response.failure_count} failures")
        
        # Optionally, handle failure responses to remove stale tokens
        if response.failure_count > 0:
            responses = response.responses
            failed_tokens = []
            for idx, resp in enumerate(responses):
                if not resp.success:
                    # The order of responses corresponds to the order of tokens
                    failed_tokens.append(tokens[idx])
                    logger.error(f"Failed to send to token {tokens[idx]}: {resp.exception}")
            
            if failed_tokens:
                # Remove invalid tokens
                UserDeviceToken.objects.filter(token__in=failed_tokens).delete()
                StudentDeviceToken.objects.filter(token__in=failed_tokens).delete()
                
    except Exception as e:
        logger.error(f"Error sending push notification: {e}")

def send_notification_to_teachers(title, body, data=None):
    """
    Send push notification to all users who have registered a device token (Teachers/Admins).
    """
    tokens = list(UserDeviceToken.objects.values_list('token', flat=True))
    if tokens:
        send_push_notification(tokens, title, body, data)

def send_notification_to_student_parents(student, title, body, data=None):
    """
    Send push notification to parents registered for a specific student.
    """
    tokens = list(student.device_tokens.values_list('token', flat=True))
    if tokens:
        send_push_notification(tokens, title, body, data)

def send_notification_to_students_parents(students, title, body, data=None):
    """
    Send push notification to parents registered for a queryset or list of students.
    """
    tokens = list(StudentDeviceToken.objects.filter(student__in=students).values_list('token', flat=True).distinct())
    if tokens:
        send_push_notification(tokens, title, body, data)
