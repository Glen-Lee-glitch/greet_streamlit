import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import pickle
import sys
from datetime import datetime, timedelta
import pytz
import folium
from streamlit_folium import st_folium
import json
import requests

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
@st.cache_data(ttl=600)
def load_data():
    """전처리된 데이터 파일을 로드합니다."""
    try:
        with open("preprocessed_data.pkl", "rb") as f:
            print('yes')
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
geo_data = get_geojson_data()

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

# --- 대시보드 표시 ---
# col1, col2, col3 = st.columns([3.5,2,1.5])

# with col1:
#     st.write("### 1. 리테일 금일/전일 요약")

#     selected_date = end_date
#     day0 = selected_date
#     day1 = (pd.to_datetime(selected_date) - pd.tseries.offsets.BDay(1)).date()

#     year = selected_date.year
#     q3_start_default = datetime(year, 6, 24).date()
#     q3_start_distribute = datetime(year, 7, 1).date()

#     cnt_today_mail = (df_5['날짜'].dt.date == day0).sum()
#     cnt_yesterday_mail = (df_5['날짜'].dt.date == day1).sum()
#     cnt_total_mail = ((df_5['날짜'].dt.date >= q3_start_default) & (df_5['날짜'].dt.date <= day0)).sum()

#     cnt_today_apply = int(df_1.loc[df_1['날짜'].dt.date == day0, '개수'].sum())
#     cnt_yesterday_apply = int(df_1.loc[df_1['날짜'].dt.date == day1, '개수'].sum())
#     cnt_total_apply = int(df_1.loc[(df_1['날짜'].dt.date >= q3_start_default) & (df_1['날짜'].dt.date <= day0), '개수'].sum())

#     cnt_today_distribute = int(df_2.loc[df_2['날짜'].dt.date == day0, '배분'].sum())
#     cnt_yesterday_distribute = int(df_2.loc[df_2['날짜'].dt.date == day1, '배분'].sum())
#     cnt_total_distribute = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= day0), '배분'].sum())

#     cnt_today_request = int(df_2.loc[df_2['날짜'].dt.date == day0, '신청'].sum())
#     cnt_yesterday_request = int(df_2.loc[df_2['날짜'].dt.date == day1, '신청'].sum())
#     cnt_total_request = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= day0), '신청'].sum())

#     # df_fail_q3, df_2_fail_q3 날짜 타입 보정
#     if not pd.api.types.is_datetime64_any_dtype(df_fail_q3['날짜']):
#         df_fail_q3['날짜'] = pd.to_datetime(df_fail_q3['날짜'], errors='coerce')
#     if not pd.api.types.is_datetime64_any_dtype(df_2_fail_q3['날짜']):
#         df_2_fail_q3['날짜'] = pd.to_datetime(df_2_fail_q3['날짜'], errors='coerce')

#     # 미신청건 계산
#     cnt_yesterday_fail = int((df_fail_q3['날짜'].dt.date == day1).sum())
#     cnt_today_fail = int((df_fail_q3['날짜'].dt.date == day0).sum())
#     cnt_total_fail = int(((df_fail_q3['날짜'].dt.date >= q3_start_default) & (df_fail_q3['날짜'].dt.date <= day0)).sum())

#     # 지급 미신청건 계산
#     cnt_yesterday_fail_2 = int(df_2_fail_q3.loc[df_2_fail_q3['날짜'].dt.date == day1, '미신청건'].sum())
#     cnt_today_fail_2 = int(df_2_fail_q3.loc[df_2_fail_q3['날짜'].dt.date == day0, '미신청건'].sum())
#     cnt_total_fail_2 = int(df_2_fail_q3.loc[(df_2_fail_q3['날짜'].dt.date >= q3_start_default) & (df_2_fail_q3['날짜'].dt.date <= day0), '미신청건'].sum())

