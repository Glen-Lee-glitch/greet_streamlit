import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import altair as alt
import pickle
import json
import re
import plotly.express as px
from shapely.geometry import shape
from shapely.ops import unary_union

import sys
from datetime import datetime, timedelta, date
import pytz

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
                # get_base_city_name을 df_6의 지역명에도 적용하여 키 일관성 확보
                base_region = get_base_city_name(region_str)
                for key in final_counts.keys():
                    if key.endswith(" " + base_region):
                        final_counts[key] += count
                        unmatched_regions.discard(region_str)
                        matched = True
                        # 하나의 시군구는 하나의 시도에만 속하므로 break
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

def create_korea_map_data():
    """간단한 한국 지도 데이터를 생성합니다."""
    # 한국의 주요 지역 데이터 (간소화된 버전)
    import numpy as np
    korea_data = {
        'region': [
            '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시', '울산광역시',
            '세종특별자치시', '경기도', '강원도', '충청북도', '충청남도', '전라북도', '전라남도', '경상북도', '경상남도', '제주특별자치도'
        ],
        'lat': [
            37.5665, 35.1796, 35.8714, 37.4563, 35.1595, 36.3504, 35.5384,
            36.4870, 37.4138, 37.8228, 36.8000, 36.5184, 35.7175, 34.8679, 36.4919, 35.4606, 33.4996
        ],
        'lon': [
            126.9780, 129.0756, 128.6014, 126.7052, 126.8526, 127.3845, 129.3114,
            127.2822, 127.5183, 128.1555, 127.7000, 126.8000, 127.1530, 126.9910, 128.8889, 128.2132, 126.5312
        ],
        'value': np.random.randint(10, 1000, size=17).tolist()  # 10~999 사이 랜덤값
    }
    return pd.DataFrame(korea_data)

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

# --- 시간대 설정 ---
KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()

