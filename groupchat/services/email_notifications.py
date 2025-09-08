"""Email notification service for expert communications"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from groupchat.config import settings
from groupchat.db.models import Contact, ExpertNotificationPreferences, Query as QueryModel
from groupchat.schemas.expert_notifications import NotificationUrgency

logger = logging.getLogger(__name__)


class EmailTemplate:
    """Email templates for different expert notifications"""
    
    @staticmethod
    def query_invitation_subject(urgency: str = "normal") -> str:
        """Generate email subject for query invitation"""
        urgency_prefix = {"urgent": "🚨 URGENT", "high": "⚡ HIGH PRIORITY", "normal": "", "low": ""}
        prefix = urgency_prefix.get(urgency, "")
        return f"{prefix} New GroupChat Query Available".strip()
    
    @staticmethod
    def query_invitation_html(
        expert_name: str,
        question: str,
        user_phone: str,
        estimated_payout: float,
        timeout_minutes: int,
        query_id: str,
        response_url: str
    ) -> str:
        """Generate HTML email for query invitation"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>New GroupChat Query</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #fff; padding: 30px; border: 1px solid #e0e0e0; border-radius: 0 0 8px 8px; }}
                .question-box {{ background: #f8f9fa; border-left: 4px solid #007bff; padding: 20px; margin: 20px 0; }}
                .details {{ background: #e8f5e8; padding: 15px; border-radius: 6px; margin: 20px 0; }}
                .cta-button {{ display: inline-block; background: #28a745; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
                .urgent {{ border-left-color: #dc3545 !important; }}
                .high {{ border-left-color: #fd7e14 !important; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>💡 New Query Available</h1>
                    <p>Hi {expert_name}, you've been matched with a new question!</p>
                </div>
                
                <div class="content">
                    <div class="question-box">
                        <h3>📝 Question:</h3>
                        <p><strong>{question}</strong></p>
                        <small>From: {user_phone}</small>
                    </div>
                    
                    <div class="details">
                        <h4>💰 Opportunity Details:</h4>
                        <ul>
                            <li><strong>Estimated Payout:</strong> ${estimated_payout:.4f}</li>
                            <li><strong>Response Time:</strong> {timeout_minutes} minutes remaining</li>
                            <li><strong>Query ID:</strong> {query_id}</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="{response_url}" class="cta-button">Respond Now</a>
                    </div>
                    
                    <div class="footer">
                        <p>You can also respond via SMS by replying to our text message.</p>
                        <p>To unsubscribe from email notifications, <a href="{settings.app_base_url}/expert/preferences">update your preferences</a></p>
                        <p>© 2024 GroupChat Network Intelligence System</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    @staticmethod
    def query_invitation_text(
        expert_name: str,
        question: str,
        user_phone: str,
        estimated_payout: float,
        timeout_minutes: int,
        query_id: str,
        response_url: str
    ) -> str:
        """Generate plain text email for query invitation"""
        return f"""
        Hi {expert_name},
        
        You've been matched with a new GroupChat query!
        
        QUESTION:
        {question}
        
        From: {user_phone}
        
        OPPORTUNITY DETAILS:
        - Estimated Payout: ${estimated_payout:.4f}
        - Response Time: {timeout_minutes} minutes remaining
        - Query ID: {query_id}
        
        RESPOND NOW: {response_url}
        
        You can also respond via SMS by replying to our text message.
        
        To unsubscribe from email notifications, visit: {settings.app_base_url}/expert/preferences
        
        --
        GroupChat Network Intelligence System
        """
    
    @staticmethod
    def payment_notification_html(
        expert_name: str,
        amount: float,
        query_id: str,
        question_preview: str
    ) -> str:
        """Generate HTML email for payment notification"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Payment Received - GroupChat</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #fff; padding: 30px; border: 1px solid #e0e0e0; border-radius: 0 0 8px 8px; }}
                .payment-box {{ background: #d4edda; border: 1px solid #c3e6cb; padding: 20px; margin: 20px 0; border-radius: 6px; text-align: center; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>💰 Payment Received!</h1>
                    <p>Hi {expert_name}, your contribution has been rewarded!</p>
                </div>
                
                <div class="content">
                    <div class="payment-box">
                        <h2>${amount:.4f}</h2>
                        <p>Payment for Query: {query_id}</p>
                        <p><em>"{question_preview}"</em></p>
                    </div>
                    
                    <p>Thank you for sharing your expertise with the GroupChat network. Your response was valuable and has been included in the final answer with proper citation.</p>
                    
                    <div class="footer">
                        <p>Payment processed via Stripe Connect to your connected account.</p>
                        <p>© 2024 GroupChat Network Intelligence System</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """


class EmailNotificationService:
    """Service for sending email notifications to experts"""
    
    def __init__(self):
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.from_email = settings.from_email or "noreply@groupchat.ai"
        self.from_name = "GroupChat Network"
    
    def _is_configured(self) -> bool:
        """Check if email service is properly configured"""
        return all([
            self.smtp_server,
            self.smtp_username,
            self.smtp_password,
            settings.enable_email_notifications
        ])
    
    async def _get_expert_email_preferences(
        self, 
        contact_id: UUID, 
        db: AsyncSession
    ) -> tuple[Optional[str], bool]:
        """Get expert's email and email notification preferences"""
        result = await db.execute(
            select(Contact).where(Contact.id == contact_id)
        )
        contact = result.scalar_one_or_none()
        
        if not contact or not contact.email:
            return None, False
        
        # Check notification preferences
        prefs_result = await db.execute(
            select(ExpertNotificationPreferences).where(
                ExpertNotificationPreferences.contact_id == contact_id
            )
        )
        preferences = prefs_result.scalar_one_or_none()
        
        # Default to enabled if no preferences set
        email_enabled = preferences.email_enabled if preferences else True
        
        return contact.email, email_enabled
    
    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """Send email via SMTP"""
        if not self._is_configured():
            logger.warning("Email service not configured, skipping email")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Add text and HTML parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def send_query_invitation_email(
        self,
        contact_id: UUID,
        query: QueryModel,
        estimated_payout_cents: int,
        urgency: NotificationUrgency = NotificationUrgency.NORMAL,
        db: AsyncSession = None
    ) -> bool:
        """Send query invitation email to expert"""
        if not db:
            logger.error("Database session required for email notifications")
            return False
        
        # Get expert email and preferences
        email, email_enabled = await self._get_expert_email_preferences(contact_id, db)
        
        if not email:
            logger.info(f"No email address for expert {contact_id}")
            return False
        
        if not email_enabled:
            logger.info(f"Email notifications disabled for expert {contact_id}")
            return False
        
        # Get expert name
        result = await db.execute(
            select(Contact).where(Contact.id == contact_id)
        )
        contact = result.scalar_one_or_none()
        expert_name = contact.name if contact else "Expert"
        
        # Generate email content
        estimated_payout = estimated_payout_cents / 100
        response_url = f"{settings.app_base_url}/expert?query_id={query.id}"
        
        subject = EmailTemplate.query_invitation_subject(urgency.value)
        html_content = EmailTemplate.query_invitation_html(
            expert_name=expert_name,
            question=query.question_text,
            user_phone=query.user_phone,
            estimated_payout=estimated_payout,
            timeout_minutes=query.timeout_minutes,
            query_id=str(query.id),
            response_url=response_url
        )
        text_content = EmailTemplate.query_invitation_text(
            expert_name=expert_name,
            question=query.question_text,
            user_phone=query.user_phone,
            estimated_payout=estimated_payout,
            timeout_minutes=query.timeout_minutes,
            query_id=str(query.id),
            response_url=response_url
        )
        
        return self._send_email(email, subject, html_content, text_content)
    
    async def send_payment_notification_email(
        self,
        contact_id: UUID,
        amount_cents: int,
        query_id: UUID,
        question_preview: str,
        db: AsyncSession = None
    ) -> bool:
        """Send payment notification email to expert"""
        if not db:
            logger.error("Database session required for email notifications")
            return False
        
        # Get expert email and preferences
        email, email_enabled = await self._get_expert_email_preferences(contact_id, db)
        
        if not email or not email_enabled:
            return False
        
        # Get expert name
        result = await db.execute(
            select(Contact).where(Contact.id == contact_id)
        )
        contact = result.scalar_one_or_none()
        expert_name = contact.name if contact else "Expert"
        
        # Generate email content
        amount_dollars = amount_cents / 100
        subject = f"💰 Payment Received: ${amount_dollars:.4f} - GroupChat"
        
        html_content = EmailTemplate.payment_notification_html(
            expert_name=expert_name,
            amount=amount_dollars,
            query_id=str(query_id),
            question_preview=question_preview[:100] + "..." if len(question_preview) > 100 else question_preview
        )
        
        text_content = f"""
        Hi {expert_name},
        
        You've received a payment for your GroupChat contribution!
        
        PAYMENT DETAILS:
        - Amount: ${amount_dollars:.4f}
        - Query ID: {query_id}
        - Question: "{question_preview[:100]}{'...' if len(question_preview) > 100 else ''}"
        
        Thank you for sharing your expertise with the GroupChat network.
        Payment has been processed to your connected Stripe account.
        
        --
        GroupChat Network Intelligence System
        """
        
        return self._send_email(email, subject, html_content, text_content)
    
    async def send_bulk_query_invitations(
        self,
        contact_ids: List[UUID],
        query: QueryModel,
        estimated_payout_cents: int,
        urgency: NotificationUrgency = NotificationUrgency.NORMAL,
        db: AsyncSession = None
    ) -> Dict[str, int]:
        """Send query invitation emails to multiple experts"""
        results = {"sent": 0, "failed": 0, "skipped": 0}
        
        for contact_id in contact_ids:
            try:
                success = await self.send_query_invitation_email(
                    contact_id, query, estimated_payout_cents, urgency, db
                )
                if success:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                logger.error(f"Error sending email to expert {contact_id}: {e}")
                results["failed"] += 1
        
        logger.info(f"Bulk email results: {results}")
        return results
    
    async def test_email_configuration(self) -> Dict[str, Any]:
        """Test email configuration by sending a test email"""
        if not self._is_configured():
            return {
                "success": False,
                "error": "Email service not configured",
                "configured": False
            }
        
        test_subject = "GroupChat Email Configuration Test"
        test_html = """
        <html>
        <body>
            <h2>GroupChat Email Test</h2>
            <p>This is a test email to verify your email configuration is working correctly.</p>
            <p>If you receive this email, your SMTP settings are configured properly!</p>
        </body>
        </html>
        """
        test_text = "GroupChat Email Test - If you receive this, your email configuration is working!"
        
        try:
            success = self._send_email(
                self.from_email,
                test_subject,
                test_html,
                test_text
            )
            
            return {
                "success": success,
                "configured": True,
                "smtp_server": self.smtp_server,
                "smtp_port": self.smtp_port,
                "from_email": self.from_email
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "configured": True
            }