#     delta_mail = cnt_today_mail - cnt_yesterday_mail
#     delta_apply = cnt_today_apply - cnt_yesterday_apply
#     delta_fail = cnt_today_fail - cnt_yesterday_fail
#     delta_distribute = cnt_today_distribute - cnt_yesterday_distribute
#     delta_request = cnt_today_request - cnt_yesterday_request
#     delta_fail_2 = cnt_today_fail_2 - cnt_yesterday_fail_2

#     def format_delta(value):
#         if value > 0: return f'<span style="color:blue;">+{value}</span>'
#         elif value < 0: return f'<span style="color:red;">{value}</span>'
#         return str(value)

#     table_data = pd.DataFrame({
#         ('지원', '파이프라인', '메일 건수'): [cnt_yesterday_mail, cnt_today_mail, cnt_total_mail],
#         ('지원', '신청', '신청 건수'): [cnt_yesterday_apply, cnt_today_apply, cnt_total_apply],
#         ('지원', '신청', '미신청건'): [cnt_yesterday_fail, cnt_today_fail, cnt_total_fail],
#         ('지급', '지급 처리', '지급 배분건'): [cnt_yesterday_distribute, cnt_today_distribute, cnt_total_distribute],
#         ('지급', '지급 처리', '지급신청 건수'): [cnt_yesterday_request, cnt_today_request, cnt_total_request],
#         ('지급', '지급 처리', '미신청건'): [cnt_yesterday_fail_2, cnt_today_fail_2, cnt_total_fail_2]
#     }, index=[f'전일 ({day1})', f'금일 ({day0})', '누적 총계 (3분기)'])

#     # 변동(Delta) 행 추가
#     table_data.loc['변동'] = [
#         format_delta(delta_mail),
#         format_delta(delta_apply),
#         format_delta(delta_fail),
#         format_delta(delta_distribute),
#         format_delta(delta_request),
#         format_delta(delta_fail_2)
#     ]
#     html_table = table_data.to_html(classes='custom_table', border=0, escape=False)
#     st.markdown(html_table, unsafe_allow_html=True)

#     # 구분선 이동에 따라 제거

#     st.markdown("<hr style='margin-top:1rem;margin-bottom:1rem;'>", unsafe_allow_html=True)
#     # ----- 리테일 월별 요약 헤더 및 기간 선택 -----
#     header_col, sel_col = st.columns([4,2])
#     with header_col:
#         st.write("##### 리테일 월별 요약")
#     with sel_col:
#         period_option = st.selectbox(
#             '기간 선택',
#             ['3Q', '7월', '전체', '1Q', '2Q'] + [f'{m}월' for m in range(1,13)],
#             index=0,
#             key='retail_period')
#     year = today_kst.year
#     july_start = datetime(year, 7, 1).date()
#     july_end = datetime(year, 7, 31).date()
#     august_start = datetime(year, 8, 1).date()
#     august_end = datetime(year, 8, 31).date()

#     july_mail_count = int(df_5[(df_5['날짜'].dt.date >= q3_start_default) & (df_5['날짜'].dt.date <= july_end)].shape[0]) if july_end >= q3_start_default else 0
#     july_apply_count = int(df_1.loc[(df_1['날짜'].dt.date >= q3_start_default) & (df_1['날짜'].dt.date <= july_end), '개수'].sum()) if july_end >= q3_start_default else 0
#     july_distribute_count = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= july_end), '배분'].sum()) if july_end >= q3_start_distribute else 0

#     mask_august_5 = (df_5['날짜'].dt.date >= august_start) & (df_5['날짜'].dt.date <= august_end)
#     mask_august_1 = (df_1['날짜'].dt.date >= august_start) & (df_1['날짜'].dt.date <= august_end)
#     mask_august_2 = (df_2['날짜'].dt.date >= august_start) & (df_2['날짜'].dt.date <= august_end)
#     august_mail_count = int(df_5.loc[mask_august_5].shape[0])
#     august_apply_count = int(df_1.loc[mask_august_1, '개수'].sum())
#     august_distribute_count = int(df_2.loc[mask_august_2, '배분'].sum())

