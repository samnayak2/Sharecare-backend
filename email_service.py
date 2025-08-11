import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import os
import logging
from datetime import datetime
from typing import List, Optional
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_address = os.getenv("EMAIL_ADDRESS", "noreply.sharecare@gmail.com")
        self.email_password = os.getenv("EMAIL_PASSWORD", "hzqcqyqqenzeprnb")
        
        if not self.email_address or not self.email_password:
            logger.warning("Email credentials not configured. Email functionality will be disabled.")
    
    def _get_base_template(self) -> str:
        """Base HTML template for all emails"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    line-height: 1.6; 
                    color: #333; 
                    margin: 0; 
                    padding: 0; 
                    background-color: #f5f5f5;
                }}
                .container {{ 
                    max-width: 600px; 
                    margin: 0 auto; 
                    background: white;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }}
                .header {{ 
                    background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); 
                    color: white; 
                    padding: 40px 30px; 
                    text-align: center; 
                }}
                .header h1 {{ 
                    margin: 0; 
                    font-size: 28px; 
                    font-weight: 300;
                }}
                .header .subtitle {{ 
                    margin: 10px 0 0 0; 
                    font-size: 16px; 
                    opacity: 0.9;
                }}
                .content {{ 
                    padding: 40px 30px; 
                }}
                .content h2 {{ 
                    color: #4CAF50; 
                    margin-top: 0;
                    font-size: 24px;
                    font-weight: 400;
                }}
                .button {{ 
                    display: inline-block; 
                    background: #4CAF50; 
                    color: white; 
                    padding: 15px 30px; 
                    text-decoration: none; 
                    border-radius: 25px; 
                    margin: 20px 0; 
                    font-weight: 500;
                    transition: background-color 0.3s;
                }}
                .button:hover {{ 
                    background: #45a049; 
                }}
                .info-box {{ 
                    background: #f8f9fa; 
                    padding: 20px; 
                    border-left: 4px solid #4CAF50; 
                    margin: 20px 0; 
                    border-radius: 0 5px 5px 0;
                }}
                .item-card {{ 
                    background: #f8f9fa; 
                    padding: 20px; 
                    border-radius: 10px; 
                    margin: 20px 0; 
                    border: 1px solid #e9ecef;
                }}
                .item-image {{ 
                    max-width: 100%; 
                    height: 200px; 
                    object-fit: cover; 
                    border-radius: 8px; 
                    margin-bottom: 15px;
                }}
                .footer {{ 
                    background: #2c3e50; 
                    color: #ecf0f1; 
                    text-align: center; 
                    padding: 30px; 
                    font-size: 14px;
                }}
                .footer a {{ 
                    color: #4CAF50; 
                    text-decoration: none;
                }}
                .social-links {{ 
                    margin: 20px 0;
                }}
                .social-links a {{ 
                    display: inline-block; 
                    margin: 0 10px; 
                    color: #4CAF50; 
                    font-size: 18px;
                }}
                ul {{ 
                    padding-left: 20px;
                }}
                li {{ 
                    margin-bottom: 8px;
                }}
                .highlight {{ 
                    background: #fff3cd; 
                    padding: 15px; 
                    border-radius: 5px; 
                    border-left: 4px solid #ffc107; 
                    margin: 20px 0;
                }}
                .success {{ 
                    background: #d4edda; 
                    padding: 15px; 
                    border-radius: 5px; 
                    border-left: 4px solid #28a745; 
                    margin: 20px 0;
                }}
                .warning {{ 
                    background: #f8d7da; 
                    padding: 15px; 
                    border-radius: 5px; 
                    border-left: 4px solid #dc3545; 
                    margin: 20px 0;
                }}
                .tracking-box {{
                    background: #e3f2fd;
                    padding: 20px;
                    border-radius: 10px;
                    border-left: 4px solid #2196F3;
                    margin: 20px 0;
                    text-align: center;
                }}
                .tracking-id {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #2196F3;
                    margin: 10px 0;
                    letter-spacing: 2px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                {content}
                <div class="footer">
                    <h3>ShareCare - Food & Clothes Connect</h3>
                    <p>Connecting communities through sharing and caring</p>
                    <div class="social-links">
                        <a href="#">📧</a>
                        <a href="#">📱</a>
                        <a href="#">🌐</a>
                    </div>
                    <p>© 2024 ShareCare. All rights reserved.</p>
                    <p>This email was sent to {email}</p>
                    <p><a href="#">Unsubscribe</a> | <a href="#">Privacy Policy</a></p>
                </div>
            </div>
        </body>
        </html>
        """
    
    async def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None, attachments: List[str] = None):
        """Send an email with optional attachments"""
        if not self.email_address or not self.email_password:
            logger.warning("Email not sent - credentials not configured")
            return
        
        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = f"ShareCare <{self.email_address}>"
            msg["To"] = to_email
            
            # Create alternative container for text and HTML
            msg_alternative = MIMEMultipart("alternative")
            
            if text_content:
                text_part = MIMEText(text_content, "plain")
                msg_alternative.attach(text_part)
            
            html_part = MIMEText(html_content, "html")
            msg_alternative.attach(html_part)
            
            msg.attach(msg_alternative)
            
            # Add image attachments if provided
            if attachments:
                for image_url in attachments:
                    try:
                        response = requests.get(image_url, timeout=10)
                        if response.status_code == 200:
                            image_data = BytesIO(response.content)
                            img = MIMEImage(image_data.read())
                            img.add_header('Content-Disposition', f'attachment; filename="item_image.jpg"')
                            msg.attach(img)
                    except Exception as e:
                        logger.error(f"Failed to attach image {image_url}: {e}")
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            raise
    
    async def send_welcome_email(self, user_email: str, user_name: str):
        """Send welcome email to new user"""
        subject = "Welcome to ShareCare! 🤝 Let's Make a Difference Together"
        
        content = f"""
        <div class="header">
            <h1>🤝 Welcome to ShareCare!</h1>
            <p class="subtitle">Connecting communities through sharing and caring</p>
        </div>
        <div class="content">
            <h2>Hi {user_name}! 👋</h2>
            <p>Thank you for joining ShareCare! We're thrilled to have you as part of our community dedicated to reducing waste and helping those in need.</p>
            
            <div class="success">
                <h3>🎉 Your account is ready!</h3>
                <p>You can now start sharing food and clothes with your community.</p>
            </div>
            
            <h3>What you can do with ShareCare:</h3>
            <ul>
                <li>🍎 <strong>Donate Food:</strong> Share surplus food with those who need it</li>
                <li>👕 <strong>Donate Clothes:</strong> Give clothes a second life</li>
                <li>📍 <strong>Find Nearby Items:</strong> Discover donations in your area</li>
                <li>💬 <strong>Connect:</strong> Chat with donors and recipients</li>
                <li>🌍 <strong>Make Impact:</strong> Track your positive environmental impact</li>
            </ul>
            
            <div class="highlight">
                <h3>🚀 Get Started:</h3>
                <p>Ready to make your first donation or find items you need?</p>
                <a href="https://sharecare.app/dashboard" class="button">Go to Dashboard</a>
            </div>
            
            <h3>💡 Tips for Success:</h3>
            <ul>
                <li>Add clear photos of your items</li>
                <li>Provide accurate descriptions and expiry dates</li>
                <li>Set convenient pickup times</li>
                <li>Be responsive to messages</li>
                <li>Rate your experiences to build trust</li>
            </ul>
            
            <p>Together, we can reduce food waste, help those in need, and build stronger communities. Every donation, no matter how small, makes a difference!</p>
            
            <p>If you have any questions, our support team is here to help. Welcome aboard! 🌟</p>
            
            <p>With gratitude,<br><strong>The ShareCare Team</strong></p>
        </div>
        """
        
        html_content = self._get_base_template().format(
            title="Welcome to ShareCare",
            content=content,
            email=user_email
        )
        
        text_content = f"""
        Welcome to ShareCare!
        
        Hi {user_name}!
        
        Thank you for joining ShareCare! We're thrilled to have you as part of our community dedicated to reducing waste and helping those in need.
        
        What you can do with ShareCare:
        - Donate Food: Share surplus food with those who need it
        - Donate Clothes: Give clothes a second life
        - Find Nearby Items: Discover donations in your area
        - Connect: Chat with donors and recipients
        - Make Impact: Track your positive environmental impact
        
        Get Started: https://sharecare.app/dashboard
        
        Tips for Success:
        - Add clear photos of your items
        - Provide accurate descriptions and expiry dates
        - Set convenient pickup times
        - Be responsive to messages
        - Rate your experiences to build trust
        
        Together, we can reduce food waste, help those in need, and build stronger communities!
        
        With gratitude,
        The ShareCare Team
        """
        
        await self.send_email(user_email, subject, html_content, text_content)
    
    async def send_login_notification(self, user_email: str, user_name: str, ip_address: str):
        """Send login notification email"""
        subject = "ShareCare Login Notification 🔐"
        current_time = datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")
        
        content = f"""
        <div class="header">
            <h1>🔐 Login Notification</h1>
            <p class="subtitle">Account security alert</p>
        </div>
        <div class="content">
            <h2>Hello {user_name}!</h2>
            <p>We wanted to let you know that your ShareCare account was accessed.</p>
            
            <div class="info-box">
                <h3>📋 Login Details:</h3>
                <p><strong>Time:</strong> {current_time}</p>
                <p><strong>IP Address:</strong> {ip_address}</p>
                <p><strong>Email:</strong> {user_email}</p>
                <p><strong>Device:</strong> Web Browser</p>
            </div>
            
            <div class="success">
                <p><strong>✅ If this was you:</strong> No action needed! You're all set.</p>
            </div>
            
            <div class="warning">
                <p><strong>⚠️ If this wasn't you:</strong> Please secure your account immediately:</p>
                <ul>
                    <li>Change your password right away</li>
                    <li>Review your recent account activity</li>
                    <li>Contact our support team</li>
                </ul>
                <a href="https://sharecare.app/security" class="button">Secure My Account</a>
            </div>
            
            <p>Your account security is important to us. We monitor all login attempts to keep your information safe.</p>
            
            <p>Stay safe and keep sharing!<br><strong>The ShareCare Security Team</strong></p>
        </div>
        """
        
        html_content = self._get_base_template().format(
            title="Login Notification",
            content=content,
            email=user_email
        )
        
        text_content = f"""
        ShareCare Login Notification
        
        Hello {user_name}!
        
        We wanted to let you know that your ShareCare account was accessed.
        
        Login Details:
        Time: {current_time}
        IP Address: {ip_address}
        Email: {user_email}
        Device: Web Browser
        
        If this was you: No action needed!
        
        If this wasn't you: Please secure your account immediately:
        - Change your password right away
        - Review your recent account activity
        - Contact our support team
        
        Secure your account: https://sharecare.app/security
        
        Stay safe and keep sharing!
        The ShareCare Security Team
        """
        
        await self.send_email(user_email, subject, html_content, text_content)
    
    async def send_item_donation_confirmation(self, user_email: str, user_name: str, item_data: dict):
        """Send item donation confirmation email"""
        subject = f"✅ Your {item_data.get('category', 'item')} donation is live on ShareCare!"
        
        item_images = item_data.get('images', [])
        image_html = ""
        if item_images:
            image_html = f'<img src="{item_images[0]}" alt="{item_data.get("name", "Item")}" class="item-image">'
        
        content = f"""
        <div class="header">
            <h1>🎉 Donation Confirmed!</h1>
            <p class="subtitle">Your item is now helping others</p>
        </div>
        <div class="content">
            <h2>Thank you, {user_name}! 🙏</h2>
            <p>Your donation has been successfully posted and is now visible to people in your community who need it.</p>
            
            <div class="item-card">
                {image_html}
                <h3>📦 {item_data.get('name', 'Your Item')}</h3>
                <p><strong>Category:</strong> {item_data.get('category', 'General')}</p>
                <p><strong>Description:</strong> {item_data.get('description', 'No description provided')}</p>
                <p><strong>Quantity:</strong> {item_data.get('quantity', 1)}</p>
                {f"<p><strong>Expiry Date:</strong> {item_data.get('expiry_date')}</p>" if item_data.get('expiry_date') else ""}
                <p><strong>Pickup Times:</strong> {item_data.get('pickup_times', 'Flexible')}</p>
                <p><strong>Status:</strong> <span style="color: #4CAF50;">Available</span></p>
            </div>
            
            <div class="success">
                <h3>🌟 What happens next?</h3>
                <ul>
                    <li>People in your area can now see and request your item</li>
                    <li>You'll get notifications when someone is interested</li>
                    <li>You can chat with potential recipients</li>
                    <li>Choose who gets your donation</li>
                </ul>
            </div>
            
            <div class="highlight">
                <h3>💡 Pro Tips:</h3>
                <ul>
                    <li>Respond quickly to messages to help more people</li>
                    <li>Be flexible with pickup times when possible</li>
                    <li>Update the status when the item is collected</li>
                    <li>Leave feedback to build community trust</li>
                </ul>
            </div>
            
            <a href="https://sharecare.app/my-donations" class="button">Manage My Donations</a>
            
            <p>Thank you for making a difference in your community! Every donation helps reduce waste and supports those in need. 🌍💚</p>
            
            <p>Keep up the amazing work!<br><strong>The ShareCare Team</strong></p>
        </div>
        """
        
        html_content = self._get_base_template().format(
            title="Donation Confirmed",
            content=content,
            email=user_email
        )
        
        text_content = f"""
        Donation Confirmed!
        
        Thank you, {user_name}!
        
        Your donation has been successfully posted and is now visible to people in your community who need it.
        
        Item Details:
        - Name: {item_data.get('name', 'Your Item')}
        - Category: {item_data.get('category', 'General')}
        - Description: {item_data.get('description', 'No description provided')}
        - Quantity: {item_data.get('quantity', 1)}
        - Pickup Times: {item_data.get('pickup_times', 'Flexible')}
        - Status: Available
        
        What happens next?
        - People in your area can now see and request your item
        - You'll get notifications when someone is interested
        - You can chat with potential recipients
        - Choose who gets your donation
        
        Manage your donations: https://sharecare.app/my-donations
        
        Thank you for making a difference in your community!
        
        The ShareCare Team
        """
        
        await self.send_email(user_email, subject, html_content, text_content, item_images[:3])
    
    async def send_reservation_request_email(self, donor_email: str, donor_name: str, requester_name: str, item_data: dict, message: str = None):
        """Send reservation request email to donor"""
        subject = f"🔔 Someone wants your {item_data.get('name', 'item')} - ShareCare"
        
        item_images = item_data.get('images', [])
        image_html = ""
        if item_images:
            image_html = f'<img src="{item_images[0]}" alt="{item_data.get("name", "Item")}" class="item-image">'
        
        message_html = ""
        if message:
            message_html = f"""
            <div class="info-box">
                <h3>💬 Message from {requester_name}:</h3>
                <p>"{message}"</p>
            </div>
            """
        
        content = f"""
        <div class="header">
            <h1>🔔 New Request!</h1>
            <p class="subtitle">Someone needs your help</p>
        </div>
        <div class="content">
            <h2>Hi {donor_name}! 👋</h2>
            <p><strong>{requester_name}</strong> has requested your donated item. They're hoping you can help them out!</p>
            
            <div class="item-card">
                {image_html}
                <h3>📦 {item_data.get('name', 'Your Item')}</h3>
                <p><strong>Category:</strong> {item_data.get('category', 'General')}</p>
                <p><strong>Description:</strong> {item_data.get('description', 'No description provided')}</p>
            </div>
            
            {message_html}
            
            <div class="highlight">
                <h3>⏰ What to do next:</h3>
                <ul>
                    <li>Review {requester_name}'s profile and ratings</li>
                    <li>Check if the pickup time works for you</li>
                    <li>Respond to accept or decline the request</li>
                    <li>Coordinate pickup details if you accept</li>
                </ul>
            </div>
            
            <div class="success">
                <p><strong>💡 Remember:</strong> Quick responses help more people and build community trust!</p>
            </div>
            
            <a href="https://sharecare.app/requests" class="button">View Request</a>
            
            <p>Thank you for being such a generous member of our community. Your kindness makes a real difference! 🌟</p>
            
            <p>Happy sharing!<br><strong>The ShareCare Team</strong></p>
        </div>
        """
        
        html_content = self._get_base_template().format(
            title="New Request",
            content=content,
            email=donor_email
        )
        
        text_content = f"""
        New Request for Your Item!
        
        Hi {donor_name}!
        
        {requester_name} has requested your donated item.
        
        Item: {item_data.get('name', 'Your Item')}
        Category: {item_data.get('category', 'General')}
        
        {f'Message from {requester_name}: "{message}"' if message else ''}
        
        What to do next:
        - Review {requester_name}'s profile and ratings
        - Check if the pickup time works for you
        - Respond to accept or decline the request
        - Coordinate pickup details if you accept
        
        View request: https://sharecare.app/requests
        
        Thank you for being such a generous member of our community!
        
        The ShareCare Team
        """
        
        await self.send_email(donor_email, subject, html_content, text_content, item_images[:1])
    
    async def send_reservation_confirmation_email(self, requester_email: str, requester_name: str, donor_name: str, item_data: dict):
        """Send reservation confirmation email to requester"""
        subject = f"🎉 Great news! Your request for {item_data.get('name', 'item')} was accepted"
        
        item_images = item_data.get('images', [])
        image_html = ""
        if item_images:
            image_html = f'<img src="{item_images[0]}" alt="{item_data.get("name", "Item")}" class="item-image">'
        
        content = f"""
        <div class="header">
            <h1>🎉 Request Accepted!</h1>
            <p class="subtitle">Your item is reserved for you</p>
        </div>
        <div class="content">
            <h2>Wonderful news, {requester_name}! 🌟</h2>
            <p><strong>{donor_name}</strong> has accepted your request! The item is now reserved for you.</p>
            
            <div class="item-card">
                {image_html}
                <h3>📦 {item_data.get('name', 'Reserved Item')}</h3>
                <p><strong>Category:</strong> {item_data.get('category', 'General')}</p>
                <p><strong>Donor:</strong> {donor_name}</p>
                <p><strong>Pickup Times:</strong> {item_data.get('pickup_times', 'To be arranged')}</p>
                <p><strong>Status:</strong> <span style="color: #4CAF50;">Reserved for you</span></p>
            </div>
            
            <div class="success">
                <h3>✅ Next Steps:</h3>
                <ul>
                    <li>Contact {donor_name} to arrange pickup details</li>
                    <li>Confirm the pickup time and location</li>
                    <li>Be punctual and respectful during pickup</li>
                    <li>Leave a review after receiving the item</li>
                </ul>
            </div>
            
            <div class="highlight">
                <h3>📍 Pickup Information:</h3>
                <p><strong>Location:</strong> {item_data.get('location', {}).get('address', 'To be shared by donor')}</p>
                <p><strong>Available Times:</strong> {item_data.get('pickup_times', 'Flexible')}</p>
            </div>
            
            <a href="https://sharecare.app/my-reservations" class="button">View Reservation Details</a>
            
            <p>Thank you for being part of our sharing community! Remember to be respectful and grateful to {donor_name} for their generosity. 💚</p>
            
            <p>Enjoy your item!<br><strong>The ShareCare Team</strong></p>
        </div>
        """
        
        html_content = self._get_base_template().format(
            title="Request Accepted",
            content=content,
            email=requester_email
        )
        
        text_content = f"""
        Request Accepted!
        
        Wonderful news, {requester_name}!
        
        {donor_name} has accepted your request! The item is now reserved for you.
        
        Item: {item_data.get('name', 'Reserved Item')}
        Category: {item_data.get('category', 'General')}
        Donor: {donor_name}
        Status: Reserved for you
        
        Next Steps:
        - Contact {donor_name} to arrange pickup details
        - Confirm the pickup time and location
        - Be punctual and respectful during pickup
        - Leave a review after receiving the item
        
        Pickup Information:
        Location: {item_data.get('location', {}).get('address', 'To be shared by donor')}
        Available Times: {item_data.get('pickup_times', 'Flexible')}
        
        View reservation: https://sharecare.app/my-reservations
        
        Thank you for being part of our sharing community!
        
        The ShareCare Team
        """
        
        await self.send_email(requester_email, subject, html_content, text_content, item_images[:1])
    
    async def send_tracking_email(self, user_email: str, user_name: str, item_data: dict, tracking_id: str):
        """Send tracking email with tracking ID"""
        subject = f"📦 Your item is being prepared! Tracking ID: {tracking_id}"
        
        item_images = item_data.get('images', [])
        image_html = ""
        if item_images:
            image_html = f'<img src="{item_images[0]}" alt="{item_data.get("name", "Item")}" class="item-image">'
        
        content = f"""
        <div class="header">
            <h1>📦 Item Tracking Started!</h1>
            <p class="subtitle">Your request has been approved</p>
        </div>
        <div class="content">
            <h2>Great news, {user_name}! 🎉</h2>
            <p>Your request has been approved and your item is now being prepared for pickup. You can track its progress using your unique tracking ID.</p>
            
            <div class="tracking-box">
                <h3>🔍 Your Tracking ID</h3>
                <div class="tracking-id">{tracking_id}</div>
                <p>Save this ID to track your item's status anytime!</p>
                <a href="https://sharecare.app/track/{tracking_id}" class="button">Track Your Item</a>
            </div>
            
            <div class="item-card">
                {image_html}
                <h3>📦 {item_data.get('name', 'Your Item')}</h3>
                <p><strong>Category:</strong> {item_data.get('category', 'General')}</p>
                <p><strong>Donor:</strong> {item_data.get('donor_name', 'Unknown')}</p>
                <p><strong>Current Status:</strong> <span style="color: #4CAF50;">Request Accepted</span></p>
            </div>
            
            <div class="success">
                <h3>📋 Tracking Stages:</h3>
                <ul>
                    <li>✅ <strong>Request Submitted:</strong> Your request was sent to the donor</li>
                    <li>✅ <strong>Request Accepted:</strong> The donor approved your request</li>
                    <li>⏳ <strong>Preparing Item:</strong> The donor is getting your item ready</li>
                    <li>⏳ <strong>Packing Completed:</strong> Your item is packed and ready</li>
                    <li>⏳ <strong>Ready for Pickup:</strong> You can collect your item</li>
                    <li>⏳ <strong>Item Picked Up:</strong> You've successfully received your item</li>
                    <li>⏳ <strong>Completed:</strong> Transaction completed</li>
                </ul>
            </div>
            
            <div class="highlight">
                <h3>💡 What's Next?</h3>
                <ul>
                    <li>You'll receive notifications as your item status updates</li>
                    <li>You can chat with the donor to coordinate pickup</li>
                    <li>Use your tracking ID to check status anytime</li>
                    <li>Be ready to collect when the item is ready for pickup</li>
                </ul>
            </div>
            
            <p>Thank you for being part of our sharing community! We'll keep you updated on your item's progress. 🌟</p>
            
            <p>Happy sharing!<br><strong>The ShareCare Team</strong></p>
        </div>
        """
        
        html_content = self._get_base_template().format(
            title="Item Tracking Started",
            content=content,
            email=user_email
        )
        
        text_content = f"""
        Item Tracking Started!
        
        Great news, {user_name}!
        
        Your request has been approved and your item is now being prepared for pickup.
        
        Your Tracking ID: {tracking_id}
        
        Item: {item_data.get('name', 'Your Item')}
        Category: {item_data.get('category', 'General')}
        Donor: {item_data.get('donor_name', 'Unknown')}
        Current Status: Request Accepted
        
        Tracking Stages:
        ✅ Request Submitted: Your request was sent to the donor
        ✅ Request Accepted: The donor approved your request
        ⏳ Preparing Item: The donor is getting your item ready
        ⏳ Packing Completed: Your item is packed and ready
        ⏳ Ready for Pickup: You can collect your item
        ⏳ Item Picked Up: You've successfully received your item
        ⏳ Completed: Transaction completed
        
        Track your item: https://sharecare.app/track/{tracking_id}
        
        What's Next?
        - You'll receive notifications as your item status updates
        - You can chat with the donor to coordinate pickup
        - Use your tracking ID to check status anytime
        - Be ready to collect when the item is ready for pickup
        
        Thank you for being part of our sharing community!
        
        The ShareCare Team
        """
        
        await self.send_email(user_email, subject, html_content, text_content, item_images[:1])
    
    async def send_account_deletion_email(self, user_email: str, user_name: str):
        """Send account deletion confirmation email"""
        subject = "Account Deletion Confirmed - ShareCare"
        current_time = datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")
        
        content = f"""
        <div class="header">
            <h1>👋 Account Deletion Confirmed</h1>
            <p class="subtitle">We're sorry to see you go</p>
        </div>
        <div class="content">
            <h2>Goodbye, {user_name} 😢</h2>
            <p>Your ShareCare account has been successfully deleted as requested. We're sad to see you leave our community.</p>
            
            <div class="warning">
                <h3>⚠️ Deletion Details:</h3>
                <p><strong>Deleted at:</strong> {current_time}</p>
                <p><strong>Account:</strong> {user_email}</p>
                <p><strong>Status:</strong> Permanently removed</p>
            </div>
            
            <h3>📋 What has been removed:</h3>
            <ul>
                <li>✅ All your personal information and profile data</li>
                <li>✅ Your donation history and posted items</li>
                <li>✅ Your reservation history and messages</li>
                <li>✅ Your preferences and settings</li>
                <li>✅ Your reviews and ratings</li>
            </ul>
            
            <div class="info-box">
                <h3>🔒 Important Notes:</h3>
                <ul>
                    <li>Your account cannot be recovered</li>
                    <li>You will no longer receive emails from us</li>
                    <li>Any active donations have been removed</li>
                    <li>Your data has been permanently deleted from our servers</li>
                </ul>
            </div>
            
            <div class="highlight">
                <h3>💚 Thank you for being part of ShareCare</h3>
                <p>During your time with us, you helped build a stronger, more caring community. Your contributions made a real difference in people's lives and helped reduce waste.</p>
            </div>
            
            <p>If you change your mind in the future, you're always welcome to create a new account and rejoin our community of sharers and carers.</p>
            
            <p>We wish you all the best in your future endeavors. Thank you for helping make the world a little bit better! 🌍</p>
            
            <p>With gratitude and best wishes,<br><strong>The ShareCare Team</strong></p>
        </div>
        """
        
        html_content = self._get_base_template().format(
            title="Account Deleted",
            content=content,
            email=user_email
        )
        
        text_content = f"""
        Account Deletion Confirmed - ShareCare
        
        Goodbye, {user_name}
        
        Your ShareCare account has been successfully deleted as requested.
        
        Deletion Details:
        Deleted at: {current_time}
        Account: {user_email}
        Status: Permanently removed
        
        What has been removed:
        - All your personal information and profile data
        - Your donation history and posted items
        - Your reservation history and messages
        - Your preferences and settings
        - Your reviews and ratings
        
        Important Notes:
        - Your account cannot be recovered
        - You will no longer receive emails from us
        - Any active donations have been removed
        - Your data has been permanently deleted from our servers
        
        Thank you for being part of ShareCare. During your time with us, you helped build a stronger, more caring community.
        
        If you change your mind in the future, you're always welcome to create a new account and rejoin our community.
        
        With gratitude and best wishes,
        The ShareCare Team
        """
        
        await self.send_email(user_email, subject, html_content, text_content)
    
    async def send_admin_notification_email(self, admin_email: str, notification_type: str, details: dict):
        """Send notification email to admin"""
        subject_map = {
            "new_user": "🆕 New User Registration - ShareCare Admin",
            "new_item": "📦 New Item Donation - ShareCare Admin",
            "user_report": "⚠️ User Report - ShareCare Admin",
            "system_alert": "🚨 System Alert - ShareCare Admin"
        }
        
        subject = subject_map.get(notification_type, "📧 ShareCare Admin Notification")
        
        content = f"""
        <div class="header">
            <h1>🔔 Admin Notification</h1>
            <p class="subtitle">ShareCare Platform Update</p>
        </div>
        <div class="content">
            <h2>Hello Admin! 👋</h2>
            <p>Here's an important update from the ShareCare platform:</p>
            
            <div class="info-box">
                <h3>📋 Notification Details:</h3>
                <p><strong>Type:</strong> {notification_type.replace('_', ' ').title()}</p>
                <p><strong>Time:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')}</p>
                <p><strong>Priority:</strong> {details.get('priority', 'Normal')}</p>
            </div>
            
            <div class="item-card">
                <h3>📊 Details:</h3>
                {self._format_admin_details(details)}
            </div>
            
            <a href="https://sharecare.app/admin/dashboard" class="button">Go to Admin Dashboard</a>
            
            <p>Please review this notification and take appropriate action if needed.</p>
            
            <p>Best regards,<br><strong>ShareCare System</strong></p>
        </div>
        """
        
        html_content = self._get_base_template().format(
            title="Admin Notification",
            content=content,
            email=admin_email
        )
        
        await self.send_email(admin_email, subject, html_content)
    
    def _format_admin_details(self, details: dict) -> str:
        """Format admin notification details as HTML"""
        html = ""
        for key, value in details.items():
            if key != 'priority':
                formatted_key = key.replace('_', ' ').title()
                html += f"<p><strong>{formatted_key}:</strong> {value}</p>"
        return html

# Initialize email service
email_service = EmailService()
