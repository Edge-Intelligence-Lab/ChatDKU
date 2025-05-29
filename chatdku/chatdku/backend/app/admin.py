from flask_admin.contrib.sqla import ModelView
from flask_admin import expose,AdminIndexView
import sqlalchemy as sa
import sqlalchemy.orm as so
import plotly
import plotly.express as px
import pandas as pd
import json
from app import db
from app.models import Request


class AdminView(ModelView):
    can_create=False
    can_delete=False
    can_edit=False
    can_export=True
    


class Base(AdminIndexView):
    @expose('/')
    def index(self):

        statement=sa.select(Request).order_by(Request.date_)
        result=db.session.execute(statement).scalars().all()
        dates=[r.date_ for r in result]
        count=[r.req_count for r in result]
        data_dict={'Dates':dates,'Count':count}
        df=pd.DataFrame.from_dict(data_dict)

        fig=px.line(df,x="Dates",y="Count")
        graph_json=json.dumps(fig,cls=plotly.utils.PlotlyJSONEncoder)

        return self.render('admin.html',graphJson=graph_json)
