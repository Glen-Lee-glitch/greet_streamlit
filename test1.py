import streamlit as st
import plotly.express as px
import json
import pandas as pd
from shapely.geometry import shape
from shapely.ops import unary_union
import random

# 페이지 설정
st.set_page_config(
    page_title="대한민국 시군구별 지도 대시보드",
    page_icon="🗺️",
    layout="wide"
)

# 제목
st.title("🗺️ 대한민국 시군구별 지도 대시보드")
st.markdown("---")

@st.cache_data
def load_and_process_geojson():
    """
    GeoJSON 파일을 로드하고, 행정동 경계를 시군구 단위로 병합합니다.
    이 과정은 한 번만 실행되어 캐시됩니다.
    """
    try:
        # 1. GeoJSON 파일 로드
        with open('HangJeongDong_ver20250401.geojson', 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
    except Exception as e:
        st.error(f"GeoJSON 파일 로드 중 오류가 발생했습니다: {e}")
        return None

    # 2. 시군구별로 행정동 그룹화
    sggnm_groups = {}
    for feature in geojson_data['features']:
        properties = feature['properties']
        sggnm = properties.get('sggnm')
        if sggnm:  # 시군구 이름이 있는 경우에만 처리
            if sggnm not in sggnm_groups:
                sggnm_groups[sggnm] = []
            sggnm_groups[sggnm].append(feature)

    # 3. 각 시군구별로 지오메트리 병합
    merged_features = []
    for sggnm, features in sggnm_groups.items():
        geometries = [shape(feature['geometry']) for feature in features]
        
        try:
            # 모든 지오메트리를 하나로 병합
            merged_geometry = unary_union(geometries)
            
            # 병합된 지오메트리를 GeoJSON 형식으로 변환 (핵심 수정 사항)
            # __geo_interface__를 사용하여 정확하고 안정적인 변환 보장
            merged_geojson_geom = merged_geometry.__geo_interface__
            
            # 병합된 새 feature 생성
            merged_feature = {
                'type': 'Feature',
                'geometry': merged_geojson_geom,
                'properties': {
                    'sggnm': sggnm,
                    'value': random.randint(100, 1000) # 샘플 데이터 생성
                }
            }
            merged_features.append(merged_feature)
        except Exception as e:
            st.warning(f"지오메트리 병합 오류 ({sggnm}): {e}")
            continue

    # 4. 최종 병합된 GeoJSON 생성
    merged_geojson = {
        'type': 'FeatureCollection',
        'features': merged_features
    }
    
    st.success(f"✅ GeoJSON 처리 완료 (총 {len(merged_features)}개 시군구)")
    return merged_geojson

def create_korea_map(merged_geojson, map_style, color_scale):
    """Plotly를 사용하여 대한민국 Choropleth 지도를 생성합니다."""
    if not merged_geojson or not merged_geojson['features']:
        return None

    # GeoJSON의 properties에서 직접 데이터를 읽어 데이터프레임 생성
    plot_df = pd.DataFrame([
        {
            'region': f['properties']['sggnm'],
            'value': f['properties']['value']
        }
        for f in merged_geojson['features']
    ])

    # Plotly Choropleth 지도 생성
    fig = px.choropleth_mapbox(
        plot_df,
        geojson=merged_geojson,
        locations='region',
        featureidkey='properties.sggnm',  # GeoJSON의 시군구명과 데이터프레임의 'region'을 매칭
        color='value',
        color_continuous_scale=color_scale,
        mapbox_style=map_style,
        zoom=5.5,
        center={'lat': 36.5, 'lon': 127.5},
        opacity=0.6,
        labels={'value': '값', 'region': '시군구'},
        hover_name='region',
        hover_data={'value': True}
    )
    
    fig.update_layout(
        title_text='대한민국 시군구별 데이터 분포',
        title_x=0.5,
        height=700,
        margin={'r': 0, 't': 40, 'l': 0, 'b': 0}
    )
    
    return fig, plot_df

def main():
    # 사이드바 설정
    st.sidebar.header("⚙️ 지도 설정")
    map_styles = {
        "기본 (밝음)": "carto-positron", "기본 (어두움)": "carto-darkmatter", 
        "위성 지도": "satellite-streets", "지형도": "stamen-terrain"
    }
    color_scales = ["Viridis", "Blues", "Reds", "Greens", "Cividis", "Inferno"]
    
    selected_style = st.sidebar.selectbox("지도 스타일", list(map_styles.keys()))
    selected_color = st.sidebar.selectbox("색상 스케일", color_scales)
    
    # 데이터 로드 및 처리
    merged_geojson = load_and_process_geojson()
    
    if merged_geojson:
        # 지도 및 데이터프레임 생성
        fig, df = create_korea_map(merged_geojson, map_styles[selected_style], selected_color)
        
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error("지도 생성에 실패했습니다.")
    else:
        st.error("GeoJSON 파일을 처리할 수 없습니다.")

if __name__ == "__main__":
    main()
