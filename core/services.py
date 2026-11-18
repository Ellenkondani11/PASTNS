import json
import logging
import os
from dataclasses import dataclass
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import requests
from .models import AuditLog, Notification, SmsTemplate
from .utils import mask_phone

logger = logging.getLogger("pastns.notifications")


@dataclass
class GatewayResult:
    status: str
    provider_ref: str = ""
    error: str = ""


class NotificationGateway:
    """Dispatcher seam: replace this class with an asynchronous dispatcher in production."""
    def send(self, notification: Notification) -> GatewayResult:
        raise NotImplementedError


class ConsoleGateway(NotificationGateway):
    """Safe demo gateway: stores the exact message and marks it simulated-sent."""
    def send(self, notification):
        logger.info("PASTNS DEMO SMS to %s: %s", notification.to, notification.body)
        return GatewayResult("sent", provider_ref="console-demo")


class AfricasTalkingGateway(NotificationGateway):
    def send(self, notification):
        if not settings.AT_USERNAME or not settings.AT_API_KEY:
            return GatewayResult("failed", error="Africa's Talking credentials are not configured.")
        headers = {"apiKey": settings.AT_API_KEY, "Accept": "application/json"}
        data = {"username": settings.AT_USERNAME, "to": notification.to, "message": notification.body}
        if settings.AT_SENDER_ID:
            data["from"] = settings.AT_SENDER_ID
        try:
            response = requests.post(settings.AT_BASE_URL, headers=headers, data=data, timeout=12)
            response.raise_for_status()
            payload = response.json()
            recipients = payload.get("SMSMessageData", {}).get("Recipients", [])
            if recipients and recipients[0].get("statusCode") in (100, 101, 102):
                return GatewayResult("sent", provider_ref=recipients[0].get("messageId", ""))
            detail = recipients[0].get("status", "Provider did not accept the message") if recipients else "Provider returned no recipient result"
            return GatewayResult("failed", error=str(detail))
        except (requests.RequestException, ValueError) as exc:
            return GatewayResult("failed", error=str(exc)[:500])


class SMTPGateway(NotificationGateway):
    def send(self, notification):
        try:
            send_mail(
                subject=f"Passport application update: {notification.application.tracking_code}",
                message=notification.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.to],
                fail_silently=False,
            )
            return GatewayResult("sent", provider_ref="smtp")
        except Exception as exc:  # noqa: BLE001 - record and show provider errors in outbox
            return GatewayResult("failed", error=str(exc)[:500])


def get_gateway(channel="sms"):
    if channel == "email":
        return SMTPGateway()
    if settings.PASTNS_SMS_GATEWAY == "africastalking":
        return AfricasTalkingGateway()
    return ConsoleGateway()


def render_message(application, event):
    key = getattr(event, "key", None) or str(event)
    template = SmsTemplate.objects.filter(key=key, is_active=True).first()
    language = application.applicant.language or "en"
    if template:
        text = template.body_for(language)
    else:
        text = "Immigration: {code} status updated at {office}. Check *384*123#."
    data = {
        "code": application.tracking_code,
        "office": application.office.name,
        "url": "pastns.gov.mw",
        "hours": application.office.collection_hours_for(language),
    }
    try:
        return text.format_map(data)
    except (KeyError, ValueError):
        return text


def send_notification(notification, actor=None, ip=None):
    """Send an existing outbox row, persist the provider outcome and audit it."""
    gateway = get_gateway("email" if notification.channel == "email" else "sms")
    notification.status = "queued"
    notification.error = ""
    notification.save(update_fields=["status", "error", "updated_at"])
    result = gateway.send(notification)
    notification.status = result.status
    notification.provider_ref = result.provider_ref or notification.provider_ref
    notification.error = result.error
    notification.sent_at = timezone.now() if result.status in ("sent", "delivered") else None
    notification.save(update_fields=["status", "provider_ref", "error", "sent_at", "updated_at"])
    destination = mask_phone(notification.to) if notification.channel == "sms" else notification.to[:2] + "•••" if "@" in notification.to else "••••"
    AuditLog.objects.create(
        user=actor,
        action="notification_failed" if result.status == "failed" else "notification_dispatched",
        object_type="Notification",
        object_id=str(notification.pk),
        details={"application": notification.application.tracking_code, "channel": notification.channel,
                 "to": destination, "template": notification.template_key, "status": result.status},
        ip=ip,
    )
    return notification


def notify(application, event, channel="sms", actor=None, ip=None):
    """Synchronous notification: create outbox row, then call the selected gateway."""
    key = getattr(event, "key", None) or str(event)
    if channel == "email":
        destination = application.applicant.email
        if not destination:
            return None
    else:
        destination = application.applicant.phone
    row = Notification.objects.create(
        application=application,
        channel=channel,
        to=destination,
        template_key=key,
        body=render_message(application, key),
        status="queued",
    )
    return send_notification(row, actor=actor, ip=ip)


def retry_notification(notification, actor=None, ip=None):
    return send_notification(notification, actor=actor, ip=ip)


def resend_last_notification(application, actor=None, ip=None):
    last = application.notifications.order_by("-created_at").first()
    if not last:
        return None
    destination = application.applicant.email if last.channel == "email" else application.applicant.phone
    if not destination:
        return None
    row = Notification.objects.create(
        application=application, channel=last.channel, to=destination,
        template_key=last.template_key, body=render_message(application, last.template_key), status="queued",
    )
    return send_notification(row, actor=actor, ip=ip)


def notify_stage(application, stage, actor=None, ip=None):
    if not stage.notify:
        return None
    return notify(application, stage.key, actor=actor, ip=ip)
