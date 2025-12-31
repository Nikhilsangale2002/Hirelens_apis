from flask import Blueprint, request, jsonify, current_app
from flask_mail import Message
from extensions import mail
from datetime import datetime

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/contact', methods=['POST'])
def send_contact_message():
    """Handle contact form submissions"""
    try:
        data = request.get_json()
        
        # Validate required fields
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        company = data.get('company', '').strip()
        
        if not all([name, email, subject, message]):
            return jsonify({'error': 'Name, email, subject, and message are required'}), 400
        
        # Create email message
        msg = Message(
            subject=f'HireLens Contact Form: {subject}',
            recipients=[current_app.config['CONTACT_EMAIL']],
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Email body
        msg.html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f4f4f4;
                }}
                .header {{
                    background: linear-gradient(135deg, #FF6B35, #F77F00);
                    color: white;
                    padding: 20px;
                    border-radius: 8px 8px 0 0;
                }}
                .content {{
                    background: white;
                    padding: 30px;
                    border-radius: 0 0 8px 8px;
                }}
                .field {{
                    margin-bottom: 15px;
                }}
                .label {{
                    font-weight: bold;
                    color: #FF6B35;
                }}
                .footer {{
                    margin-top: 20px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🎯 New Contact Form Submission</h2>
                    <p>HireLens AI - Contact Form</p>
                </div>
                <div class="content">
                    <div class="field">
                        <span class="label">From:</span> {name}
                    </div>
                    <div class="field">
                        <span class="label">Email:</span> <a href="mailto:{email}">{email}</a>
                    </div>
                    {f'<div class="field"><span class="label">Company:</span> {company}</div>' if company else ''}
                    <div class="field">
                        <span class="label">Subject:</span> {subject}
                    </div>
                    <div class="field">
                        <span class="label">Message:</span>
                        <p style="background: #f9f9f9; padding: 15px; border-radius: 4px; margin-top: 10px;">
                            {message.replace(chr(10), '<br>')}
                        </p>
                    </div>
                    <div class="footer">
                        <p>Received: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                        <p>This is an automated message from HireLens contact form.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        msg.body = f"""
New Contact Form Submission - HireLens AI

From: {name}
Email: {email}
{f'Company: {company}' if company else ''}
Subject: {subject}

Message:
{message}

---
Received: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
        """
        
        # Send email
        try:
            mail.send(msg)
            current_app.logger.info(f'Contact form email sent to {current_app.config["CONTACT_EMAIL"]} from {email}')
        except Exception as email_error:
            current_app.logger.error(f'Failed to send email: {str(email_error)}')
            return jsonify({
                'error': 'Failed to send message. Please try again later or email us directly.',
                'details': str(email_error) if current_app.config.get('DEBUG') else None
            }), 500
        
        return jsonify({
            'message': 'Thank you for contacting us! We will get back to you soon.',
            'success': True
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Contact form error: {str(e)}')
        return jsonify({'error': 'An error occurred. Please try again later.'}), 500
