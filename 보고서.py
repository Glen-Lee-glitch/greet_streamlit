import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pandas.tseries.offsets import CustomBusinessDay
import numpy as np
import altair as alt
import pickle
import os
import json
import re
import plotly.express as px
from shapely.geometry import shape
from shapely.ops import unary_union

import sys
from datetime import datetime, timedelta, date
import pytz

# 별도 뷰어 모듈 임포트
from polestar_viewer import show_polestar_viewer
from map_viewer import show_map_viewer, apply_counts_to_map_optimized
from car_region_dashboard import show_car_region_dashboard


# 기존 import 섹션 뒤에 추가
@st.cache_data(ttl=7200)  # 2시간 캐시
def preload_map_data():
    """애플리케이션 시작 시 지도 데이터를 미리 로드합니다."""
    try:
        # 1. 전처리된 지도 파일 로드
        if os.path.exists('preprocessed_map.geojson'):
            with open('preprocessed_map.geojson', 'r', encoding='utf-8') as f:
                preprocessed_map = json.load(f)
        else:
            return None, {}
        
        # 2. 분기별 데이터 모두 미리 처리
        quarter_options = ['전체', '1Q', '2Q', '3Q']
        preloaded_maps = {}
        
        for quarter in quarter_options:
            # 분기별 지역 카운트 가져오기
            quarterly_counts = st.session_state.quarterly_counts
            region_counts = quarterly_counts.get(quarter, {})
            
            # 지도에 데이터 적용
            final_geojson, unmatched_df = apply_counts_to_map_optimized(
                preprocessed_map, region_counts
            )
            
            preloaded_maps[quarter] = {
                'geojson': final_geojson,
                'unmatched': unmatched_df
            }
        
        return preprocessed_map, preloaded_maps
        
    except Exception as e:
        st.error(f"지도 사전 로딩 중 오류: {e}")
        return None, {}