# --- 사이드바: 조회 옵션 설정 ---
with st.sidebar:
    st.header("👁️ 뷰어 옵션")
    viewer_option = st.radio("뷰어 유형을 선택하세요.", ('내부', '테슬라', '폴스타', '지도(테스트)', '분석'), key="viewer_option")
    st.markdown("---")
    st.header("📊 조회 옵션")
    view_option = st.radio(
        "조회 유형을 선택하세요.",
        ('금일', '특정일 조회', '기간별 조회', '분기별 조회', '월별 조회'),
        key="view_option"
    )

    start_date, end_date = None, None
    
    lst_1 = ['내부', '테슬라', '폴스타']

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
        day1 = (pd.to_datetime(selected_date) - pd.tseries.offsets.BDay(1)).date()

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
                today_single_count = int((df_today['신청대수'] == 1).sum())

                return new_bulk_sum, new_single_sum, new_bulk_count, today_bulk_count, today_single_count

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

            new_bulk_sum, new_single_sum, new_bulk_count, new_today_bulk_count, new_today_single_count = process_new(df_3, selected_date)
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

            df_total.loc['벌크', ('지원', '신청(건)', '당일')] = new_today_bulk_count
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
                    ['3Q', '7월', '전체', '1Q', '2Q'] + [f'{m}월' for m in range(1,13)],
                    index=0,
                    key='retail_period')
        else:
            st.write("##### 리테일 월별 요약")
            period_option = '전체'  # 테슬라 옵션일 때는 기본값으로 '전체' 사용
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
            # (1Q, 2Q 계산 로직은 기존과 동일)
            q1_total_mail = int(df_5[df_5['날짜'].dt.month.isin([1,2,3])].shape[0])
            q1_total_apply = int(df_1[df_1['날짜'].dt.month.isin([1,2,3])]['개수'].sum())
            q1_total_distribute = int(df_2[df_2['날짜'].dt.month.isin([1,2,3])]['배분'].sum())
            q2_total_mail = int(df_5[df_5['날짜'].dt.month.isin([4,5,6])].shape[0])
            q2_apply_mask = (df_1['날짜'].dt.month.isin([4,5])) | ((df_1['날짜'].dt.month == 6) & (df_1['날짜'].dt.date <= june_23))
            q2_total_apply = int(df_1[q2_apply_mask]['개수'].sum())
            q2_total_distribute = int(df_2[df_2['날짜'].dt.month.isin([4,5,6])]['배분'].sum())
            
            # --- 3Q 데이터 계산 (수정된 로직) ---
            july_mail_total = int(df_5[(df_5['날짜'].dt.date >= june_24) & (df_5['날짜'].dt.date <= july_31)].shape[0])
            july_apply_total = int(df_1[(df_1['날짜'].dt.date >= june_24) & (df_1['날짜'].dt.date <= july_31)]['개수'].sum())
            july_distribute_total = int(df_2[(df_2['날짜'].dt.date >= july_1) & (df_2['날짜'].dt.date <= july_31)]['배분'].sum())

            august_cumulative_mail = int(df_5[(df_5['날짜'].dt.date >= august_1) & (df_5['날짜'].dt.date <= day0)].shape[0])
            august_cumulative_apply = int(df_1[(df_1['날짜'].dt.date >= august_1) & (df_1['날짜'].dt.date <= day0)]['개수'].sum())
            august_cumulative_distribute = int(df_2[(df_2['날짜'].dt.date >= august_1) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())
            
            september_cumulative_mail = int(df_5[(df_5['날짜'].dt.date >= september_1) & (df_5['날짜'].dt.date <= day0)].shape[0])
            september_cumulative_apply = int(df_1[(df_1['날짜'].dt.date >= september_1) & (df_1['날짜'].dt.date <= day0)]['개수'].sum())
            september_cumulative_distribute = int(df_2[(df_2['날짜'].dt.date >= september_1) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())

            q3_total_mail = july_mail_total + august_cumulative_mail + september_cumulative_mail
            q3_total_apply = july_apply_total + august_cumulative_apply + september_cumulative_apply
            q3_total_distribute = july_distribute_total + august_cumulative_distribute + september_cumulative_distribute

            q1_target, q2_target, q3_target = 4300, 10000, 10000
            q1_progress = q1_total_mail / q1_target if q1_target > 0 else 0
            q2_progress = q2_total_mail / q2_target if q2_target > 0 else 0
            q3_progress = q3_total_mail / q3_target if q3_target > 0 else 0

            # 계산을 위한 합계
            total_target = q1_target + q2_target + q3_target
            total_mail = q1_total_mail + q2_total_mail + q3_total_mail
            total_apply = q1_total_apply + q2_total_apply + q3_total_apply
            total_distribute = q1_total_distribute + q2_total_distribute + q3_total_distribute

            retail_df_data = {
                'Q1': [q1_target, q1_total_mail, q1_total_apply, f"{q1_progress:.1%}", '', q1_total_distribute],
                'Q2': [q2_target, q2_total_mail, q2_total_apply, f"{q2_progress:.1%}", '', q2_total_distribute],
                'Q3': [q3_target, q3_total_mail, q3_total_apply, f"{q3_progress:.1%}", 288, q3_total_distribute],
                '계': [total_target, total_mail, total_apply, '', 288, total_distribute]
            }
            retail_index = ['타겟', '파이프라인', '지원신청완료', '진척률', '취소', '지급신청']
            retail_df = pd.DataFrame(retail_df_data, index=retail_index)

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
                int(df_1[(df_1['날짜'].dt.date >= september_1) & (df_1['날짜'].dt.date <= day0)]['개수'].sum()),
                int(df_2[(df_2['날짜'].dt.date >= september_1) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())
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
                '계': ['', q3_total_mail, q3_total_apply, 288, q3_total_distribute]
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
        html_retail = retail_df.to_html(classes='custom_table', border=0, escape=False)

        # 이미지 형태에 맞는 스타일링 적용
        if period_option in ['전체', '1Q', '1분기', '2Q', '2분기', '3Q', '3분기']:
            # 타겟 값들에 배경색 적용
            target_values = ['4300', '10000']
            for target in target_values:
                html_retail = html_retail.replace(f'<td>{target}</td>', f'<td style="background-color: #f0f0f0;">{target}</td>')
            
            # 진척률 셀 하이라이트 (모든 진척률 값에 대해)
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
            
            # '전체' 선택 시 Q1, Q2, Q3 컬럼 헤더 하이라이트
            if period_option == '전체':
                html_retail = re.sub(
                    r'(<th[^>]*>Q1</th>)',
                    r'<th style="background-color: #ffe0b2;">Q1</th>',
                    html_retail
                )
                html_retail = re.sub(
                    r'(<th[^>]*>Q2</th>)',
                    r'<th style="background-color: #ffe0b2;">Q2</th>',
                    html_retail
                )
                html_retail = re.sub(
                    r'(<th[^>]*>Q3</th>)',
                    r'<th style="background-color: #ffe0b2;">Q3</th>',
                    html_retail
                )

            else:
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
                st.write("##### 법인팀 월별 요약")
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
        # --- 데이터프레임 생성 ---
        corp_df_data = {
            '7월': ['', july_pipeline, july_apply, '', july_distribute],
            '8월': ['', august_pipeline, august_apply, '', august_distribute]
        }
        corp_df = pd.DataFrame(corp_df_data, index=['타겟 (진척률)', '파이프라인', '지원신청완료', '취소', '지급신청'])
        corp_df['계'] = corp_df['7월'] + corp_df['8월']

        # --- '타겟 (진척률)' 데이터 계산 ---
        q3_target_corp = 1500
        ttl_apply_corp = corp_df.loc['지원신청완료', '계']
        progress_rate_corp = ttl_apply_corp / q3_target_corp if q3_target_corp > 0 else 0
        formatted_progress_corp = f"{progress_rate_corp:.2%}"
        target_text = f"{q3_target_corp} ({formatted_progress_corp})"

        # --- HTML로 변환 및 스타일 적용 ---
        html_corp = corp_df.to_html(classes='custom_table', border=0, escape=False)
        
        # '타겟 (진척률)' 행을 병합하고 배경색 적용 (col4와 동일한 방식)
        import re
        html_corp = re.sub(
            r'(<tr>\s*<th>타겟 \(진척률\)</th>)(.*?)(</tr>)',
            lambda m: m.group(1) + 
                        re.sub(
                            r'<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>',
                            f'<td\\1 colspan="5" style="background-color:#e0f7fa;">{target_text}</td>',
                            m.group(2), count=1
                        ) + 
                        m.group(3),
            html_corp,
            flags=re.DOTALL
        )
        
        # '계' 헤더에 배경색 적용 (리테일과 동일한 색상 #ffe0b2)
        html_corp = re.sub(
            r'(<th[^>]*>계</th>)',
            r'<th style="background-color: #ffe0b2;">계</th>',
            html_corp
        )

        # 빈 셀들을 공백으로 표시
        html_corp = html_corp.replace('<td></td>', '<td style="background-color: #fafafa;">&nbsp;</td>')
        
        if show_monthly_summary:
            st.markdown(html_corp, unsafe_allow_html=True)

    with col6:

        st.subheader("기타")
        memo_etc = load_memo_file("memo_etc.txt")
        new_etc = st.text_area(
            "",
            value=memo_etc,
            height=150,
            key="memo_etc_input"
        )
        if new_etc != memo_etc:
            save_memo_file("memo_etc.txt", new_etc)
            st.toast("기타 메모가 저장되었습니다!")

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
            # 현재 날짜가 15일 이전이면 해당 월 데이터 제외
            if selected_date.day < 15 and end_month == selected_date.month:
                end_month -= 1
                # 1월인 경우 0이 되지 않도록 방어
                if end_month == 0:
                    end_month = 12
            start_month = 2
            months_to_show = list(range(start_month, end_month + 1))
            # 15일 이전이면 해당 월을 제외 (3Q 포함 모든 경우에 적용)
            if selected_date.day < 15:
                months_to_show = [m for m in months_to_show if m < selected_date.month]
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
            # 현재 날짜가 15일 이전이면 해당 월 데이터 제외
            months_to_show_corp = [7]
            pipeline_values_corp = [july_pipeline]
            
            if selected_date.day >= 15:
                months_to_show_corp.append(8)
                pipeline_values_corp.append(august_pipeline)

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
                title_corp = f"{selected_date.year}년 법인팀 파이프라인 추이 (7월)"
            else:
                title_corp = f"{selected_date.year}년 법인팀 파이프라인 추이 (7~8월)"
                
            corp_combo = (bar_corp + line_corp + point_corp + text_corp).properties(
                title=title_corp
            )
            st.altair_chart(corp_combo, use_container_width=True)

# 폴스타 뷰 시작 부분
if viewer_option == '폴스타':
    # pkl에서 폴스타 DataFrame 로드
    @st.cache_data
    def load_polestar_data():
        try:
            with open("preprocessed_data.pkl", "rb") as f:
                data = pickle.load(f)
            return data.get('df_pole_pipeline', pd.DataFrame()), data.get('df_pole_apply', pd.DataFrame())
        except FileNotFoundError:
            st.error("preprocessed_data.pkl 파일을 찾을 수 없습니다. 먼저 전처리.py를 실행해주세요.")
            return pd.DataFrame(), pd.DataFrame()
        except Exception as e:
            st.error(f"데이터 로드 중 오류: {e}")
            return pd.DataFrame(), pd.DataFrame()
    
    df_pole_pipeline, df_pole_apply = load_polestar_data()
    
    # 월별 집계 계산 함수
    @st.cache_data
    def calculate_monthly_summary(pipeline_df, apply_df, selected_month):
        """선택된 월의 데이터를 계산"""
        month_num = int(selected_month.replace('월', ''))
        
        # 파이프라인 월 누계
        pipeline_month_total = 0
        if not pipeline_df.empty and '날짜' in pipeline_df.columns:
            month_pipeline = pipeline_df[pipeline_df['날짜'].dt.month == month_num]
            pipeline_month_total = month_pipeline['파이프라인'].sum()
        
        # 지원신청 월 누계
        apply_month_total = pak_month_total = cancel_month_total = unreceived_total = supplement_total = 0
        if not apply_df.empty and '날짜' in apply_df.columns:
            month_apply = apply_df[apply_df['날짜'].dt.month == month_num]
            apply_month_total = month_apply['지원신청'].sum()
            pak_month_total = month_apply['PAK_내부지원'].sum()
            cancel_month_total = month_apply['접수후취소'].sum()
            unreceived_total = month_apply['미신청건'].sum()
            supplement_total = month_apply['보완'].sum()
        
        return {
            'pipeline_today': 0,  # 당일 데이터는 현재 0
            'pipeline_month_total': pipeline_month_total,
            'apply_today': 0,  # 당일 데이터는 현재 0
            'apply_month_total': apply_month_total,
            'unreceived_today': 0,  # 당일 데이터는 현재 0
            'unreceived_total': unreceived_total,
            'supplement_today': 0,  # 당일 데이터는 현재 0
            'supplement_total': supplement_total,
            'cancel_today': 0,  # 당일 데이터는 현재 0
            'cancel_total': cancel_month_total,
            'pak_month_total': pak_month_total,
            'cancel_month_total': cancel_month_total
        }
    
    # 제목 영역
    st.title(f"📊 폴스타 2025 보고서 - {today_kst.strftime('%Y년 %m월 %d일')}")

    # 현황 요약 (월 선택)
    header_col, select_col = st.columns([3, 1])
    with header_col:
        st.subheader("📈 현황 요약")
    with select_col:
        month_options = ["8월", "7월", "6월", "5월", "4월", "3월", "2월", "1월"]
        selected_month_label = st.selectbox(
            "조회 월",
            month_options,
            index=0,
            label_visibility="collapsed",
            key="polestar_month_select"
        )

    current_month_label = f"{today_kst.month}월"
    is_current_month_selected = (selected_month_label == current_month_label)

    # 월별 지표 데이터를 계산된 데이터로 교체
    current_month_data = calculate_monthly_summary(df_pole_pipeline, df_pole_apply, selected_month_label)

    # 상단 요약 카드
    if is_current_month_selected:
        metric_columns = st.columns(5)
        with metric_columns[0]:
            st.metric(label="파이프라인", value=f"{current_month_data['pipeline_month_total']} 건", delta=f"{current_month_data['pipeline_today']} 건 (당일)")
        with metric_columns[1]:
            st.metric(label="지원신청", value=f"{current_month_data['apply_month_total']} 건", delta=f"{current_month_data['apply_today']} 건 (당일)")
        with metric_columns[2]:
            st.metric(label="미접수", value=f"{current_month_data['unreceived_total']} 건", delta=f"{current_month_data['unreceived_today']} 건 (당일)", delta_color="inverse")
        with metric_columns[3]:
            st.metric(label="보완필요", value=f"{current_month_data['supplement_total']} 건", delta=f"{current_month_data['supplement_today']} 건 (당일)", delta_color="inverse")
        with metric_columns[4]:
            st.metric(label="취소", value=f"{current_month_data['cancel_total']} 건", delta=f"{current_month_data['cancel_today']} 건 (당일)", delta_color="inverse")
    else:
        metric_columns = st.columns(2)
        with metric_columns[0]:
            st.metric(label="파이프라인", value=f"{current_month_data['pipeline_month_total']} 건")
        with metric_columns[1]:
            st.metric(label="지원신청", value=f"{current_month_data['apply_month_total']} 건")

    # 상세 내역 부분도 계산된 데이터 사용
    with st.expander("상세 내역 보기"):
        detail_row_index = ['지원신청', '폴스타 내부지원', '접수 후 취소']
        
        if selected_month_label == "8월":
            # 8월은 현재 월이므로 실제 데이터 사용
            detailed_second_data = {
                '전월 이월수량': [54, 32, 0],  # 파이프라인 제거
                '당일': [0, 0, 0],  # 당일 데이터는 별도 계산 필요
                '당월_누계': [current_month_data['apply_month_total'], 
                        current_month_data['pak_month_total'], 
                        current_month_data['cancel_month_total']]
            }
        else:
            # 과거 월은 누계 데이터만 표시
            detailed_second_data = {
                '전월 이월수량': [0, 0, 0],
                '당일': [0, 0, 0],
                '당월_누계': [current_month_data['apply_month_total'], 
                        current_month_data['pak_month_total'], 
                        current_month_data['cancel_month_total']]
            }
        
        second_detail_df = pd.DataFrame(detailed_second_data, index=detail_row_index)
        second_detail_html = second_detail_df.to_html(classes='custom_table', border=0, escape=False)

        expander_col1, expander_col2 = st.columns(2)
        with expander_col1:
            st.subheader(f"{selected_month_label} 현황 (상세)")
            st.markdown(second_detail_html, unsafe_allow_html=True)
        with expander_col2:
            st.subheader("미접수/보완 현황 (상세)")

            # 간단한 테이블로 표시 (취소 제거)
            detail_summary_df = pd.DataFrame({
                '구분': ['미접수', '보완'],
                '수량': [
                    current_month_data['unreceived_total'],
                    current_month_data['supplement_total']
                ]
            })
            st.markdown(detail_summary_df.to_html(classes='custom_table', border=0, escape=False), unsafe_allow_html=True)

    st.markdown("---")

    # 폴스타 월별 요약 (표 + 스타일) - 기존 스타일 유지
    st.subheader("폴스타 월별 요약")

    summary_row_index = ['파이프라인', '지원신청', '폴스타 내부지원', '접수 후 취소']
    monthly_summary_data = {
        '1월': [72, 0, 68, 4],
        '2월': [52, 27, 25, 0],
        '3월': [279, 249, 20, 10],
        '4월': [182, 146, 16, 20],
        '5월': [332, 246, 63, 23],
        '6월': [47, 29, 11, 7],
        '1~6월 합계': [964, 697, 203, 64],
        '7월': [140, 83, 48, 9],
        '8월': [np.nan, np.nan, np.nan, np.nan],
        '9월': [np.nan, np.nan, np.nan, np.nan],
        '10월': [np.nan, np.nan, np.nan, np.nan],
        '11월': [np.nan, np.nan, np.nan, np.nan],
        '12월': [np.nan, np.nan, np.nan, np.nan],
        '7~12월 합계': [140, 83, 48, 9],
        '2025 총합': [1104, 780, 251, 73]
    }
    summary_df = pd.DataFrame(monthly_summary_data, index=summary_row_index)

    html_summary = summary_df.fillna('-').to_html(classes='custom_table', border=0, escape=False)
    html_summary = re.sub(
        r'(<thead>\s*<tr>)',
        r'\1<th rowspan="2">청구<br>세금계산서</th>',
        html_summary,
        count=1
    )
    html_summary = re.sub(
        r'(<tr>\s*<th>1~6월 합계</th>)(.*?)(</tr>)',
        lambda m: m.group(1) + re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', m.group(2)) + m.group(3),
        html_summary,
        flags=re.DOTALL
    )
    html_summary = html_summary.replace('<th>1~6월 합계</th>', '<th style="background-color:#ffe0b2;">1~6월 합계</th>')
    html_summary = re.sub(
        r'(<tr>\s*<th>7~12월 합계</th>)(.*?)(</tr>)',
        lambda m: m.group(1) + re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', m.group(2)) + m.group(3),
        html_summary,
        flags=re.DOTALL
    )
    html_summary = html_summary.replace('<th>7~12월 합계</th>', '<th style="background-color:#ffe0b2;">7~12월 합계</th>')
    html_summary = re.sub(
        r'(<th[^>]*>2025 총합</th>)',
        r'<th style="background-color:#e3f2fd;">2025 총합</th>',
        html_summary
    )
    html_summary = re.sub(
        r'(<tr>.*?)(<td[^>]*>[^<]*</td>)(\s*</tr>)',
        lambda m: re.sub(
            r'(<td[^>]*>)([^<]*)(</td>)$',
            r'<td style="background-color:#e3f2fd;">\2</td>',
            m.group(0)
        ),
        html_summary,
        flags=re.DOTALL
    )
    def color_sum_cols(match):
        row = match.group(0)
        tds = re.findall(r'(<td[^>]*>[^<]*</td>)', row)
        if len(tds) >= 14:
            tds[6] = re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', tds[6])
            tds[13] = re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', tds[13])
            row_new = row
            for i, td in enumerate(tds):
                row_new = re.sub(r'(<td[^>]*>[^<]*</td>)', lambda m: td if m.start() == 0 else m.group(0), row_new, count=1)
            return row_new
        return row
    html_summary = re.sub(r'<tr>(.*?)</tr>', color_sum_cols, html_summary, flags=re.DOTALL)
    st.markdown(html_summary, unsafe_allow_html=True)

# --- 지도 뷰어 ---
if viewer_option == '지도(테스트)':
    # --- 지도 관련 라이브러리 임포트 ---
    import json
    import pandas as pd
    import plotly.express as px
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
    def get_filtered_data(_df_6, selected_quarter):
        """
        분기별로 필터링된 데이터를 반환합니다.
        """
        if selected_quarter == '전체':
            return _df_6['지역구분'].value_counts().to_dict()
        
        filtered_df = _df_6.copy()
        filtered_df['신청일자'] = pd.to_datetime(filtered_df['신청일자'], errors='coerce')
        q_map = {'1Q': [1,2,3], '2Q': [4,5,6], '3Q': [7,8,9], '4Q': [10,11,12]}
        if selected_quarter in q_map:
            filtered_df = filtered_df[filtered_df['신청일자'].dt.month.isin(q_map[selected_quarter])]
        
        return filtered_df['지역구분'].value_counts().to_dict()

    @st.cache_data
    def apply_counts_to_map(_preprocessed_map, _region_counts):
        """
        미리 병합된 GeoJSON에 count 데이터를 빠르게 매핑합니다.
        """
        if not _preprocessed_map:
            return None, pd.DataFrame()

        # 원본 GeoJSON을 복사하여 사용
        final_geojson = _preprocessed_map.copy()
        
        # 지도에 있는 모든 지역의 count를 0으로 초기화
        final_counts = {feat['properties']['sggnm']: 0 for feat in final_geojson['features']}
        unmatched_regions = set(_region_counts.keys())

        # df_6의 데이터를 지도에 매핑
        for region, count in _region_counts.items():
            region_str = str(region).strip()
            matched = False
            
            # Case 1: '서울특별시'와 같은 시도명 직접 매칭
            if region_str in final_counts:
                final_counts[region_str] += count
                unmatched_regions.discard(region_str)
                matched = True
            
            # Case 2 & 3: '수원시' -> '경기도 수원시'와 같은 시군구명 매칭
            if not matched:
                for key in final_counts.keys():
                    if key.endswith(" " + region_str):
                        final_counts[key] += count
                        unmatched_regions.discard(region_str)
                        matched = True
                        break
        
        # 최종 계산된 count 값을 GeoJSON의 'value' 속성에 주입
        for feature in final_geojson['features']:
            key = feature['properties']['sggnm']
            feature['properties']['value'] = final_counts.get(key, 0)
            
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

    # --- 대한민국 지도 시각화 실행 로직 ---
    st.header("🗺️ 지도 시각화")
    quarter_options = ['전체', '1Q', '2Q', '3Q']
    selected_quarter = st.selectbox("분기 선택", quarter_options)
    
    # 미리 처리된 가벼운 지도 파일을 로드 (캐시됨)
    preprocessed_map = load_preprocessed_map('preprocessed_map.geojson')
    
    if preprocessed_map and not df_6.empty:
        # 분기별 필터링된 데이터 가져오기 (캐시됨)
        region_counts = get_filtered_data(df_6, selected_quarter)
        
        # 필터링된 데이터를 지도에 적용 (캐시됨)
        final_geojson, unmatched_df = apply_counts_to_map(preprocessed_map, region_counts)
        
        st.sidebar.header("⚙️ 지도 설정")
        map_styles = {"기본 (밝음)": "carto-positron", "기본 (어두움)": "carto-darkmatter"}
        color_scales = ["Reds","Blues", "Greens", "Viridis"]
        selected_style = st.sidebar.selectbox("지도 스타일", list(map_styles.keys()))
        selected_color = st.sidebar.selectbox("색상 스케일", color_scales)
        
        # 지도 생성 (캐시됨)
        result = create_korea_map(final_geojson, map_styles[selected_style], selected_color)
        if result:
            fig, df = result
            st.plotly_chart(fig, use_container_width=True)
            st.sidebar.metric("총 지역 수", len(df))
            st.sidebar.metric("데이터가 있는 지역", len(df[df['value'] > 0]))
            st.sidebar.metric("최대 신청 건수", f"{df['value'].max():,}")
            st.subheader("데이터 테이블")
            st.dataframe(df[['sggnm', 'value']].sort_values('value', ascending=False), use_container_width=True)
            if not unmatched_df.empty:
                st.subheader("⚠️ 매칭되지 않은 지역 목록")
                st.dataframe(unmatched_df, use_container_width=True)
            else:
                st.success("✅ 모든 지역이 성공적으로 매칭되었습니다.")
        else:
            st.error("지도 생성 실패.")
    else:
        st.error("전처리된 지도(preprocessed_map.geojson) 또는 df_6 데이터를 찾을 수 없습니다.")

# --- 지자체별 정리 ---
if viewer_option == '분석':

    # --- 데이터 로딩 및 전처리 함수 ---
    @st.cache_data
    def load_and_process_data_1():
        """
        preprocessed_data.pkl에서 테슬라 EV 데이터를 로드합니다.
        이 함수는 한 번만 실행되어 결과가 캐시됩니다.
        """
        try:
            import pickle
            
            with open("preprocessed_data.pkl", "rb") as f:
                data = pickle.load(f)
            
            df = data.get("df_tesla_ev", pd.DataFrame())
            
            if df.empty:
                st.error("❌ preprocessed_data.pkl에서 테슬라 EV 데이터를 찾을 수 없습니다.")
                st.info("💡 전처리.py를 먼저 실행하여 데이터를 준비해주세요.")
                return pd.DataFrame()
            
            # 날짜 컬럼이 있는 경우 날짜 필터링 적용
            date_col = next((col for col in df.columns if '신청일자' in col), None)
            if date_col:
                df = df.dropna(subset=[date_col])
            
            return df

        except FileNotFoundError:
            st.error("❌ 'preprocessed_data.pkl' 파일을 찾을 수 없습니다.")
            st.info("💡 전처리.py를 먼저 실행하여 데이터를 준비해주세요.")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"❌ 데이터 로드 중 오류: {str(e)}")
            st.info("💡 전처리.py를 먼저 실행하여 데이터를 준비해주세요.")
            return pd.DataFrame()

    # --- 데이터 로드 ---
    df_original = load_and_process_data_1()

    if not df_original.empty:
        # --- 메인 레이아웃 설정 ---
        main_col, filter_col = st.columns([0.75, 0.25])

        # --- 필터 영역 (오른쪽 컬럼) ---
        with filter_col:
            with st.container():
                st.markdown("<div class='filter-container'>", unsafe_allow_html=True)
                st.header("🔍 데이터 필터")
                
                default_end_date = pd.to_datetime('2025-08-06').date()
                
                # 1. 기간 필터
                date_col = next((col for col in df_original.columns if '신청일자' in col), None)
                min_date = df_original[date_col].min().date()
                max_date = df_original[date_col].max().date()

                # 시작일과 종료일을 분리해서 입력
                date_col1, date_col2 = st.columns(2)

                with date_col1:
                    start_date = st.date_input(
                        "시작일",
                        value=min_date,
                        min_value=min_date,
                        max_value=max_date,
                        key="start_date_filter"
                    )

                with date_col2:
                    end_date = st.date_input(
                        "종료일",
                        value=default_end_date,
                        min_value=min_date,
                        max_value=max_date,
                        key="end_date_filter"
                    )

                # 날짜 유효성 검사 및 보정
                if start_date > end_date:
                    st.warning("⚠️ 시작일이 종료일보다 늦습니다. 자동으로 교체합니다.")
                    start_date, end_date = end_date, start_date

                # 2. 차종 필터
                model_options = df_original['분류된_차종'].unique().tolist()
                selected_models = st.multiselect(
                    "차종 선택",
                    options=model_options,
                    default=model_options,
                    key="model_filter"
                )

                # 3. 신청유형 필터
                applicant_options = df_original['분류된_신청유형'].unique().tolist()
                selected_applicants = st.multiselect(
                    "신청유형 선택",
                    options=applicant_options,
                    default=applicant_options,
                    key="applicant_filter"
                )
                st.markdown("</div>", unsafe_allow_html=True)

        # --- 필터링된 데이터 생성 ---
        df_filtered = df_original[
            (df_original[date_col].dt.date >= start_date) &
            (df_original[date_col].dt.date <= end_date) &
            (df_original['분류된_차종'].isin(selected_models)) &
            (df_original['분류된_신청유형'].isin(selected_applicants))
        ]

        # --- 메인 대시보드 (왼쪽 컬럼) ---
        with main_col:
            st.title("🚗 테슬라 EV 데이터 대시보드")
            st.markdown(f"**조회 기간:** `{start_date}` ~ `{end_date}`")
            st.markdown("---")

            # --- 탭 구성 ---
            tab1, tab2, tab3, tab4 = st.tabs(["📊 종합 현황", "👥 신청자 분석", "👨‍💼 작업자 분석", "🏛️ 지자체별 현황 정리"])

            with tab1:
                st.subheader("핵심 지표")
                
                total_count = len(df_filtered)
                model_counts = df_filtered['분류된_차종'].value_counts()
                applicant_counts = df_filtered['분류된_신청유형'].value_counts()

                metric_cols = st.columns(4)
                metric_cols[0].metric("총 신청 대수", f"{total_count:,} 대")
                metric_cols[1].metric("Model Y", f"{model_counts.get('Model Y', 0):,} 대")
                metric_cols[2].metric("Model 3", f"{model_counts.get('Model 3', 0):,} 대")
                metric_cols[3].metric("개인 신청 비율", f"{(applicant_counts.get('개인', 0) / total_count * 100 if total_count > 0 else 0):.1f} %")

                st.markdown("<br>", unsafe_allow_html=True)
                
                chart_col1, chart_col2 = st.columns(2)
                with chart_col1:
                    st.subheader("차종별 분포")
                    if not model_counts.empty:
                        fig_model = px.pie(
                            values=model_counts.values, 
                            names=model_counts.index, 
                            hole=0.4,
                            color_discrete_sequence=px.colors.sequential.Blues_r
                        )
                        fig_model.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_model, use_container_width=True)
                    else:
                        st.info("데이터 없음")

                with chart_col2:
                    st.subheader("차종 × 신청유형 교차 분석")
                    cross_tab = pd.crosstab(df_filtered['분류된_차종'], df_filtered['분류된_신청유형'])
                    st.dataframe(cross_tab, use_container_width=True)

            with tab2:
                st.subheader("신청유형 및 연령대 분석")
                
                analysis_cols = st.columns(2)
                with analysis_cols[0]:
                    st.markdown("##### 📋 신청유형별 분포")
                    if not applicant_counts.empty:
                        fig_applicant = px.pie(
                            values=applicant_counts.values,
                            names=applicant_counts.index,
                            hole=0.4,
                            color_discrete_sequence=px.colors.sequential.Greens_r
                        )
                        fig_applicant.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_applicant, use_container_width=True)
                    else:
                        st.info("데이터 없음")

                if '연령대' in df_filtered.columns:
                    with analysis_cols[1]:
                        st.markdown("##### 📋 연령대별 분포 (개인/개인사업자)")
                        personal_df = df_filtered[df_filtered['분류된_신청유형'].isin(['개인', '개인사업자'])]
                        age_group_counts = personal_df['연령대'].value_counts()
                        
                        if not age_group_counts.empty:
                            fig_age = px.pie(
                                values=age_group_counts.values,
                                names=age_group_counts.index,
                                hole=0.4,
                                color_discrete_sequence=px.colors.sequential.Oranges_r
                            )
                            fig_age.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig_age, use_container_width=True)
                        else:
                            st.info("데이터 없음")

            with tab3:
                st.subheader("작성자별 작업 현황")
                # 주의사항 한줄(심플)
                st.markdown('<span style="color:#666; font-size:14px;">※ 5월 20일 이전까지는 배은영, 이경구 계정으로 매크로 작업이 많았습니다.</span>', unsafe_allow_html=True)
                
                if '작성자' in df_filtered.columns:
                    # 작성자별 통계
                    writer_counts = df_filtered['작성자'].value_counts()
                    
                    # 상위 10명만 표시 (너무 많으면 차트가 복잡해짐)
                    top_writers = writer_counts.head(10)
                    others_count = writer_counts.iloc[10:].sum() if len(writer_counts) > 10 else 0
                    
                    if others_count > 0:
                        # 상위 10명 + 기타로 구성
                        display_data = pd.concat([
                            top_writers,
                            pd.Series({'기타': others_count})
                        ])
                    else:
                        display_data = top_writers
                    
                    # 메트릭 표시
                    metric_cols = st.columns(4)
                    metric_cols[0].metric("총 작성자 수", f"{len(writer_counts):,} 명")
                    metric_cols[1].metric("최다 작성자", f"{writer_counts.iloc[0] if not writer_counts.empty else 0:,} 건")
                    metric_cols[2].metric("평균 작성 건수", f"{writer_counts.mean():.1f} 건")
                    metric_cols[3].metric("상위 10명 비율", f"{(top_writers.sum() / len(df_filtered) * 100):.1f} %")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # 파이차트
                    chart_col1, chart_col2 = st.columns(2)
                    
                    with chart_col1:
                        st.markdown("##### 📊 작성자별 작업 분포")
                        if not display_data.empty:
                            fig_writer = px.pie(
                                values=display_data.values,
                                names=display_data.index,
                                hole=0.4,
                                color_discrete_sequence=px.colors.sequential.Purples_r
                            )
                            fig_writer.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig_writer, use_container_width=True)
                        else:
                            st.info("데이터 없음")
                    
                    with chart_col2:
                        st.markdown("##### 📋 상위 작성자 현황")
                        writer_stats_df = pd.DataFrame({
                            '작성자': top_writers.index,
                            '작성 건수': top_writers.values,
                            '비율(%)': (top_writers.values / len(df_filtered) * 100).round(1)
                        })
                        
                        st.dataframe(
                            writer_stats_df,
                            use_container_width=True,
                            hide_index=True
                        )
                    
                else:
                    st.warning("⚠️ '작성자' 컬럼을 찾을 수 없습니다.")
                    st.info("현재 파일의 컬럼명:", list(df_filtered.columns))

            with tab4:
                st.markdown("""
                <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #e0e0e0; margin-bottom: 30px;">
                    <h2 style="color: #1f77b4; margin: 0; font-weight: 600;">🏛️ 지자체별 현황 정리</h2>
                    <p style="color: #666; margin: 10px 0 0 0; font-size: 16px;">지역별 보조금 현황 및 필요 서류 정보</p>
                </div>
                """, unsafe_allow_html=True)
                if df_master.empty or '지역' not in df_master.columns:
                    st.warning("지자체 데이터가 없습니다.")
                else:
                    region_list = df_master['지역'].dropna().unique().tolist()
                    # 수정된 코드
                    st.markdown("##### 📍 분석 대상 지역")
                    selected_region = st.selectbox(
                        "지역을 선택하세요",
                        options=region_list,
                        index=0,
                        help="분석할 지자체를 선택하세요"
                    )
                    st.markdown(f"**선택된 지역:** `{selected_region}`")

                    # 선택된 지역의 데이터 추출 (한 행)
                    filtered = df_master[df_master['지역'] == selected_region].iloc[0]

                    # --- 1. 현황 (차량 대수) ---
                    st.markdown("### 📊 현황 (차량 대수)")
                    st.markdown("---")

                    # 먼저 변수들을 계산
                    general_status = filtered.get('현황_일반', 0)
                    try:
                        if pd.isna(general_status) or general_status == '' or str(general_status).strip() == '':
                            general_status = 0
                        else:
                            general_status = int(float(str(general_status).replace(',', '')))
                    except (ValueError, TypeError):
                        general_status = 0

                    priority_status = filtered.get('현황_우선', 0)
                    try:
                        if pd.isna(priority_status) or priority_status == '' or str(priority_status).strip() == '':
                            priority_status = 0
                        else:
                            priority_status = int(float(str(priority_status).replace(',', '')))
                    except (ValueError, TypeError):
                        priority_status = 0

                    # 그 다음에 HTML 표시
                    status_cols = st.columns(2)
                    with status_cols[0]:
                        st.markdown("""
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                    padding: 20px; border-radius: 15px; color: white; text-align: center;">
                            <h4 style="margin: 0 0 10px 0; font-size: 18px;">일반 현황</h4>
                            <h2 style="margin: 0; font-size: 32px; font-weight: 700;">{general_status:,} 대</h2>
                        </div>
                        """.format(general_status=general_status), unsafe_allow_html=True)

                    with status_cols[1]:
                        st.markdown("""
                        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                                    padding: 20px; border-radius: 15px; color: white; text-align: center;">
                            <h4 style="margin: 0 0 10px 0; font-size: 18px;">우선 현황</h4>
                            <h2 style="margin: 0; font-size: 32px; font-weight: 700;">{priority_status:,} 대</h2>
                        </div>
                        """.format(priority_status=priority_status), unsafe_allow_html=True)

                    st.markdown("---")

                    # --- 2. 모델별 보조금 ---
                    st.subheader("🚗 모델별 보조금 (단위: 만 원)")

                    # 모델명과 컬럼명 매핑
                    model_cols = {
                        'Model 3 RWD': 'Model 3 RWD_기본',
                        'Model 3 RWD (2024)': 'Model 3 RWD(2024)_기본',
                        'Model 3 LongRange': 'Model 3 LongRange_기본',
                        'Model 3 Performance': 'Model 3 Performance_기본',
                        'Model Y New RWD': 'Model Y New RWD_기본',
                        'Model Y New LongRange': 'Model Y New LongRange_기본'
                    }

                    # 보조금 데이터 수집
                    subsidy_data = []
                    for model_name, col_name in model_cols.items():
                        if col_name in filtered.index:
                            subsidy_value = filtered[col_name]
                            try:
                                if pd.notna(subsidy_value) and subsidy_value != '' and str(subsidy_value).strip() != '':
                                    numeric_value = float(str(subsidy_value).replace(',', ''))
                                    if numeric_value > 0:
                                        subsidy_data.append((model_name, numeric_value))
                            except (ValueError, TypeError):
                                continue

                    if subsidy_data:
                        # 3열 그리드로 표시
                        cols = st.columns(3)
                        for idx, (model_name, amount) in enumerate(subsidy_data):
                            with cols[idx % 3]:
                                st.markdown(f"""
                                <div style="background: #f8f9fa; padding: 10px; border-radius: 8px; 
                                            border-left: 3px solid #007bff; margin: 5px 0;">
                                    <h6 style="margin: 0 0 5px 0; color: #495057; font-size: 12px; font-weight: 600;">{model_name}</h6>
                                    <h4 style="margin: 0; color: #007bff; font-size: 18px; font-weight: 600;">
                                        {int(amount):,} 만원
                                    </h4>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("해당 지역의 모델별 보조금 정보가 없습니다.")

                    st.markdown("---")

                    # --- 3. 필요 서류 ---
                    st.subheader("📝 필요 서류")
                    doc_cols = st.columns(2)

                    with doc_cols[0]:
                        st.markdown("##### 지원신청서류")
                        doc_text_apply = str(filtered.get('지원신청서류', '내용 없음')).replace('\n', '<br>')
                        st.markdown(
                            f"<div style='background-color:#f0f2f6; border-radius:10px; padding:15px; height: 300px; overflow-y: auto;'>{doc_text_apply}</div>",
                            unsafe_allow_html=True
                        )

                    with doc_cols[1]:
                        st.markdown("##### 지급신청서류")
                        doc_text_payment = str(filtered.get('지급신청서류', '내용 없음')).replace('\n', '<br>')
                        st.markdown(
                            f"<div style='background-color:#f0f2f6; border-radius:10px; padding:15px; height: 300px; overflow-y: auto;'>{doc_text_payment}</div>",
                            unsafe_allow_html=True
                        )

    else:
        st.warning("데이터를 불러올 수 없습니다. 파일을 확인해주세요.")



    
