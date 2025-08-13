import streamlit as st
import pandas as pd
import json
import plotly.express as px
import re

@st.cache_data
def load_preprocessed_map(geojson_path):
    """
    미리 병합된 가벼운 GeoJSON 파일을 로드합니다.
    """
    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"'{geojson_path}' 파일을 찾을 수 없습니다. 먼저 preprocess_map.py를 실행해주세요.")
        return None
    except Exception as e:
        st.error(f"지도 데이터 로드 중 오류: {e}")
        return None

@st.cache_data
def get_filtered_data_optimized(data, selected_quarter):
    """
    전처리 파일에 미리 계산된 분기별 데이터를 빠르게 가져옵니다.
    이 함수는 전처리.py에서 'quarterly_region_counts'가 생성되었다고 가정합니다.
    """
    quarterly_counts = data.get("quarterly_region_counts", {})
    return quarterly_counts.get(selected_quarter, {})
    
@st.cache_data
def apply_counts_to_map_optimized(_preprocessed_map, _region_counts):
    """
    최적화된 매칭 로직을 사용하여 GeoJSON에 count 데이터를 빠르게 적용합니다.
    """
    if not _preprocessed_map:
        return None, pd.DataFrame()

    # 1. 지도에 있는 모든 지역의 count를 0으로 초기화
    final_counts = {feat['properties']['sggnm']: 0 for feat in _preprocessed_map['features']}
    
    # 2. 빠른 조회를 위한 조회용 지도(lookup map) 생성 (한 번만 실행됨)
    sgg_to_full_key_map = {}
    for key in final_counts.keys():
        parts = key.split(" ", 1)
        sgg_part = parts[1] if len(parts) > 1 else key
        if sgg_part not in sgg_to_full_key_map:
            sgg_to_full_key_map[sgg_part] = []
        sgg_to_full_key_map[sgg_part].append(key)

    # 3. 데이터(region_counts)를 한 번만 순회하며 값 적용
    unmatched_regions = set(_region_counts.keys())
    for region, count in _region_counts.items():
        region_str = str(region).strip()
        matched = False

        # Case 1: '서울특별시'와 같은 시도명 직접 매칭
        if region_str in final_counts:
            final_counts[region_str] += count
            unmatched_regions.discard(region_str)
            matched = True
        
        # Case 2 & 3: '수원시'와 같은 시군구명을 조회용 지도에서 찾아 매칭
        if not matched and region_str in sgg_to_full_key_map:
            for full_key in sgg_to_full_key_map[region_str]:
                final_counts[full_key] += count
            unmatched_regions.discard(region_str)
            matched = True

    # 4. 최종 GeoJSON 생성 (값만 업데이트)
    final_geojson = _preprocessed_map.copy()
    final_geojson['features'] = [feat.copy() for feat in final_geojson['features']]
    for feature in final_geojson['features']:
        key = feature['properties']['sggnm']
        feature['properties'] = {'sggnm': key, 'value': final_counts.get(key, 0)}

    unmatched_df = pd.DataFrame({
        '지역구분': list(unmatched_regions),
        '카운트': [_region_counts.get(r, 0) for r in unmatched_regions]
    })

    return final_geojson, unmatched_df

@st.cache_data
def create_korea_map(_merged_geojson, map_style, color_scale_name):
    """Plotly 지도를 생성합니다. (캐시 적용)"""
    if not _merged_geojson or not _merged_geojson['features']: 
        return None, pd.DataFrame()
    
    plot_df = pd.DataFrame([f['properties'] for f in _merged_geojson['features']])
    if not plot_df.empty and plot_df['value'].max() > 0:
        bins = [-1, 0, 15, 60, 100, 200, 500, 1000, 3000, float('inf')]
        labels = ["0", "1-15", "16-60", "61-100", "101-200", "201-500", "501-1000", "1001-3000", "3001+"]
    else:
        bins = [-1, 0, float('inf')]
        labels = ["0", "1+"]
    plot_df['category'] = pd.cut(plot_df['value'], bins=bins, labels=labels, right=True).astype(str)
    colors = px.colors.sequential.__getattribute__(color_scale_name)
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(labels)}
    fig = px.choropleth_mapbox(
        plot_df, geojson=_merged_geojson, locations='sggnm', featureidkey='properties.sggnm',
        color='category', color_discrete_map=color_map, category_orders={'category': labels},
        mapbox_style=map_style, zoom=6, center={'lat': 36.5, 'lon': 127.5}, opacity=0.7,
        labels={'category': '신청 건수', 'sggnm': '지역'}, hover_name='sggnm', hover_data={'value': True}
    )
    fig.update_layout(height=700, margin={'r': 0, 't': 0, 'l': 0, 'b': 0}, legend_title_text='신청 건수 (구간)')
    return fig, plot_df

def show_map_viewer(data, df_6):
    """메인 지도 뷰어 실행 함수"""
    st.header("🗺️ 지도 시각화")
    quarter_options = ['전체', '1Q', '2Q', '3Q']
    selected_quarter = st.selectbox("분기 선택", quarter_options)
    
    preprocessed_map = load_preprocessed_map('preprocessed_map.geojson')
    
    if preprocessed_map and not df_6.empty:
        region_counts = get_filtered_data_optimized(data, selected_quarter)
        final_geojson, unmatched_df = apply_counts_to_map_optimized(preprocessed_map, region_counts)
        
        st.sidebar.header("⚙️ 지도 설정")
        map_styles = {"기본 (밝음)": "carto-positron", "기본 (어두움)": "carto-darkmatter"}
        color_scales = ["Reds","Blues", "Greens", "Viridis"]
        selected_style = st.sidebar.selectbox("지도 스타일", list(map_styles.keys()))
        selected_color = st.sidebar.selectbox("색상 스케일", color_scales)
        
        result = create_korea_map(final_geojson, map_styles[selected_style], selected_color)
        if result:
            fig, df = result
            st.plotly_chart(fig, use_container_width=True)
            st.sidebar.metric("총 지역 수", len(df))
            st.sidebar.metric("데이터가 있는 지역", len(df[df['value'] > 0]))
            st.sidebar.metric("최대 신청 건수", f"{df['value'].max():,}")
            st.subheader("데이터 테이블")
            df_nonzero = df[df['value'] > 0][['sggnm', 'value']].sort_values('value', ascending=False)
            if not df_nonzero.empty:
                st.dataframe(df_nonzero, use_container_width=True)
            if not unmatched_df.empty:
                st.subheader("⚠️ 매칭되지 않은 지역 목록")
                st.dataframe(unmatched_df, use_container_width=True)
            else:
                st.success("✅ 모든 지역이 성공적으로 매칭되었습니다.")

def main():
    """독립 실행을 위한 메인 함수"""
    import pickle
    st.set_page_config(page_title="지도 뷰어", page_icon="🗺️", layout="wide")
    
    @st.cache_data(ttl=3600)
    def load_main_data():
        try:
            with open("preprocessed_data.pkl", "rb") as f:
                return pickle.load(f)
        except FileNotFoundError:
            st.error("preprocessed_data.pkl 파일을 찾을 수 없습니다.")
            return {}
    
    data = load_main_data()
    if data:
        df_6 = data.get("df_6", pd.DataFrame())
        show_map_viewer(data, df_6)
    else:
        st.stop()

if __name__ == "__main__":
    main()
