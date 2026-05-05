import pandas as pd
import numpy as np
from datetime import date

wload = pd.read_csv('workload.csv')
wload.fillna(0)
wload['Day']=pd.Categorical(wload['Day'], categories=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], ordered=True)
wload['Hour'] = pd.to_datetime(wload['Hour'], format='%H:%M:%S.000').dt.time
wload['Date']= wload.apply(lambda row: date(row['Year'],row['Month'],1),axis=1)

dates=set(list(zip(wload['Date'],wload['Day'],wload['Day'].str[:3])))
c=[]
for x in dates:
    c.append([x[0].year,x[0].month,x[1],np.busday_count(x[0],x[0].replace(year=x[0].month // 12 +x[0].year,month=x[0].month % 12 +1),x[2]).item()])
cal=pd.DataFrame(c,columns=['Year','Month','Day','count'])
print(cal)