#     # ----- 기간별 필터링 -----
#     def filter_by_period(df):
#         if period_option == '3Q' or period_option in ('3분기'):
#             return df[df['분기'] == '3분기']
#         if period_option == '2Q' or period_option in ('2분기'):
#             return df[df['분기'] == '2분기']
#         if period_option == '1Q' or period_option in ('1분기'):
#             return df[df['분기'] == '1분기']
#         if period_option.endswith('월'):
#             try:
#                 month_num = int(period_option[:-1])
#                 return df[df['날짜'].dt.month == month_num]
#             except ValueError:
#                 return df
#         return df

    
#     # --- 월별/분기별 요약 계산 ---
#     current_year = day0.year
#     # 날짜 변수 정의
#     june_23 = datetime(current_year, 6, 23).date()
#     june_24 = datetime(current_year, 6, 24).date()
#     july_1 = datetime(current_year, 7, 1).date()
#     july_31 = datetime(current_year, 7, 31).date()
#     august_1 = datetime(current_year, 8, 1).date()
#     september_1 = datetime(current_year, 9, 1).date()

#     retail_df = pd.DataFrame() # 초기화

#     # --- 이미지 형태의 월별 요약 표 생성 ---
#     if period_option == '전체':
#         # (1Q, 2Q 계산 로직은 기존과 동일)
#         q1_total_mail = int(df_5[df_5['날짜'].dt.month.isin([1,2,3])].shape[0])
#         q1_total_apply = int(df_1[df_1['날짜'].dt.month.isin([1,2,3])]['개수'].sum())
#         q1_total_distribute = int(df_2[df_2['날짜'].dt.month.isin([1,2,3])]['배분'].sum())
#         q2_total_mail = int(df_5[df_5['날짜'].dt.month.isin([4,5,6])].shape[0])
#         q2_apply_mask = (df_1['날짜'].dt.month.isin([4,5])) | ((df_1['날짜'].dt.month == 6) & (df_1['날짜'].dt.date <= june_23))
#         q2_total_apply = int(df_1[q2_apply_mask]['개수'].sum())
#         q2_total_distribute = int(df_2[df_2['날짜'].dt.month.isin([4,5,6])]['배분'].sum())
        
#         # --- 3Q 데이터 계산 (수정된 로직) ---
#         july_mail_total = int(df_5[(df_5['날짜'].dt.date >= june_24) & (df_5['날짜'].dt.date <= july_31)].shape[0])
#         july_apply_total = int(df_1[(df_1['날짜'].dt.date >= june_24) & (df_1['날짜'].dt.date <= july_31)]['개수'].sum())
#         july_distribute_total = int(df_2[(df_2['날짜'].dt.date >= july_1) & (df_2['날짜'].dt.date <= july_31)]['배분'].sum())

#         august_cumulative_mail = int(df_5[(df_5['날짜'].dt.date >= august_1) & (df_5['날짜'].dt.date <= day0)].shape[0])
#         august_cumulative_apply = int(df_1[(df_1['날짜'].dt.date >= august_1) & (df_1['날짜'].dt.date <= day0)]['개수'].sum())
#         august_cumulative_distribute = int(df_2[(df_2['날짜'].dt.date >= august_1) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())
        
#         september_cumulative_mail = int(df_5[(df_5['날짜'].dt.date >= september_1) & (df_5['날짜'].dt.date <= day0)].shape[0])
#         september_cumulative_apply = int(df_1[(df_1['날짜'].dt.date >= september_1) & (df_1['날짜'].dt.date <= day0)]['개수'].sum())
#         september_cumulative_distribute = int(df_2[(df_2['날짜'].dt.date >= september_1) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())

#         q3_total_mail = july_mail_total + august_cumulative_mail + september_cumulative_mail
#         q3_total_apply = july_apply_total + august_cumulative_apply + september_cumulative_apply
#         q3_total_distribute = july_distribute_total + august_cumulative_distribute + september_cumulative_distribute

