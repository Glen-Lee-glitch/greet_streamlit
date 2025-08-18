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
def get_model_column_map():
	# car_region_dashboard.py와 동일한 매핑 사용
	return {
		'Model 3 RWD': 'Model 3 RWD_기본',
		'Model 3 RWD (2024)': 'Model 3 RWD(2024)_기본',
		'Model 3 LongRange': 'Model 3 LongRange_기본',
		'Model 3 Performance': 'Model 3 Performance_기본',
		'Model Y New RWD': 'Model Y New RWD_기본',
		'Model Y New LongRange': 'Model Y New LongRange_기본'
	}

def _normalize_region(name):
	if pd.isna(name):
		return ""
	return str(name).strip()

def _find_subsidy_for_region_name(region_name, subsidy_map):
	"""지도 지역명(sggnm)에서 df_master 키와 최대한 유사 매칭하여 보조금 딕셔너리 반환"""
	name = _normalize_region(region_name)
	if not name:
		return {}
	# 1) 직접 일치
	if name in subsidy_map:
		return subsidy_map.get(name, {}) or {}
	# 2) 시/도 분리 및 기본 도시명 후보
	parts = name.split(" ", 1)
	sido = parts[0] if len(parts) == 2 else ""
	key_body = parts[1] if len(parts) == 2 else name
	m = re.search(r'(.+?시)', str(key_body))
	base_city = m.group(1) if m else key_body
	candidates = [key_body, base_city]
	if sido and base_city:
		candidates.append(f"{sido} {base_city}")
	for cand in candidates:
		cand_norm = _normalize_region(cand)
		if cand_norm in subsidy_map:
			return subsidy_map.get(cand_norm, {}) or {}
	# 3) 후방 일치(… {key}) 형태
	for key in subsidy_map.keys():
		key_norm = _normalize_region(key)
		if name.endswith(" " + key_norm) or name.endswith(key_norm):
			return subsidy_map.get(key_norm, {}) or {}
	return {}

def _format_subsidy_value(value):
	"""NaN 방지용 표시 문자열 반환"""
	try:
		if value is None or (isinstance(value, float) and pd.isna(value)):
			return "-"
		return f"{float(value):,.0f} 만원"
	except Exception:
		return "-"

@st.cache_data
def build_subsidy_map(df_master):
	"""
	df_master['지역'] 기준으로 지역별(키) -> {모델명: 보조금(숫자)} 딕셔너리 생성
	"""
	if df_master is None or df_master.empty or '지역' not in df_master.columns:
		return {}

	model_map = get_model_column_map()
	subsidy_map = {}

	for _, row in df_master.iterrows():
		region = _normalize_region(row.get('지역', ''))
		if not region:
			continue

		region_subs = {}
		for model_name, col_name in model_map.items():
			val = row.get(col_name, None)
			try:
				if pd.isna(val) or str(val).strip() == '':
					continue
				# "1,000" 등 문자열을 숫자로
				num = float(str(val).replace(',', ''))
				if num > 0:
					region_subs[model_name] = num
			except Exception:
				continue

		subsidy_map[region] = region_subs

	return subsidy_map

