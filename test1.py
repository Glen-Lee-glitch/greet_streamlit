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
st.markdown("`sample.xlsx`의 주소 데이터를 집계하여 지도에 시각화합니다.")
st.markdown("---")

@st.cache_data
def parse_address(address):
    """
    주소 문자열에서 '시도'와 '시군구'를 추출합니다.
    (예: "경기도 안산시 상록구 ..." -> "경기도", "안산시 상록구")
    (예: "경기도 수원시 장안구 ..." -> "경기도", "수원시 장안구")
    (예: "세종특별자치시 ..." -> "세종특별자치시", "세종시")
    """
    if pd.isna(address):
        return None, None
    address = str(address).strip()
    
    # 시도명 목록 (표준 명칭)
    sido_list = ['서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시', 
                 '울산광역시', '세종특별자치시', '경기도', '강원특별자치도', '강원도', '충청북도', '충청남도', 
                 '전라북도', '전북특별자치도', '전라남도', '경상북도', '경상남도', '제주특별자치도']
    
    sido = next((s for s in sido_list if address.startswith(s)), None)
    if not sido:
        return None, None
        
    # 시도명 이후의 주소 부분
    remaining = address[len(sido):].strip()
    
    # 세종특별자치시의 경우 특별 처리 (GeoJSON에서 '세종시'로 되어 있음)
    if sido == '세종특별자치시':
        return sido, "세종시"
    
    # 시군구가 있는 경우 처리
    if remaining:
        parts = remaining.split()
        if parts:
            # 복합 시군구 처리 (시+구, 시+군, 군+구 등)
            sgg_parts = []
            i = 0
            while i < len(parts):
                current_part = parts[i]
                
                # 현재 부분이 시/군/구로 끝나는지 확인
                if current_part.endswith(('시', '군', '구')):
                    sgg_parts.append(current_part)
                    i += 1
                else:
                    # 시/군/구가 아닌 부분이 나오면 중단
                    break
            
            if sgg_parts:
                sgg = " ".join(sgg_parts)
                return sido, sgg
    
    return sido, ""

def normalize_sggnm(sggnm):
    """
    시군구명을 정규화합니다.
    (예: "수원시 장안구" -> "수원시장안구")
    """
    if not sggnm:
        return sggnm
    
    # 공백 제거
    normalized = sggnm.replace(" ", "")
    return normalized

