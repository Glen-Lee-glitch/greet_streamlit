import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import json
import pandas as pd
import os

# 페이지 설정
st.set_page_config(
    page_title="대한민국 행정구역별 지도 대시보드",
    page_icon="🗺️",
    layout="wide"
)

# 제목
st.title("🗺️ 대한민국 행정구역별 지도 대시보드")
st.markdown("---")

@st.cache_data
def load_geojson():
    """GeoJSON 파일을 로드합니다."""
    try:
        with open('HangJeongDong_ver20250401.geojson', 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        st.success(f"✅ GeoJSON 파일 로드 완료 (총 {len(geojson_data['features'])}개 행정구역)")
        return geojson_data
    except Exception as e:
        st.error(f"GeoJSON 파일 로드 중 오류가 발생했습니다: {e}")
        return None

def create_sample_data(geojson_data):
    """모든 행정구역에 대한 샘플 데이터를 생성합니다."""
    sample_data = []
    
    for feature in geojson_data['features']:
        properties = feature['properties']
        
        # 행정구역명 추출 (가장 구체적인 이름 사용)
        region_name = None
        if 'adm_nm' in properties and properties['adm_nm']:
            region_name = properties['adm_nm']  # 행정동명
        elif 'sggnm' in properties and properties['sggnm']:
            region_name = properties['sggnm']  # 시군구명
        elif 'sidonm' in properties and properties['sidonm']:
            region_name = properties['sidonm']  # 시도명
        else:
            continue
        
        # 샘플 값 생성 (실제 데이터로 교체 가능)
        import random
        value = random.randint(100, 10000)  # 샘플 값
        
        sample_data.append({
            'region': region_name,
            'value': value
        })
    
    return pd.DataFrame(sample_data)

def create_korea_map(geojson_data, map_style="carto-positron", color_scale="Viridis"):
    """대한민국 지도를 생성합니다."""
    if geojson_data is None:
        return None
    
    # 샘플 데이터 생성
    df = create_sample_data(geojson_data)
    
    # 디버깅 정보
    st.write(f"데이터프레임 지역 수: {len(df)}")
    st.write(f"GeoJSON feature 수: {len(geojson_data['features'])}")
    
    # GeoJSON의 지역명들 확인
    geojson_regions = set()
    for feature in geojson_data['features']:
        properties = feature['properties']
        if 'adm_nm' in properties and properties['adm_nm']:
            geojson_regions.add(properties['adm_nm'])
        elif 'sggnm' in properties and properties['sggnm']:
            geojson_regions.add(properties['sggnm'])
        elif 'sidonm' in properties and properties['sidonm']:
            geojson_regions.add(properties['sidonm'])
    
    st.write(f"GeoJSON 지역명 예시: {list(geojson_regions)[:5]}")
    st.write(f"데이터프레임 지역명 예시: {list(df['region'])[:5]}")
    
    # 매칭되지 않는 지역들 확인
    df_regions = set(df['region'])
    unmatched_geojson = geojson_regions - df_regions
    unmatched_df = df_regions - geojson_regions
    
    if unmatched_geojson or unmatched_df:
        st.warning(f"매칭되지 않는 지역이 있습니다:")
        if unmatched_geojson:
            st.write(f"GeoJSON에만 있는 지역: {list(unmatched_geojson)[:10]}")
        if unmatched_df:
            st.write(f"데이터프레임에만 있는 지역: {list(unmatched_df)[:10]}")
    
    # 데이터를 GeoJSON의 각 feature에 직접 매핑하여 모든 지역이 색상으로 채워지도록 함
    value_dict = dict(zip(df['region'], df['value']))
    
    for feature in geojson_data['features']:
        properties = feature['properties']
        region_name = None
        
        # 지역명 추출
        if 'adm_nm' in properties and properties['adm_nm']:
            region_name = properties['adm_nm']
        elif 'sggnm' in properties and properties['sggnm']:
            region_name = properties['sggnm']
        elif 'sidonm' in properties and properties['sidonm']:
            region_name = properties['sidonm']
        
        # 값 매핑
        if region_name and region_name in value_dict:
            feature['properties']['value'] = value_dict[region_name]
        else:
            feature['properties']['value'] = 0  # 매칭되지 않는 지역은 0으로 설정
    
    # 데이터프레임을 다시 생성하여 Plotly에 전달
    plot_data = []
    for feature in geojson_data['features']:
        properties = feature['properties']
        region_name = None
        
        if 'adm_nm' in properties and properties['adm_nm']:
            region_name = properties['adm_nm']
        elif 'sggnm' in properties and properties['sggnm']:
            region_name = properties['sggnm']
        elif 'sidonm' in properties and properties['sidonm']:
            region_name = properties['sidonm']
        
        if region_name:
            plot_data.append({
                'region': region_name,
                'value': properties.get('value', 0)
            })
    
    plot_df = pd.DataFrame(plot_data)
    
    # Plotly Choropleth 지도 생성
    fig = px.choropleth_mapbox(
        plot_df,
        geojson=geojson_data,
        locations='region',
        featureidkey='properties.adm_nm',  # 행정동명으로 매칭
        color='value',
        color_continuous_scale=color_scale,
        mapbox_style=map_style,
        zoom=5,
        center={'lat': 36.5, 'lon': 127.5},  # 대한민국 중심
        title='대한민국 행정구역별 데이터',
        labels={'value': '값', 'region': '지역'},
        opacity=0.7
    )
    
    fig.update_layout(
        title_x=0.5,
        height=600,
        margin={'r': 0, 't': 50, 'l': 0, 'b': 0}
    )
    
    return fig

def main():
    # 사이드바
    st.sidebar.header("설정")
    
    # 지도 스타일 선택
    map_styles = {
        "기본 (밝은 배경)": "carto-positron",
        "기본 (어두운 배경)": "carto-darkmatter", 
        "OpenStreetMap": "open-street-map",
        "지형도": "stamen-terrain",
        "흑백": "stamen-toner"
    }
    
    selected_style = st.sidebar.selectbox(
        "지도 스타일 선택",
        options=list(map_styles.keys()),
        index=0
    )
    
    # 색상 스케일 선택
    color_scales = [
        "Viridis", "Plasma", "Inferno", "Magma", "Blues", 
        "Greens", "Reds", "Purples", "Oranges", "RdBu", 
        "Spectral", "RdYlBu", "Set1", "Set2", "Set3"
    ]
    
    selected_color = st.sidebar.selectbox(
        "색상 스케일 선택",
        options=color_scales,
        index=0
    )
    
    # GeoJSON 파일 로드
    with st.spinner("GeoJSON 파일을 로드하는 중..."):
        geojson_data = load_geojson()
    
    if geojson_data:
        # 지도 생성
        fig = create_korea_map(geojson_data, map_styles[selected_style], selected_color)
        
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            
            # 데이터 테이블 표시
            st.subheader("📊 데이터 테이블")
            
            # 샘플 데이터프레임 생성
            sample_df = create_sample_data(geojson_data)
            st.dataframe(sample_df.head(20), use_container_width=True)
            
            # 통계 정보
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("총 행정구역 수", len(sample_df))
            
            with col2:
                st.metric("평균값", f"{sample_df['value'].mean():.0f}")
            
            with col3:
                st.metric("최대값", sample_df['value'].max())
            
            with col4:
                st.metric("최소값", sample_df['value'].min())
        
        else:
            st.error("지도 생성에 실패했습니다.")
    
    else:
        st.error("GeoJSON 파일을 로드할 수 없습니다.")

if __name__ == "__main__":
    main()
