import streamlit as st
import plotly.express as px
import json
import pandas as pd
from shapely.geometry import shape
from shapely.ops import unary_union
import re

# 페이지 설정
st.set_page_config(
    page_title="대한민국 시군구별 지도 대시보드",
    page_icon="🗺️",
    layout="wide"
)

# 제목
st.title("🗺️ 대한민국 시군구별 데이터 분포 지도")
st.markdown("`sample.xlsx`의 '지역구분' 데이터를 집계하여 지도에 시각화합니다.")
st.markdown("---")

@st.cache_data
def load_and_process_data(excel_path, geojson_path):
    """
    Excel과 GeoJSON 파일을 로드하고, 지역구분 데이터를 기반으로 집계하여
    지도 시각화에 사용할 최종 GeoJSON과 매칭되지 않은 지역 목록을 반환합니다.
    """
    try:
        # --- 1. GeoJSON을 시군구 단위로 병합하여 기본 지도 생성 ---
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        # 시도별로 그룹화 (1단계 매칭용)
        sido_groups = {}
        sgg_groups = {}
        
        for feature in geojson_data['features']:
            properties = feature['properties']
            sido = properties.get('sidonm', '')
            sgg = properties.get('sggnm', '')
            
            if sido and sgg:
                # 시도별 그룹화 (서울특별시, 광역시 등)
                if sido not in sido_groups:
                    sido_groups[sido] = []
                sido_groups[sido].append(shape(feature['geometry']))
                
                # 시군구별 그룹화 (기존 로직)
                key = f"{sido} {sgg}"
                if key not in sgg_groups:
                    sgg_groups[key] = []
                sgg_groups[key].append(shape(feature['geometry']))
        
        # 시도별 지오메트리 병합
        sido_map_geoms = {}
        for sido, geoms in sido_groups.items():
            if geoms:
                try:
                    sido_map_geoms[sido] = unary_union(geoms)
                except Exception:
                    continue
        
        # 시군구별 지오메트리 병합 (기존 로직)
        sgg_map_geoms = {}
        for sggnm, geoms in sgg_groups.items():
            if geoms:
                try:
                    sgg_map_geoms[sggnm] = unary_union(geoms)
                except Exception:
                    continue

        # --- 2. Excel 데이터 로드 및 집계 ---
        df = pd.read_excel(excel_path)
        region_counts = df['지역구분'].value_counts().to_dict()

        # --- 3. 3단계 매칭 로직 구현 ---
        final_counts = {}
        unmatched_regions = []

        # 시도명 목록 (1단계 매칭용)
        sido_list = [
            '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시', 
            '울산광역시', '세종특별자치시', '제주특별자치도'
        ]

        for region, count in region_counts.items():
            region_str = str(region).strip()
            matched = False

            # 1단계: 서울, 광역시, 제주, 세종은 sidonm에 따라 매칭 (시도 단위로 통합)
            if region_str in sido_list:
                if region_str in sido_map_geoms:
                    final_counts[region_str] = final_counts.get(region_str, 0) + count
                    matched = True
            
            # 2단계: sggnm이 5글자 이상인 것들은 앞 3글자로 매칭
            elif len(region_str) >= 3:
                for sggnm_key in sgg_map_geoms.keys():
                    # sggnm에서 시도명 제거하고 시군구명만 추출
                    sgg_part = sggnm_key.split(' ', 1)[1] if ' ' in sggnm_key else sggnm_key
                    
                    # sggnm이 5글자 이상이고 앞 3글자가 일치하는 경우
                    if len(sgg_part) >= 5 and sgg_part[:3] == region_str[:3]:
                        final_counts[sggnm_key] = final_counts.get(sggnm_key, 0) + count
                        matched = True
            
            # 3단계: 나머지는 sggnm에 따라 매칭
            if not matched:
                for sggnm_key in sgg_map_geoms.keys():
                    # sggnm에서 시도명 제거하고 시군구명만 추출
                    sgg_part = sggnm_key.split(' ', 1)[1] if ' ' in sggnm_key else sggnm_key
                    
                    # 정확히 일치하는 경우
                    if sgg_part == region_str:
                        final_counts[sggnm_key] = final_counts.get(sggnm_key, 0) + count
                        matched = True
                        break
            
            if not matched:
                unmatched_regions.append(region)

        # --- 4. 최종 GeoJSON 생성 ---
        merged_features = []
        
        # 시도 단위로 매칭된 지역들 (통합된 경계선)
        for sido, geom in sido_map_geoms.items():
            if sido in final_counts:
                merged_feature = {
                    'type': 'Feature',
                    'geometry': geom.__geo_interface__,
                    'properties': {
                        'sggnm': sido,
                        'value': final_counts[sido]
                    }
                }
                merged_features.append(merged_feature)
        
        # 시군구 단위로 매칭된 지역들 (개별 경계선)
        for sggnm, geom in sgg_map_geoms.items():
            if sggnm in final_counts and sggnm not in sido_list:  # 시도 단위가 아닌 경우만
                merged_feature = {
                    'type': 'Feature',
                    'geometry': geom.__geo_interface__,
                    'properties': {
                        'sggnm': sggnm,
                        'value': final_counts[sggnm]
                    }
                }
                merged_features.append(merged_feature)

        merged_geojson = {'type': 'FeatureCollection', 'features': merged_features}
        
        # 매칭 실패한 지역 정보 DataFrame 생성
        unmatched_df = pd.DataFrame({
            '지역구분': unmatched_regions,
            '카운트': [region_counts[r] for r in unmatched_regions]
        })

        return merged_geojson, unmatched_df
        
    except FileNotFoundError as e:
        st.error(f"파일을 찾을 수 없습니다: {e.filename}")
        return None, pd.DataFrame()
    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
        return None, pd.DataFrame()