#         q1_target, q2_target, q3_target = 4300, 10000, 10000
#         q1_progress = q1_total_mail / q1_target if q1_target > 0 else 0
#         q2_progress = q2_total_mail / q2_target if q2_target > 0 else 0
#         q3_progress = q3_total_mail / q3_target if q3_target > 0 else 0

#         retail_df_data = {
#             'Q1': [q1_target, q1_total_mail, q1_total_apply, f"{q1_progress:.1%}", '', q1_total_distribute],
#             'Q2': [q2_target, q2_total_mail, q2_total_apply, f"{q2_progress:.1%}", '', q2_total_distribute],
#             'Q3': [q3_target, q3_total_mail, q3_total_apply, f"{q3_progress:.1%}", '', q3_total_distribute]
#         }
#         retail_index = ['타겟', '파이프라인', '지원신청완료', '진척률', '취소', '지급신청']
#         retail_df = pd.DataFrame(retail_df_data, index=retail_index)
#     elif period_option == '1Q' or period_option == '1분기':
#         # Q1 데이터 계산 (1, 2, 3월)
#         q1_monthly_data = {}
#         for month in [1, 2, 3]:
#             month_mail = int(df_5[df_5['날짜'].dt.month == month].shape[0])
#             month_apply = int(df_1[df_1['날짜'].dt.month == month]['개수'].sum())
#             month_distribute = int(df_2[df_2['날짜'].dt.month == month]['배분'].sum())
#             q1_monthly_data[f'{month}'] = [month_mail, month_apply, month_distribute]
        
#         # Q1 합계 계산
#         q1_total_mail = sum(q1_monthly_data[f'{m}'][0] for m in [1, 2, 3])
#         q1_total_apply = sum(q1_monthly_data[f'{m}'][1] for m in [1, 2, 3])
#         q1_total_distribute = sum(q1_monthly_data[f'{m}'][2] for m in [1, 2, 3])
        
#         # 타겟 설정
#         q1_target = 4300
        
#         # 진척률 계산
#         q1_progress_rate = q1_total_mail / q1_target if q1_target > 0 else 0
        
#         # 데이터프레임 생성
#         retail_df_data = {
#             '1': [q1_target, q1_monthly_data['1'][0], q1_monthly_data['1'][1], f"{q1_progress_rate:.1%}", '', q1_monthly_data['1'][2]],
#             '2': ['', q1_monthly_data['2'][0], q1_monthly_data['2'][1], '', '', q1_monthly_data['2'][2]],
#             '3': ['', q1_monthly_data['3'][0], q1_monthly_data['3'][1], '', '', q1_monthly_data['3'][2]],
#             '계': [q1_target, q1_total_mail, q1_total_apply, f"{q1_progress_rate:.1%}", '', q1_total_distribute]
#         }
#         retail_index = ['타겟', '파이프라인', '지원신청완료', '진척률', '취소', '지급신청']
#         retail_df = pd.DataFrame(retail_df_data, index=retail_index)
#     elif period_option == '2Q' or period_option == '2분기':
#         # Q2 데이터 계산 (4, 5, 6월) - 6월은 6월 23일까지
#         q2_monthly_data = {}
        
#         # 6월 23일 날짜 객체 생성 (현재 연도 기준)
#         current_year = datetime.now().year
#         june_23 = datetime(current_year, 6, 23).date()
        
#         for month in [4, 5, 6]:
#             month_mail = int(df_5[df_5['날짜'].dt.month == month].shape[0])
            
#             # 6월의 경우 6월 23일까지의 데이터만 포함
#             if month == 6:
#                 month_apply = int(df_1[
#                     (df_1['날짜'].dt.month == 6) & 
#                     (df_1['날짜'].dt.date <= june_23)
#                 ]['개수'].sum())
#             else:
#                 month_apply = int(df_1[df_1['날짜'].dt.month == month]['개수'].sum())
            
