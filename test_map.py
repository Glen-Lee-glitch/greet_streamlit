import streamlit as st
import pandas as pd
import json
import plotly.express as px
import os
import re

@st.cache_data
def load_preprocessed_map(geojson_path):
    """
    미리 병합된 가벼운 GeoJSON 파일을 로드합니다.
    이 함수는 무거운 지오메트리 연산을 수행하지 않습니다.
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
    """사전 계산된 분기별 데이터에서 바로 반환"""
    quarterly_counts = data.get("quarterly_region_counts", {})
    return quarterly_counts.get(selected_quarter, {})
    
@st.cache_data
def apply_counts_to_map_optimized(_preprocessed_map, _region_counts):
    """메모리 효율적인 GeoJSON 매핑"""
    if not _preprocessed_map:
        return None, pd.DataFrame()

    # 깊은 복사 대신 참조로 처리하고 필요한 부분만 수정
    final_geojson = {
        'type': _preprocessed_map['type'],
        'features': []
    }
    
    # 지역별 카운트 맵 생성 (한 번만)
    region_count_map = _region_counts
    unmatched_regions = set(_region_counts.keys())
    
    for feature in _preprocessed_map['features']:
        new_feature = {
            'type': feature['type'],
            'geometry': feature['geometry'],  # 지오메트리는 참조만
            'properties': feature['properties'].copy()  # 속성만 복사
        }
        
        region_name = new_feature['properties']['sggnm']
        matched_count = 0
        
        # 직접 매칭
        if region_name in region_count_map:
            matched_count = region_count_map[region_name]
            unmatched_regions.discard(region_name)
        else:
            # 1) 기존: '... {시}'로 끝나는 경우
            for region, count in region_count_map.items():
                if region_name.endswith(" " + region):
                    matched_count = count
                    unmatched_regions.discard(region)
                    break

            # 2) 보강: 지도 키에서 시/시도+시를 모두 후보로 매칭
            if matched_count == 0:
                # '경기도 부천시소사구' → sido='경기도', key_body='부천시소사구' → city='부천시'
                parts = region_name.split(" ", 1)
                sido = parts[0] if len(parts) == 2 else ""
                key_body = parts[1] if len(parts) == 2 else region_name

                m = re.search(r'(.+?시)', str(key_body))
                map_city_base = m.group(1) if m else key_body

                candidates = [map_city_base]  # '부천시'
                if sido and map_city_base:
                    candidates.append(f"{sido} {map_city_base}")  # '경기도 부천시'

                for cand in candidates:
                    if cand in region_count_map:
                        matched_count = region_count_map[cand]
                        unmatched_regions.discard(cand)
                        break
        
        new_feature['properties']['value'] = matched_count
        final_geojson['features'].append(new_feature)
    
    unmatched_df = pd.DataFrame({
        '지역구분': list(unmatched_regions),
        '카운트': [region_count_map.get(r, 0) for r in unmatched_regions]
    })

    return final_geojson, unmatched_df

@st.cache_data
def create_korea_map(_merged_geojson, map_style, color_scale_name):
    """Plotly 지도를 생성합니다. (툴팁 커스터마이징 적용)"""
    if not _merged_geojson or not _merged_geojson['features']: 
        return None, pd.DataFrame()
    
    plot_df = pd.DataFrame([f['properties'] for f in _merged_geojson['features']])
    
    if not plot_df.empty and plot_df['value'].max() > 0:
        bins = [-1, 0, 50, 200, 1000, float('inf')]
        labels = ["0", "1-50", "51-200", "201-1000", "1000+"]
    else:
        bins = [-1, 0, float('inf')]
        labels = ["0", "1+"]
    
    plot_df['category'] = pd.cut(plot_df['value'], bins=bins, labels=labels, right=True).astype(str)
    
    color_map = {
        "0": "#f0f0f0", "1-50": "#fee5d9", "51-200": "#fcae91",
        "201-1000": "#fb6a4a", "1000+": "#cb181d", "1+": "#fee5d9"
    }
    
    # --- 툴팁 커스터마이징 ---
    # 1. 툴팁에 표시할 내용 정의
    hovertemplate = (
        "<b>%{customdata[0]}</b><br><br>" +  # 지역명 (sggnm)
        "신청 건수: %{customdata[1]:,}건<br>" + # 값 (value)
        "구간: %{customdata[2]}" +             # 구간 (category)
        "<extra></extra>" # Plotly의 보조 툴팁 숨기기
    )
    
    fig = px.choropleth_mapbox(
        plot_df, 
        geojson=_merged_geojson, 
        locations='sggnm', 
        featureidkey='properties.sggnm',
        color='category', 
        color_discrete_map=color_map, 
        category_orders={'category': labels},
        mapbox_style=map_style, 
        zoom=6, 
        center={'lat': 36.5, 'lon': 127.5}, 
        opacity=0.8,
        labels={'category': '신청 건수', 'sggnm': '지역'},
        # 2. 툴팁에 사용할 데이터 전달
        custom_data=['sggnm', 'value', 'category']
    )
    
    # 3. 툴팁 스타일 및 템플릿 적용
    fig.update_traces(
        hovertemplate=hovertemplate,
        hoverlabel=dict(
            bgcolor="white",
            font_size=16, # 글자 크기 키우기
            font_family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"
        ),
        marker_line_width=0.5,
        marker_line_color='white'
    )
    
    fig.update_layout(
        height=700, 
        margin={'r': 0, 't': 0, 'l': 0, 'b': 0}, 
        legend_title_text='신청 건수',
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01)
    )
    
    return fig, plot_df

def show_map_viewer(data, df_6, use_preloaded=True):
    """지도 뷰어 표시 - 사전 로딩된 데이터 활용 옵션 추가"""
    
    st.header("🗺️ 지도 시각화")
    quarter_options = ['전체', '1Q', '2Q', '3Q']
    selected_quarter = st.selectbox("분기 선택", quarter_options)
    
    if use_preloaded and hasattr(st.session_state, 'map_preloaded_data'):
        preloaded_data = st.session_state.map_preloaded_data.get(selected_quarter)
        
        if preloaded_data:
            final_geojson = preloaded_data['geojson']
            unmatched_df = preloaded_data['unmatched']
            
            st.sidebar.header("⚙️ 지도 설정")
            map_styles = {"기본 (밝음)": "carto-positron", "기본 (어두움)": "carto-darkmatter"}
            color_scales = ["Reds","Blues", "Greens", "Viridis"]
            selected_style = st.sidebar.selectbox("지도 스타일", list(map_styles.keys()))
            selected_color = st.sidebar.selectbox("색상 스케일", color_scales)
            
            map_col, info_col = st.columns([9, 1])
            
            with map_col:
                result = create_korea_map(final_geojson, map_styles[selected_style], selected_color)
                if result:
                    fig, df = result
                    st.plotly_chart(fig, use_container_width=True)
            
            with info_col:
                if not unmatched_df.empty:
                    st.markdown("**⚠️ 매칭 안됨**")
                    for _, row in unmatched_df.iterrows():
                        st.markdown(f"<small>{row['지역구분']} ({row['카운트']})</small>", unsafe_allow_html=True)
                else:
                    st.markdown("**✅ 매칭 완료**")
                    st.markdown("<small>모든 지역 매칭됨</small>", unsafe_allow_html=True)
            
            if result:
                fig, df = result
                st.sidebar.metric("총 지역 수", len(df))
                st.sidebar.metric("데이터가 있는 지역", len(df[df['value'] > 0]))
                st.sidebar.metric("최대 신청 건수", f"{df['value'].max():,}")
                st.sidebar.metric("값 0 지역 수", len(df[df['value'] == 0]))
                
                st.subheader("데이터 테이블")
                df_nonzero = df[df['value'] > 0][['sggnm', 'value']].sort_values('value', ascending=False)
                df_zero = df[df['value'] == 0][['sggnm', 'value']].sort_values('sggnm')
                
                if not df_nonzero.empty:
                    st.dataframe(df_nonzero, use_container_width=True)
                else:
                    st.info("value > 0 인 지역이 없습니다.")
                
                if not df_zero.empty:
                    st.markdown("---")
                    st.subheader("값 0 지역 목록")
                    html_zero = df_zero.to_html(classes='custom_table', border=0, index=False)
                    st.markdown(html_zero, unsafe_allow_html=True)
                else:
                    st.info("value = 0 인 지역이 없습니다.")
                    
            return
    
    st.warning("사전 로딩된 데이터를 사용할 수 없어 기존 방식으로 로딩합니다...")
    
    preprocessed_map = load_preprocessed_map('preprocessed_map.geojson')
    
    if preprocessed_map and not df_6.empty:
        region_counts = get_filtered_data_optimized(data, selected_quarter)
        final_geojson, unmatched_df = apply_counts_to_map_optimized(preprocessed_map, region_counts)
        
        st.sidebar.header("⚙️ 지도 설정")
        map_styles = {"기본 (밝음)": "carto-positron", "기본 (어두움)": "carto-darkmatter"}
        color_scales = ["Reds","Blues", "Greens", "Viridis"]
        selected_style = st.sidebar.selectbox("지도 스타일", list(map_styles.keys()))
        selected_color = st.sidebar.selectbox("색상 스케일", color_scales)
        
        map_col, info_col = st.columns([9, 1])
        
        with map_col:
            result = create_korea_map(final_geojson, map_styles[selected_style], selected_color)
            if result:
                fig, df = result
                st.plotly_chart(fig, use_container_width=True)
        
        with info_col:
            if not unmatched_df.empty:
                st.markdown("**⚠️ 매칭 안됨**")
                for _, row in unmatched_df.iterrows():
                    st.markdown(f"<small>{row['지역구분']} ({row['카운트']})</small>", unsafe_allow_html=True)
            else:
                st.markdown("**✅ 매칭 완료**")
                st.markdown("<small>모든 지역 매칭됨</small>", unsafe_allow_html=True)
        
        if result:
            fig, df = result
            st.sidebar.metric("총 지역 수", len(df))
            st.sidebar.metric("데이터가 있는 지역", len(df[df['value'] > 0]))
            st.sidebar.metric("최대 신청 건수", f"{df['value'].max():,}")
            st.sidebar.metric("값 0 지역 수", len(df[df['value'] == 0]))
            
            st.subheader("데이터 테이블")

            df_nonzero = df[df['value'] > 0][['sggnm', 'value']].sort_values('value', ascending=False)
            df_zero = df[df['value'] == 0][['sggnm', 'value']].sort_values('sggnm')

            if not df_nonzero.empty:
                st.dataframe(df_nonzero, use_container_width=True)
            else:
                st.info("value > 0 인 지역이 없습니다.")

            if not df_zero.empty:
                st.markdown("---")
                st.subheader("값 0 지역 목록")
                html_zero = df_zero.to_html(classes='custom_table', border=0, index=False)
                st.markdown(html_zero, unsafe_allow_html=True)
            else:
                st.info("value = 0 인 지역이 없습니다.")

def main():
    """지도 뷰어를 독립적으로 실행하기 위한 메인 함수"""
    import pickle
    import pytz
    from datetime import datetime
    
    st.set_page_config(page_title="지도 뷰어", page_icon="🗺️", layout="wide")
    
    st.markdown("""
    <style>
        .custom_table {
            width: 100%; border-collapse: collapse; font-size: 0.9rem;
        }
        .custom_table th, .custom_table td {
            border: 1px solid #e0e0e0; padding: 8px; text-align: center;
        }
        .custom_table th {
            background-color: #f7f7f9; font-weight: bold;
        }
        .custom_table tr:nth-child(even) {
            background-color: #fafafa;
        }
    </style>
    """, unsafe_allow_html=True)
    
    @st.cache_data(ttl=3600)
    def load_data():
        try:
            with open("preprocessed_data.pkl", "rb") as f:
                return pickle.load(f)
        except FileNotFoundError:
            st.error("preprocessed_data.pkl 파일을 찾을 수 없습니다.")
            return {}
    
    data = load_data()
    
    if data:
        df_6 = data.get("df_6", pd.DataFrame())
        show_map_viewer(data, df_6)
    else:
        st.error("데이터를 로드할 수 없습니다.")
        st.stop()

if __name__ == "__main__":
    main()
