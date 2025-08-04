import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import altair as alt
import pickle
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
df_admin_coords = data.get("df_admin_coords", pd.DataFrame())  # 행정구역별 위경도 좌표 데이터
df_fail_q3 = data["df_fail_q3"]
df_2_fail_q3 = data["df_2_fail_q3"]
update_time_str = data["update_time_str"]

# --- 시간대 설정 ---
KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()

# --- 사이드바: 조회 옵션 설정 ---
with st.sidebar:
    st.header("👁️ 뷰어 옵션")
    viewer_option = st.radio("뷰어 유형을 선택하세요.", ('내부', '테슬라', '폴스타'), key="viewer_option")
    st.markdown("---")
    st.header("📊 조회 옵션")
    view_option = st.radio(
        "조회 유형을 선택하세요.",
        ('금일', '특정일 조회', '기간별 조회', '분기별 조회', '월별 조회', '전체 누적'),
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
    elif view_option == '전체 누적':
        min_date_1 = df_1['날짜'].min().date() if not df_1.empty else today_kst
        min_date_5 = df_5['날짜'].min().date() if not df_5.empty else today_kst
        start_date = min(min_date_1, min_date_5)
        end_date = today_kst
        title = "전체 누적 리포트"

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


# --- 대한민국 지도 시각화 ---
st.markdown("---")
st.header("🗺️ 대한민국 지도 시각화")

# 행정구역 좌표 데이터가 있는지 확인
if not df_admin_coords.empty:
    st.success("행정구역별 위경도 좌표 데이터가 로드되었습니다!")
    
    try:
        # 시도 목록 가져오기
        sido_list = ["전체"] + sorted(df_admin_coords['시도'].unique().tolist())
        
        # 지역 선택 UI
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            selected_sido = st.selectbox("시도 선택", sido_list)
        
        with col2:
            # 선택된 시도에 따른 시군구 목록
            if selected_sido and selected_sido != "전체":
                # 시군구 데이터를 문자열로 변환하여 안전하게 정렬
                sigungu_data = df_admin_coords[df_admin_coords['시도'] == selected_sido]['시군구'].unique()
                sigungu_list = ["전체"] + sorted([str(x) for x in sigungu_data if pd.notna(x)])
            else:
                sigungu_list = ["전체"]
            selected_sigungu = st.selectbox("시군구 선택", sigungu_list)
        
        # --- 지도 확대/축소 로직 추가 ---
        zoom_level = 6  # 기본 전국 뷰
        if selected_sido != "전체":
            zoom_level = 8  # 시도 선택 시 확대
        if selected_sigungu != "전체" and selected_sigungu:
            zoom_level = 11 # 시군구 선택 시 더 확대

        # 행정구역 좌표 데이터를 사용한 지도 데이터 생성 (sample_value 제거)
        map_data = create_admin_map_data(df_admin_coords, selected_sido, selected_sigungu)
        
        # 지도 표시 (동적 zoom_level 적용)
        st.subheader("행정구역별 데이터 지도")
        if map_data and map_data['lat']:
            # size 데이터가 있으면 사용, 없으면 기본값 사용
            if 'size' in map_data:
                # size 데이터를 사용하여 지도 표시
                map_df = pd.DataFrame({
                    'lat': map_data['lat'],
                    'lon': map_data['lon'],
                    'size': map_data['size']
                })
                st.map(data=map_df, zoom=zoom_level+2)
            else:
                # 기존 방식으로 지도 표시
                st.map(data=map_data, zoom=zoom_level+2)
        else:
            st.warning("선택한 조건에 맞는 데이터가 없어 지도를 표시할 수 없습니다.")
        
        # 선택된 지역 정보 표시
        if selected_sido != "전체":
            st.info(f"**선택된 시도:** {selected_sido}")
            if selected_sigungu != "전체":
                st.info(f"**선택된 시군구:** {selected_sigungu}")
            st.info(f"**생성된 포인트 수:** {len(map_data['lat'])}")
            
            # size 데이터가 있으면 표시
            if 'size' in map_data and map_data['size']:
                avg_size = sum(map_data['size']) / len(map_data['size'])
                min_size = min(map_data['size'])
                max_size = max(map_data['size'])
                st.info(f"**원 크기 데이터:** 평균 {avg_size:.1f}, 최소 {min_size}, 최대 {max_size}")
        
        # 필터링된 데이터 테이블 표시
        st.subheader("📊 선택된 지역 데이터 현황")
        filtered_data = df_admin_coords.copy()
        if selected_sido != "전체":
            filtered_data = filtered_data[filtered_data['시도'] == selected_sido]
        if selected_sigungu != "전체":
            filtered_data = filtered_data[filtered_data['시군구'].astype(str) == selected_sigungu]
        
        if not filtered_data.empty:
            # size 데이터 추가
            display_data = filtered_data.copy()
            size_list = []
            for i in range(len(display_data)):
                sigungu_name = str(display_data.iloc[i]['시군구'])
                np.random.seed(hash(sigungu_name) % 2**32)
                random_value = np.random.randint(10, 1001)
                size_list.append(random_value)
            display_data['원_크기_데이터'] = size_list
            
            st.dataframe(display_data, use_container_width=True)
            st.info(f"총 {len(filtered_data)}개의 행정구역이 표시됩니다.")
        else:
            st.warning("선택한 조건에 맞는 데이터가 없습니다.")

    except Exception as e:
        st.error(f"지도 데이터 처리 중 오류가 발생했습니다: {e}")
        st.write("**전체 행정구역 데이터:**")
        st.dataframe(df_admin_coords.head(10))

else:
    st.warning("⚠️ 행정구역별 위경도 좌표 데이터가 없습니다.")
    st.info("'전처리.py'를 실행하여 '행정구역별_위경도_좌표.xlsx' 파일을 처리해주세요.")
    
    # 기존 간단한 지도 데이터로 대체
    st.subheader("📍 기본 지도 (임시)")
    korea_map_df = create_korea_map_data()
    
    if not korea_map_df.empty:
        try:
            # 지역 선택 UI
            col1, col2 = st.columns([2, 1])
            with col1:
                selected_region = st.selectbox("지역 선택", ["전체"] + korea_map_df['region'].tolist())
            
            # st.map을 위한 간단한 데이터 생성 (sample_value 제거)
            map_data = create_simple_map_data(selected_region)
            
            # 지도 표시
            st.map(data=map_data, zoom=6)
            
            # 선택된 지역 정보 표시
            if selected_region != "전체":
                selected_data = korea_map_df[korea_map_df['region'] == selected_region]
                st.info(f"**선택된 지역:** {selected_region}")
                st.info(f"**위도:** {selected_data['lat'].values[0]:.4f}")
                st.info(f"**경도:** {selected_data['lon'].values[0]:.4f}")
                st.info(f"**생성된 포인트 수:** {len(map_data['lat'])}")
            
            # 전체 데이터 테이블 표시
            st.subheader("📊 지역별 데이터 현황")
            st.dataframe(korea_map_df, use_container_width=True)

        except Exception as e:
            st.error(f"지도 데이터 처리 중 오류가 발생했습니다: {e}")
            st.write("**전체 지도 데이터:**")
            st.dataframe(korea_map_df)
    else:
        st.warning("지도 데이터를 표시할 수 없습니다. 데이터가 비어있습니다.")