# --- 페이지 설정 및 기본 스타일 ---
st.set_page_config(layout="wide")
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
    /* 사이드바 스타일 */
    .css-1d391kg {
        padding-top: 3rem;
    }
    /* 인쇄 또는 PDF 생성 시 불필요한 UI 숨기기 */
    @media print {
        /* 사이드바와 모든 no-print 클래스 요소 숨기기 */
        div[data-testid="stSidebar"], .no-print {
            display: none !important;
        }
        /* 메인 콘텐츠 영역 패딩 조절 */
        .main .block-container {
            padding: 1rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- 데이터 및 메모 로딩 함수 ---
@st.cache_data(ttl=3600)
def load_data():
    """전처리된 데이터 파일을 로드합니다."""
    try:
        with open("preprocessed_data.pkl", "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        st.error("전처리된 데이터 파일(preprocessed_data.pkl)을 찾을 수 없습니다.")
        st.info("먼저 '전처리.py'를 실행하여 데이터 파일을 생성해주세요.")

def get_base_city_name(sggnm_str):
    """
    시군구명에서 기본 시 이름을 추출합니다.
    예: '수원시팔달구' -> '수원시', '청주시흥덕구' -> '청주시'
    """
    if pd.isna(sggnm_str): return None
    sggnm_str = str(sggnm_str)
    match = re.search(r'(.+?시)', sggnm_str)
    if match:
        return match.group(1)
    return sggnm_str

@st.cache_data
def load_and_process_data(region_counts, geojson_path):
    """
    df_6 데이터를 GeoJSON과 매칭하고, 3가지 케이스에 맞춰
    GeoJSON의 경계를 동적으로 병합하여 최종 지도 데이터를 생성합니다.
    """
    try:
        # 1. GeoJSON 파일 로드
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)

        # --- 2. GeoJSON 그룹화 (핵심 로직) ---
        geometries_to_merge = {}
        
        sido_special_list = [
            '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시', 
            '울산광역시', '세종특별자치시', '제주특별자치도'
        ]

        for feature in geojson_data['features']:
            properties = feature['properties']
            sido = properties.get('sidonm', '')
            sgg = properties.get('sggnm', '')
            if not (sido and sgg and feature.get('geometry')):
                continue

            geom = shape(feature['geometry'])

            # Case 1: 서울특별시, 광역시 등은 '시도' 이름으로 그룹화
            if sido in sido_special_list:
                key = sido
            # Case 2 & 3: 그 외 지역은 '시도 시군구' 이름으로 그룹화
            else:
                # '수원시영통구' -> '수원시'로 변환
                base_sgg = get_base_city_name(sgg)
                key = f"{sido} {base_sgg}"
            
            if key not in geometries_to_merge:
                geometries_to_merge[key] = []
            geometries_to_merge[key].append(geom)

        # --- 3. 지오메트리 병합 ---
        base_map_geoms = {}
        for key, geoms in geometries_to_merge.items():
            if geoms:
                try:
                    base_map_geoms[key] = unary_union(geoms)
                except Exception:
                    continue
        
        # --- 4. df_6 데이터를 병합된 지도에 매핑 ---
        final_counts = {key: 0 for key in base_map_geoms.keys()}
        unmatched_regions = set(region_counts.keys())

        for region, count in region_counts.items():
            region_str = str(region).strip()
            matched = False
            
            # Case 1: '서울특별시'와 같은 시도명 직접 매칭
            if region_str in final_counts:
                final_counts[region_str] += count
                unmatched_regions.discard(region_str)
                matched = True
            
            # Case 2 & 3: '수원시' -> '경기도 수원시'와 같은 시군구명 매칭
            if not matched:
                base_region = get_base_city_name(region_str)

                # 1) 기존: '... {시}'로 끝나는 키 우선 매칭
                for key in final_counts.keys():
                    if key.endswith(" " + base_region):
                        final_counts[key] += count
                        unmatched_regions.discard(region_str)
                        matched = True
                        break

                # 2) 보강: 키의 시 부분만 추출해서 동일한지 비교 (예: '경기도 부천시소사구' → '부천시')
                if not matched:
                    for key in final_counts.keys():
                        # '경기도 부천시소사구' → '부천시소사구' → '부천시'
                        key_body = key.split(" ", 1)[1] if " " in key else key
                        key_city_base = get_base_city_name(key_body)
                        if key_city_base == base_region:
                            final_counts[key] += count
                            unmatched_regions.discard(region_str)
                            matched = True
                            break
        
        # --- 5. 최종 GeoJSON 생성 ---
        merged_features = []
        for region_key, geom in base_map_geoms.items():
            merged_feature = {
                'type': 'Feature',
                'geometry': geom.__geo_interface__,
                'properties': {
                    'sggnm': region_key, # 병합된 지역의 이름을 key로 사용
                    'value': final_counts.get(region_key, 0)
                }
            }
            merged_features.append(merged_feature)

        merged_geojson = {'type': 'FeatureCollection', 'features': merged_features}
        
        unmatched_df = pd.DataFrame({
            '지역구분': list(unmatched_regions),
            '카운트': [region_counts.get(r, 0) for r in unmatched_regions]
        })

        return merged_geojson, unmatched_df

    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
        return None, pd.DataFrame()

def load_memo():
    """저장된 메모를 로드합니다."""
    try:
        with open("memo.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

# --- 데이터 로딩 ---
data = load_data()
df = data["df"]
df_1 = data["df_1"]
df_2 = data["df_2"]
df_3 = data["df_3"]
df_4 = data["df_4"]
df_5 = data["df_5"]
df_sales = data["df_sales"]
df_fail_q3 = data["df_fail_q3"]
df_2_fail_q3 = data["df_2_fail_q3"]
update_time_str = data["update_time_str"]
df_master = data.get("df_master", pd.DataFrame())  # 지자체 정리 master.xlsx 데이터
df_6 = data.get("df_6", pd.DataFrame())  # 지역구분 데이터
df_tesla_ev = data["df_tesla_ev"]
preprocessed_map_geojson = data["preprocessed_map_geojson"]

def load_quarterly_counts():
    """분기별 카운트 데이터만 별도로 로드"""
    try:
        with open("preprocessed_data.pkl", "rb") as f:
            data = pickle.load(f)
        return data.get("quarterly_region_counts", {})
    except:
        return {}

if 'quarterly_counts' not in st.session_state:
    st.session_state.quarterly_counts = load_quarterly_counts()

# 지도 데이터 사전 로딩
if 'map_preloaded' not in st.session_state:
    with st.spinner('🗺️ 지도 데이터를 준비하는 중입니다...'):
        preprocessed_map, preloaded_maps = preload_map_data()
        st.session_state.map_preprocessed = preprocessed_map
        st.session_state.map_preloaded_data = preloaded_maps
        st.session_state.map_preloaded = True


# --- 시간대 설정 ---
KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()

# 전일 계산에서 제외할 공휴일(YYYY-MM-DD)
holiday_lst = [
	'2025-08-15',
    '2025-10-03',
    '2025-10-06',
    '2025-10-07',
    '2025-10-09',
]
# 주말 + 공휴일 제외 영업일 오프셋
cbd = CustomBusinessDay(weekmask='Mon Tue Wed Thu Fri', holidays=pd.to_datetime(holiday_lst))

# --- 사이드바: 조회 옵션 설정 ---
with st.sidebar:
    if hasattr(st.session_state, 'map_preloaded') and st.session_state.map_preloaded:
        st.success("✅ 지도 준비 완료")
        if hasattr(st.session_state, 'map_preloaded_data'):
            quarters_ready = len(st.session_state.map_preloaded_data)
    else:
        st.warning("⏳ 지도 준비 중...")


    st.header("👁️ 뷰어 옵션")
    viewer_option = st.radio("뷰어 유형을 선택하세요.", ('내부', '테슬라', '폴스타', '지도', '분석'), key="viewer_option")
    st.markdown("---")
    st.header("📊 조회 옵션")
    view_option = st.radio(
        "조회 유형을 선택하세요.",
        ('금일', '특정일 조회', '기간별 조회'),
        key="view_option"
    )

    start_date, end_date = None, None
    
    lst_1 = ['내부', '테슬라']

    if viewer_option in lst_1:

        if view_option == '금일' :
            title = f"금일 리포트 - {today_kst.strftime('%Y년 %m월 %d일')}"
        else:
            title = f"{view_option} 리포트"

        if view_option == '금일':
            start_date = end_date = today_kst
        elif view_option == '특정일 조회':
            # 6월 24일부터만 선택 가능하도록 최소 날짜 제한 설정
            earliest_date = datetime(today_kst.year, 6, 24).date()
            # 만약 오늘이 6월 24일 이전이라면 전년도 6월 24일을 최소값으로 사용
            if today_kst < earliest_date:
                earliest_date = datetime(today_kst.year - 1, 6, 24).date()
            selected_date = st.date_input(
                '날짜 선택',
                value=max(today_kst, earliest_date),
                min_value=earliest_date,
                max_value=today_kst
            )
            start_date = end_date = selected_date
            title = f"{selected_date.strftime('%Y-%m-%d')} 리포트"
        elif view_option == '기간별 조회':
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input('시작일', value=today_kst.replace(day=1))
            with col2:
                end_date = st.date_input('종료일', value=today_kst)
            if start_date > end_date:
                st.error("시작일이 종료일보다 늦을 수 없습니다.")
                st.stop()
            title = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} 리포트"
        elif view_option == '분기별 조회':
            year = today_kst.year
            quarter = st.selectbox('분기 선택', [f'{q}분기' for q in range(1, 5)], index=(today_kst.month - 1) // 3)
            q_num = int(quarter[0])
            start_month = 3 * q_num - 2
            end_month = 3 * q_num
            start_date = datetime(year, start_month, 1).date()
            end_day = (datetime(year, end_month % 12 + 1, 1) - timedelta(days=1)).day if end_month < 12 else 31
            end_date = datetime(year, end_month, end_day).date()
            title = f"{year}년 {quarter} 리포트"
        elif view_option == '월별 조회':
            year = today_kst.year
            month = st.selectbox('월 선택', [f'{m}월' for m in range(1, 13)], index=today_kst.month - 1)
            month_num = int(month[:-1])
            start_date = datetime(year, month_num, 1).date()
            end_day = (datetime(year, (month_num % 12) + 1, 1) - timedelta(days=1)).day if month_num < 12 else 31
            end_date = datetime(year, month_num, end_day).date()
            title = f"{year}년 {month} 리포트"

        # 월별 요약은 항상 표시
    show_monthly_summary = True

    st.markdown("---")
    st.header("📝 메모")
    memo_content = load_memo()
    new_memo = st.text_area(
        "메모를 입력하거나 수정하세요.",
        value=memo_content, height=250, key="memo_input"
    )
    if new_memo != memo_content:
        with open("memo.txt", "w", encoding="utf-8") as f:
            f.write(new_memo)
        st.toast("메모가 저장되었습니다!")

# --- 메인 대시보드 ---

if viewer_option in lst_1:
    st.title(title)
    st.caption(f"마지막 데이터 업데이트: {update_time_str}")
    st.markdown("---")
else:
    pass

# --- 계산 함수 (기존과 동일) ---
def get_corporate_metrics(df3_raw, df4_raw, start, end):
    """기간 내 법인팀 실적을 계산합니다."""
    # 지원 (파이프라인, 지원신청)
    pipeline, apply = 0, 0
    df3 = df3_raw.copy()
    date_col_3 = '신청 요청일'
    if not pd.api.types.is_datetime64_any_dtype(df3[date_col_3]):
        df3[date_col_3] = pd.to_datetime(df3[date_col_3], errors='coerce')
    
    mask3 = (df3[date_col_3].dt.date >= start) & (df3[date_col_3].dt.date <= end)
    df3_period = df3.loc[mask3].dropna(subset=[date_col_3])

    df3_period = df3_period[df3_period['접수 완료'].astype(str).str.strip().isin(['O', 'ㅇ'])]
    if '그리트 노트' in df3_period.columns:
        is_cancelled = df3_period['그리트 노트'].astype(str).str.contains('취소', na=False)
        is_reapplied = df3_period['그리트 노트'].astype(str).str.contains('취소 후 재신청', na=False)
        df3_period = df3_period[~(is_cancelled & ~is_reapplied)]
    
    b_col_name = df3_period.columns[1]
    df3_period = df3_period[df3_period[b_col_name].notna() & (df3_period[b_col_name] != "")]

    pipeline = int(df3_period['신청대수'].sum())
    mask_bulk_3 = df3_period['신청대수'] > 1
    mask_single_3 = df3_period['신청대수'] == 1
    apply = int(mask_bulk_3.sum() + df3_period.loc[mask_single_3, '신청대수'].sum())

    # 지급 (지급신청)
    distribute = 0
    df4 = df4_raw.copy()
    date_col_4 = '요청일자'
    if not pd.api.types.is_datetime64_any_dtype(df4[date_col_4]):
        df4[date_col_4] = pd.to_datetime(df4[date_col_4], errors='coerce')

    mask4 = (df4[date_col_4].dt.date >= start) & (df4[date_col_4].dt.date <= end)
    df4_period = df4.loc[mask4].dropna(subset=[date_col_4])
    
    df4_period = df4_period[df4_period['지급신청 완료 여부'].astype(str).str.strip() == '완료']
    unique_df4_period = df4_period.drop_duplicates(subset=['신청번호'])

    mask_bulk_4 = unique_df4_period['접수대수'] > 1
    mask_single_4 = unique_df4_period['접수대수'] == 1
    distribute = int(mask_bulk_4.sum() + unique_df4_period.loc[mask_single_4, '접수대수'].sum())

    return {'pipeline': pipeline, 'apply': apply, 'distribute': distribute}

# --- 실적 계산 ---
corporate_metrics = get_corporate_metrics(df_3, df_4, start_date, end_date)

# --- 특이사항 추출 ---
def extract_special_memo(df_fail_q3, today):
    """
    오늘 날짜의 df_fail_q3에서 'Greet Note'별 건수를 ['내용', '건수'] 형태로 한 줄씩 리스트로 반환합니다.
    """
    # '날짜' 컬럼이 datetime이 아닐 경우 변환
    if not pd.api.types.is_datetime64_any_dtype(df_fail_q3['날짜']):
        df_fail_q3['날짜'] = pd.to_datetime(df_fail_q3['날짜'], errors='coerce')
    # 오늘 날짜 필터링
    today_fail = df_fail_q3[df_fail_q3['날짜'].dt.date == today]
    # 'Greet Note' 컬럼명을 유연하게 찾기 (공백·대소문자 무시)
    lowered_cols = {c.lower().replace(' ', ''): c for c in today_fail.columns}
    # 'greetnote' 또는 '노트' 키워드 포함 컬럼 탐색
    note_col = next((orig for key, orig in lowered_cols.items() if 'greetnote' in key or '노트' in key), None)
    if note_col is None:
        return []
    # value_counts
    note_counts = today_fail[note_col].astype(str).value_counts().reset_index()
    note_counts.columns = ['내용', '건수']
    # 한 줄씩 메모 형태로 변환
    memo_lines = [f"{row['내용']}: {row['건수']}건" for _, row in note_counts.iterrows()]
    return memo_lines

if viewer_option == '내부' or viewer_option == '테슬라':

    # --- 대시보드 표시 ---
    col1, col2, col3 = st.columns([3.5,2,1.5])

    with col1:
        st.write("### 1. 리테일 금일/전일 요약")

        selected_date = end_date
        day0 = selected_date
        day1 = (pd.to_datetime(selected_date) - cbd).date()

        year = selected_date.year
        q3_start_default = datetime(year, 6, 24).date()
        q3_start_distribute = datetime(year, 7, 1).date()

        # 기간별 조회인지 확인
        is_period_view = view_option == '기간별 조회'

        if is_period_view:
            # 기간별 조회: 선택한 기간의 합계와 누적 총계만 표시
            cnt_period_mail = ((df_5['날짜'].dt.date >= start_date) & (df_5['날짜'].dt.date <= end_date)).sum()
            cnt_total_mail = ((df_5['날짜'].dt.date >= q3_start_default) & (df_5['날짜'].dt.date <= end_date)).sum()

            cnt_period_apply = int(df_1.loc[(df_1['날짜'].dt.date >= start_date) & (df_1['날짜'].dt.date <= end_date), '개수'].sum())
            cnt_total_apply = int(df_1.loc[(df_1['날짜'].dt.date >= q3_start_default) & (df_1['날짜'].dt.date <= end_date), '개수'].sum())

            cnt_period_distribute = int(df_2.loc[(df_2['날짜'].dt.date >= start_date) & (df_2['날짜'].dt.date <= end_date), '배분'].sum())
            cnt_total_distribute = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= end_date), '배분'].sum())

            cnt_period_request = int(df_2.loc[(df_2['날짜'].dt.date >= start_date) & (df_2['날짜'].dt.date <= end_date), '신청'].sum())
            cnt_total_request = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= end_date), '신청'].sum())

            # df_fail_q3, df_2_fail_q3 날짜 타입 보정
            if not pd.api.types.is_datetime64_any_dtype(df_fail_q3['날짜']):
                df_fail_q3['날짜'] = pd.to_datetime(df_fail_q3['날짜'], errors='coerce')
            if not pd.api.types.is_datetime64_any_dtype(df_2_fail_q3['날짜']):
                df_2_fail_q3['날짜'] = pd.to_datetime(df_2_fail_q3['날짜'], errors='coerce')

            # 미신청건 계산 (기간별)
            cnt_period_fail = int(((df_fail_q3['날짜'].dt.date >= start_date) & (df_fail_q3['날짜'].dt.date <= end_date)).sum())
            cnt_total_fail = int(((df_fail_q3['날짜'].dt.date >= q3_start_default) & (df_fail_q3['날짜'].dt.date <= end_date)).sum())

            # 지급 미신청건 계산 (기간별)
            cnt_period_fail_2 = int(df_2_fail_q3.loc[(df_2_fail_q3['날짜'].dt.date >= start_date) & (df_2_fail_q3['날짜'].dt.date <= end_date), '미신청건'].sum())
            cnt_total_fail_2 = int(df_2_fail_q3.loc[(df_2_fail_q3['날짜'].dt.date >= q3_start_default) & (df_2_fail_q3['날짜'].dt.date <= end_date), '미신청건'].sum())

            table_data = pd.DataFrame({
                ('지원', '파이프라인', '메일 건수'): [cnt_period_mail, cnt_total_mail],
                ('지원', '신청', '신청 건수'): [cnt_period_apply, cnt_total_apply],
                ('지원', '신청', '미신청건'): [cnt_period_fail, cnt_total_fail],
                ('지급', '지급 처리', '지급 배분건'): [cnt_period_distribute, cnt_total_distribute],
                ('지급', '지급 처리', '지급신청 건수'): [cnt_period_request, cnt_total_request],
                ('지급', '지급 처리', '미신청건'): [cnt_period_fail_2, cnt_total_fail_2]
            }, index=['선택기간', '누적 총계 (3분기)'])

        else:
            # 기존 로직: 금일/전일/누적 표시
            cnt_today_mail = (df_5['날짜'].dt.date == day0).sum()
            cnt_yesterday_mail = (df_5['날짜'].dt.date == day1).sum()
            cnt_total_mail = ((df_5['날짜'].dt.date >= q3_start_default) & (df_5['날짜'].dt.date <= day0)).sum()

            cnt_today_apply = int(df_1.loc[df_1['날짜'].dt.date == day0, '개수'].sum())
            cnt_yesterday_apply = int(df_1.loc[df_1['날짜'].dt.date == day1, '개수'].sum())
            cnt_total_apply = int(df_1.loc[(df_1['날짜'].dt.date >= q3_start_default) & (df_1['날짜'].dt.date <= day0), '개수'].sum())

            cnt_today_distribute = int(df_2.loc[df_2['날짜'].dt.date == day0, '배분'].sum())
            cnt_yesterday_distribute = int(df_2.loc[df_2['날짜'].dt.date == day1, '배분'].sum())
            cnt_total_distribute = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= day0), '배분'].sum())

            cnt_today_request = int(df_2.loc[df_2['날짜'].dt.date == day0, '신청'].sum())
            cnt_yesterday_request = int(df_2.loc[df_2['날짜'].dt.date == day1, '신청'].sum())
            cnt_total_request = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= day0), '신청'].sum())

            # df_fail_q3, df_2_fail_q3 날짜 타입 보정
            if not pd.api.types.is_datetime64_any_dtype(df_fail_q3['날짜']):
                df_fail_q3['날짜'] = pd.to_datetime(df_fail_q3['날짜'], errors='coerce')
            if not pd.api.types.is_datetime64_any_dtype(df_2_fail_q3['날짜']):
                df_2_fail_q3['날짜'] = pd.to_datetime(df_2_fail_q3['날짜'], errors='coerce')

            # 미신청건 계산
            cnt_yesterday_fail = int((df_fail_q3['날짜'].dt.date == day1).sum())
            cnt_today_fail = int((df_fail_q3['날짜'].dt.date == day0).sum())
            cnt_total_fail = int(((df_fail_q3['날짜'].dt.date >= q3_start_default) & (df_fail_q3['날짜'].dt.date <= day0)).sum())

            # 지급 미신청건 계산
            cnt_yesterday_fail_2 = int(df_2_fail_q3.loc[df_2_fail_q3['날짜'].dt.date == day1, '미신청건'].sum())
            cnt_today_fail_2 = int(df_2_fail_q3.loc[df_2_fail_q3['날짜'].dt.date == day0, '미신청건'].sum())
            cnt_total_fail_2 = int(df_2_fail_q3.loc[(df_2_fail_q3['날짜'].dt.date >= q3_start_default) & (df_2_fail_q3['날짜'].dt.date <= day0), '미신청건'].sum())

            delta_mail = cnt_today_mail - cnt_yesterday_mail
            delta_apply = cnt_today_apply - cnt_yesterday_apply
            delta_fail = cnt_today_fail - cnt_yesterday_fail
            delta_distribute = cnt_today_distribute - cnt_yesterday_distribute
            delta_request = cnt_today_request - cnt_yesterday_request
            delta_fail_2 = cnt_today_fail_2 - cnt_yesterday_fail_2

            def format_delta(value):
                if value > 0: return f'<span style="color:blue;">+{value}</span>'
                elif value < 0: return f'<span style="color:red;">{value}</span>'
                return str(value)

            table_data = pd.DataFrame({
                ('지원', '파이프라인', '메일 건수'): [cnt_yesterday_mail, cnt_today_mail, cnt_total_mail],
                ('지원', '신청', '신청 건수'): [cnt_yesterday_apply, cnt_today_apply, cnt_total_apply],
                ('지원', '신청', '미신청건'): [cnt_yesterday_fail, cnt_today_fail, cnt_total_fail],
                ('지급', '지급 처리', '지급 배분건'): [cnt_yesterday_distribute, cnt_today_distribute, cnt_total_distribute],
                ('지급', '지급 처리', '지급신청 건수'): [cnt_yesterday_request, cnt_today_request, cnt_total_request],
                ('지급', '지급 처리', '미신청건'): [cnt_yesterday_fail_2, cnt_today_fail_2, cnt_total_fail_2]
            }, index=[f'전일 ({day1})', f'금일 ({day0})', '누적 총계 (3분기)'])

            # 변동(Delta) 행 추가
            table_data.loc['변동'] = [
                format_delta(delta_mail),
                format_delta(delta_apply),
                format_delta(delta_fail),
                format_delta(delta_distribute),
                format_delta(delta_request),
                format_delta(delta_fail_2)
            ]

        html_table = table_data.to_html(classes='custom_table', border=0, escape=False)
        st.markdown(html_table, unsafe_allow_html=True)

    with col2:
        st.write("### 2. 법인팀 금일 요약")
        
        # 자세한 법인팀 실적 테이블 생성
        required_cols_df3 = ['신청 요청일', '접수 완료', '신청대수']
        required_cols_df4 = ['요청일자', '지급신청 완료 여부', '신청번호', '접수대수']

        has_all_cols = all(col in df_3.columns for col in required_cols_df3) and \
                    all(col in df_4.columns for col in required_cols_df4)

        if has_all_cols:
            def process_new(df, end_date):
                df = df.copy()
                date_col = '신청 요청일'
                if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                df_cumulative = df[df[date_col].notna() & (df[date_col].dt.date <= end_date)]
                df_cumulative = df_cumulative[df_cumulative['접수 완료'].astype(str).str.strip().isin(['O', 'ㅇ'])]
                if '그리트 노트' in df_cumulative.columns:
                    is_cancelled = df_cumulative['그리트 노트'].astype(str).str.contains('취소', na=False)
                    is_reapplied = df_cumulative['그리트 노트'].astype(str).str.contains('취소 후 재신청', na=False)
                    df_cumulative = df_cumulative[~(is_cancelled & ~is_reapplied)]
                b_col_name = df_cumulative.columns[1]
                df_cumulative = df_cumulative[df_cumulative[b_col_name].notna() & (df_cumulative[b_col_name] != "")]
                df_today = df_cumulative[df_cumulative[date_col].dt.date == end_date]

                mask_bulk = df_cumulative['신청대수'] > 1
                mask_single = df_cumulative['신청대수'] == 1

                new_bulk_sum = int(df_cumulative.loc[mask_bulk, '신청대수'].sum())
                new_single_sum = int(df_cumulative.loc[mask_single, '신청대수'].sum())
                new_bulk_count = int(mask_bulk.sum())
                today_bulk_count = int((df_today['신청대수'] > 1).sum())
                today_bulk_sum = int(df_today[df_today['신청대수'] > 1]['신청대수'].sum())
                today_single_count = int((df_today['신청대수'] == 1).sum())

                return new_bulk_sum, new_single_sum, new_bulk_count, today_bulk_count, today_bulk_sum, today_single_count

            def process_give(df, end_date):
                df = df.copy()
                date_col = '요청일자'
                if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                df_cumulative = df[df[date_col].notna() & (df[date_col].dt.date <= end_date)]
                df_cumulative = df_cumulative[df_cumulative['지급신청 완료 여부'].astype(str).str.strip() == '완료']
                unique_df_cumulative = df_cumulative.drop_duplicates(subset=['신청번호'])
                df_today = unique_df_cumulative[unique_df_cumulative[date_col].dt.date == end_date]

                mask_bulk = unique_df_cumulative['접수대수'] > 1
                mask_single = unique_df_cumulative['접수대수'] == 1

                give_bulk_sum = int(unique_df_cumulative.loc[mask_bulk, '접수대수'].sum())
                give_single_sum = int(unique_df_cumulative.loc[mask_single, '접수대수'].sum())
                give_bulk_count = int(mask_bulk.sum())
                give_today_bulk_count = int((df_today['접수대수'] > 1).sum())
                give_today_single_count = int((df_today['접수대수'] == 1).sum())

                return give_bulk_sum, give_single_sum, give_bulk_count, give_today_bulk_count, give_today_single_count

            new_bulk_sum, new_single_sum, new_bulk_count, new_today_bulk_count, new_today_bulk_sum, new_today_single_count = process_new(df_3, selected_date)
            give_bulk_sum, give_single_sum, give_bulk_count, give_today_bulk_count, give_today_single_count = process_give(df_4, selected_date)

            row_names = ['벌크', '낱개', 'TTL']
            columns = pd.MultiIndex.from_tuples([
                ('지원', '파이프라인', '대수'), ('지원', '신청(건)', '당일'), ('지원', '신청(건)', '누계'),
                ('지급', '파이프라인', '대수'), ('지급', '신청(건)', '당일'), ('지급', '신청(건)', '누계')
            ], names=['', '분류', '항목'])
            df_total = pd.DataFrame(0, index=row_names, columns=columns)

            # 지원
            df_total.loc['벌크', ('지원', '파이프라인', '대수')] = new_bulk_sum
            df_total.loc['낱개', ('지원', '파이프라인', '대수')] = new_single_sum
            df_total.loc['TTL', ('지원', '파이프라인', '대수')] = new_bulk_sum + new_single_sum

            df_total.loc['벌크', ('지원', '신청(건)', '당일')] = f"{new_today_bulk_count}({new_today_bulk_sum})"
            df_total.loc['낱개', ('지원', '신청(건)', '당일')] = new_today_single_count
            df_total.loc['TTL', ('지원', '신청(건)', '당일')] = new_today_bulk_count + new_today_single_count

            df_total.loc['벌크', ('지원', '신청(건)', '누계')] = new_bulk_count
            df_total.loc['낱개', ('지원', '신청(건)', '누계')] = new_single_sum  # 원본 로직 유지
            df_total.loc['TTL', ('지원', '신청(건)', '누계')] = new_bulk_count + new_single_sum

            # 지급
            df_total.loc['벌크', ('지급', '파이프라인', '대수')] = give_bulk_sum
            df_total.loc['낱개', ('지급', '파이프라인', '대수')] = give_single_sum
            df_total.loc['TTL', ('지급', '파이프라인', '대수')] = give_bulk_sum + give_single_sum

            df_total.loc['벌크', ('지급', '신청(건)', '당일')] = give_today_bulk_count
            df_total.loc['낱개', ('지급', '신청(건)', '당일')] = give_today_single_count
            df_total.loc['TTL', ('지급', '신청(건)', '당일')] = give_today_bulk_count + give_today_single_count

            df_total.loc['벌크', ('지급', '신청(건)', '누계')] = give_bulk_count
            df_total.loc['낱개', ('지급', '신청(건)', '누계')] = give_single_sum  # 원본 로직 유지
            df_total.loc['TTL', ('지급', '신청(건)', '누계')] = give_bulk_count + give_single_sum

            html_table_corp = df_total.to_html(classes='custom_table', border=0)
            st.markdown(html_table_corp, unsafe_allow_html=True)
        else:
            st.warning("법인팀 실적을 계산하기 위한 필수 컬럼이 누락되었습니다.")
    
    # --- 메모 영역 ---
    with col3:

        def load_memo_file(path:str):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except FileNotFoundError:
                return ""

        def save_memo_file(path:str, content:str):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        # 특이사항 메모 (자동 추가)
        st.subheader("미신청건")

        # 오늘 기준 자동 추출된 특이사항 라인들
        auto_special_lines = extract_special_memo(df_fail_q3, selected_date)
        if not auto_special_lines:
            auto_special_lines = ["없음"]
        auto_special_text = "\n".join(auto_special_lines)

        # memo_special.txt 에 저장된 사용자 메모
        memo_special_saved = load_memo_file("memo_special.txt")

        # 디폴트 값: 자동 특이사항 + 저장된 사용자 메모(있다면 이어붙임)
        default_special = auto_special_text
        if memo_special_saved.strip():
            default_special += ("\n" if default_special else "") + memo_special_saved.strip()

        # CSS로 폰트 크기 16px, 줄바꿈 유지, 배경 연초록색(#e0f7fa), 텍스트 Bold로 표출
        st.markdown(
            f"<div style='font-size:16px; white-space:pre-wrap; background-color:#e0f7fa; border-radius:8px; padding:10px'><b>{default_special}</b></div>",
            unsafe_allow_html=True,
        )
    
    st.markdown("<hr style='margin-top:1rem;margin-bottom:1rem;'>", unsafe_allow_html=True)

    col4, col5, col6 = st.columns([3.5,2,1.5])

    with col4:
        # ----- 리테일 월별 요약 헤더 및 기간 선택 -----
        if viewer_option == '내부':
            header_col, sel_col = st.columns([4,2])
            with header_col:
                st.write("##### 리테일 월별 요약")
            with sel_col:
                period_option = st.selectbox(
                    '기간 선택',
                    ['전체', '3Q', '7월', '8월', '1Q', '2Q'] + [f'{m}월' for m in range(1,13)],
                    index=0,
                    key='retail_period')
        else:
            period_option = '3Q'  # 테슬라 옵션일 때는 기본값으로 '전체' 사용
            
        year = today_kst.year
        july_start = datetime(year, 7, 1).date()
        july_end = datetime(year, 7, 31).date()
        august_start = datetime(year, 8, 1).date()
        august_end = datetime(year, 8, 31).date()

        july_mail_count = int(df_5[(df_5['날짜'].dt.date >= q3_start_default) & (df_5['날짜'].dt.date <= july_end)].shape[0]) if july_end >= q3_start_default else 0
        july_apply_count = int(df_1.loc[(df_1['날짜'].dt.date >= q3_start_default) & (df_1['날짜'].dt.date <= july_end), '개수'].sum()) if july_end >= q3_start_default else 0
        july_distribute_count = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= july_end), '배분'].sum()) if july_end >= q3_start_distribute else 0

        mask_august_5 = (df_5['날짜'].dt.date >= august_start) & (df_5['날짜'].dt.date <= august_end)
        mask_august_1 = (df_1['날짜'].dt.date >= august_start) & (df_1['날짜'].dt.date <= august_end)
        mask_august_2 = (df_2['날짜'].dt.date >= august_start) & (df_2['날짜'].dt.date <= august_end)
        august_mail_count = int(df_5.loc[mask_august_5].shape[0])
        august_apply_count = int(df_1.loc[mask_august_1, '개수'].sum())
        august_distribute_count = int(df_2.loc[mask_august_2, '배분'].sum())

        # ----- 기간별 필터링 -----
        def filter_by_period(df):
            if period_option == '3Q' or period_option in ('3분기'):
                return df[df['분기'] == '3분기']
            if period_option == '2Q' or period_option in ('2분기'):
                return df[df['분기'] == '2분기']
            if period_option == '1Q' or period_option in ('1분기'):
                return df[df['분기'] == '1분기']
            if period_option.endswith('월'):
                try:
                    month_num = int(period_option[:-1])
                    return df[df['날짜'].dt.month == month_num]
                except ValueError:
                    return df
            return df

        # --- 월별/분기별 요약 계산 ---
        current_year = day0.year
        # 날짜 변수 정의
        june_23 = datetime(current_year, 6, 23).date()
        june_24 = datetime(current_year, 6, 24).date()
        july_1 = datetime(current_year, 7, 1).date()
        july_31 = datetime(current_year, 7, 31).date()
        august_1 = datetime(current_year, 8, 1).date()
        september_1 = datetime(current_year, 9, 1).date()

        retail_df = pd.DataFrame() # 초기화

        # --- 이미지 형태의 월별 요약 표 생성 ---
        if period_option == '전체':
            # 1. 월별 데이터 계산
            monthly_data = {}
            current_year = day0.year
            june_23 = datetime(current_year, 6, 23).date()
            june_24 = datetime(current_year, 6, 24).date()
            july_1 = datetime(current_year, 7, 1).date()
            july_31 = datetime(current_year, 7, 31).date()
            august_1 = datetime(current_year, 8, 1).date()
            september_1 = datetime(current_year, 9, 1).date()

            for month in range(1, 10):
                mail_count = apply_count = distribute_count = 0
                if month in [1, 2, 3]:
                    mail_count = int(df_5[df_5['날짜'].dt.month == month].shape[0])
                    apply_count = int(df_1[df_1['날짜'].dt.month == month]['개수'].sum())
                    distribute_count = int(df_2[df_2['날짜'].dt.month == month]['배분'].sum())
                elif month in [4, 5]:
                    mail_count = int(df_5[df_5['날짜'].dt.month == month].shape[0])
                    apply_count = int(df_1[df_1['날짜'].dt.month == month]['개수'].sum())
                    distribute_count = int(df_2[df_2['날짜'].dt.month == month]['배분'].sum())
                elif month == 6:
                    mail_count = int(df_5[df_5['날짜'].dt.month == month].shape[0])
                    apply_count = int(df_1[(df_1['날짜'].dt.month == 6) & (df_1['날짜'].dt.date <= june_23)]['개수'].sum())
                    distribute_count = int(df_2[df_2['날짜'].dt.month == month]['배분'].sum())
                elif month == 7:
                    mail_count = int(df_5[(df_5['날짜'].dt.date >= june_24) & (df_5['날짜'].dt.date <= july_31)].shape[0])
                    apply_count = int(df_1[(df_1['날짜'].dt.date >= june_24) & (df_1['날짜'].dt.date <= july_31)]['개수'].sum())
                    distribute_count = int(df_2[(df_2['날짜'].dt.date >= july_1) & (df_2['날짜'].dt.date <= july_31)]['배분'].sum())
                elif month == 8:
                    mail_count = int(df_5[(df_5['날짜'].dt.date >= august_1) & (df_5['날짜'].dt.date <= day0)].shape[0])
                    apply_count = int(df_1[(df_1['날짜'].dt.date >= august_1) & (df_1['날짜'].dt.date <= day0)]['개수'].sum())
                    distribute_count = int(df_2[(df_2['날짜'].dt.date >= august_1) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())
                elif month == 9:
                    mail_count = int(df_5[(df_5['날짜'].dt.date >= september_1) & (df_5['날짜'].dt.date <= day0)].shape[0])
                    apply_count = int(df_1[(df_1['날짜'].dt.month == 9) & (df_1['날짜'].dt.date <= day0)]['개수'].sum())
                    distribute_count = int(df_2[(df_2['날짜'].dt.month == 9) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())
                
                monthly_data[month] = {'파이프라인': mail_count, '지원신청완료': apply_count, '취소': 0, '지급신청': distribute_count}

            # 2. 분기별/전체 합계 계산
            q_totals = {}
            for q in [1, 2, 3]:
                q_months = range((q-1)*3 + 1, q*3 + 1)
                q_totals[q] = {key: sum(monthly_data[m][key] for m in q_months) for key in ['파이프라인', '지원신청완료', '취소', '지급신청']}
            q_totals[3]['취소'] = 468

            total_all = {key: sum(q_totals[q][key] for q in [1,2,3]) for key in q_totals[1]}

            # 3. 타겟 및 진척률 계산
            q1_target, q2_target, q3_target = 4300, 10000, 10000
            q_targets = {1: q1_target, 2: q2_target, 3: q3_target}
            q_progress = {q: q_totals[q]['파이프라인'] / q_targets[q] if q_targets[q] > 0 else 0 for q in [1,2,3]}

            # 4. HTML 테이블 수동 생성
            retail_df = None # '전체'의 경우 DataFrame을 사용하지 않음
            html_retail = '<table class="custom_table" border="0"><thead><tr>'
            html_retail += '<th rowspan="2" style="background-color: #f7f7f9;">항목</th>'
            for q in [1, 2, 3]:
                html_retail += f'<th colspan="4" style="background-color: #ffe0b2;">Q{q}</th>'
            html_retail += '<th rowspan="2" style="background-color: #c7ceea;">총계</th></tr><tr>'
            for q in [1, 2, 3]:
                for month in range((q-1)*3 + 1, q*3 + 1):
                    html_retail += f'<th style="background-color: #fff2cc;">{month}월</th>'
                html_retail += '<th style="background-color: #ffe0b2;">계</th>'
            html_retail += '</tr></thead><tbody>'

            # 타겟 (진척률) 행
            html_retail += '<tr><th style="background-color: #f7f7f9;">타겟 (진척률)</th>'
            for q in [1, 2, 3]:
                html_retail += f'<td colspan="4" style="background-color:#e0f7fa;">{q_targets[q]} ({q_progress[q]:.1%})</td>'
            html_retail += f'<td style="background-color:#e6e8f0;">{sum(q_targets.values())}</td></tr>'

            # 데이터 행
            rows = ['파이프라인', '지원신청완료', '취소', '지급신청']
            for i, row_name in enumerate(rows):
                html_retail += f'<tr style="background-color: #fafafa;">' if (i+1) % 2 == 1 else '<tr>'
                html_retail += f'<th style="background-color: #f7f7f9;">{row_name}</th>'
                for q in [1, 2, 3]:
                    for month in range((q-1)*3 + 1, q*3 + 1):
                        html_retail += f'<td>{monthly_data[month][row_name]}</td>'
                    html_retail += f'<td style="background-color: #fff2e6;">{q_totals[q][row_name]}</td>'
                html_retail += f'<td style="background-color: #e6e8f0;">{total_all[row_name]}</td></tr>'
            html_retail += '</tbody></table>'

        elif period_option == '1Q' or period_option == '1분기':
            # Q1 데이터 계산 (1, 2, 3월)
            q1_monthly_data = {}
            for month in [1, 2, 3]:
                month_mail = int(df_5[df_5['날짜'].dt.month == month].shape[0])
                month_apply = int(df_1[df_1['날짜'].dt.month == month]['개수'].sum())
                month_distribute = int(df_2[df_2['날짜'].dt.month == month]['배분'].sum())
                q1_monthly_data[f'{month}'] = [month_mail, month_apply, month_distribute]
            
            # Q1 합계 계산
            q1_total_mail = sum(q1_monthly_data[f'{m}'][0] for m in [1, 2, 3])
            q1_total_apply = sum(q1_monthly_data[f'{m}'][1] for m in [1, 2, 3])
            q1_total_distribute = sum(q1_monthly_data[f'{m}'][2] for m in [1, 2, 3])
            
            # 타겟 설정
            q1_target = 4300
            
            # 진척률 계산
            q1_progress_rate = q1_total_mail / q1_target if q1_target > 0 else 0
            
            retail_df_data = {
                '1': ['', q1_monthly_data['1'][0], q1_monthly_data['1'][1], '', q1_monthly_data['1'][2]],
                '2': ['', q1_monthly_data['2'][0], q1_monthly_data['2'][1], '', q1_monthly_data['2'][2]],
                '3': ['', q1_monthly_data['3'][0], q1_monthly_data['3'][1], '', q1_monthly_data['3'][2]],
                '계': ['', q1_total_mail, q1_total_apply, '', q1_total_distribute]
            }
            retail_index = ['타겟 (진척률)', '파이프라인', '지원신청완료', '취소', '지급신청']
            retail_df = pd.DataFrame(retail_df_data, index=retail_index)
            
        elif period_option == '2Q' or period_option == '2분기':
            # Q2 데이터 계산 (4, 5, 6월) - 6월은 6월 23일까지
            q2_monthly_data = {}
            
            # 6월 23일 날짜 객체 생성 (현재 연도 기준)
            current_year = datetime.now().year
            june_23 = datetime(current_year, 6, 23).date()
            
            for month in [4, 5, 6]:
                month_mail = int(df_5[df_5['날짜'].dt.month == month].shape[0])
                
                # 6월의 경우 6월 23일까지의 데이터만 포함
                if month == 6:
                    month_apply = int(df_1[
                        (df_1['날짜'].dt.month == 6) & 
                        (df_1['날짜'].dt.date <= june_23)
                    ]['개수'].sum())
                else:
                    month_apply = int(df_1[df_1['날짜'].dt.month == month]['개수'].sum())
                
                month_distribute = int(df_2[df_2['날짜'].dt.month == month]['배분'].sum())
                q2_monthly_data[f'{month}'] = [month_mail, month_apply, month_distribute]
            
            # Q2 합계 계산
            q2_total_mail = sum(q2_monthly_data[f'{m}'][0] for m in [4, 5, 6])
            q2_total_apply = sum(q2_monthly_data[f'{m}'][1] for m in [4, 5, 6])
            q2_total_distribute = sum(q2_monthly_data[f'{m}'][2] for m in [4, 5, 6])
            
            # 타겟 설정
            q2_target = 10000
            
            # 진척률 계산
            q2_progress_rate = q2_total_mail / q2_target if q2_target > 0 else 0
            
            # 데이터프레임 생성
            retail_df_data = {
                '4': ['', q2_monthly_data['4'][0], q2_monthly_data['4'][1], '', q2_monthly_data['4'][2]],
                '5': ['', q2_monthly_data['5'][0], q2_monthly_data['5'][1], '', q2_monthly_data['5'][2]],
                '6': ['', q2_monthly_data['6'][0], q2_monthly_data['6'][1], '', q2_monthly_data['6'][2]],
                '계': ['', q2_total_mail, q2_total_apply, '', q2_total_distribute]
            }
            retail_index = ['타겟 (진척률)', '파이프라인', '지원신청완료', '취소', '지급신청']
            retail_df = pd.DataFrame(retail_df_data, index=retail_index)
        elif period_option in ('3Q', '3분기'):
            # --- 3Q 월별 데이터 계산 (수정된 로직) ---
            q3_monthly_data = {}
            
            # 7월 데이터 (전체 월)
            q3_monthly_data['7'] = [
                int(df_5[(df_5['날짜'].dt.date >= june_24) & (df_5['날짜'].dt.date <= july_31)].shape[0]),
                int(df_1[(df_1['날짜'].dt.date >= june_24) & (df_1['날짜'].dt.date <= july_31)]['개수'].sum()),
                int(df_2[(df_2['날짜'].dt.date >= july_1) & (df_2['날짜'].dt.date <= july_31)]['배분'].sum())
            ]
            # 8월 데이터 (월초 ~ 현재)
            q3_monthly_data['8'] = [
                int(df_5[(df_5['날짜'].dt.date >= august_1) & (df_5['날짜'].dt.date <= day0)].shape[0]),
                int(df_1[(df_1['날짜'].dt.date >= august_1) & (df_1['날짜'].dt.date <= day0)]['개수'].sum()),
                int(df_2[(df_2['날짜'].dt.date >= august_1) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())
            ]
            # 9월 데이터 (월초 ~ 현재)
            q3_monthly_data['9'] = [
                int(df_5[(df_5['날짜'].dt.date >= september_1) & (df_5['날짜'].dt.date <= day0)].shape[0]),
                int(df_1[(df_1['날짜'].dt.month.isin([9])) & (df_1['날짜'].dt.date <= day0)]['개수'].sum()),
                int(df_2[(df_2['날짜'].dt.month.isin([9])) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())
            ]
            
            q3_total_mail = sum(q3_monthly_data[m][0] for m in ['7', '8', '9'])
            q3_total_apply = sum(q3_monthly_data[m][1] for m in ['7', '8', '9'])
            q3_total_distribute = sum(q3_monthly_data[m][2] for m in ['7', '8', '9'])
            
            q3_target = 10000
            q3_progress = q3_total_mail / q3_target if q3_target > 0 else 0
            
            retail_df_data = {
                '7': ['', q3_monthly_data['7'][0], q3_monthly_data['7'][1], '', q3_monthly_data['7'][2]],
                '8': ['', q3_monthly_data['8'][0], q3_monthly_data['8'][1], '', q3_monthly_data['8'][2]],
                '9': ['', q3_monthly_data['9'][0], q3_monthly_data['9'][1], '', q3_monthly_data['9'][2]],
                '계': ['', q3_total_mail, q3_total_apply, 468, q3_total_distribute]
            }
            retail_index = ['타겟 (진척률)', '파이프라인', '지원신청완료', '취소', '지급신청']
            retail_df = pd.DataFrame(retail_df_data, index=retail_index)
        else:
            # 기존 로직 유지 (다른 기간 선택 시)
            df5_p = filter_by_period(df_5)
            df1_p = filter_by_period(df_1)
            df2_p = filter_by_period(df_2)
            mail_total = int(df5_p.shape[0])
            apply_total = int(df1_p['개수'].sum())
            distribute_total = int(df2_p['배분'].sum())
            retail_df_data = {period_option: [mail_total, apply_total, distribute_total]}
            retail_index = ['파이프라인', '신청', '지급신청']
            retail_df = pd.DataFrame(retail_df_data, index=retail_index)

        # --- HTML 변환 및 스타일링 ---
        if period_option != '전체':
            html_retail = retail_df.to_html(classes='custom_table', border=0, escape=False)

        # 이미지 형태에 맞는 스타일링 적용
        if period_option in ['1Q', '1분기', '2Q', '2분기', '3Q', '3분기']:
            # 타겟 값들에 배경색 적용
            target_values = ['4300', '10000']
            for target in target_values:
                html_retail = html_retail.replace(f'<td>{target}</td>', f'<td style="background-color: #f0f0f0;">{target}</td>')
            
            import re
            # 1Q/1분기에서 '타겟 (진척률)' 행을 병합하고 배경색 적용 (3분기 방식과 동일하게)
            if period_option in ('1Q', '1분기'):
                target_text = f"{q1_target} ({q1_progress_rate:.1%})"
                html_retail = re.sub(
                    r'(<tr>\s*<th>타겟 \(진척률\)</th>)(.*?)(</tr>)',
                    lambda m: m.group(1) + 
                                re.sub(
                                    r'<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>',
                                    f'<td\\1 colspan="4" style="background-color:#e0f7fa;">{target_text}</td>',
                                    m.group(2), count=1
                                ) + 
                                m.group(3),
                    html_retail,
                    flags=re.DOTALL
                )

            # 2Q/2분기에서 '타겟 (진척률)' 행을 병합하고 배경색 적용 (3분기 방식과 동일하게)
            elif period_option in ('2Q', '2분기'):
                target_text = f"{q2_target} ({q2_progress_rate:.1%})"
                html_retail = re.sub(
                    r'(<tr>\s*<th>타겟 \(진척률\)</th>)(.*?)(</tr>)',
                    lambda m: m.group(1) + 
                                re.sub(
                                    r'<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>',
                                    f'<td\\1 colspan="4" style="background-color:#e0f7fa;">{target_text}</td>',
                                    m.group(2), count=1
                                ) + 
                                m.group(3),
                    html_retail,
                    flags=re.DOTALL
                )

            # 3Q/3분기에서 '타겟 (진척률)' 행을 병합하고 배경색 적용
            elif period_option in ('3Q', '3분기'):
                target_text = f"{q3_target} ({q3_progress:.1%})"
                html_retail = re.sub(
                    r'(<tr>\s*<th>타겟 \(진척률\)</th>)(.*?)(</tr>)',
                    lambda m: m.group(1) + 
                                re.sub(
                                    r'<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>',
                                    f'<td\\1 colspan="4" style="background-color:#e0f7fa;">{target_text}</td>',
                                    m.group(2), count=1
                                ) + 
                                m.group(3),
                    html_retail,
                    flags=re.DOTALL
                )
            
            # 빈 셀들을 공백으로 표시
            html_retail = html_retail.replace('<td></td>', '<td style="background-color: #fafafa;">&nbsp;</td>')
            
            # "계" 컬럼 하이라이트 (개별 분기 선택 시)
            html_retail = re.sub(
                r'(<th[^>]*>계</th>)',
                r'<th style="background-color: #ffe0b2;">계</th>',
                html_retail
            )
            
            # "계" 행의 데이터 셀들도 하이라이트
            html_retail = re.sub(
                r'(<tr>\s*<th>계</th>)(.*?)(</tr>)',
                lambda m: m.group(1) + re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', m.group(2)) + m.group(3),
                html_retail,
                flags=re.DOTALL
            )
            

        st.markdown(html_retail, unsafe_allow_html=True)

    with col5:
        if show_monthly_summary:
           
            # ----- 법인팀 월별 요약 헤더 및 기간 선택 -----
            if viewer_option == '내부':
                header_corp, sel_corp = st.columns([4,2])
                with header_corp:
                    st.write("##### 법인팀 월별 요약")
                with sel_corp:
                    corp_period_option = st.selectbox(
                        '기간 선택',
                        ['전체'],
                        index=0,
                        key='corp_period')
            else:
                corp_period_option = '전체'  # 테슬라 옵션일 때는 기본값으로 '전체' 사용
        
        # --- 날짜 변수 설정 ---
        year = today_kst.year
        q3_apply_start = datetime(year, 6, 18).date()
        q3_distribute_start = datetime(year, 6, 18).date()
        july_end = datetime(year, 7, 31).date()
        august_start = datetime(year, 8, 1).date()
        august_end = datetime(year, 8, 31).date()

        # --- 월별 계산 함수 (수정된 최종 로직) ---
        def get_corp_period_metrics(df3_raw, df4_raw, apply_start, apply_end, distribute_start, distribute_end):
            # --- df_3 (지원: 파이프라인, 지원신청) 계산 ---
            pipeline, apply = 0, 0
            df3 = df3_raw.copy()
            date_col_3 = '신청 요청일'
            if not pd.api.types.is_datetime64_any_dtype(df3[date_col_3]):
                df3[date_col_3] = pd.to_datetime(df3[date_col_3], errors='coerce')
            
            mask3 = (df3[date_col_3].dt.date >= apply_start) & (df3[date_col_3].dt.date <= apply_end)
            df3_period = df3.loc[mask3]

            df3_period = df3_period[df3_period['접수 완료'].astype(str).str.strip().isin(['O', 'ㅇ'])]
            if '그리트 노트' in df3_period.columns:
                is_cancelled = df3_period['그리트 노트'].astype(str).str.contains('취소', na=False)
                is_reapplied = df3_period['그리트 노트'].astype(str).str.contains('취소 후 재신청', na=False)
                df3_period = df3_period[~(is_cancelled & ~is_reapplied)]
            b_col_name = df3_period.columns[1]
            df3_period = df3_period[df3_period[b_col_name].notna() & (df3_period[b_col_name] != "")]

            pipeline = int(df3_period['신청대수'].sum())
            mask_bulk_3 = df3_period['신청대수'] > 1
            mask_single_3 = df3_period['신청대수'] == 1
            apply = int(mask_bulk_3.sum() + df3_period.loc[mask_single_3, '신청대수'].sum())

            # --- df_4 (지급: 지급신청) 계산 ---
            distribute = 0
            df4 = df4_raw.copy()
            date_col_4 = '요청일자'
            if not pd.api.types.is_datetime64_any_dtype(df4[date_col_4]):
                df4[date_col_4] = pd.to_datetime(df4[date_col_4], errors='coerce')

            mask4 = (df4[date_col_4].dt.date >= distribute_start) & (df4[date_col_4].dt.date <= distribute_end)
            df4_period = df4.loc[mask4]

            df4_period = df4_period[df4_period['지급신청 완료 여부'].astype(str).str.strip() == '완료']
            unique_df4_period = df4_period.drop_duplicates(subset=['신청번호'])

            mask_bulk_4 = unique_df4_period['접수대수'] > 1
            mask_single_4 = unique_df4_period['접수대수'] == 1
            # 벌크 건의 '대수 합'이 아닌 '건수 합'을 사용하도록 변경
            distribute = int(mask_bulk_4.sum() + unique_df4_period.loc[mask_single_4, '접수대수'].sum())

            return pipeline, apply, distribute

        # --- 월별 데이터 계산 실행 ---
        july_pipeline, july_apply, july_distribute = get_corp_period_metrics(
            df_3, df_4, q3_apply_start, july_end, q3_distribute_start, july_end
        )

        august_pipeline, august_apply, august_distribute = get_corp_period_metrics(
            df_3, df_4, august_start, august_end, august_start, august_end
        )
        # --- 월별 데이터 및 합계 계산 ---
        july_data = {'파이프라인': july_pipeline, '지원신청완료': july_apply, '취소': '', '지급신청': july_distribute}
        august_data = {'파이프라인': august_pipeline, '지원신청완료': august_apply, '취소': '', '지급신청': august_distribute}
        total_data = {
            '파이프라인': july_pipeline + august_pipeline,
            '지원신청완료': july_apply + august_apply,
            '취소': '',
            '지급신청': july_distribute + august_distribute
        }

        # --- '타겟 (진척률)' 데이터 계산 ---
        q3_target_corp = 1500
        ttl_apply_corp = total_data['지원신청완료']
        progress_rate_corp = ttl_apply_corp / q3_target_corp if q3_target_corp > 0 else 0
        target_text = f"{q3_target_corp} ({progress_rate_corp:.2%})"

        # --- HTML 테이블 수동 생성 ---
        html_corp = '<table class="custom_table" border="0"><thead><tr>'
        html_corp += '<th rowspan="2" style="background-color: #f7f7f9;">항목</th>'
        if viewer_option == '내부':
            html_corp += '<th colspan="3" style="background-color: #ffb3ba;">Q3</th>'
        else:
            html_corp += '<th style="background-color: #ffd6dd;">7월</th>'
            html_corp += '<th style="background-color: #ffd6dd;">8월</th>'
            html_corp += '<th style="background-color: #ffe0b2;">계</th>'
        html_corp += '</tr><tr>'
        if viewer_option == '내부':
            html_corp += '<th style="background-color: #ffd6dd;">7월</th>'
            html_corp += '<th style="background-color: #ffd6dd;">8월</th>'
            html_corp += '<th style="background-color: #ffe0b2;">계</th>'
        html_corp += '</tr></thead><tbody>'

        # --- 데이터 행 ---
        rows = ['타겟 (진척률)', '파이프라인', '지원신청완료', '취소', '지급신청']
        for i, row_name in enumerate(rows):
            row_style = 'style="background-color: #fafafa;"' if i % 2 == 1 else ''
            html_corp += f'<tr {row_style}>'
            html_corp += f'<th style="background-color: #f7f7f9;">{row_name}</th>'
            
            if row_name == '타겟 (진척률)':
                # 타겟 행은 colspan="3"으로 병합하여 하나의 셀로 표시
                html_corp += f'<td colspan="3" style="background-color:#e0f7fa;">{target_text}</td>'
            else:
                # 일반 데이터 행은 7월, 8월, 계 각각 별도 셀로 표시
                html_corp += f'<td>{july_data[row_name]}</td>'
                html_corp += f'<td>{august_data[row_name]}</td>'
                html_corp += f'<td style="background-color: #ffe0b2;">{total_data[row_name]}</td>'
            
            html_corp += '</tr>'

    
        html_corp += '</tbody></table>'

        # 빈 셀들을 공백으로 표시
        html_corp = html_corp.replace('<td></td>', '<td style="background-color: #fafafa;">&nbsp;</td>')
        
        if show_monthly_summary:
            st.markdown(html_corp, unsafe_allow_html=True)

    with col6:
        # ----- 기타 헤더 (col4, col5와 동일한 폰트 크기) -----
        if viewer_option == '내부':
            st.markdown("##### 기타")
        else:
            pass
        
        memo_etc = load_memo_file("memo_etc.txt")
        
        # HTML textarea를 사용하여 '미신청건'과 동일한 스타일 적용
        textarea_html = f"""
        <textarea 
            style="width: 100%; height: 240px; padding: 10px; border: 1px solid #ccc; border-radius: 4px; font-family: inherit; resize: vertical;"
            id="memo_etc_textarea"
            onchange="updateMemo(this.value)"
        >{memo_etc}</textarea>
     
        """
        
        st.markdown(textarea_html, unsafe_allow_html=True)

    st.markdown("<hr style='margin-top:1rem;margin-bottom:1rem;'>", unsafe_allow_html=True)

    col7, col8, col9 = st.columns([3.5,2,1.5])

    with col7:
        # --- 리테일 월별 추이 그래프 ---
        if viewer_option == '내부':
            # --- months_to_show 결정 ---
            def get_end_month(option):
                if option.endswith('월'):
                    try:
                        return int(option[:-1])
                    except ValueError:
                        pass
                if option in ('1Q', '1분기'): return 3
                if option in ('2Q', '2분기'): return 6
                if option in ('3Q', '3분기'): return 9
                return selected_date.month
            end_month = get_end_month(period_option)

            # 항상 현재 달은 제외하여 '전달'까지만 표시
            prev_month = selected_date.month - 1 if selected_date.month > 1 else 12
            end_month = min(end_month, prev_month)

            start_month = 2
            months_to_show = list(range(start_month, end_month + 1))

            if months_to_show:
                # 월별 파이프라인(메일) 건수 집계 - 6월과 7월 특별 처리
                pipeline_counts = {}
                
                for month in months_to_show:
                    if month == 6:
                        # 6월은 6월 23일까지만 집계
                        june_23 = datetime(selected_date.year, 6, 23).date()
                        month_count = int(df_5[
                            (df_5['날짜'].dt.year == selected_date.year) &
                            (df_5['날짜'].dt.month == 6) &
                            (df_5['날짜'].dt.date <= june_23)
                        ].shape[0])
                    elif month == 7:
                        # 7월은 6월 24일부터 7월 31일까지 집계
                        june_24 = datetime(selected_date.year, 6, 24).date()
                        july_31 = datetime(selected_date.year, 7, 31).date()
                        month_count = int(df_5[
                            (df_5['날짜'].dt.date >= june_24) &
                            (df_5['날짜'].dt.date <= july_31)
                        ].shape[0])
                    else:
                        # 다른 월들은 전체 월 집계
                        month_count = int(df_5[
                            (df_5['날짜'].dt.year == selected_date.year) &
                            (df_5['날짜'].dt.month == month)
                        ].shape[0])
                    
                    pipeline_counts[month] = month_count

                # 차트용 데이터프레임 생성
                chart_df = pd.DataFrame(
                    {
                        '월': months_to_show,
                        '파이프라인 건수': [int(pipeline_counts.get(m, 0)) for m in months_to_show]
                    }
                )
                chart_df['월 라벨'] = chart_df['월'].astype(str) + '월'

                # 막대 그래프 (파이프라인)
                bar = alt.Chart(chart_df).mark_bar(size=25, color='#2ca02c').encode(
                    x=alt.X('월 라벨:N', title='월', sort=[f"{m}월" for m in months_to_show], axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('파이프라인 건수:Q', title='건수')
                )

                # 선 그래프 + 포인트
                line = alt.Chart(chart_df).mark_line(color='#FF5733', strokeWidth=2).encode(
                    x='월 라벨:N',
                    y='파이프라인 건수:Q'
                )
                point = alt.Chart(chart_df).mark_point(color='#FF5733', size=60).encode(
                    x='월 라벨:N',
                    y='파이프라인 건수:Q'
                )

                # 값 레이블 텍스트
                text = alt.Chart(chart_df).mark_text(dy=-10, color='black').encode(
                    x='월 라벨:N',
                    y='파이프라인 건수:Q',
                    text=alt.Text('파이프라인 건수:Q')
                )

                combo_chart = (bar + line + point + text).properties(
                    title=f"{selected_date.year}년 월별 파이프라인 추이 ({start_month}월~{end_month}월)"
                )
                st.altair_chart(combo_chart, use_container_width=True)

    with col8:
        # --- 법인팀 월별 추이 그래프 (내부 뷰어 전용) ---
        if viewer_option == '내부':
            # 항상 현재 달은 제외하여 '전달'까지만 표시
            corp_data = {
                7: july_pipeline,
                8: august_pipeline,
            }
            months_to_show_corp = sorted([m for m in corp_data.keys() if m < selected_date.month])
            pipeline_values_corp = [corp_data[m] for m in months_to_show_corp]

            if months_to_show_corp:
                corp_chart_df = pd.DataFrame(
                    {
                        '월': months_to_show_corp,
                        '파이프라인 건수': pipeline_values_corp
                    }
                )
                corp_chart_df['월 라벨'] = corp_chart_df['월'].astype(str) + '월'

                # 막대 그래프
                bar_corp = alt.Chart(corp_chart_df).mark_bar(size=25, color='#2ca02c').encode(
                    x=alt.X('월 라벨:N', title='월', sort=[f"{m}월" for m in months_to_show_corp], axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('파이프라인 건수:Q', title='건수')
                )
                # 선 그래프 및 포인트
                line_corp = alt.Chart(corp_chart_df).mark_line(color='#FF5733', strokeWidth=2).encode(
                    x=alt.X('월 라벨:N', axis=alt.Axis(labelAngle=0)),
                    y='파이프라인 건수:Q'
                )
                point_corp = alt.Chart(corp_chart_df).mark_point(color='#FF5733', size=60).encode(
                    x=alt.X('월 라벨:N', axis=alt.Axis(labelAngle=0)),
                    y='파이프라인 건수:Q'
                )
                # 레이블 텍스트
                text_corp = alt.Chart(corp_chart_df).mark_text(dy=-10, color='black').encode(
                    x=alt.X('월 라벨:N', axis=alt.Axis(labelAngle=0)),
                    y='파이프라인 건수:Q',
                    text=alt.Text('파이프라인 건수:Q')
                )
                
                # 제목 동적 설정
                if len(months_to_show_corp) == 1:
                    title_corp = f"{selected_date.year}년 법인팀 파이프라인 추이 ({months_to_show_corp[0]}월)"
                else:
                    title_corp = f"{selected_date.year}년 법인팀 파이프라인 추이 ({months_to_show_corp[0]}~{months_to_show_corp[-1]}월)"
                    
                corp_combo = (bar_corp + line_corp + point_corp + text_corp).properties(
                    title=title_corp
                )
                st.altair_chart(corp_combo, use_container_width=True)
# 폴스타 뷰 시작 부분
if viewer_option == '폴스타':
    show_polestar_viewer(data, today_kst)

# --- 지도 뷰어 ---
if viewer_option == '지도':
    if hasattr(st.session_state, 'map_preloaded') and st.session_state.map_preloaded:
        show_map_viewer(data, df_6, use_preloaded=True)
    else:
        st.warning("지도 데이터가 아직 준비되지 않았습니다.")
        show_map_viewer(data, df_6, use_preloaded=False)

# --- 분석 뷰어 ---
if viewer_option == '분석':
    show_car_region_dashboard(data, today_kst)