#             month_distribute = int(df_2[df_2['날짜'].dt.month == month]['배분'].sum())
#             q2_monthly_data[f'{month}'] = [month_mail, month_apply, month_distribute]
        
#         # Q2 합계 계산
#         q2_total_mail = sum(q2_monthly_data[f'{m}'][0] for m in [4, 5, 6])
#         q2_total_apply = sum(q2_monthly_data[f'{m}'][1] for m in [4, 5, 6])
#         q2_total_distribute = sum(q2_monthly_data[f'{m}'][2] for m in [4, 5, 6])
        
#         # 타겟 설정
#         q2_target = 10000
        
#         # 진척률 계산
#         q2_progress_rate = q2_total_mail / q2_target if q2_target > 0 else 0
        
#         # 데이터프레임 생성
#         retail_df_data = {
#             '4': [q2_target, q2_monthly_data['4'][0], q2_monthly_data['4'][1], f"{q2_progress_rate:.1%}", '', q2_monthly_data['4'][2]],
#             '5': ['', q2_monthly_data['5'][0], q2_monthly_data['5'][1], '', '', q2_monthly_data['5'][2]],
#             '6': ['', q2_monthly_data['6'][0], q2_monthly_data['6'][1], '', '', q2_monthly_data['6'][2]],
#             '계': [q2_target, q2_total_mail, q2_total_apply, f"{q2_progress_rate:.1%}", '', q2_total_distribute]
#         }
#         retail_index = ['타겟', '파이프라인', '지원신청완료', '진척률', '취소', '지급신청']
#         retail_df = pd.DataFrame(retail_df_data, index=retail_index)
#     elif period_option in ('3Q', '3분기'):
#         # --- 3Q 월별 데이터 계산 (수정된 로직) ---
#         q3_monthly_data = {}
        
#         # 7월 데이터 (전체 월)
#         q3_monthly_data['7'] = [
#             int(df_5[(df_5['날짜'].dt.date >= june_24) & (df_5['날짜'].dt.date <= july_31)].shape[0]),
#             int(df_1[(df_1['날짜'].dt.date >= june_24) & (df_1['날짜'].dt.date <= july_31)]['개수'].sum()),
#             int(df_2[(df_2['날짜'].dt.date >= july_1) & (df_2['날짜'].dt.date <= july_31)]['배분'].sum())
#         ]
#         # 8월 데이터 (월초 ~ 현재)
#         q3_monthly_data['8'] = [
#             int(df_5[(df_5['날짜'].dt.date >= august_1) & (df_5['날짜'].dt.date <= day0)].shape[0]),
#             int(df_1[(df_1['날짜'].dt.date >= august_1) & (df_1['날짜'].dt.date <= day0)]['개수'].sum()),
#             int(df_2[(df_2['날짜'].dt.date >= august_1) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())
#         ]
#         # 9월 데이터 (월초 ~ 현재)
#         q3_monthly_data['9'] = [
#             int(df_5[(df_5['날짜'].dt.date >= september_1) & (df_5['날짜'].dt.date <= day0)].shape[0]),
#             int(df_1[(df_1['날짜'].dt.date >= september_1) & (df_1['날짜'].dt.date <= day0)]['개수'].sum()),
#             int(df_2[(df_2['날짜'].dt.date >= september_1) & (df_2['날짜'].dt.date <= day0)]['배분'].sum())
#         ]
        
#         q3_total_mail = sum(q3_monthly_data[m][0] for m in ['7', '8', '9'])
#         q3_total_apply = sum(q3_monthly_data[m][1] for m in ['7', '8', '9'])
#         q3_total_distribute = sum(q3_monthly_data[m][2] for m in ['7', '8', '9'])
        
#         q3_target = 10000
#         q3_progress = q3_total_mail / q3_target if q3_target > 0 else 0
        
