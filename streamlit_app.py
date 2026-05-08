import streamlit as st
import pandas as pd
import numpy as np
from pyworkforce.scheduling import MinRequiredResources
from pyworkforce.queuing import ErlangC
from datetime import date, datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def workload_ini():
    wload = pd.read_csv('workload.csv')
    wload.fillna(0)
    wload['Day']=pd.Categorical(wload['Day'], categories=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], ordered=True)
    wload['Hour'] = pd.to_datetime(wload['Hour'], format='%H:%M:%S.000').dt.time
    wload['Date']= wload.apply(lambda row: date(row['Year'],row['Month'],1),axis=1)
    timz=pd.read_csv('tz.csv')
    wload=pd.merge(wload,timz,on='Market',how='left')
    hoo = pd.read_csv('hoo.csv')
    hoo['Open'] = pd.to_datetime(hoo['Open'], format='%H:%M').dt.time
    hoo['Close'] = pd.to_datetime(hoo['Close'], format='%H:%M').dt.time
    hoo['Sat Open'] = pd.to_datetime(hoo['Sat Open'], format='%H:%M').dt.time
    hoo['Sat Close'] = pd.to_datetime(hoo['Sat Close'], format='%H:%M').dt.time
    wload = pd.merge(wload, hoo, on='Market', how='left')
    wload['drop']=wload.apply(lambda row: (row['Day']=='Sunday') | 
                              (row['Day']=='Saturday') & (True if pd.isna(row['Sat Open']) else ((row['Hour'] <= row['Sat Open']) | (row['Hour'] >= row['Sat Close']))) | 
                              (row['Day']!='Saturday') & ((row['Hour']<row['Open']) | (row['Hour']>row['Close'])) ,axis=1)
    #wload = wload[(wload['Day'] != 'Sunday') & ~((wload['Day'] == 'Saturday') & (wload['Sat Open'].isna() | (wload['Hour'] <= wload['Sat Open'] | wload['Hour'] >= wload['Sat Close']))) & (wload['Hour'] >= wload['Open']) & (wload['Hour'] < wload['Close'])]
    wload=wload[~wload['drop']]
    wload=wload.sort_values(['Day','Hour'])
    dates=set(list(zip(wload['Date'],wload['Day'],wload['Day'].str[:3])))
    c=[]
    for x in dates:
        c.append([x[0].year,x[0].month,x[1],np.busday_count(x[0],x[0].replace(year=x[0].month // 12 +x[0].year,month=x[0].month % 12 +1),x[2]).item()])
    cal=pd.DataFrame(c,columns=['Year','Month','Day','count'])
    wload = pd.merge(wload,cal, on=['Year','Month','Day'],how="left")
    return wload

def workload_agg(wload):
    wload['W Mgmt'] = wload['Order Mgmt HT (hr)'] * wload['Occur Int'] / wload['count']
    wload['W Int'] = wload['Order Mgmt Interactions'] * wload['Occur Int'] / wload['count']
    wload['W Ord'] = wload['Orders'] * wload['Occur Ord'] / wload['count']
    wload['W Ana'] = wload['Analog'] * wload['Occur Ord'] / wload['count']
    wload['W Dig'] = wload['Digital'] * wload['Occur Ord'] / wload['count']
    agru1=wload.groupby(['ADay','AHour'])[['Order Mgmt HT (hr)','Order Mgmt Interactions','W Mgmt', 'W Int', 'W Ord', 'W Ana', 'W Dig']].sum().reset_index()
    #agru = wload.groupby('Market')[['W Mgmt', 'W Int', 'W Ord', 'W Ana', 'W Dig']].sum().reset_index()
    #wload = pd.merge(wload, agru, on='Market', how='left')
    colu_norm=['W Mgmt', 'W Int', 'W Ord', 'W Ana', 'W Dig']
    agru_ss=agru1[colu_norm]
    csum=agru_ss.sum()
    agru1[colu_norm]=agru_ss.div(csum,axis=1)
    #agru1['Mgmt WL'] = agru1['W Mgmt_x'] / wload['W Mgmt_y']
    agru1['Mgmt HT (s)'] = (agru1['Order Mgmt HT (hr)'] / agru1['Order Mgmt Interactions'] * 3600).fillna(0)
    #wload['Analog Order WL'] = (wload['W Ana_x'] / wload['W Ana_y']).fillna(0)
    #wload['Digital Order WL'] = (wload['W Dig_x'] / wload['W Dig_y']).fillna(0)
    #wload['Mgmt Interactions']= (wload['W Int_x'] / wload['W Int_y']).fillna(0)
    #keep = ['Market','Time Zone', 'Day', 'Hour', 'Mgmt WL', 'Mgmt HT (s)','Mgmt Interactions', 'Analog Order WL', 'Digital Order WL']
    #wload.loc[(wload['Day'] == 'Saturday') & (wload['Hour'] >= wload['Sat Close']), ['Mgmt WL', 'Mgmt HT (s)', 'Analog Order WL', 'Digital Order WL']] = 0
    #wload = wload[keep]
    agru1=agru1.fillna(0)
    agru1['Digital Order WL flat'] = 1 / len(agru1)
    return agru1

def historic_time(avg):
    weekly={}
    weekly['peak']=(avg.groupby('Date')['Total Orders'].sum()*12/52).max()
    weekly['adoption']=avg['Digital Total'].sum()/avg['Digitizable Orders'].sum()
    weekly['mod_adoption']=avg['Modification Digital'].sum()/avg['Digitizable Orders'].sum()
    weekly['can_adoption']=avg['Cancellation Digital'].sum()/avg['Digitizable Orders'].sum()
    weekly['digitization_create']=avg['Digitizable Orders'].sum()/avg['Total Orders'].sum()
    weekly['digitization_cancel']=avg['Cancellation Digitizable'].sum()/(avg['Cancellation Digital'].sum()+avg['Cancellation Analog'].sum())
    weekly['digitization_modify']=avg['Modification Digitizable'].sum()/(avg['Modification Digital'].sum()+avg['Modification Analog'].sum())
    weekly['auto_create']=(avg['Digital Auto'].sum()+avg['Analog Auto'].sum())/avg['Digitizable Orders'].sum()
    weekly['ht_create_ana']=avg['HTCreate'].sum()/(avg['Analog Total'].sum())
    weekly['ht_modify']=avg['HTModify'].sum()/(avg['Modification Analog'].sum()+avg['Modification Digital'].sum())
    weekly['ht_cancel']=avg['HTCancel'].sum()/(avg['Cancellation Analog'].sum()+avg['Cancellation Digital'].sum())
    weekly['ht_mgmt']=avg['HTOther'].sum()/avg['Total Orders'].sum()
    weekly['mod_rate']=(avg['Modification Analog'].sum()+avg['Modification Digital'].sum())/avg['Total Orders'].sum()
    weekly['can_rate']=(avg['Cancellation Analog'].sum()+avg['Cancellation Digital'].sum())/avg['Total Orders'].sum()
    #weekly = avg[['Market']].copy()
    #weekly['Peak Orders'] = np.ceil(avg['Peak Orders'] * 12 / 52)
    #weekly['Digital Orders'] = weekly['Peak Orders'] * avg['Adoption']
    #weekly['Analog Orders'] = weekly['Peak Orders'] * (1 - avg['Adoption'])
    #weekly['Digital Creation'] = weekly['Peak Orders'] * avg['Adoption'] * (
                #d_auto + (1 - avg['Automation']) * d_rev) / 60
    #weekly['Analog Creation'] = weekly['Peak Orders'] * (1 - avg['Adoption']) * avg[
        #'HT per Created Analog Order (sec)'] / 60
    #weekly['Modification'] = weekly['Peak Orders'] * avg['Modify Rate'] * (1 - avg['Modify Adoption']) * avg[
        #'HT per Modified Order (sec)'] / 60
   # weekly['Cancellation'] = weekly['Peak Orders'] * avg['Cancel Rate'] * (1 - avg['Cancel Adoption']) * avg[
        #'HT per Cancelled Order (sec)'] / 60
    #weekly['Other Mgmt'] = weekly['Peak Orders'] * avg['Misc. HT per Created Order (sec)'] / 60
    return weekly

def intensity(wl,fac,su,tot,peak,as1,as2,effectivity,service_level,max_utilization):
    demand=pd.DataFrame()
    demand['Weekday']=wl['ADay']
    demand['Hour']=wl['AHour']
    mipo=tot/wl['Order Mgmt Interactions'].sum()
    demand['Interactions']=(fac['Digital (Confirmed)']+fac['Digital (In Review)'])*wl['W Dig']+(fac['Analog (Confirmed)']+fac['Analog (In Review)'])*wl['W Ana']+wl['W Int']*peak*mipo
    demand['AHT']=((su['Digital Order Creation']*wl['Digital Order WL flat']+su['Analog Order Creation']*wl['W Ana']+(su['Order Modification']+su['Order Cancellation']+su['Misc. Order Management'])*wl['W Mgmt'])*60)/demand['Interactions']
    demand['ASA']=(as1*((fac['Analog (Confirmed)']+fac['Analog (In Review)'])*wl['W Ana']+wl['W Int']*peak*mipo)+as2*(fac['Digital (Confirmed)']+fac['Digital (In Review)'])*wl['W Dig'])/demand['Interactions']
    demand['ErlangC'] = demand.apply(
        lambda row: ErlangC(transactions=row['Interactions'], asa=row['ASA'], aht=row['AHT'], interval=60,
                            shrinkage=1 - effectivity) if row['Interactions']>0 else 0, axis=1)
    demand['Reqs'] = demand.apply(
        lambda row: row['ErlangC'].required_positions(service_level=service_level, max_occupancy=max_utilization) if row['Interactions']>0 else 0,
        axis=1)
    requirements = demand['Reqs'].apply(pd.Series)
    demand = pd.concat([demand, requirements], axis=1)
    demand['Digital WL']=su['Digital Order Creation']*wl['W Dig']
    demand['Digital WL flat']=su['Digital Order Creation']*wl['Digital Order WL flat']
    demand['Analog WL']=su['Analog Order Creation']*wl['W Ana']+(su['Order Modification']+su['Order Cancellation']+su['Misc. Order Management'])*wl['W Mgmt']
    demand['Total Workload']=demand['Analog WL']+demand['Digital WL flat']
    demand['positions']=demand['positions'].astype('Int64')
    demand['raw_positions']=demand['raw_positions'].astype('Int64')
    demand['shrink_delta']=demand['positions']-demand['raw_positions']
    demand['dig delta']=demand['Digital WL']-effectivity*(demand['positions']-demand['Analog WL'])
    demand=demand.drop(['ErlangC','Interactions','AHT','ASA','Reqs'],axis=1)
    demand=demand.fillna(0)
    c=0
    res=np.zeros(len(demand['dig delta']))
    for i,value in enumerate(demand['dig delta']):
        c= max(0,c+value)
        res[i]=c
    demand['Digital CWL']=pd.Series(res)
    return demand

def create_demand_plot(dem1,dem2):
    mkt=', '.join(chosen_mkts)
    figx=make_subplots(rows=2,cols=1,shared_xaxes=True,shared_yaxes=True,vertical_spacing=0.2,subplot_titles=(f"Historic Demand\n{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}",f"Projected Demand\n{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}"),y_title="Workload / HC")
    figy=go.Figure()
    figz=make_subplots(rows=2,cols=1,shared_xaxes=True,shared_yaxes=True,vertical_spacing=0.2,subplot_titles=(f"Historic Digital Demand\n{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}",f"Projected Digital Demand\n{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}"),y_title="Workload (hrs)")
    
    figx.add_trace(go.Bar(x=[dem1['Weekday'],dem1['Hour']],y=dem1['raw_positions'],name='Required HC w/o shrinkage',marker=dict(color='#0068c9'),legendgroup='A',showlegend=True),row=1,col=1)
    figx.add_trace(go.Bar(x=[dem1['Weekday'],dem1['Hour']],y=dem1['shrink_delta'],name=f"Required Headcount with {(1-eff):.0%} shrinkage",marker=dict(color='#83c9ff'),legendgroup='A',showlegend=True),row=1,col=1)
    figx.add_trace(go.Bar(x=[dem2['Weekday'],dem2['Hour']],y=dem2['raw_positions'],name='Required HC w/o shrinkage',marker=dict(color='#0068c9'),legendgroup='A',showlegend=False),row=2,col=1)
    figx.add_trace(go.Bar(x=[dem2['Weekday'],dem2['Hour']],y=dem2['shrink_delta'],name=f"Required Headcount with {(1-eff):.0%} shrinkage",marker=dict(color='#83c9ff'),legendgroup='A',showlegend=False),row=2,col=1)
    figx.add_trace(go.Scatter(x=[dem1['Weekday'],dem1['Hour']],y=dem1['Total Workload'],mode='lines',line=dict(color='#840032', width=3),name='Total Workload',legendgroup='A',showlegend=True),row=1,col=1)
    figx.add_trace(go.Scatter(x=[dem1['Weekday'],dem1['Hour']],y=dem1['Digital WL'],mode='lines',line=dict(color='#ff312e', width=3),name='Digital Workload',legendgroup='A',showlegend=True),row=1,col=1)
    figx.add_trace(go.Scatter(x=[dem2['Weekday'],dem2['Hour']],y=dem2['Total Workload'],mode='lines',line=dict(color='#840032', width=3),name='Total Workload',legendgroup='A',showlegend=False),row=2,col=1)
    figx.add_trace(go.Scatter(x=[dem2['Weekday'],dem2['Hour']],y=dem2['Digital WL'],mode='lines',line=dict(color='#ff312e', width=3),name='Digital Workload',legendgroup='A',showlegend=False),row=2,col=1)
    figx_ymax=max(dem1['positions'].max(),dem2['positions'].max(),dem1['Total Workload'].max(),dem2['Total Workload'].max(),dem1['Digital WL'].max(),dem2['Digital WL'].max())
    figx.update_layout(barmode='stack',legend=dict(
        traceorder='normal',
        orientation="h",
        yanchor="bottom",
        y=-0.6,
        xanchor="center",
        x=0.5
    ))
    figx.update_yaxes(range=[0,figx_ymax],title_text="")
    figy.add_trace(go.Scatter(x=[dem1['Weekday'],dem1['Hour']],y=dem1['occupancy'], mode='lines+markers',name='Historic Data',line=dict(color='#0068c9', width=3)))
    figy.add_trace(go.Scatter(x=[dem2['Weekday'],dem2['Hour']],y=dem2['occupancy'], mode='lines+markers',name='Projection',line=dict(color="#9a9a9a", width=3,dash='dot')))
    figy.update_layout(showlegend=True,yaxis_range=[0, 1],yaxis_title="Agent Utilization (%)", yaxis_tickformat=".0%", title=f"{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}")
    
    figz.add_trace(go.Bar(x=[dem1['Weekday'],dem1['Hour']],y=dem1['Digital WL'], name='Digital Work Creation',marker=dict(color='#840032'),legendgroup='B',showlegend=True),row=1,col=1)
    figz.add_trace(go.Scatter(x=[dem1['Weekday'],dem1['Hour']],y=dem1['Digital CWL'], mode='lines',name='Digital Work Burndown',line=dict(color='#0068c9', width=3),legendgroup='B',showlegend=True),row=1,col=1)
    figz.add_trace(go.Bar(x=[dem2['Weekday'],dem2['Hour']],y=dem2['Digital WL'], name='Digital Work Creation',marker=dict(color='#840032'),legendgroup='B',showlegend=False),row=2,col=1)
    figz.add_trace(go.Scatter(x=[dem2['Weekday'],dem2['Hour']],y=dem2['Digital CWL'], mode='lines',name='Digital Work Burndown',line=dict(color='#0068c9', width=3),legendgroup='B',showlegend=False),row=2,col=1)
    figz_ymax=max(dem1['Digital WL'].max(),dem2['Digital WL'].max(),dem1['Digital CWL'].max(),dem2['Digital CWL'].max())
    figz.update_layout(legend=dict(
        traceorder='normal',
        orientation="h",
        yanchor="bottom",
        y=-0.5,
        xanchor="center",
        x=0.5
    ))
    figz.update_yaxes(range=[0,figz_ymax])
    return figx,figy,figz

def agg_hc(schedule):
    rows=[]
    for _,r in schedule.iterrows():
        hrs= pd.date_range(start=r['shift start']('H'),end=r['shift end']('H'),freq='H',closed='left')
        for h in hrs:
            rows.append({'Day':r['weekday'],'Hour':h.hour,'Headcount':'hc'})
    tot=pd.DataFrame(rows)
    tota=(tot.groupby(['Weekday','Hour'],as_index=False)['Headcount'].sum())
    return tota

def create_roster_fig(demand,resources):
    #mkt=', '.join(chosen_mkts)
    #figx=make_subplots(rows=2,cols=1,shared_xaxes=True,shared_yaxes=True,vertical_spacing=0.2,subplot_titles=(f"Historic Demand\n{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}",f"Projected Demand\n{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}"),y_title="Workload / HC")
    figx=go.Figure()
    figx.add_trace(go.Bar(x=[resources['Weekday'],resources['Hour']],y=resources['Headcount'],name='Calculated HC',marker=dict(color='#0068c9'),legendgroup='A',showlegend=True))
    figx.add_trace(go.Scatter(x=[demand['Weekday'],demand['Hour']],y=demand['positions'],mode='lines',line=dict(color='#9a9a9a', width=3),name='Calculated Demand',legendgroup='A',showlegend=True))
    figx.update_layout(legend=dict(
        traceorder='normal',
        orientation="h",
        yanchor="bottom",
        y=-0.6,
        xanchor="center",
        x=0.5
    ))
    return figx

def calc_reqs(req,shifts,costs,overtime):
    scheduler = MinRequiredResources(num_days=len(req),  # S
                                     periods=len(req[0]),  # P
                                     shifts_coverage=shifts,
                                     required_resources=req,
                                     cost_dict=costs,
                                     max_period_concurrency=100,  # gamma
                                     max_shift_concurrency=100)  # beta
    solution = scheduler.solve()
    reqs=pd.DataFrame(solution['resources_shifts'])
    reqs['weekday']=pd.Categorical(reqs.apply(lambda row: days[row['day']],axis=1), categories=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], ordered=True)
    ovrt=pd.DataFrame({'shift':overtime.keys(),'overtime':overtime.values()})
    c_ovt=pd.merge(reqs,ovrt,how='left',on='shift')
    wfm={'FTE':c_ovt['resources'].sum()//5,'OT':(c_ovt['resources']*c_ovt['overtime']).sum()+8*(c_ovt['resources'].sum()%5)}
    sched=reqs.pivot(index='shift',columns='weekday',values='resources').reset_index()
    sched[['shift start','shift end']]=sched['shift'].str.split(' - ', expand=True)
    sched['shift start']=pd.to_datetime(sched['shift start'],format='%H:%M:%S').dt.time
    sched['shift end']=pd.to_datetime(sched['shift end'],format='%H:%M:%S').dt.time
    sched=sched.sort_values(by=['shift start','shift end'])
    dsched=sched.drop(columns=['shift start','shift end'])
    m_sched=sched.drop(columns=['shift'])
    m_sched=m_sched.melt(id_vars=['shift start','shift end'],var_name='weekday',value_name='hc')
    tot_res=agg_hc(m_sched)
    return wfm,dsched,tot_res

def calculate_resources(demand):
    open=min(demand['Hour'])
    pos=demand.pivot(index='Weekday', columns='Hour', values='positions').fillna(0)
    r_pos = demand.pivot(index='Weekday', columns='Hour', values='raw_positions').fillna(0)
    req=pos.to_numpy().tolist()
    r_req=r_pos.to_numpy().tolist()
    shifts={}
    for j in range(0,len(req[0])-7):
        for i in range(0,len(req[0])-(8+j-1)):
            sh_open=timedelta(hours=open.hour)+timedelta(hours=i)
            sh_close=sh_open+timedelta(hours=j+8)
            shifts[str(sh_open)+' - '+str(sh_close)]=[0]*i+[1]*(j+8)+[0]*(len(req[0])-(j+8)-i)
    costs={}
    ovt={}
    for k,v in shifts.items():
        costs[k]=8+1.5*(sum(v)-8)
        ovt[k]=sum(v)-8
    wfm,dsched,tot_res=calc_reqs(req,shifts,costs,ovt)
    rwfm,dr_sched,rtot_res=calc_reqs(r_req,shifts,costs,ovt)
    
    return wfm,dsched,dr_sched,tot_res,rtot_res

if __name__ == '__main__':
    st.set_page_config(layout="wide")
    timezones=['PACIFIC','PHX','CENTRAL','EAST']
    days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    work=workload_ini()
    avail_mkt=sorted(work['Market'].unique())
    cola,colb=st.columns([1,4])
    with cola:
        st.title("WFM")
        chosen_mkts=st.multiselect('Market(s):', avail_mkt)
        date_range=st.slider(label="Historic Data Date Range",min_value=min(work['Date']),max_value=max(work['Date']),value=(min(work['Date']),max(work['Date'])),format="MMM/YY",key='date_range')
        summ = pd.read_csv('summary.csv')
        summ['Date']= summ.apply(lambda row: date(row['Year'],row['Month'],1),axis=1)
        media=pd.read_csv('media_types.csv',header=0)
        media['Date']= media.apply(lambda row: date(row['YEAR'],row['MONTH'],1),axis=1)  
        if len(chosen_mkts)==0:
            work_fil=work[work['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
            summ_fil=summ[summ['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
            media_fil=media[media['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
        else:
            work_fil=work[work['Market'].isin(chosen_mkts) & work['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
            summ_fil=summ[summ['Market'].isin(chosen_mkts) & summ['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
            media_fil=media[media['Market'].isin(chosen_mkts) & media['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
        media_fil=media_fil.groupby('Media Type')[['Handle Time (seconds)','Interactions']].sum()
        media_fil['ht_pct']= (media_fil['Handle Time (seconds)'] / media_fil['Handle Time (seconds)'].sum())
        media_fil['int_pct']= (media_fil['Interactions'] / media_fil['Interactions'].sum())
        tz=st.pills("Choose Grouping Time Zone" if len(work_fil['Time Zone'].unique())>1 else "Time Zone",work_fil['Time Zone'].unique(),selection_mode='single',default=work_fil['Time Zone'].unique()[0])
        work_fil['TDelta']=work_fil.apply(lambda row: timezones.index(tz)-timezones.index(row['Time Zone']),axis=1)
        work_fil['t_align']=work_fil.apply(lambda row: datetime.combine(date.today(),row['Hour'])+timedelta(hours=row['TDelta']),axis=1)
        work_fil['ADay']=work_fil.apply(lambda row: days[(days.index(row['Day'])+(row['t_align'].date()-date.today()).days)%7],axis=1)
        work_fil['AHour']=work_fil.apply(lambda row: row['t_align'].time(),axis=1)
        work_sum=workload_agg(work_fil)
        work_sum['ADay']=pd.Categorical(work_sum['ADay'], categories=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], ordered=True)
        work_sum=work_sum.sort_values(['ADay','AHour']).reset_index()
        historic=historic_time(summ_fil)
        #st.dataframe(historic)
        proj_param={}
        st.header('Tunable Parameters')
        with st.container(border=False):
            with st.expander("Service Center Speed Benchmarks",expanded=False):
                st.write("Order Processing Times (sec)")
                col1,col2=st.columns([0.8,1])
                with col1:
                    dig_auto_num=st.number_input("CXGO Confirmed",value=15,min_value=0,format='%i', help='Time required to process an order placed through CXGO with DCO confirmation.')
                with col2:
                    dig_auto_u=st.segmented_control(label="",options=['sec','min','hr'],selection_mode='single',default='sec',required=True,key='d_aut')
                col3,col4=st.columns([0.8,1])
                with col3:
                    dig_rev_num=st.number_input("CXGO Review",value=135,min_value=0,format='%i', help='Time required to process an order placed through CXGO without DCO confirmation.')
                with col4:
                    dig_rev_u=st.segmented_control(label="",options=['sec','min','hr'],selection_mode='single',default='sec',required=True,key='d_rev')
                col17,col18=st.columns([0.8,1])
                with col17:
                    ana_rev_num=st.number_input("Analog Review",value=135,min_value=0,format='%i', help='After Call Work required to process an Analog Order created in Review.')
                with col18:
                    ana_rev_u=st.segmented_control(label="",options=['sec','min','hr'],selection_mode='single',default='sec',required=True,key='a_rev')
                match dig_auto_u:
                    case 'sec':
                        dig_auto=dig_auto_num
                    case 'min':
                        dig_auto=dig_auto_num*60
                    case 'hr':
                        dig_auto=dig_auto_num*3600
                match dig_rev_u:
                    case 'sec':
                        dig_rev=dig_rev_num
                    case 'min':
                        dig_rev=dig_rev_num*60
                    case 'hr':
                        dig_rev=dig_rev_num*3600
                match ana_rev_u:
                    case 'sec':
                        ana_rev=ana_rev_num
                    case 'min':
                        ana_rev=ana_rev_num*60
                    case 'hr':
                        ana_rev=ana_rev_num*3600
                st.divider()
                st.write("Target Order Request Response Times")
                col5,col6=st.columns([0.8,1])
                with col5:
                    asa_voice_v=st.number_input("Call (voice):",value=1.0,min_value=0.1,help='Target Speed of Answer for Media Type: voice.')
                with col6:
                    asa_voice_u=st.segmented_control(label="",options=['sec','min','hr'],selection_mode='single',default='min',required=True,key='avu')

                col7,col8=st.columns([0.8,1])
                with col7:
                    asa_callback_v=st.number_input("Callback:",value=5.0,min_value=0.1,help='Target Speed of Answer for Media Type: callback.')
                with col8:
                    asa_callback_u=st.segmented_control(label="",options=['sec','min','hr'],selection_mode='single',default='min',required=True,key='acu')

                col9,col10=st.columns([0.8,1])
                with col9:
                    asa_message_v=st.number_input("Message:",value=1.0,min_value=0.1,help='Target Speed of Answer for Media Type: message.')
                with col10:
                    asa_message_u=st.segmented_control(label="",options=['sec','min','hr'],selection_mode='single',default='min',required=True,key='amu')

                col11,col12=st.columns([0.8,1])
                with col11:
                    asa_email_v=st.number_input("Email:",value=1.0,min_value=0.1,help='Target Speed of Answer for Media Type: email.')
                with col12:
                    asa_email_u=st.segmented_control(label="",options=['sec','min','hr'],selection_mode='single',default='hr',required=True,key='aeu')
                
                col13,col14=st.columns([0.8,1])
                with col13:
                    asad_v=st.number_input("Cemex Go:",value=24.0,min_value=0.1, help='Target Reponse time for orders placed through CXGO.')
                with col14:
                    asad_u=st.segmented_control(label="",options=['sec','min','hr'],selection_mode='single',default='hr',required=True,key='asad')
                match asa_voice_u:
                    case 'sec':
                        asa_voice=asa_voice_v/60
                    case 'min':
                        asa_voice=asa_voice_v
                    case 'hr':
                        asa_voice=asa_voice_v*60
                match asa_callback_u:
                    case 'sec':
                        asa_callback=asa_callback_v/60
                    case 'min':
                        asa_callback=asa_callback_v
                    case 'hr':
                        asa_callback=asa_callback_v*60
                match asa_message_u:
                    case 'sec':
                        asa_message=asa_message_v/60
                    case 'min':
                        asa_message=asa_message_v
                    case 'hr':
                        asa_message=asa_message_v*60
                match asa_email_u:
                    case 'sec':
                        asa_email=asa_email_v/60
                    case 'min':
                        asa_email=asa_email_v
                    case 'hr':
                        asa_email=asa_email_v*60    
                
                med=pd.DataFrame({'asa':[asa_callback,asa_email,asa_message,asa_voice]},index=['callback','email','message','voice'])
                mf=media_fil.join(med)
                mf['asa_av']=mf['asa']*mf['int_pct']
                asa=mf['asa_av'].sum()
                match asad_u:
                    case 'sec':
                        asad=asad_v/60
                    case 'min':
                        asad=asad_v
                    case 'hr':
                        asad=asad_v*60     
                st.divider()
                col15,col16=st.columns(2)
                with col15:
                    sl=st.number_input("Service Level Target (%):",value=80,min_value=0,max_value=100)/100
                    max_util=st.number_input("Max utilization (%):",value=95,min_value=0,max_value=100)/100
                with col16:   
                    eff=st.number_input("Efficiency (%):",value=76,min_value=0,max_value=100,help='Percentage of time dedicated by agents to Value-adding tasks. (1 - Shrinkage).')/100
                    other_act=st.number_input("Other Activities (%):",value=0,min_value=0,max_value=50,help='Percentage of time dedicated by agents to Value-adding activities unrelated to Order Taking.')/100
            with st.expander("Order Creation Parameters"):
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c2:
                        st.write("Historic Values")
                    with c3:
                        st.write("Projection Values")
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Peak Weekly Orders")
                    with c2:
                        st.write(f"{historic['peak']:.0f}")
                    with c3:
                        proj_param['peak']=st.number_input(label='',min_value=0.0,value=round(historic['peak'],0),format='%0.0f')
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Digital Adoption")
                    with c2:
                        st.write(f"{historic['adoption']:.2%}")
                    with c3:
                        proj_param['adoption']=st.slider(label='',min_value=historic['adoption'],max_value=1.0,value=historic['adoption'],format="percent", key='p_ado')
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Digitized Orders")
                    with c2:
                        st.write(f"{historic['adoption']*historic['digitization_create']:.2%}")
                    with c3:
                        st.write(f"{proj_param['adoption']*historic['digitization_create']:.2%}")
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Automation")
                    with c2:
                        st.write(f"{historic['auto_create']:.2%}")
                    with c3:
                        proj_param['auto_create']=st.slider(label='',min_value=historic['auto_create'],max_value=1.0,value=historic['auto_create'],format="percent",key='p_auto')    
            with st.expander("Order Management Parameters"):
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c2:
                        st.write("Historic Values")
                    with c3:
                        st.write("Projection Values")
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Modification Rate")
                    with c2:
                        st.write(f"{historic['mod_rate']:.2%}")
                    with c3:
                        proj_param['mod_rate']=st.slider(label='',min_value=0.0,max_value=1.0,value=historic['mod_rate'],format="percent",key='p_modrate')
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Modification Adoption")
                    with c2:
                        st.write(f"{historic['mod_adoption']:.2%}")
                    with c3:
                        proj_param['mod_adoption']=st.slider(label='',min_value=historic['mod_adoption'],max_value=1.0,value=historic['mod_adoption'],format="percent",key='p_modado')
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Digitized Modifications")
                    with c2:
                        st.write(f"{historic['mod_adoption']*historic['digitization_modify']:.2%}")
                    with c3:
                        st.write(f"{proj_param['mod_adoption']*historic['digitization_modify']:.2%}")
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Cancellation Rate")
                    with c2:
                        st.write(f"{historic['can_rate']:.2%}")
                    with c3:
                        proj_param['can_rate']=st.slider(label='',min_value=0.0,max_value=1.0,value=historic['can_rate'],format="percent",key='p_canrate')
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Cancellation Adoption")
                    with c2:
                        st.write(f"{historic['can_adoption']:.2%}")
                    with c3:
                        proj_param['can_adoption']=st.slider(label='',min_value=historic['can_adoption'],max_value=1.0,value=historic['can_adoption'],format="percent",key='p_canado"')
                with st.container(border=False):
                    c1,c2,c3=st.columns(3,vertical_alignment='center')
                    with c1:
                        st.write("Digitized Cancellations")
                    with c2:
                        st.write(f"{historic['can_adoption']*historic['digitization_cancel']:.2%}")
                    with c3:
                        st.write(f"{proj_param['can_adoption']*historic['digitization_cancel']:.2%}")
    with colb:
        tab1,tab2,tab3=st.tabs(["Weekly Workload","Hourly Workload","Optimal Scheduling"])
        with tab1:
            with st.container(border=False):
                col1, col2=st.columns(2)
                with col1:
                    h={'Digital (Confirmed)':(historic['peak']*historic['adoption']*historic['digitization_create']*historic['auto_create']),
                    "Digital (In Review)":(historic['peak']*historic['adoption']*historic['digitization_create']*(1-historic['auto_create'])),
                    "Analog (Confirmed)":(historic['peak']*(1-historic['adoption']*historic['digitization_create'])*historic['auto_create']),
                    "Analog (In Review)":(historic['peak']*(1-historic['adoption']*historic['digitization_create'])*(1-historic['auto_create']))
                    }
                    p={'Digital (Confirmed)':(proj_param['peak']*proj_param['adoption']*historic['digitization_create']*proj_param['auto_create']),
                    "Digital (In Review)":(proj_param['peak']*proj_param['adoption']*historic['digitization_create']*(1-proj_param['auto_create'])),
                    "Analog (Confirmed)":(proj_param['peak']*(1-proj_param['adoption']*historic['digitization_create'])*proj_param['auto_create']),
                    "Analog (In Review)":(proj_param['peak']*(1-proj_param['adoption']*historic['digitization_create'])*(1-proj_param['auto_create']))
                    }
                    md={'Historic Values':h,'Projected Values':p}
                    ord=pd.DataFrame(md)
                    ord['% Change']=(ord['Projected Values']-ord['Historic Values'])/ord['Historic Values']
                    ords=ord.style.format({"Historic Values": "{:,.0f}","Projected Values": "{:,.0f}", "% Change": "{:.1%}"})
                    st.write('Weekly Order Creation Distribution')
                    st.table(ords)
                    st.space('large')
                    ordx=ord[['Historic Values','Projected Values']].melt(ignore_index=False,var_name='Scenario')
                    ordx=ordx.reset_index(names=['Activity'])
                    
                with col2:
                    h2={'Digital Order Creation': (dig_auto*h['Digital (Confirmed)']+dig_rev*h['Digital (In Review)'])/3600,
                        'Analog Order Creation': (historic['ht_create_ana']*h['Analog (Confirmed)']+(historic['ht_create_ana']+ana_rev)*h['Analog (In Review)'])/3600,
                        'Order Modification': historic['peak']*historic['mod_rate']*(1-historic['mod_adoption']*historic['digitization_modify'])*historic['ht_modify']/3600,
                        'Order Cancellation': historic['peak']*historic['can_rate']*(1-historic['can_adoption']*historic['digitization_cancel'])*historic['ht_cancel']/3600,
                        'Misc. Order Management': historic['peak']*historic['ht_mgmt']/3600}
                    p2={'Digital Order Creation': (dig_auto*p['Digital (Confirmed)']+dig_rev*p['Digital (In Review)'])/3600,
                        'Analog Order Creation': (historic['ht_create_ana']*p['Analog (Confirmed)']+(historic['ht_create_ana']+ana_rev)*p['Analog (In Review)'])/3600,
                        'Order Modification': proj_param['peak']*proj_param['mod_rate']*(1-proj_param['mod_adoption']*historic['digitization_modify'])*historic['ht_modify']/3600,
                        'Order Cancellation': proj_param['peak']*proj_param['can_rate']*(1-proj_param['can_adoption']*historic['digitization_cancel'])*historic['ht_cancel']/3600,
                        'Misc. Order Management': proj_param['peak']*historic['ht_mgmt']/3600}

                    md2={'Historic Values':h2,'Projected Values':p2}
                    ord2=pd.DataFrame(md2)
                    ord2['% Change']=(ord2['Projected Values']-ord2['Historic Values'])/ord2['Historic Values']
                    #ords2=ord2.style.format({"Historic Values": "{:,.0f}","Projected Values": "{:,.0f}", "% Change": "{:.1%}"})
                    st.write("Weekly Workload Distribution (hours)")
                    #st.table(ords2)
                    ord3=pd.DataFrame({'Historic Values':ord2['Historic Values'].sum(),'Projected Values':ord2['Projected Values'].sum()},index=pd.Index(['Total Workload']))
                    ord3['% Change']=(ord3['Projected Values']-ord3['Historic Values'])/ord3['Historic Values']
                    ord4=pd.concat([ord2,ord3])
                    ords4=ord4.style.format({"Historic Values": "{:,.0f}","Projected Values": "{:,.0f}", "% Change": "{:.1%}"})
                    st.table(ords4)
                    ord5=ord2[['Historic Values','Projected Values']].melt(ignore_index=False,var_name='Scenario')
                    ord5=ord5.reset_index(names=['Activity'])
                    ord5['percentage_of_total'] = ord5['value'] / ord5.groupby('Scenario')['value'].transform('sum')
                col3,col4=st.columns(2)
                with col3:
                    fig=px.pie(ordx,values='value',names='Activity',facet_col='Scenario',labels={'index':'Scenario','value':'Orders','Activity':'Order type'},hole=0.7,facet_col_spacing=0.08,hover_data={'value':':.0f'})
                    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                    fig.update_layout(legend=dict(orientation="h",yanchor="bottom",y=-0.2, xanchor="center", x=0.5),margin=dict(b=50))
                    with st.container(border=True):
                        st.plotly_chart(fig)
                with col4:
                    fig2=px.bar(ord5,x='Scenario',y='value',color='Activity',labels={'index':'Scenario','value':'Workload (hr)','variable':'Activity','percentage_of_total':"% of Workload"},hover_data={'Activity': False,'Scenario': False,'value':':.1f','percentage_of_total':':.1%'})
                    with st.container(border=True):
                        st.plotly_chart(fig2)
        with tab2:
            hdemand=intensity(work_sum,h,h2,summ_fil['Total Orders'].sum(),historic['peak'],asa, asad,eff-other_act,sl,max_util)
            pdemand=intensity(work_sum,p,p2,summ_fil['Total Orders'].sum(),proj_param['peak'],asa, asad,eff-other_act,sl,max_util)
            h_wf,h_sch,h_r_sch,htr=calculate_resources(hdemand)
            p_wf,p_sch,p_r_sch,ptr=calculate_resources(pdemand)
            hwft=pd.DataFrame(list(h_wf.values()), index=h_wf.keys(),columns=['Historical'])
            pwft=pd.DataFrame(list(p_wf.values()), index=p_wf.keys(),columns=['Projected'])
            twf=hwft.join(pwft)
            #twf=twf.drop(index=['FTE (no shrinkage)','OT (no shrinkage)'])
            st.write('Optimized Headcount and Overtime for each Scenario')
            st.table(twf.T)
            fig3,fig4,fig5=create_demand_plot(hdemand,pdemand)
            t1,t2,t3=st.tabs(['Workload / HC','Agent Utilization','Digital Work Burndown'])
            with t1:
                st.plotly_chart(fig3,height='stretch')
            with t2:
                st.plotly_chart(fig4)
            with t3:
                st.plotly_chart(fig5,height='stretch')

        with tab3:
            scen_choice=st.pills("Scenario", options=['Historical Data','Projection'],selection_mode='single',default='Historical Data',required=True)
            if scen_choice=='Projection':
                dafr= p_sch
                fig_ros=create_roster_fig(pdemand,ptr)
            else:
                dafr=h_sch
                fig_ros=create_roster_fig(hdemand,htr)
            with st.expander('Suggested Roster per Shift and Business Day', expanded=False):
                st.dataframe(dafr)
            st.plotly_chart(fig_ros)
