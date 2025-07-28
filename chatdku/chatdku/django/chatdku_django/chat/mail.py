from django.core.mail import BadHeaderError, EmailMultiAlternatives
import logging
import json
logger=logging.getLogger(__name__)
class EmailUtil:
    """Util Class for sending emails"""


    @staticmethod
    def send_mail(from_email:str,to_email:list,subject:str,content_text:str,content_html=None):
        '''Send Weekly Load Email
         Args:
            from_email: Email Sender
            to_email: Email Receiver/s
            subject: Email Subject
            content_text: Body in text
            content_html: Body in HTML
           '''


        try:
            email=EmailMultiAlternatives(
                subject=subject,
                body=content_text,
                from_email=from_email,
                to=json.loads(to_email)
            )

            email.attach_alternative(content_html,mimetype='text/html')
            try:
                email.send()

            except BadHeaderError:
                logger.error(f"BadHeaderError: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in Sending Email: {str(e)}")

    