#         retail_df_data = {
#             '7': [q3_target, q3_monthly_data['7'][0], q3_monthly_data['7'][1], f"{q3_progress:.1%}", '', q3_monthly_data['7'][2]],
#             '8': ['', q3_monthly_data['8'][0], q3_monthly_data['8'][1], '', '', q3_monthly_data['8'][2]],
#             '9': ['', q3_monthly_data['9'][0], q3_monthly_data['9'][1], '', '', q3_monthly_data['9'][2]],
#             '계': [q3_target, q3_total_mail, q3_total_apply, f"{q3_progress:.1%}", '', q3_total_distribute]
#         }
#         retail_index = ['타겟', '파이프라인', '지원신청완료', '진척률', '취소', '지급신청']
#         retail_df = pd.DataFrame(retail_df_data, index=retail_index)

#     else:
#         # 기존 로직 유지 (다른 기간 선택 시)
#         df5_p = filter_by_period(df_5)
#         df1_p = filter_by_period(df_1)
#         df2_p = filter_by_period(df_2)
#         mail_total = int(df5_p.shape[0])
#         apply_total = int(df1_p['개수'].sum())
#         distribute_total = int(df2_p['배분'].sum())
#         retail_df_data = {period_option: [mail_total, apply_total, distribute_total]}
#         retail_index = ['파이프라인', '신청', '지급신청']
#         retail_df = pd.DataFrame(retail_df_data, index=retail_index)

#     # --- HTML 변환 및 스타일링 ---
#     html_retail = retail_df.to_html(classes='custom_table', border=0, escape=False)
    
#     # 이미지 형태에 맞는 스타일링 적용
#     if period_option in ['전체', '1Q', '1분기', '2Q', '2분기', '3Q', '3분기']:
#         # 타겟 값들에 배경색 적용
#         target_values = ['4300', '10000']
#         for target in target_values:
#             html_retail = html_retail.replace(f'<td>{target}</td>', f'<td style="background-color: #f0f0f0;">{target}</td>')
        
#         # 진척률 셀 하이라이트 (모든 진척률 값에 대해)
#         import re
#         html_retail = re.sub(
#             r'<td>(\d+\.\d+)%</td>',
#             r'<td style="background-color: #e0f7fa;">\1%</td>',
#             html_retail
#         )
        
#         # 빈 셀들을 공백으로 표시
#         html_retail = html_retail.replace('<td></td>', '<td style="background-color: #fafafa;">&nbsp;</td>')
        
#         # '전체' 선택 시 Q1, Q2, Q3 컬럼 헤더 하이라이트
#         if period_option == '전체':
#             html_retail = re.sub(
#                 r'(<th[^>]*>Q1</th>)',
#                 r'<th style="background-color: #ffe0b2;">Q1</th>',
#                 html_retail
#             )
#             html_retail = re.sub(
#                 r'(<th[^>]*>Q2</th>)',
#                 r'<th style="background-color: #ffe0b2;">Q2</th>',
#                 html_retail
#             )
#             html_retail = re.sub(
#                 r'(<th[^>]*>Q3</th>)',
#                 r'<th style="background-color: #ffe0b2;">Q3</th>',
#                 html_retail
#             )
#         else:
#             # "계" 컬럼 하이라이트 (개별 분기 선택 시)
#             html_retail = re.sub(
#                 r'(<th[^>]*>계</th>)',
#                 r'<th style="background-color: #ffe0b2;">계</th>',
#                 html_retail
#             )
            
#             # "계" 행의 데이터 셀들도 하이라이트
#             html_retail = re.sub(
#                 r'(<tr>\s*<th>계</th>)(.*?)(</tr>)',
#                 lambda m: m.group(1) + re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', m.group(2)) + m.group(3),
#                 html_retail,
#                 flags=re.DOTALL
#             )
            
