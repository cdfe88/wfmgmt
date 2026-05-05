import streamlit as st
import pandas as pd
import numpy as np
from pyworkforce.scheduling import MinRequiredResources
from pyworkforce.queuing import ErlangC
from pprint import PrettyPrinter
from datetime import date, datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

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
    return wload

def workload_agg(wload):
    wload['W Mgmt'] = wload['Order Mgmt HT (hr)'] * wload['Occur Int']
    wload['W Int'] = wload['Order Mgmt Interactions'] * wload['Occur Int']
    wload['W Ord'] = wload['Orders'] * wload['Occur Ord']
    wload['W Ana'] = wload['Analog'] * wload['Occur Ord']
    wload['W Dig'] = wload['Digital'] * wload['Occur Ord']
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
    demand['dig delta']=demand['Digital WL']-eff*(demand['positions']-demand['Analog WL'])
    demand=demand.drop(['ErlangC','Interactions','AHT','ASA','Reqs'],axis=1)
    c=0
    res=np.zeros(len(demand['dig delta']))
    for i,value in enumerate(demand['dig delta']):
        c= max(0,c+value)
        res[i]=c
    demand['Digital CWL']=pd.Series(res)
    return demand

def create_demand_plot(dem,typ,ymax):
    figx=go.Figure()
    figy=go.Figure()
    figz=go.Figure()
    mkt=', '.join(chosen_mkts)
    figx.add_trace(go.Bar(x=[dem['Weekday'],dem['Hour']],y=dem['raw_positions'],name='Required HC w/o shrinkage',marker=dict(color='#0068c9')))
    figx.add_trace(go.Bar(x=[dem['Weekday'],dem['Hour']],y=dem['shrink_delta'],name=f"Required Headcount with {(1-eff):.0%} shrinkage",marker=dict(color='#83c9ff')))
    figx.update_layout(yaxis_range=[0,ymax],barmode='stack',yaxis_title="Workload / HC", title=f"{typ}\n{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}",legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.5,
        xanchor="center",
        x=0.5
    ))
    figx.add_trace(go.Scatter(x=[dem['Weekday'],dem['Hour']],y=dem['Total Workload'],mode='lines',line=dict(color='#840032', width=3),name='Total Workload'))
    figx.add_trace(go.Scatter(x=[dem['Weekday'],dem['Hour']],y=dem['Digital WL'],mode='lines',line=dict(color='#ff312e', width=3),name='Digital Workload'))
    figy.add_trace(go.Scatter(x=[dem['Weekday'],dem['Hour']],y=dem['occupancy'], mode='lines+markers',name='Agent Utilization',line=dict(color='#0068c9', width=3)))
    figy.update_layout(yaxis_range=[0, 1],yaxis_title="Agent Utilization (%)", title=f"{typ}\n{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}")
    figz.add_trace(go.Bar(x=[dem['Weekday'],dem['Hour']],y=dem['Digital WL'], name='Digital Work Creation',marker=dict(color='#840032')))
    figz.add_trace(go.Scatter(x=[dem['Weekday'],dem['Hour']],y=dem['Digital CWL'], mode='lines',name='Digital Work Burndown',line=dict(color='#0068c9', width=3)))
    figz.update_layout(yaxis_title="Workload (hrs)", title=f"{typ}\n{'All Markets' if len(chosen_mkts)==0 else 'Market: ' if len(chosen_mkts)==1 else 'Markets: '} {mkt}",legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.5,
        xanchor="center",
        x=0.5
    ))
    return figx,figy,figz

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
    scheduler = MinRequiredResources(num_days=len(req),  # S
                                     periods=len(req[0]),  # P
                                     shifts_coverage=shifts,
                                     required_resources=req,
                                     cost_dict=costs,
                                     max_period_concurrency=100,  # gamma
                                     max_shift_concurrency=100)  # beta
    r_scheduler = MinRequiredResources(num_days=len(r_req),  # S
                                     periods=len(r_req[0]),  # P
                                     shifts_coverage=shifts,
                                     required_resources=r_req,
                                     cost_dict=costs,
                                     max_period_concurrency=100,  # gamma
                                     max_shift_concurrency=100)  # beta
    solution = scheduler.solve()
    r_solution=r_scheduler.solve()
    #cost=[r_solution['cost'], solution['cost']]
    reqs=pd.DataFrame(solution['resources_shifts'])
    reqs['weekday']=pd.Categorical(reqs.apply(lambda row: days[row['day']],axis=1), categories=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], ordered=True)
    r_reqs=pd.DataFrame(r_solution['resources_shifts'])
    r_reqs['weekday']=pd.Categorical(r_reqs.apply(lambda row: days[row['day']],axis=1), categories=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], ordered=True)
    ovrt=pd.DataFrame({'shift':ovt.keys(),'overtime':ovt.values()})
    c_ovt=pd.merge(reqs,ovrt,how='left',on='shift')
    r_c_ovt=pd.merge(r_reqs,ovrt,how='left',on='shift')
    wfm={'FTE':c_ovt['resources'].sum()//5,'OT':(c_ovt['resources']*c_ovt['overtime']).sum()+8*(c_ovt['resources'].sum()%5),'FTE (no shrinkage)':r_c_ovt['resources'].sum()//5,'OT (no shrinkage)':(r_c_ovt['resources']*r_c_ovt['overtime']).sum()+8*(r_c_ovt['resources'].sum()%5)}
    sched=reqs.pivot(index='shift',columns='weekday',values='resources').reset_index()
    sched[['shift start','shift end']]=sched['shift'].str.split(' - ', expand=True)
    sched['shift start']=pd.to_datetime(sched['shift start'],format='%H:%M:%S').dt.time
    sched['shift end']=pd.to_datetime(sched['shift end'],format='%H:%M:%S').dt.time
    sched=sched.sort_values(by=['shift start','shift end'])
    sched=sched.drop(columns=['shift start','shift end'])
    r_sched=r_reqs.pivot(index='shift',columns='weekday',values='resources').reset_index()
    r_sched[['shift start','shift end']]=r_sched['shift'].str.split(' - ', expand=True)
    r_sched['shift start']=pd.to_datetime(r_sched['shift start'],format='%H:%M:%S').dt.time
    r_sched['shift end']=pd.to_datetime(r_sched['shift end'],format='%H:%M:%S').dt.time
    r_sched=r_sched.sort_values(by=['shift start','shift end'])
    r_sched=r_sched.drop(columns=['shift start','shift end'])
    #sched=pd.merge(r_reqs,reqs,how='outer',on=['day','shift'],suffixes=(' min',''))
    #occ=pd.DataFrame([[k,v] for k,v in shifts.items()])
    #occ.columns=['shift','dist']
    #rost=pd.merge(sched, occ, on='shift',how='left')
    #rost['HC min']=rost.apply(lambda row: row['resources min']*np.array(row['dist']),axis=1)
    #rost['HC'] = rost.apply(lambda row: row['resources'] * np.array(row['dist']), axis=1)
    #rost2=rost.groupby('day')[['HC min','HC']].sum().reset_index()
    #return pd.DataFrame(solution['resources_shifts']),pd.DataFrame(r_solution['resources_shifts'])
    return wfm,sched,r_sched

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
        if len(chosen_mkts)==0:
            work_fil=work[work['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
            summ_fil=summ[summ['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
        else:
            work_fil=work[work['Market'].isin(chosen_mkts) & work['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
            summ_fil=summ[summ['Market'].isin(chosen_mkts) & summ['Date'].between(date_range[0].replace(day=1),date_range[1].replace(day=1))]
        tz=st.pills("Choose Grouping Time Zone" if len(work_fil['Time Zone'].unique())>1 else "Time Zone",work_fil['Time Zone'].unique(),selection_mode='single',default=work_fil['Time Zone'].unique()[0])
        work_fil['TDelta']=work_fil.apply(lambda row: timezones.index(tz)-timezones.index(row['Time Zone']),axis=1)
        work_fil['t_align']=work_fil.apply(lambda row: datetime.combine(date.today(),row['Hour'])+timedelta(hours=row['TDelta']),axis=1)
        work_fil['ADay']=work_fil.apply(lambda row: days[(days.index(row['Day'])+(row['t_align'].date()-date.today()).days)%7],axis=1)
        work_fil['AHour']=work_fil.apply(lambda row: row['t_align'].time(),axis=1)
        work_sum=workload_agg(work_fil)
        work_sum['ADay']=pd.Categorical(work_sum['ADay'], categories=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], ordered=True)
        work_sum=work_sum.sort_values(['ADay','AHour']).reset_index()
        historic=historic_time(summ_fil)
        with st.expander("Tunable Parameters",expanded=True):
            col1, col2=st.columns([0.5,0.5])
            with col1:
                st.write("Order Processing Times (sec)")
                dig_auto=st.number_input("Self-service orders",value=15,min_value=0,format='%i')
                dig_rev=st.number_input("Orders in Review",value=135,min_value=0,format='%i')
            with col2:    
                st.write("Target Speed of Answer")
                col4,col5=st.columns(2)
                with col4:
                    asa_v=st.number_input("Analog:",value=40.0,min_value=0.1)
                    asad_v=st.number_input("Online:",value=24.0,min_value=0.1)
                with col5:
                    asa_u=st.selectbox("",['sec','min','hr'],index=0)
                    asad_u=st.selectbox("",['sec','min','hr'],index=2)
                match asa_u:
                    case 'sec':
                        asa=asa_v/60
                    case 'min':
                        asa=asa_v
                    case 'hr':
                        asa=asa_v*60
                match asad_u:
                    case 'sec':
                        asad=asad_v/60
                    case 'min':
                        asad=asad_v
                    case 'hr':
                        asad=asad_v*60     
            st.divider()
            col6,col7,col8=st.columns(3)
            with col6:
                max_util=st.number_input("Max utilization (%):",value=95,min_value=0,max_value=100)/100
            with col7:    
                eff=st.number_input("Efficiency (%):",value=76,min_value=0,max_value=100)/100
            with col8:    
                sl=st.number_input("Service Level Target (%):",value=80,min_value=0,max_value=100)/100
            
    with colb:
        proj_param={}
        col1, col2=st.columns(2)
        with col1:
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
        with col2:
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
                    fig=px.bar(ord[['Historic Values','Projected Values']].T,labels={'index':'Scenario','value':'Orders','variable':'Creation type'})
                    st.plotly_chart(fig)
                with col2:
                    h2={'Digital Order Creation': (dig_auto*h['Digital (Confirmed)']+dig_rev*h['Digital (In Review)'])/3600,
                        'Analog Order Creation': historic['ht_create_ana']*(h['Analog (Confirmed)']+h['Analog (In Review)'])/3600,
                        'Order Modification': historic['peak']*historic['mod_rate']*(1-historic['mod_adoption']*historic['digitization_modify'])*historic['ht_modify']/3600,
                        'Order Cancellation': historic['peak']*historic['can_rate']*(1-historic['can_adoption']*historic['digitization_cancel'])*historic['ht_cancel']/3600,
                        'Misc. Order Management': historic['peak']*historic['ht_mgmt']/3600}
                    p2={'Digital Order Creation': (dig_auto*p['Digital (Confirmed)']+dig_rev*p['Digital (In Review)'])/3600,
                        'Analog Order Creation': historic['ht_create_ana']*(p['Analog (Confirmed)']+p['Analog (In Review)'])/3600,
                        'Order Modification': proj_param['peak']*proj_param['mod_rate']*(1-proj_param['mod_adoption']*historic['digitization_modify'])*historic['ht_modify']/3600,
                        'Order Cancellation': proj_param['peak']*proj_param['can_rate']*(1-proj_param['can_adoption']*historic['digitization_cancel'])*historic['ht_cancel']/3600,
                        'Misc. Order Management': proj_param['peak']*historic['ht_mgmt']/3600}

                    md2={'Historic Values':h2,'Projected Values':p2}
                    ord2=pd.DataFrame(md2)
                    ord2['% Change']=(ord2['Projected Values']-ord2['Historic Values'])/ord2['Historic Values']
                    ords2=ord2.style.format({"Historic Values": "{:,.0f}","Projected Values": "{:,.0f}", "% Change": "{:.1%}"})
                    st.write("Weekly Workload Distribution (hours)")
                    st.table(ords2)
                    ord3=pd.DataFrame({'Historic':ord2['Historic Values'].sum(),'Projected':ord2['Projected Values'].sum()},index=pd.Index(['Total Workload']))
                    ord3['% Change']=(ord3['Projected']-ord3['Historic'])/ord3['Historic']
                    ords3=ord3.style.format({"Historic": "{:,.0f}","Projected": "{:,.0f}", "% Change": "{:.1%}"})
                    st.table(ords3)
                    fig2=px.bar(ord2[['Historic Values','Projected Values']].T,labels={'index':'Scenario','value':'Workload (hr)','variable':'Activity'})
                    st.plotly_chart(fig2)
        with tab2:
            hdemand=intensity(work_sum,h,h2,summ_fil['Total Orders'].sum(),historic['peak'],asa, asad,eff,sl,max_util)
            pdemand=intensity(work_sum,p,p2,summ_fil['Total Orders'].sum(),proj_param['peak'],asa, asad,eff,sl,max_util)
            h_wf,h_sch,h_r_sch=calculate_resources(hdemand)
            p_wf,p_sch,p_r_sch=calculate_resources(pdemand)
            col1,col2=st.columns([3,1])
            with col1:
                m=max(hdemand['positions'].max(),pdemand['positions'].max())
                fig3,fig5,fig7=create_demand_plot(hdemand,'Historic Data Analysis',m)
                fig4,fig6,fig8=create_demand_plot(pdemand,'Projected Values',m)
                t1,t2,t3=st.tabs(['Workload / HC','Agent Utilization','Digital Work Burndown'])
                with t1:
                    st.plotly_chart(fig3)
                    st.plotly_chart(fig4)
                with t2:
                    st.plotly_chart(fig5)
                    st.plotly_chart(fig6)
                with t3:
                    st.plotly_chart(fig7)
                    st.plotly_chart(fig8)
            with col2:
                st.write('Historical WF Requirements')    
                st.dataframe(h_wf)
                st.write('Projected WF Requirements')
                st.dataframe(p_wf)
        with tab3:
            col1,col2=st.columns(2)
            with col1:
                st.write('Historic Data')
                st.dataframe(h_sch)
            with col2:
                st.write('Projected Scenario')
                st.dataframe(p_sch)
