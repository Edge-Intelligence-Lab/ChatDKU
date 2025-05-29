from app import db
from datetime import datetime,timezone
import sqlalchemy as sa
import sqlalchemy.orm as so
from typing import Optional




class Feedback(db.Model):
    __tablename__="feedback"
    id=db.Column(db.Integer,primary_key=True)
    date=db.Column(db.DateTime)
    user_input=db.Column(db.String,nullable=False)
    bot_answer=db.Column(db.String)
    feedback_reason=db.Column(db.String)
    question_id=db.Column(db.Integer)
    time=db.Column(db.DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