#             # '타겟'과 '진척률' 행을 병합된 셀로 표시 (월별 컬럼 + 계 컬럼까지 전체 병합)
#             # 타겟 행 병합 (월별 3개 컬럼 + 계 컬럼까지 총 4개 컬럼 병합)
#             html_retail = re.sub(
#                 r'(<tr>\s*<th>타겟</th>)(.*?)(</tr>)',
#                 lambda m: m.group(1) + 
#                          re.sub(r'<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>', 
#                                 r'<td\1 colspan="4">\2</td>', m.group(2), count=1) + 
#                          m.group(3),
#                 html_retail,
#                 flags=re.DOTALL
#             )
            
#             # 진척률 행 병합 (월별 3개 컬럼 + 계 컬럼까지 총 4개 컬럼 병합)
#             html_retail = re.sub(
#                 r'(<tr>\s*<th>진척률</th>)(.*?)(</tr>)',
#                 lambda m: m.group(1) + 
#                          re.sub(r'<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>\s*<td([^>]*)>([^<]*)</td>', 
#                                 r'<td\1 colspan="4">\2</td>', m.group(2), count=1) + 
#                          m.group(3),
#                 html_retail,
#                 flags=re.DOTALL
#             )

#     st.markdown(html_retail, unsafe_allow_html=True)

#     # --- 리테일 월별 추이 그래프 ---
#     if viewer_option == '내부':
#         # --- months_to_show 결정 ---
#         def get_end_month(option):
#             if option.endswith('월'):
#                 try:
#                     return int(option[:-1])
#                 except ValueError:
#                     pass
#             if option in ('1Q', '1분기'): return 3
#             if option in ('2Q', '2분기'): return 6
#             if option in ('3Q', '3분기'): return 9
#             return selected_date.month
#         end_month = get_end_month(period_option)
#         # 현재 날짜가 15일 이전이면 해당 월 데이터 제외
#         if selected_date.day < 15 and end_month == selected_date.month:
#             end_month -= 1
#             # 1월인 경우 0이 되지 않도록 방어
#             if end_month == 0:
#                 end_month = 12
#         start_month = 2
#         months_to_show = list(range(start_month, end_month + 1))
#         # 15일 이전이면 해당 월을 제외 (3Q 포함 모든 경우에 적용)
#         if selected_date.day < 15:
#             months_to_show = [m for m in months_to_show if m < selected_date.month]
#         if months_to_show:
#             # 월별 파이프라인(메일) 건수 집계
#             df_5_monthly = df_5[
#                 (df_5['날짜'].dt.year == selected_date.year) &
#                 (df_5['날짜'].dt.month.isin(months_to_show))
#             ]
#             pipeline_counts = df_5_monthly.groupby(df_5_monthly['날짜'].dt.month).size()

#             # 차트용 데이터프레임 생성
#             chart_df = pd.DataFrame(
#                 {
#                     '월': months_to_show,
#                     '파이프라인 건수': [int(pipeline_counts.get(m, 0)) for m in months_to_show]
#                 }
#             )
#             chart_df['월 라벨'] = chart_df['월'].astype(str) + '월'

#             # 막대 그래프 (파이프라인)
#             bar = alt.Chart(chart_df).mark_bar(size=25, color='#2ca02c').encode(
#                 x=alt.X('월 라벨:N', title='월', sort=[f"{m}월" for m in months_to_show], axis=alt.Axis(labelAngle=0)),
#                 y=alt.Y('파이프라인 건수:Q', title='건수')
#             )

#             # 선 그래프 + 포인트
#             line = alt.Chart(chart_df).mark_line(color='#FF5733', strokeWidth=2).encode(
#                 x='월 라벨:N',
#                 y='파이프라인 건수:Q'
#             )
#             point = alt.Chart(chart_df).mark_point(color='#FF5733', size=60).encode(
#                 x='월 라벨:N',
#                 y='파이프라인 건수:Q'
#             )

#             # 값 레이블 텍스트
#             text = alt.Chart(chart_df).mark_text(dy=-10, color='black').encode(
#                 x='월 라벨:N',
#                 y='파이프라인 건수:Q',
#                 text=alt.Text('파이프라인 건수:Q')
#             )

