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
from datetime import datetime, timedelta
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
        sys.exit()

def get_base_city_name(sggnm_str):
    """
    시군구명에서 기본 시 이름을 추출합니다.
    예: '수원시팔달구' -> '수원시', '청주시흥덕구' -> '청주시'
    """
    import re
    
    # 패턴: ~시로 끝나는 부분을 찾아서 ~시까지만 추출
    # 예: '수원시팔달구' -> '수원시', '청주시흥덕구' -> '청주시'
    match = re.search(r'(.+?시)', sggnm_str)
    if match:
        return match.group(1)
    
    # 시가 아닌 경우 원본 반환
    return sggnm_str

def load_and_process_data(region_counts, geojson_path):
    """
    region_counts와 GeoJSON 파일을 로드하고, 지역구분 데이터를 기반으로 집계하여
    지도 시각화에 사용할 최종 GeoJSON과 매칭되지 않은 지역 목록을 반환합니다.
    """
    try:
        # --- 1. region_counts 통합 처리 (동적 방식) ---
        consolidated_counts = {}
        consolidation_log = []
        for region, count in region_counts.items():
            region_str = str(region).strip()
            
            # 동적 통합: ~시로 끝나는 지역은 기본 시 이름으로 통합
            consolidated_region = get_base_city_name(region_str)
            consolidated_counts[consolidated_region] = consolidated_counts.get(consolidated_region, 0) + count
            
            # 통합이 적용된 경우 로그 기록
            if consolidated_region != region_str:
                consolidation_log.append(f"{region_str} → {consolidated_region}")
        
        # 통합 로그 출력 (디버깅용)
        if consolidation_log:
            st.write("🔗 지역 통합 적용:")
            for log in consolidation_log:
                st.write(f"  - {log}")
        
        # --- 2. GeoJSON을 시군구 단위로 병합하여 기본 지도 생성 ---
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
                
                # 시군구별 그룹화 (동적 통합 적용)
                # sgg에서 동적 통합 매핑 적용
                consolidated_sgg = get_base_city_name(sgg)
                key = f"{sido} {consolidated_sgg}"
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
                    merged_geom = unary_union(geoms)
                    sgg_map_geoms[sggnm] = merged_geom
                except Exception as e:
                    st.write(f"❌ 지오메트리 병합 실패: {sggnm}, 오류: {e}")
                    continue

        # --- 3. 3단계 매칭 로직 구현 ---
        final_counts = {}
        unmatched_regions = []

        # 시도명 목록 (1단계 매칭용)
        sido_list = [
            '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시', 
            '울산광역시', '세종특별자치시', '제주특별자치도'
        ]

        for region, count in consolidated_counts.items():
            region_str = str(region).strip()
            matched = False

            # 1단계: 서울, 광역시, 제주, 세종은 sidonm에 따라 매칭 (시도 단위로 통합)
            if region_str in sido_list:
                if region_str in sido_map_geoms:
                    final_counts[region_str] = final_counts.get(region_str, 0) + count
                    matched = True
            
            # 2단계: 통합된 시군구명으로 매칭 (예: '수원시' -> '경기도 수원시')
            if not matched:
                for sggnm_key in sgg_map_geoms.keys():
                    # sggnm에서 시도명 제거하고 시군구명만 추출
                    sgg_part = sggnm_key.split(' ', 1)[1] if ' ' in sggnm_key else sggnm_key
                    
                    # 통합된 시군구명과 정확히 일치하는 경우
                    if sgg_part == region_str:
                        final_counts[sggnm_key] = final_counts.get(sggnm_key, 0) + count
                        matched = True
                        break
            
            if not matched:
                # 원본 region_counts에서 해당 지역을 찾아서 추가
                for original_region, original_count in region_counts.items():
                    original_region_str = str(original_region).strip()
                    consolidated_original = get_base_city_name(original_region_str)
                    if consolidated_original == region:
                        unmatched_regions.append(original_region)
                        break

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
        
        # 통합된 시군구 단위로 매칭된 지역들 (통합된 경계선)
        for sggnm, geom in sgg_map_geoms.items():
            if sggnm in final_counts and sggnm not in sido_list:  # 시도 단위가 아닌 경우만
                # sggnm에서 시도명 제거하고 시군구명만 추출하여 표시명으로 사용
                display_name = sggnm.split(' ', 1)[1] if ' ' in sggnm else sggnm
                
                merged_feature = {
                    'type': 'Feature',
                    'geometry': geom.__geo_interface__,
                    'properties': {
                        'sggnm': display_name,  # '경기도 수원시' -> '수원시'로 표시
                        'value': final_counts[sggnm]
                    }
                }
                merged_features.append(merged_feature)

        merged_geojson = {'type': 'FeatureCollection', 'features': merged_features}
        
        # 디버깅: 최종 GeoJSON에서 수원시 관련 features 확인
        suwon_features = [f for f in merged_features if '수원시' in f['properties']['sggnm']]
        if suwon_features:
            st.write(f"🔍 최종 GeoJSON에서 수원시 features: {[f['properties']['sggnm'] for f in suwon_features]}")
        
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