@st.cache_data
def create_korea_map(_merged_geojson, map_style, color_scale_name, subsidy_map=None, models_to_show=None, demographics_map=None):
    """Plotly 지도를 생성합니다. (캐시 적용, 성능 최적화)"""
    if not _merged_geojson or not _merged_geojson['features']: 
        return None, pd.DataFrame()
    
    # GeoJSON 간소화 - 불필요한 속성 제거
    simplified_geojson = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'geometry': f['geometry'],
                'properties': {'sggnm': f['properties']['sggnm'], 'value': f['properties']['value']}
            } for f in _merged_geojson['features']
        ]
    }
    
    plot_df = pd.DataFrame([f['properties'] for f in simplified_geojson['features']])

    # 성별/연령대 텍스트 매핑 추가
    if demographics_map:
        plot_df['gender_text'] = plot_df['sggnm'].map(lambda n: (demographics_map.get(n) or {}).get('gender_text', '-'))
        plot_df['age_text'] = plot_df['sggnm'].map(lambda n: (demographics_map.get(n) or {}).get('age_text', '-'))
    else:
        plot_df['gender_text'] = '-'
        plot_df['age_text'] = '-'

    # subsidy_map, models_to_show의 기본값 처리 (탭/스페이스 혼용 금지)
    if subsidy_map is None:
        subsidy_map = {}
    if not models_to_show:
        # 기본 표시 모델(원하면 바꿔도 됨)
        models_to_show = ['Model Y New RWD', 'Model 3 RWD']

    # 지역명 정규화 및 보조금 매핑(유사 매칭 포함)
    plot_df['region_key'] = plot_df['sggnm'].map(_normalize_region)
    for model in models_to_show:
        raw_col = f"보조금_{model}"
        disp_col = f"보조금표시_{model}"
        # 수치값 추출(매칭 실패시 None)
        plot_df[raw_col] = plot_df['sggnm'].map(
            lambda n: (_find_subsidy_for_region_name(n, subsidy_map) or {}).get(model, None)
        )
        # 표시용 문자열 컬럼 생성("-" 처리 포함)
        plot_df[disp_col] = plot_df[raw_col].map(_format_subsidy_value)

    # 더 단순한 색상 구간으로 변경
    if not plot_df.empty and plot_df['value'].max() > 0:
        bins = [-1, 0, 50, 200, 1000, float('inf')]
        labels = ["0", "1-50", "51-200", "201-1000", "1000+"]
    else:
        bins = [-1, 0, float('inf')]
        labels = ["0", "1+"]
    
    plot_df['category'] = pd.cut(plot_df['value'], bins=bins, labels=labels, right=True).astype(str)
    
    # 고정된 색상 맵 사용 (계산 시간 단축)
    color_map = {
        "0": "#f0f0f0",
        "1-50": "#fee5d9", 
        "51-200": "#fcae91",
        "201-1000": "#fb6a4a",
        "1000+": "#cb181d",
        "1+": "#fee5d9"
    }
    
    fig = px.choropleth_mapbox(
        plot_df, 
        geojson=simplified_geojson, 
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
        hover_name='sggnm', 
        hover_data={'value': True}
    )
    
    # 레이아웃 최적화
    fig.update_layout(
        height=700, 
        margin={'r': 0, 't': 0, 'l': 0, 'b': 0}, 
        legend_title_text='신청 건수',
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01),
        hoverlabel=dict(
            font_size=16,  # 폰트 크기
            font_family="Pretendard, 'Noto Sans KR', Arial",
            bgcolor="rgba(255,255,255,0.95)",  # 배경색(가독성 향상)
            bordercolor="#666"  # 테두리색
        )
    )
    # 지도 성능 최적화
    fig.update_traces(
        marker_line_width=0.5,
        marker_line_color='white'
    )

    # customdata 구성: [value] + [모델별 보조금 표시 문자열...] + [gender_text, age_text]
    custom_cols = ['value'] + [f"보조금표시_{m}" for m in models_to_show] + ['gender_text', 'age_text']
    plot_df['value_fmt'] = plot_df['value'].fillna(0).astype(int)
    fig.update_traces(
        customdata=plot_df[custom_cols].to_numpy(),
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "────────────────────<br>"
            "<b>신청 현황</b><br>"
            "신청 건수: %{customdata[0]:,} 건<br>"
            "<br><b>모델별 보조금</b><br>"
            + "<br>".join([
                f"• {m}: %{{customdata[{idx}]}}"
                for idx, m in enumerate(models_to_show, start=1)
            ])
            + "<br><br><b>성별 비율</b><br>"
            f"%{{customdata[{len(models_to_show) + 1}]}}"
            + "<br><br><b>연령대 분포</b><br>"
            f"%{{customdata[{len(models_to_show) + 2}]}}"
            + "<br>────────────────────"
            + "<extra></extra>"
        )
    )
    
    return fig, plot_df


