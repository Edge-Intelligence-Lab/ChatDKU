from django.core.mail import BadHeaderError, EmailMultiAlternatives
import logging
import json
logger=logging.getLogger(__name__)

class EmailUtil:
    """Util Class for sending emails"""


    @staticmethod
    def send_mail(from_email:str,to_email:list,subject:str,content_text:str,content_html=None,mimetype='text/html'):
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
                to=json.loads(to_email),
            )

            email.attach_alternative(content_html,mimetype=mimetype)
            try:
                email.send()

            except BadHeaderError:
                logger.error(f"BadHeaderError: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in Sending Email: {str(e)}")

    