def create_korea_map(merged_geojson, map_style, color_scale_name):
    """Plotly를 사용하여 8단계로 구분된 Choropleth 지도를 생성합니다."""
    if not merged_geojson or not merged_geojson['features']:
        return None

    plot_df = pd.DataFrame([f['properties'] for f in merged_geojson['features']])
    
    # 값이 있는 경우에만 동적으로 구간 설정
    if not plot_df.empty and plot_df['value'].max() > 0:
        max_value = plot_df['value'].max()
        if max_value <= 10:
            bins = [-1, 0, 1, 2, 3, 5, 10, float('inf')]
            labels = ["0", "1", "2", "3", "4-5", "6-10", "11+"]
        elif max_value <= 100:
            bins = [-1, 0, 10, 20, 30, 50, 100, float('inf')]
            labels = ["0", "1-10", "11-20", "21-30", "31-50", "51-100", "101+"]
        else:
            bins = [-1, 0, 20, 50, 100, 200, 500, float('inf')]
            labels = ["0", "1-20", "21-50", "51-100", "101-200", "201-500", "501+"]
    else:
        bins = [-1, 0, float('inf')]
        labels = ["0", "1+"]
    
    plot_df['category'] = pd.cut(plot_df['value'], bins=bins, labels=labels, right=True).astype(str)
    
    # 색상표 생성
    colors = px.colors.sequential.__getattribute__(color_scale_name)
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(labels)}

    fig = px.choropleth_mapbox(
        plot_df,
        geojson=merged_geojson,
        locations='sggnm',
        featureidkey='properties.sggnm',
        color='category',
        color_discrete_map=color_map,
        category_orders={'category': labels},
        mapbox_style=map_style,
        zoom=6,
        center={'lat': 36.5, 'lon': 127.5},
        opacity=0.7,
        labels={'category': '신청 건수', 'sggnm': '지역'},
        hover_name='sggnm',
        hover_data={'value': True}
    )
    
    fig.update_layout(
        height=700,
        margin={'r': 0, 't': 0, 'l': 0, 'b': 0},
        legend_title_text='신청 건수 (구간)'
    )
    
    return fig, plot_df

def main():
    # 사이드바 설정
    st.sidebar.header("⚙️ 지도 설정")
    map_styles = {
        "기본 (밝음)": "carto-positron", "기본 (어두움)": "carto-darkmatter", 
        "위성 지도": "satellite-streets", "지형도": "stamen-terrain"
    }
    color_scales = ["Blues", "Reds", "Greens", "Viridis", "Cividis", "Inferno"]
    
    selected_style = st.sidebar.selectbox("지도 스타일", list(map_styles.keys()))
    selected_color = st.sidebar.selectbox("색상 스케일", color_scales)
    
    # 데이터 로드 및 처리
    merged_geojson, unmatched_df = load_and_process_data('sample.xlsx', 'HangJeongDong_ver20250401.geojson')
    
    if merged_geojson:
        fig, df = create_korea_map(merged_geojson, map_styles[selected_style], selected_color)
        
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            
            st.sidebar.markdown("---")
            st.sidebar.header("📊 데이터 요약")
            st.sidebar.metric("총 시군구 수", len(df))
            st.sidebar.metric("데이터가 있는 시군구", len(df[df['value'] > 0]))
            st.sidebar.metric("최대 신청 건수", f"{df['value'].max():,}")
            
            st.subheader("데이터 테이블 (신청 건수 높은 순)")
            st.dataframe(df[['sggnm', 'value']].sort_values('value', ascending=False), use_container_width=True)

            # 매칭되지 않은 지역 표시
            st.markdown("---")
            if not unmatched_df.empty:
                st.subheader("⚠️ 매칭되지 않은 지역 목록")
                st.warning(
                    "아래 목록의 지역들은 GeoJSON 지도 데이터에서 찾을 수 없어 지도에 포함되지 않았습니다."
                )
                st.dataframe(unmatched_df, use_container_width=True)
            else:
                st.success("✅ 모든 지역이 지도 데이터와 성공적으로 매칭되었습니다.")
        else:
            st.error("지도 생성에 실패했습니다.")
    else:
        st.error("데이터를 처리할 수 없습니다.")

if __name__ == "__main__":
    main()