def create_simple_map_data(selected_region=None):
    """st.map을 위한 간단한 지도 데이터를 생성합니다."""
    # 기본 서울 중심 데이터
    myData = {'lat': [37.56668], 'lon': [126.9784]}
    
    # 선택된 지역이 있으면 해당 지역의 좌표로 변경
    if selected_region and selected_region != "전체":
        korea_map_df = create_korea_map_data()
        region_data = korea_map_df[korea_map_df['region'] == selected_region]
        if not region_data.empty:
            myData['lat'] = [region_data['lat'].values[0]]
            myData['lon'] = [region_data['lon'].values[0]]
    
    # 고정된 포인트 수로 랜덤 포인트 추가
    point_count = 10  # 고정된 포인트 수
    
    # 선택된 지역 주변에 랜덤 포인트 추가
    for _ in range(point_count - 1):
        myData['lat'].append(myData['lat'][0] + np.random.randn() / 50.0)
        myData['lon'].append(myData['lon'][0] + np.random.randn() / 50.0)
    
    return myData

def create_admin_map_data(df_admin_coords, selected_sido=None, selected_sigungu=None):
    """행정구역별 위경도 좌표 데이터를 사용하여 지도 데이터를 생성합니다."""
    if df_admin_coords.empty:
        # 데이터가 없으면 기본 서울 중심 데이터 반환
        return {'lat': [37.56668], 'lon': [126.9784], 'size': [100]}
    
    # 필터링된 데이터
    filtered_data = df_admin_coords.copy()
    
    if selected_sido and selected_sido != "전체":
        filtered_data = filtered_data[filtered_data['시도'] == selected_sido]
    
    if selected_sigungu and selected_sigungu != "전체":
        # 시군구 데이터를 문자열로 변환하여 비교
        filtered_data = filtered_data[filtered_data['시군구'].astype(str) == selected_sigungu]
    
    if filtered_data.empty:
        # 필터링 결과가 없으면 기본 서울 중심 데이터 반환
        return {'lat': [37.56668], 'lon': [126.9784], 'size': [100]}
    
    # 위도, 경도 데이터 추출
    lat_list = filtered_data['위도'].tolist()
    lon_list = filtered_data['경도'].tolist()
    
    # 각 시군구별로 랜덤 데이터 생성 (10~1000 사이)
    size_list = []
    for i in range(len(filtered_data)):
        # 시군구별로 고유한 랜덤값 생성 (시드 고정으로 일관성 유지)
        sigungu_name = str(filtered_data.iloc[i]['시군구'])
        np.random.seed(hash(sigungu_name) % 2**32)  # 시군구명을 시드로 사용
        random_value = np.random.randint(10, 1001)  # 10~1000 사이 랜덤값
        size_list.append(random_value)
    
    # 각 시군구별로 고유한 랜덤 크기 데이터만 사용 (추가 포인트 생성 제거)
    
    return {'lat': lat_list, 'lon': lon_list, 'size': size_list}

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

# --- 시간대 설정 ---
KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()

# --- 사이드바: 조회 옵션 설정 ---
with st.sidebar:
    st.header("👁️ 뷰어 옵션")
    viewer_option = st.radio("뷰어 유형을 선택하세요.", ('내부', '테슬라', '폴스타', '지도(테스트)', '지자체별 정리'), key="viewer_option")
    st.markdown("---")
    st.header("📊 조회 옵션")
    view_option = st.radio(
        "조회 유형을 선택하세요.",
        ('금일', '특정일 조회', '기간별 조회', '분기별 조회', '월별 조회'),
        key="view_option"
    )

    start_date, end_date = None, None
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
st.title(title)
st.caption(f"마지막 데이터 업데이트: {update_time_str}")
st.markdown("---")

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
            '7월': ['', july_pipeline, july_apply, july_distribute],
            '8월': ['', august_pipeline, august_apply, august_distribute]
        }
        corp_df = pd.DataFrame(corp_df_data, index=['타겟 (진척률)', '파이프라인', '지원신청', '지급신청'])
        corp_df['계'] = corp_df['7월'] + corp_df['8월']

        # --- '타겟 (진척률)' 데이터 계산 ---
        q3_target_corp = 1500
        ttl_apply_corp = corp_df.loc['지원신청', '계']
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
                            f'<td\\1 colspan="3" style="background-color:#e0f7fa;">{target_text}</td>',
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
            "기타메모",
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

