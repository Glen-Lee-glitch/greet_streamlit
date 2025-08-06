import os, json
import pandas as pd
import plotly.express as px
os.chdir('./Local_HangJeongDong')

with open('./hangjeongdong_서울특별시.geojson', 'r') as f:
    seoul_geo = json.load(f)
    
seoul_info = pd.read_csv('./sample.txt', delimiter='\t')
seoul_info = seoul_info.iloc[3:,:]
seoul_info = seoul_info[seoul_info['동']!='소계']
seoul_info['full_name'] = '서울특별시'+' '+seoul_info['자치구']+' '+seoul_info['동']
seoul_info['full_name'] = seoul_info['full_name'].apply(lambda x: x.replace('.','·'))
seoul_info['인구'] = seoul_info['인구'].apply(lambda x: int(''.join(x.split(','))))

fig = px.choropleth_mapbox(seoul_info,
                           geojson=seoul_geo,
                           locations='full_name',
                           color='인구',
                           color_continuous_scale='viridis', featureidkey = 'properties.adm_nm',
                           mapbox_style='carto-positron',
                           zoom=9.5,
                           center = {"lat": 37.563383, "lon": 126.996039},
                           opacity=0.5,
                          )

fig