#             combo_chart = (bar + line + point + text).properties(
#                 title=f"{selected_date.year}년 월별 파이프라인 추이 ({start_month}월~{end_month}월)"
#             )
#             st.altair_chart(combo_chart, use_container_width=True)



# 테스트 지자체별 정리 페이지
# --- 대한민국 지도 시각화 ---
st.markdown("---")
st.header("🗺️ 대한민국 지도 시각화")

if geo_data:
    # 1. 지역 선택을 위한 데이터 준비
    provinces = sorted(list(set(feat['properties']['name_1'] for feat in geo_data['features'])))
    districts_by_province = {prov: sorted(list(set(
        feat['properties']['name'] for feat in geo_data['features'] if feat['properties']['name_1'] == prov
    ))) for prov in provinces}

    # 2. 지역 선택 UI
    col1, col2 = st.columns(2)
    with col1:
        selected_province = st.selectbox("시/도 선택", ["전체"] + provinces)
    with col2:
        if selected_province == "전체":
            selected_district = st.selectbox("시/군/구 선택", ["전체"])
        else:
            selected_district = st.selectbox("시/군/구 선택", ["전체"] + districts_by_province[selected_province])

    # 3. 지도 생성
    # 지도 중심 및 확대/축소 수준 설정
    map_center = [36.5, 127.5]
    zoom_level = 7

    # 선택된 지역에 따라 지도 중심 및 확대/축소 수준 동적 변경
    if selected_province != "전체":
        zoom_level = 9
        # 선택된 시/도의 평균 위도/경도 계산
        province_coords = [
            feat['geometry']['coordinates'] for feat in geo_data['features']
            if feat['properties']['name_1'] == selected_province
        ]
        # 간단한 중심점 계산 (실제 중심과는 다를 수 있음)
        all_lons = [lon for poly in province_coords for part in poly for point in part for lon in [point[0]]]
        all_lats = [lat for poly in province_coords for part in poly for point in part for lat in [point[1]]]
        if all_lons and all_lats:
            map_center = [np.mean(all_lats), np.mean(all_lons)]


    if selected_district != "전체":
        zoom_level = 11
        district_coords = [
            feat['geometry']['coordinates'] for feat in geo_data['features']
            if feat['properties']['name'] == selected_district
        ]
        all_lons = [lon for poly in district_coords for part in poly for point in part for lon in [point[0]]]
        all_lats = [lat for poly in district_coords for part in poly for point in part for lat in [point[1]]]
        if all_lons and all_lats:
            map_center = [np.mean(all_lats), np.mean(all_lons)]


    m = folium.Map(location=map_center, zoom_start=zoom_level, tiles="CartoDB positron")

    # 4. GeoJSON 레이어 스타일링 함수
    def style_function(feature):
        style = {'fillOpacity': 0.5, 'weight': 1, 'color': 'gray', 'fillColor': '#d3d3d3'}
        # 선택된 시/도 강조
        if selected_province != "전체" and feature['properties']['name_1'] == selected_province:
            style['fillColor'] = 'dodgerblue'
            style['color'] = 'blue'
            style['weight'] = 2
        # 선택된 시/군/구 강조
        if selected_district != "전체" and feature['properties']['name'] == selected_district:
            style['fillColor'] = 'crimson'
            style['color'] = 'red'
            style['weight'] = 3
        return style

    # 5. GeoJSON 레이어 추가
    folium.GeoJson(
        geo_data,
        name='korea_municipalities',
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(fields=['name_1', 'name'], aliases=['시/도:', '시/군/구:'])
    ).add_to(m)

    # 6. 지도 출력
    st_folium(m, width='100%', height=500)

else:
    st.warning("지도 데이터를 표시할 수 없습니다. 인터넷 연결을 확인하거나 나중에 다시 시도해주세요.")