# --- 폴스타 뷰 전용 표 ---
if viewer_option == '폴스타':
    # 데이터프레임 생성
    pol_data = {
        '1월': [72, 0, 68, 4],
        '2월': [52, 27, 25, 0],
        '3월': [279, 249, 20, 10],
        '4월': [182, 146, 16, 20],
        '5월': [332, 246, 63, 23],
        '6월': [47, 29, 11, 7],
        '합계': [964, 697, 203, 64],
        '7월': [140, 83, 48, 9],
        '8월': [np.nan, np.nan, np.nan, np.nan],
        '9월': [np.nan, np.nan, np.nan, np.nan],
        '10월': [np.nan, np.nan, np.nan, np.nan],
        '11월': [np.nan, np.nan, np.nan, np.nan],
        '12월': [np.nan, np.nan, np.nan, np.nan],
        '합계': [140, 83, 48, 9],
        '2025 총합': [1104, 780, 251, 73]
    }
    row_idx = ['파이프라인', '지원신청', '폴스타 내부지원', '접수 후 취소']
    pol_df = pd.DataFrame(pol_data, index=row_idx)

    st.title("폴스타 2025")
    # NaN 값을 '-'로 치환
    html_pol = pol_df.fillna('-').to_html(classes='custom_table', border=0, escape=False)

    import re

    # <thead> 바로 뒤에 <tr><th>청구<br>세금계산서</th> ... 삽입
    html_pol = re.sub(
        r'(<thead>\s*<tr>)',
        r'\1<th rowspan="2">청구<br>세금계산서</th>',
        html_pol,
        count=1
    )

    # ['합계'] 행(7번째 컬럼) 연주황색(#ffe0b2) 배경, ['2025 총합'] 열 연파랑색(#e3f2fd) 배경
    # <tr>에서 <th>합계</th>가 포함된 행 전체의 <td>에 스타일 적용
    html_pol = re.sub(
        r'(<tr>\s*<th>합계</th>)(.*?)(</tr>)',
        lambda m: m.group(1) + re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', m.group(2)) + m.group(3),
        html_pol,
        flags=re.DOTALL
    )
    # <th>합계</th>에도 배경색 적용
    html_pol = html_pol.replace('<th>합계</th>', '<th style="background-color:#ffe0b2;">합계</th>')

    # ['2025 총합'] 열(마지막 컬럼) 연파랑색(#e3f2fd) 배경
    # <thead>의 마지막 <th>에 스타일 적용
    html_pol = re.sub(
        r'(<th[^>]*>2025 총합</th>)',
        r'<th style="background-color:#e3f2fd;">2025 총합</th>',
        html_pol
    )

    # <tbody>의 각 행에서 마지막 <td>에 스타일 적용 (2025 총합 데이터 셀)
    html_pol = re.sub(
        r'(<tr>.*?)(<td[^>]*>[^<]*</td>)(\s*</tr>)',
        lambda m: re.sub(
            r'(<td[^>]*>)([^<]*)(</td>)$',
            r'<td style="background-color:#e3f2fd;">\2</td>',
            m.group(0)
        ),
        html_pol,
        flags=re.DOTALL
    )

    # <tbody>의 각 행에서 '2025 총합'에 해당하는 <td>에도 배경색 적용 (헤더뿐 아니라 데이터까지)
    # 위에서 이미 마지막 <td>에 칠했으나, 혹시 순서가 바뀌거나 컬럼 추가시 대비해 '2025 총합' 텍스트가 들어간 <td>도 칠함
    html_pol = re.sub(
        r'(<td[^>]*>)([^<]*2025 총합[^<]*)(</td>)',
        r'<td style="background-color:#e3f2fd;">\2</td>',
        html_pol
    )

    # <tbody>의 각 행에서 '합계' 컬럼(즉, 7번째 컬럼)에 해당하는 <td>에도 배경색 적용
    # '합계'는 헤더에만 칠하는 것이 아니라, 데이터 셀에도 칠해야 하므로, 7번째 <td>에 칠함
    def color_sum_column(match):
        row = match.group(0)
        # 7번째 <td>를 찾아서 색칠
        tds = re.findall(r'(<td[^>]*>[^<]*</td>)', row)
        if len(tds) >= 7:
            tds[6] = re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', tds[6])
            # 다시 조립
            row_new = row
            for i, td in enumerate(tds):
                # 첫 번째 등장하는 <td>만 순서대로 교체
                row_new = re.sub(r'(<td[^>]*>[^<]*</td>)', lambda m: td if m.start() == 0 else m.group(0), row_new, count=1)
            return row_new
        else:
            return row
    html_pol = re.sub(r'<tr>(.*?)</tr>', color_sum_column, html_pol, flags=re.DOTALL)

    st.markdown(html_pol, unsafe_allow_html=True)

    # --- 두 번째 표: 7월 현황 (반쪽 영역) ---
    second_data = {
        '전월 이월수량': [86,54,32,0],
        '당일': [0,0,0,0],
        '당월_누계': [0,0,0,0]
    }
    second_df = pd.DataFrame(second_data, index=row_idx)
    second_html = second_df.to_html(classes='custom_table', border=0, escape=False)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("7월 현황")
        st.markdown(second_html, unsafe_allow_html=True)

    with col2:
        st.subheader("미접수/보완/취소 현황")
        third_cols = pd.MultiIndex.from_tuples([
            ('미접수량','서류미비'), ('미접수량','대기요청'),
            ('보완 잔여 수량','서류미비'), ('보완 잔여 수량','미처리'),
            ('취소','단순취소'), ('취소','내부지원전환')
        ])
        third_df = pd.DataFrame([
            [2,2,4,0,6,3],
            [4,4,4,4,9,9]
        ], index=['당일','누계'], columns=third_cols)
        third_html = third_df.to_html(classes='custom_table', border=0, escape=False)
        st.markdown(third_html, unsafe_allow_html=True)

    st.stop()

