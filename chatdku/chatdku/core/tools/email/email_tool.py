from typing import Optional,Union,List, Dict
import os
import dotenv

from smtplib import SMTP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from pathlib import Path


dotenv.load_dotenv()

class EmailTools(SMTP):
    """
    Email Tool to allow sending emails.

    Args:
        host (str): SMTP host
        port (int): SMTP port
        receiver_email (list): Receiver Email 
        sender_name (str): Sender Name
        sender_email (str): Sender Email
        sender_passkey (str): Sender Password

    """
    def __init__(
        self,
        host:str,
        port:int,
        receiver_email: Optional[Union[str,List[str]]] = [''],
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None,
        sender_passkey: Optional[str] = '',
    ):
        self.host=host
        self.port=port
        self.receiver_email: Optional[str] = receiver_email
        self.sender_name: Optional[str] = sender_name
        self.sender_email: Optional[str] = sender_email
        self.sender_passkey: Optional[str] = sender_passkey
        super().__init__(self.host,self.port)

    def send_mail(self,
                  subject:str,
                  body:str,
                  attachment:Optional[List[str]]=None,
                  in_line: Optional[Dict[str,str]]=None
                  ):
        
        """
        Sends an email.

        Args:
            subject (str): Subject of the email.
            body (str): Body of the email. Supports both HTML and plain text.
            attachments (Optional[List[str]]): List of file paths to attach. 
                Example: ['abc.png', 'def.pdf']
            inline (Optional[Dict[str, str]]): Inline image attachments. 
                Keys are content IDs, values are image file paths. 
                Example: {'logo': 'abc.png'}
        """

        
        if not self.sender_email or not self.receiver_email:
            raise ValueError("Sender email or receiver email not found")
        
        try:
            msg=MIMEMultipart()

            msg['Subject']=subject
            msg['To']=", ".join(self.receiver_email)
            msg['From']=f"{self.sender_name} <{self.sender_email}>"

            msg.attach(MIMEText(body))


            if attachment:
                for files in attachment:
                    with open(files,'rb') as f:
                        att=MIMEBase("application","octet-stream")
                        att.set_payload(f.read())
                    encoders.encode_base64(att)
                    att.add_header("content-disposition",f"attachment; filename={Path(files).name}")
                    msg.attach(att)

            if in_line:
                for k,v in in_line.items():
                    with open(v,'rb') as f:
                        att=MIMEImage(f.read())
                        att.add_header('content-id',f"<{k}>")
                        msg.attach(att)

            self.starttls()
            if self.sender_passkey: #No need to login for duke's smtp
                self.login(self.sender_email,self.sender_passkey)
            self.send_message(msg)
            self.quit()
            return "Email Sent successfully"
        
        except Exception as e:
            raise e