def _normalize_text_or_empty(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_gender(value):
    """다양한 성별 표기를 '남'/'여'로 표준화"""
    text = _normalize_text_or_empty(value).lower()
    mapping = {
        '남': '남', '남자': '남', '남성': '남', 'm': '남', 'male': '남',
        '여': '여', '여자': '여', '여성': '여', 'f': '여', 'female': '여'
    }
    return mapping.get(text, "")


def _build_demographics_map(df_6, geojson, selected_quarter):
    """GeoJSON의 지역명에 맞춰 df_6에서 성별/연령대 비율 텍스트를 생성하여 dict로 반환"""
    try:
        if df_6 is None or df_6.empty or '지역구분' not in df_6.columns:
            return {}

        # 분기 필터
        df = df_6.copy()
        if '신청일자' in df.columns:
            df['신청일자'] = pd.to_datetime(df['신청일자'], errors='coerce')
        if selected_quarter in ['1Q', '2Q', '3Q', '4Q'] and '신청일자' in df.columns:
            quarter_months = {
                '1Q': [1, 2, 3],
                '2Q': [4, 5, 6],
                '3Q': [7, 8, 9],
                '4Q': [10, 11, 12],
            }[selected_quarter]
            df = df[df['신청일자'].dt.month.isin(quarter_months)]

        # 안전 컬럼 체크
        has_gender = '성별' in df.columns
        has_agegrp = '연령대' in df.columns

        demo_map = {}

        for feature in (geojson or {}).get('features', []):
            sggnm = _normalize_text_or_empty(feature.get('properties', {}).get('sggnm', ''))
            if not sggnm:
                continue

            # 지도 지역명에서 후보 지역 키 생성 (apply_counts_to_map_optimized와 유사)
            parts = sggnm.split(" ", 1)
            sido = parts[0] if len(parts) == 2 else ""
            key_body = parts[1] if len(parts) == 2 else sggnm
            m = re.search(r'(.+?시)', str(key_body))
            map_city_base = m.group(1) if m else key_body
            candidates = [map_city_base]
            if sido and map_city_base:
                candidates.append(f"{sido} {map_city_base}")

            # df_6에서 지역 매칭
            region_series = df['지역구분'].map(_normalize_text_or_empty)
            mask_direct = region_series.isin(candidates)
            # 후방 일치(… {key}) 포함
            mask_suffix = region_series.map(lambda r: bool(sggnm.endswith(" " + r)) or bool(sggnm.endswith(r)))
            matched = df[mask_direct | mask_suffix]

            total = len(matched)
            if total == 0:
                demo_map[sggnm] = {
                    'gender_text': "성별 데이터 없음",
                    'age_text': "연령대 데이터 없음"
                }
                continue

            # 성별 비율 계산
            if has_gender:
                g_counts = matched['성별'].map(_normalize_gender)
                male = int((g_counts == '남').sum())
                female = int((g_counts == '여').sum())
                denom = male + female
                if denom > 0:
                    male_pct = int(round(male * 100 / denom))
                    female_pct = int(round(female * 100 / denom))
                    gender_text = f"남 {male_pct}%/여 {female_pct}%"
                else:
                    gender_text = "성별 데이터 없음"
            else:
                gender_text = "성별 데이터 없음"

            # 연령대 비율 계산 (정해진 순서)
            if has_agegrp:
                order = ["10대", "20대", "30대", "40대", "50대", "60대", "70대 이상"]
                a_counts = matched['연령대'].map(_normalize_text_or_empty).value_counts()
                age_items = []
                for label in order:
                    cnt = int(a_counts.get(label, 0))
                    pct = int(round(cnt * 100 / total)) if total else 0
                    age_items.append(f"{label}: {pct}%")
                # 두 개씩 끊어 줄바꿈 처리
                lines = [" ".join(age_items[i:i+2]) for i in range(0, len(age_items), 2)]
                age_text = "<br>".join(lines)
            else:
                age_text = "연령대 데이터 없음"

            demo_map[sggnm] = {
                'gender_text': gender_text,
                'age_text': age_text
            }

        return demo_map
    except Exception:
        return {}

def show_map_viewer(data, df_6, use_preloaded=True):
    """지도 뷰어 표시 - 사전 로딩된 데이터 활용 옵션 추가"""
    
    st.header("🗺️ 지도 시각화")
    col_q_main, col_q_info = st.columns([8, 2])
    with col_q_main:
        quarter_options = ['전체', '1Q', '2Q', '3Q']
        selected_quarter = st.selectbox("분기 선택", quarter_options)
    with col_q_info:
        # df_6의 신청일자 기준 전체 데이터 기간 표시
        if df_6 is not None and not df_6.empty and '신청일자' in df_6.columns:
            date_series = pd.to_datetime(df_6['신청일자'], errors='coerce')
            if not date_series.dropna().empty:
                min_date = date_series.min().date()
                max_date = date_series.max().date()
                st.markdown(f"<div style='text-align:right; font-size:17px; color:#555;'>조회 기간<br><b>{min_date} ~ {max_date}</b></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='text-align:right; font-size:17px; color:#888;'>조회 기간<br><b>-</b></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align:right; font-size:17px; color:#888;'>조회 기간<br><b>데이터 없음</b></div>", unsafe_allow_html=True)
    
    # 사전 로딩된 데이터 사용
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
            # 툴팁에 표시할 모델 선택 및 보조금 맵 생성
            model_map = get_model_column_map()
            model_options = list(model_map.keys())
            selected_models = st.sidebar.multiselect(
                "툴팁에 표시할 모델",
                options=model_options,
                default=["Model 3 RWD", "Model Y New RWD"]
            )
            df_master = data.get("df_master", pd.DataFrame())
            subsidy_map = build_subsidy_map(df_master)
            
            # 지도와 매칭 정보를 나란히 배치 (9:1 비율)
            map_col, info_col = st.columns([9, 1])
            
            with map_col:
                # 인구통계 맵 생성 후 즉시 지도 표시 (캐시된 데이터 사용)
                demo_map = _build_demographics_map(df_6, final_geojson, selected_quarter)
                result = create_korea_map(
                    final_geojson, map_styles[selected_style], selected_color,
                    subsidy_map, selected_models, demographics_map=demo_map
                )
                if result:
                    fig, df = result
                    st.plotly_chart(fig, use_container_width=True)
            
            with info_col:
                # 매칭되지 않은 지역 목록을 오른쪽에 작게 표시
                if not unmatched_df.empty:
                    st.markdown("**⚠️ 매칭 안됨**")
                    # 작은 폰트로 표시
                    for _, row in unmatched_df.iterrows():
                        st.markdown(f"<small>{row['지역구분']} ({row['카운트']})</small>", unsafe_allow_html=True)
                else:
                    st.markdown("**✅ 매칭 완료**")
                    st.markdown("<small>모든 지역 매칭됨</small>", unsafe_allow_html=True)
            
            # 사이드바 메트릭들
            if result:
                fig, df = result
                st.sidebar.metric("총 지역 수", len(df))
                st.sidebar.metric("데이터가 있는 지역", len(df[df['value'] > 0]))
                st.sidebar.metric("최대 신청 건수", f"{df['value'].max():,}")
                st.sidebar.metric("값 0 지역 수", len(df[df['value'] == 0]))
                
                # 데이터 테이블 표시 (지도 아래)
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
                    
            return  # 사전 로딩 데이터 사용 완료
    
    # 기존 로직 (fallback) - 사전 로딩 실패시
    st.warning("사전 로딩된 데이터를 사용할 수 없어 기존 방식으로 로딩합니다...")
    
    # 미리 처리된 가벼운 지도 파일을 로드 (캐시됨)
    preprocessed_map = load_preprocessed_map('preprocessed_map.geojson')
    
    if preprocessed_map and not df_6.empty:
        # 분기별 필터링된 데이터 가져오기 (캐시됨)
        region_counts = get_filtered_data_optimized(data, selected_quarter)
        
        # 필터링된 데이터를 지도에 적용 (캐시됨)
        final_geojson, unmatched_df = apply_counts_to_map_optimized(preprocessed_map, region_counts)
        
        st.sidebar.header("⚙️ 지도 설정")
        map_styles = {"기본 (밝음)": "carto-positron", "기본 (어두움)": "carto-darkmatter"}
        color_scales = ["Reds","Blues", "Greens", "Viridis"]
        selected_style = st.sidebar.selectbox("지도 스타일", list(map_styles.keys()))
        selected_color = st.sidebar.selectbox("색상 스케일", color_scales)
        # 툴팁에 표시할 모델 선택 및 보조금 맵 생성
        model_map = get_model_column_map()
        model_options = list(model_map.keys())
        selected_models = st.sidebar.multiselect(
            "툴팁에 표시할 모델",
            options=model_options,
            default=["Model 3 RWD", "Model Y New RWD"]
        )
        df_master = data.get("df_master", pd.DataFrame())
        subsidy_map = build_subsidy_map(df_master)
        
        # 지도와 매칭 정보를 나란히 배치 (9:1 비율)
        map_col, info_col = st.columns([9, 1])
        
        with map_col:
            # 인구통계 맵 생성 후 지도 생성 (캐시됨)
            demo_map = _build_demographics_map(df_6, final_geojson, selected_quarter)
            result = create_korea_map(
                final_geojson, map_styles[selected_style], selected_color,
                subsidy_map, selected_models, demographics_map=demo_map
            )
            if result:
                fig, df = result
                st.plotly_chart(fig, use_container_width=True)
        
        with info_col:
            # 매칭되지 않은 지역 목록을 오른쪽에 작게 표시
            if not unmatched_df.empty:
                st.markdown("**⚠️ 매칭 안됨**")
                # 작은 폰트로 표시
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

            # 값 유무에 따라 분할
            df_nonzero = df[df['value'] > 0][['sggnm', 'value']].sort_values('value', ascending=False)
            df_zero = df[df['value'] == 0][['sggnm', 'value']].sort_values('sggnm')

            # value > 0 테이블 (기존 상단 테이블 대체)
            if not df_nonzero.empty:
                st.dataframe(df_nonzero, use_container_width=True)
            else:
                st.info("value > 0 인 지역이 없습니다.")

            # value = 0 테이블 (아래 별도 섹션)
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
    
    # 페이지 설정
    st.set_page_config(
        page_title="지도 뷰어",
        page_icon="🗺️",
        layout="wide"
    )
    
    # 기본 스타일 추가
    st.markdown("""
    <style>
        /* 기본 테이블 스타일 */
        .custom_table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }
        .custom_table th, .custom_table td {
            border: 1px solid #e0e0e0;
            padding: 8px;
            text-align: center;
        }
        .custom_table th {
            background-color: #f7f7f9;
            font-weight: bold;
        }
        .custom_table tr:nth-child(even) {
            background-color: #fafafa;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # 데이터 로딩
    @st.cache_data(ttl=3600)
    def load_data():
        """전처리된 데이터 파일을 로드합니다."""
        try:
            with open("preprocessed_data.pkl", "rb") as f:
                return pickle.load(f)
        except FileNotFoundError:
            st.error("전처리된 데이터 파일(preprocessed_data.pkl)을 찾을 수 없습니다.")
            st.info("먼저 '전처리.py'를 실행하여 데이터 파일을 생성해주세요.")
            return {}
    
    # 데이터 로드
    data = load_data()
    
    if data:
        df_6 = data.get("df_6", pd.DataFrame())
        # 지도 뷰어 실행
        show_map_viewer(data, df_6)
    else:
        st.error("데이터를 로드할 수 없습니다.")
        st.stop()

if __name__ == "__main__":
    main()