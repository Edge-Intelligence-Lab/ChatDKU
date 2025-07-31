from app import db
from datetime import datetime,timezone
import sqlalchemy as sa
import sqlalchemy.orm as so
from typing import Optional
from datetime import date,datetime,time



class Feedback(db.Model):
    __tablename__="feedback"
    id=db.Column(db.Integer,primary_key=True)
    user_input=db.Column(db.String,nullable=False)
    bot_answer=db.Column(db.String)
    feedback_reason=db.Column(db.String)
    question_id=db.Column(db.String)
    time=db.Column(db.DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))



class Request(db.Model):
    
    date_:so.Mapped[datetime]=so.mapped_column(sa.DateTime,primary_key=True,unique=True)
    req_count:so.Mapped[int]=so.mapped_column(sa.Integer,default=0)

    def req_increment(self):
        self.req_count+=1

    @classmethod
    def get_date_count(cls,startdate:date|None=None,enddate:date|None=None)->int:

        earliest=db.session.query(sa.func.min(cls.date_)).scalar()
        if earliest is None:
            return [], []
        if startdate is None:
            start_date=datetime.combine(earliest.date(),time.min())
        else:
            start_date=datetime.combine(startdate,time.min())


        if enddate is None:
            end_date=datetime.combine(date.today(),time.max())
        else:
            end_date=datetime.combine(enddate,time.max())
        
        date_only=sa.cast(cls.date_,sa.Date)

        dates=sa.select(date_only,sa.func.sum(cls.req_count)).where(cls.date_.between(start_date,end_date)).group_by(date_only).order_by(date_only)
        result=db.session.execute(dates).all()

        date_list,req_list=zip(*result) if result else ([],[])

        

        return list(date_list),list(req_list)
    

class UserModel(db.Model):
    __tablename__ = 'user_model'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    netid: so.Mapped[str] = so.mapped_column(sa.String(50), unique=True, nullable=False)
    files: so.Mapped[list['UploadedFile']] = so.relationship(back_populates="user")
    

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_file'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    file_name: so.Mapped[str] = so.mapped_column(sa.String(200), unique=True, nullable=False)
    uploaded_date: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('user_model.id'), index=True)
    user: so.Mapped['UserModel'] = so.relationship(back_populates="files")