@st.cache_data
def load_and_process_data(excel_path, geojson_path):
    """
    Excel과 GeoJSON 파일을 로드하고, 주소 데이터를 시군구별로 집계하여
    지도 시각화에 사용할 최종 GeoJSON과 매칭되지 않은 주소 목록을 반환합니다.
    """
    try:
        # 1. Excel 파일 로드 및 주소 파싱
        df = pd.read_excel(excel_path)
        df[['sido', 'sgg']] = df['주소'].apply(lambda x: pd.Series(parse_address(x)))
        
        df_valid = df.dropna(subset=['sido'])
        
        # 시군구명 생성 (시도명만 있는 경우와 시군구가 있는 경우 구분)
        def create_sggnm(row):
            if row['sgg']:  # 시군구가 있는 경우
                return f"{row['sido']} {row['sgg']}"
            else:  # 시도명만 있는 경우 (세종특별자치시 등)
                return row['sido']
        
        df_valid['sggnm'] = df_valid.apply(create_sggnm, axis=1)
        
        # 정규화된 시군구명도 생성 (매칭을 위해)
        df_valid['sggnm_normalized'] = df_valid['sggnm'].apply(normalize_sggnm)
        
        # 원본과 정규화된 버전 모두로 카운트
        sgg_counts = {}
        for _, row in df_valid.iterrows():
            sggnm = row['sggnm']
            sggnm_norm = row['sggnm_normalized']
            
            # 원본 버전으로 카운트
            if sggnm not in sgg_counts:
                sgg_counts[sggnm] = 0
            sgg_counts[sggnm] += 1
            
            # 정규화된 버전으로도 카운트 (중복 제거)
            if sggnm_norm != sggnm:
                if sggnm_norm not in sgg_counts:
                    sgg_counts[sggnm_norm] = 0
                sgg_counts[sggnm_norm] += 1
        
        # 2. GeoJSON 파일 로드 및 구조 확인
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        # GeoJSON 구조 디버깅
        st.subheader("🔍 GeoJSON 구조 분석")
        
        # 첫 번째 feature의 properties 확인
        if geojson_data['features']:
            first_feature = geojson_data['features'][0]
            st.write("**첫 번째 feature의 properties:**")
            st.json(first_feature['properties'])
            
            # 모든 properties 키 확인
            all_properties = set()
            for feature in geojson_data['features']:
                all_properties.update(feature['properties'].keys())
            
            st.write("**GeoJSON의 모든 properties 키:**")
            st.write(list(all_properties))
            
            # 시도명과 시군구명 샘플 확인
            sido_samples = set()
            sgg_samples = set()
            for feature in geojson_data['features'][:100]:  # 처음 100개만 확인
                props = feature['properties']
                if 'sidonm' in props:
                    sido_samples.add(props['sidonm'])
                if 'sggnm' in props:
                    sgg_samples.add(props['sggnm'])
            
            st.write("**시도명 샘플 (처음 100개 feature에서):**")
            st.write(list(sido_samples))
            st.write("**시군구명 샘플 (처음 100개 feature에서):**")
            st.write(list(sgg_samples))
        
        # 3. 시군구별 그룹화 (정규화된 버전도 고려)
        sggnm_groups = {}
        for feature in geojson_data['features']:
            properties = feature['properties']
            
            # 시도명과 시군구명을 조합하여 키 생성
            sido = properties.get('sidonm', '')
            sgg = properties.get('sggnm', '')
            
            if sido and sgg:  # 시도명과 시군구명이 모두 있는 경우
                sggnm_key = f"{sido} {sgg}".strip()
                sggnm_key_norm = normalize_sggnm(sggnm_key)
            elif sido:  # 시도명만 있는 경우 (세종특별자치시 등)
                sggnm_key = sido
                sggnm_key_norm = normalize_sggnm(sggnm_key)
            else:
                continue
                
            # 원본과 정규화된 버전 모두 저장
            for key in [sggnm_key, sggnm_key_norm]:
                if key not in sggnm_groups:
                    sggnm_groups[key] = []
                sggnm_groups[key].append(feature)

        # 4. 매칭 결과 확인
        st.subheader("🔍 매칭 결과 분석")
        
        # Excel에서 파싱된 시군구명들
        excel_sgg_keys = set(sgg_counts.keys())
        st.write("**Excel에서 파싱된 시군구명들:**")
        st.write(list(excel_sgg_keys)[:10])  # 처음 10개만 표시
        
        # GeoJSON에서 생성된 시군구명들
        geojson_sgg_keys = set(sggnm_groups.keys())
        st.write("**GeoJSON에서 생성된 시군구명들:**")
        st.write(list(geojson_sgg_keys)[:10])  # 처음 10개만 표시
        
        # 매칭되지 않은 키들
        unmatched_sgg_keys = excel_sgg_keys - geojson_sgg_keys
        st.write("**매칭되지 않은 Excel 시군구명들:**")
        st.write(list(unmatched_sgg_keys)[:10])  # 처음 10개만 표시

        # 5. 시군구 경계 병합 및 카운트 데이터 결합
        merged_features = []
        for sggnm, features in sggnm_groups.items():
            geometries = [shape(f['geometry']) for f in features if f.get('geometry')]
            if not geometries: continue
            
            try:
                merged_geometry = unary_union(geometries)
                merged_geojson_geom = merged_geometry.__geo_interface__
                
                merged_feature = {
                    'type': 'Feature',
                    'geometry': merged_geojson_geom,
                    'properties': {
                        'sggnm': sggnm,
                        'value': sgg_counts.get(sggnm, 0)
                    }
                }
                merged_features.append(merged_feature)
            except Exception:
                continue

        # 6. 매칭되지 않은 주소 찾기
        unmatched_df = pd.DataFrame()
        if unmatched_sgg_keys:
            unmatched_df = df_valid[df_valid['sggnm'].isin(unmatched_sgg_keys)][['주소', 'sido', 'sgg', 'sggnm']].drop_duplicates()

        merged_geojson = {'type': 'FeatureCollection', 'features': merged_features}
        
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
    
    bins = [-1, 0, 5, 10, 20, 50, 100, 200, float('inf')]
    labels = ["0", "1-5", "6-10", "11-20", "21-50", "51-100", "101-200", "201+"]
    plot_df['category'] = pd.cut(plot_df['value'], bins=bins, labels=labels, right=True)
    
    # 8단계에 맞는 색상표 생성
    colors = px.colors.sequential.__getattribute__(color_scale_name)
    color_map = {label: colors[i] for i, label in enumerate(labels)}

    fig = px.choropleth_mapbox(
        plot_df,
        geojson=merged_geojson,
        locations='sggnm',
        featureidkey='properties.sggnm',
        color='category',
        color_discrete_map=color_map,
        category_orders={'category': labels},
        mapbox_style=map_style,
        zoom=5.5,
        center={'lat': 36.5, 'lon': 127.5},
        opacity=0.7,
        labels={'category': '신청 건수', 'sggnm': '시군구'},
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

            # 매칭되지 않은 주소 표시
            st.markdown("---")
            if not unmatched_df.empty:
                st.subheader("⚠️ 매칭되지 않은 주소 목록 (디버깅용)")
                st.warning(
                    "아래 목록의 주소들은 GeoJSON 지도 데이터의 시군구명과 정확히 일치하지 않아 지도에 포함되지 않았습니다. "
                    "주소 파싱 로직이나 원본 데이터의 주소 형식을 확인해 보세요."
                )
                st.dataframe(unmatched_df, use_container_width=True)
            else:
                st.success("✅ 모든 주소가 지도 데이터와 성공적으로 매칭되었습니다.")
        else:
            st.error("지도 생성에 실패했습니다.")

if __name__ == "__main__":
    main()