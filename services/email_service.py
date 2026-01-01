import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import Config
from models.interview import EmailLog
from extensions import db
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails to candidates"""
    
    def __init__(self, smtp_server=None, smtp_port=None, smtp_username=None, smtp_password=None, from_email=None, from_name=None):
        self.smtp_server = smtp_server or Config.SMTP_SERVER
        self.smtp_port = smtp_port or Config.SMTP_PORT
        self.smtp_username = smtp_username or Config.SMTP_USERNAME
        self.smtp_password = smtp_password or Config.SMTP_PASSWORD
        self.from_email = from_email or Config.FROM_EMAIL
        self.from_name = from_name or Config.FROM_NAME
    
    def send_email(self, to_email, subject, html_content, email_type=None, related_id=None):
        """Send email and log the attempt"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email via SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            # Log success
            self._log_email(to_email, subject, email_type, related_id, 'sent')
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            # Log failure
            self._log_email(to_email, subject, email_type, related_id, 'failed', str(e))
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def _log_email(self, to_email, subject, email_type, related_id, status, error_message=None):
        """Log email sending attempt"""
        try:
            email_log = EmailLog(
                to_email=to_email,
                subject=subject,
                email_type=email_type,
                related_id=related_id,
                status=status,
                error_message=error_message
            )
            db.session.add(email_log)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log email: {str(e)}")
            db.session.rollback()
    
    def send_status_change_email(self, candidate_name, candidate_email, job_title, old_status, new_status, company_name):
        """Send email when candidate status changes"""
        
        status_messages = {
            'shortlisted': {
                'subject': f'Congratulations! You\'ve been shortlisted for {job_title}',
                'message': f'''
                    <p>Dear {candidate_name},</p>
                    <p>Great news! We're pleased to inform you that your application for the <strong>{job_title}</strong> position at {company_name} has been shortlisted.</p>
                    <p>Our hiring team was impressed with your qualifications and experience. We will be reaching out soon with next steps.</p>
                    <p>Best regards,<br>{company_name} Hiring Team</p>
                '''
            },
            'rejected': {
                'subject': f'Update on your application for {job_title}',
                'message': f'''
                    <p>Dear {candidate_name},</p>
                    <p>Thank you for your interest in the <strong>{job_title}</strong> position at {company_name}.</p>
                    <p>After careful consideration, we have decided to move forward with other candidates whose qualifications more closely match our current needs.</p>
                    <p>We appreciate the time you invested in the application process and wish you the best in your job search.</p>
                    <p>Best regards,<br>{company_name} Hiring Team</p>
                '''
            },
            'hired': {
                'subject': f'Congratulations! Job Offer for {job_title}',
                'message': f'''
                    <p>Dear {candidate_name},</p>
                    <p><strong>Congratulations!</strong> We are delighted to offer you the position of <strong>{job_title}</strong> at {company_name}.</p>
                    <p>We were very impressed with your skills and experience. Our HR team will contact you shortly with the formal offer letter and next steps.</p>
                    <p>We look forward to welcoming you to our team!</p>
                    <p>Best regards,<br>{company_name} Hiring Team</p>
                '''
            }
        }
        
        if new_status in status_messages:
            template = status_messages[new_status]
            html_content = f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }}
                        .header {{ background: linear-gradient(135deg, #FF6B35 0%, #F77F00 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                        .logo {{ width: 50px; height: 50px; background: linear-gradient(135deg, #FF6B35 0%, #F77F00 100%); border-radius: 10px; display: inline-block; margin: 0 auto 15px; font-size: 24px; font-weight: bold; line-height: 50px; text-align: center; color: white; border: 3px solid white; }}
                        .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1 style="margin: 0; font-size: 28px;">HireLens</h1>
                            <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">AI-Powered Recruitment</p>
                        </div>
                        <div class="content">
                            {template['message']}
                        </div>
                        <div class="footer">
                            <p>This is an automated message from {company_name} recruiting system.</p>
                        </div>
                    </div>
                </body>
                </html>
            '''
            
            return self.send_email(
                to_email=candidate_email,
                subject=template['subject'],
                html_content=html_content,
                email_type='status_change'
            )
        
        return False
    
    def send_interview_invitation(self, candidate_name, candidate_email, job_title, interview_date, 
                                  interview_type, meeting_link, duration_minutes, company_name, ai_interview_link=None, access_code=None):
        """Send interview invitation email"""
        
        subject = f'Interview Invitation - {job_title} at {company_name}'
        
        # Build access code section for AI interviews
        access_code_html = ''
        if access_code and ai_interview_link:
            access_code_html = f'''
                <div style="background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">
                    <h3 style="margin: 0 0 10px 0; color: #856404;">Your Interview Access Code</h3>
                    <div style="background: white; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #004E89; font-family: monospace;">{access_code}</span>
                    </div>
                    <p style="margin: 10px 0 0 0; font-size: 14px; color: #856404;">
                        Keep this code confidential. You'll need it to access your AI interview.
                    </p>
                </div>
            '''
        
        html_content = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }}
                    .header {{ background: linear-gradient(135deg, #FF6B35 0%, #F77F00 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .logo {{ width: 50px; height: 50px; background: linear-gradient(135deg, #FF6B35 0%, #F77F00 100%); border-radius: 10px; display: inline-block; margin: 0 auto 15px; font-size: 24px; font-weight: bold; line-height: 50px; text-align: center; color: white; border: 3px solid white; }}
                    .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .interview-details {{ background: #f0f8ff; border-left: 4px solid #004E89; padding: 15px; margin: 20px 0; }}
                    .button {{ display: inline-block; padding: 12px 30px; background: #06A77D; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 style="margin: 0; font-size: 28px;">HireLens</h1>
                        <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">Interview Invitation</p>
                    </div>
                    <div class="content">
                        <p>Dear {candidate_name},</p>
                        <p>We are pleased to invite you for a <strong>{interview_type}</strong> interview for the <strong>{job_title}</strong> position at {company_name}.</p>
                        
                        <div class="interview-details">
                            <h3>Interview Details:</h3>
                            <p><strong>Date & Time:</strong> {interview_date}</p>
                            <p><strong>Duration:</strong> {duration_minutes} minutes</p>
                            <p><strong>Type:</strong> {interview_type}</p>
                        </div>
                        
                        {access_code_html}
                        
                        {f'<p style="text-align: center;"><a href="{ai_interview_link}" class="button">Start AI Interview</a></p>' if ai_interview_link else ''}
                        {f'<p style="text-align: center;"><a href="{meeting_link}" class="button">Join Interview</a></p>' if meeting_link and not ai_interview_link else ''}
                        
                        {f'<p><strong>To start your AI interview:</strong><br>1. Click the button above<br>2. Enter your email address<br>3. Enter your access code: <code style="background: #f0f0f0; padding: 2px 8px; border-radius: 3px; font-weight: bold;">{access_code}</code></p>' if access_code else ''}
                        
                        <p>Please confirm your availability at your earliest convenience.</p>
                        <p>We look forward to speaking with you!</p>
                        
                        <p>Best regards,<br>{company_name} Hiring Team</p>
                    </div>
                    <div class="footer">
                        <p>This is an automated message from {company_name} recruiting system.</p>
                    </div>
                </div>
            </body>
            </html>
        '''
        
        return self.send_email(
            to_email=candidate_email,
            subject=subject,
            html_content=html_content,
            email_type='interview_invite'
        )
    
    def send_welcome_email(self, user_name, user_email, company_name=None):
        """Send welcome email to new users (first time only)"""
        
        subject = f'Welcome to HireLens - Your AI-Powered Recruiting Platform!'
        
        html_content = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }}
                    .header {{ background: linear-gradient(135deg, #FF6B35 0%, #F77F00 100%); color: white; padding: 40px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .logo {{ width: 60px; height: 60px; background: linear-gradient(135deg, #FF6B35 0%, #F77F00 100%); border-radius: 12px; display: inline-block; margin: 0 auto 15px; font-size: 28px; font-weight: bold; line-height: 60px; text-align: center; color: white; border: 3px solid white; }}
                    .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .feature-box {{ background: #f0f8ff; border-left: 4px solid #004E89; padding: 15px; margin: 15px 0; }}
                    .button {{ display: inline-block; padding: 15px 40px; background: linear-gradient(135deg, #06A77D 0%, #004E89 100%); color: white; text-decoration: none; border-radius: 8px; margin: 20px 0; font-weight: bold; }}
                    .steps {{ background: #fff9f0; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                    .step {{ margin: 10px 0; padding-left: 30px; position: relative; }}
                    .step::before {{ content: "✓"; position: absolute; left: 0; color: #06A77D; font-weight: bold; font-size: 18px; }}
                    .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; padding: 20px; }}
                    h2 {{ color: #004E89; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 style="margin: 0; font-size: 32px;">HireLens</h1>
                        <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">AI-Powered Recruitment Made Easy</p>
                    </div>
                    <div class="content">
                        <h2>Welcome Aboard, {user_name}!</h2>
                        
                        <p>Thank you for joining HireLens{f" - {company_name}" if company_name else ""}! We're thrilled to have you on board and can't wait to help you transform your hiring process with the power of AI.</p>
                        
                        <div class="steps">
                            <h3 style="margin-top: 0; color: #FF6B35;">Get Started in 3 Easy Steps:</h3>
                            <div class="step">Post your first job opening and let candidates find you</div>
                            <div class="step">Upload candidate resumes and get instant AI-powered scoring</div>
                            <div class="step">Schedule interviews and track candidates through your pipeline</div>
                        </div>
                        
                        <h3>What You Can Do with HireLens:</h3>
                        
                        <div class="feature-box">
                            <p><strong>AI Resume Analysis:</strong> Get intelligent scoring and matching for every candidate with our advanced AI algorithms.</p>
                        </div>
                        
                        <div class="feature-box">
                            <p><strong>Smart Interview Scheduling:</strong> Schedule interviews, send automated invitations, and manage your calendar effortlessly.</p>
                        </div>
                        
                        <div class="feature-box">
                            <p><strong>Candidate Pipeline:</strong> Track candidates from application to hire with our intuitive dashboard.</p>
                        </div>
                        
                        <div class="feature-box">
                            <p><strong>Automated Emails:</strong> Keep candidates informed with automated status updates and interview reminders.</p>
                        </div>
                        
                        <div class="feature-box">
                            <p><strong>Real-time Notifications:</strong> Stay updated with instant notifications for new applications and important events.</p>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="http://localhost:3000/dashboard" class="button">Go to Dashboard</a>
                        </div>
                        
                        <p>If you have any questions or need assistance, our support team is here to help. Just reply to this email!</p>
                        
                        <p style="margin-top: 30px;">Happy Hiring!<br>
                        <strong>The HireLens Team</strong></p>
                    </div>
                    <div class="footer">
                        <p><strong>HireLens</strong> - Intelligent Recruitment Platform</p>
                        <p>You received this email because you created an account at HireLens.</p>
                        <p style="margin-top: 15px; color: #999;">© 2025 HireLens. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
        '''
        
        return self.send_email(
            to_email=user_email,
            subject=subject,
            html_content=html_content,
            email_type='welcome'
        )
