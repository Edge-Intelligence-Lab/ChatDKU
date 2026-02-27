from django.core.mail import BadHeaderError, EmailMultiAlternatives
import logging
import json
from  email.mime.image import MIMEImage
from django.conf import settings
import os


logger=logging.getLogger(__name__)


class EmailUtil:
    """Util Class for sending emails"""


    @staticmethod
    def send_mail(from_email:str,to_email:list,subject:str,content_text:str,content_html=None,mimetype='text/html',add_logo=False):
        '''Send Weekly Load Email
         Args:
            from_email: Email Sender
            to_email: JSON string list of receiver addresses (e.g., '["a@x.com", "b@y.com"]')
            subject: Email Subject
            content_text: Body in text
            content_html: Body in HTML
            mimetype: MIME type for HTML part
           '''

        try:
            email=EmailMultiAlternatives(
                subject=subject,
                body=content_text,
                from_email=from_email,
                to=json.loads(to_email) if isinstance(to_email, str) else to_email,
            )
            if content_html:
                email.attach_alternative(content_html,mimetype=mimetype)
            
            if add_logo:
            #Add the logo for every email as an attachment
                logo_path = os.path.join(settings.BASE_DIR, "chat", "templates", "images", "edge-intelligence.png")

                with open(logo_path,'rb') as f:
                    logo=MIMEImage(f.read())
                    logo.add_header("Content-ID","<lablogo>")
                    logo.add_header("Content-Disposition","inline",filename="edge-intelligence.png")
                    email.attach(logo)
            try:
                email.send()

            except BadHeaderError:
                logger.error(f"BadHeaderError: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in Sending Email: {str(e)}")


    