# --- 지도 뷰어 ---
if viewer_option == '지도(테스트)':
    # --- 지도 관련 라이브러리 임포트 ---
    from shapely.geometry import shape
    from shapely.ops import unary_union
    import re

    @st.cache_data
    def load_and_process_data(region_counts, geojson_path):
        """
        Excel 데이터를 GeoJSON과 매칭하고, 데이터의 지역 단위에 맞춰
        GeoJSON의 경계를 동적으로 병합하여 최종 지도 데이터를 생성합니다.
        """
        try:
            # 1. GeoJSON 파일 로드
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)

            # --- 2. GeoJSON 그룹화 ---
            # Case 1을 위한 그룹 (예: 서울특별시)
            sido_geoms_for_merge = {} 
            # Case 2, 3을 위한 그룹 (예: 경기도 수원시, 경기도 가평군)
            sgg_geoms_for_merge = {}  

            # 광역시/특별시/특별자치시 목록
            metro_sido_list = [
                '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시', 
                '울산광역시', '세종특별자치시', '제주특별자치도'
            ]
            # 행정구를 가진 일반시 목록
            general_si_with_gu = ['고양시', '성남시', '수원시', '안산시', '안양시', '용인시', '창원시', '청주시', '포항시', '천안시', '전주시']

            for feature in geojson_data['features']:
                properties = feature['properties']
                sido = properties.get('sidonm', '')
                sgg = properties.get('sggnm', '')
                if not (sido and sgg and feature.get('geometry')):
                    continue

                geom = shape(feature['geometry'])

                # Case 1: 광역시/특별시 등은 sido 단위로 그룹화
                if sido in metro_sido_list:
                    if sido not in sido_geoms_for_merge:
                        sido_geoms_for_merge[sido] = []
                    sido_geoms_for_merge[sido].append(geom)
                
                # Case 2 & 3: 일반 도(道)의 시/군은 sgg 단위로 그룹화
                else:
                    base_sgg = sgg
                    # 일반시의 하위 행정구는 '시' 단위로 통합
                    for city in general_si_with_gu:
                        if city in sgg:
                            base_sgg = city
                            break
                    
                    key = f"{sido} {base_sgg}"
                    if key not in sgg_geoms_for_merge:
                        sgg_geoms_for_merge[key] = []
                    sgg_geoms_for_merge[key].append(geom)

            # --- 3. 지오메트리 병합 ---
            base_map_geoms = {}
            # Case 1 병합
            for sido, geoms in sido_geoms_for_merge.items():
                if geoms:
                    base_map_geoms[sido] = unary_union(geoms)
            # Case 2, 3 병합
            for sgg, geoms in sgg_geoms_for_merge.items():
                if geoms:
                    base_map_geoms[sgg] = unary_union(geoms)

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
                
                # Case 2, 3: '수원시' -> '경기도 수원시'와 같은 시군구명 매칭
                if not matched:
                    for key in final_counts.keys():
                        if key.endswith(" " + region_str):
                            final_counts[key] += count
                            unmatched_regions.discard(region_str)
                            # 하나의 시군구는 하나의 시도에만 속하므로 break
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

    @st.cache_data
    def load_map_data():
        """지도 뷰어가 선택되었을 때만 지도 관련 파일들을 로드합니다."""
        try:
            if not df_6.empty and '지역구분' in df_6.columns:
                region_counts = df_6['지역구분'].value_counts().to_dict()
            else:
                region_counts = {}
                st.warning("df_6이 비어있거나 '지역구분' 컬럼이 없습니다.")
            
            merged_geojson, unmatched_df = load_and_process_data(region_counts, 'HangJeongDong_ver20250401.geojson')
            
            return merged_geojson, region_counts, unmatched_df
        except FileNotFoundError as e:
            st.error(f"지도 파일을 찾을 수 없습니다: {e}")
            return None, {}, pd.DataFrame()
        except Exception as e:
            st.error(f"지도 데이터 로드 중 오류: {e}")
            return None, {}, pd.DataFrame()

    def create_korea_map(merged_geojson, map_style, color_scale_name):
        """Plotly를 사용하여 8단계로 구분된 Choropleth 지도를 생성합니다."""
        if not merged_geojson or not merged_geojson['features']:
            return None

        plot_df = pd.DataFrame([f['properties'] for f in merged_geojson['features']])
        
        if not plot_df.empty and plot_df['value'].max() > 0:
            # 9단계 색상 범위 설정 (사용자 요청 범위)
            bins = [-1, 0, 15, 60, 100, 200, 500, 1000, 3000, float('inf')]
            labels = ["0", "1-15", "16-60", "61-100", "101-200", "201-500", "501-1000", "1001-3000", "3001+"]
        else:
            bins = [-1, 0, float('inf')]
            labels = ["0", "1+"]
        
        plot_df['category'] = pd.cut(plot_df['value'], bins=bins, labels=labels, right=True).astype(str)
        
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

    # --- 대한민국 지도 시각화 ---
    st.header("🗺️ 지도 시각화")
    st.markdown("`df_6`의 '지역구분' 데이터를 집계하여 지도에 시각화합니다.")

    with st.spinner("지도 데이터를 로드하고 있습니다..."):
        merged_geojson, region_counts, unmatched_df = load_map_data()
        
        if merged_geojson:
            st.sidebar.header("⚙️ 지도 설정")
            map_styles = {
                "기본 (밝음)": "carto-positron", "기본 (어두움)": "carto-darkmatter", 
                "위성 지도": "satellite-streets", "지형도": "stamen-terrain"
            }
            color_scales = ["Reds","Blues", "Greens", "Viridis", "Cividis", "Inferno"]
            
            selected_style = st.sidebar.selectbox("지도 스타일", list(map_styles.keys()))
            selected_color = st.sidebar.selectbox("색상 스케일", color_scales)
            
            result = create_korea_map(merged_geojson, map_styles[selected_style], selected_color)
            
            if result is not None:
                fig, df = result
                st.plotly_chart(fig, use_container_width=True)
                
                st.sidebar.markdown("---")
                st.sidebar.header("📊 데이터 요약")
                st.sidebar.metric("총 지역 수", len(df))
                st.sidebar.metric("데이터가 있는 지역", len(df[df['value'] > 0]))
                st.sidebar.metric("최대 신청 건수", f"{df['value'].max():,}")
                
                st.subheader("데이터 테이블 (신청 건수 높은 순)")
                st.dataframe(df[['sggnm', 'value']].sort_values('value', ascending=False), use_container_width=True)

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
            st.error("지도 파일을 로드할 수 없습니다.")

# --- 지자체별 정리 ---
if viewer_option == '지자체별 정리':
    st.header("지자체별 현황 정리")
    if df_master.empty or '지역' not in df_master.columns:
        st.warning("지자체 데이터가 없습니다.")
    else:
        region_list = df_master['지역'].dropna().unique().tolist()
        selected_region = st.selectbox("지역 선택", region_list)
        columns_to_show = [
            '현황_일반', '현황_우선',
            'Model 3 RWD_기본', 'Model 3 RWD(2024)_기본',
            'Model 3 LongRange_기본', 'Model 3 Performance_기본',
            'Model Y New RWD_기본', 'Model Y New LongRange_기본'
        ]
        filtered = df_master[df_master['지역'] == selected_region]
        display_columns = [col.replace('_기본', '') for col in columns_to_show]
        display_df = filtered[columns_to_show].copy()
        display_df.columns = display_columns
        st.dataframe(display_df, use_container_width=True)


