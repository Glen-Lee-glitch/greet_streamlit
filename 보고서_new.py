import streamlit as st
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
    /* 인쇄 시 불필요한 UI 숨기기 */
    @media print {
        .no-print {
            display: none !important;
        }
        .main .block-container {
            padding: 1rem;
        }
    }
    /* 사이드바 스타일 */
    .css-1d391kg {
        padding-top: 3rem;
    }
</style>
""", unsafe_allow_html=True)


# --- 데이터 및 메모 로딩 함수 ---
@st.cache_data(ttl=600)
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

# --- 데이터 로딩 ---
data = load_data()
df = data["df"]
df_1 = data["df_1"]
df_2 = data["df_2"]
df_3 = data["df_3"]
df_4 = data["df_4"]
df_5 = data["df_5"]
update_time_str = data["update_time_str"]

# --- 시간대 설정 ---
KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()

# --- 사이드바: 조회 옵션 설정 ---
with st.sidebar:
    st.header("📊 조회 옵션")
    view_option = st.radio(
        "조회 유형을 선택하세요.",
        ('오늘 실적', '특정일 조회', '기간별 조회', '분기별 조회', '월별 조회', '전체 누적'),
        key="view_option"
    )

    start_date, end_date = None, None
    title = f"{view_option} 리포트"

    if view_option == '오늘 실적':
        start_date = end_date = today_kst
    elif view_option == '특정일 조회':
        selected_date = st.date_input('날짜 선택', value=today_kst)
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
        # 데이터의 가장 빠른 날짜를 시작일로 설정
        min_date_1 = df_1['날짜'].min().date()
        min_date_5 = df_5['날짜'].min().date()
        start_date = min(min_date_1, min_date_5)
        end_date = today_kst
        title = "전체 누적 리포트"

    st.markdown("---")
    # 메모 기능
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

# --- 계산 함수 ---
def get_retail_metrics(df1, df2, df5, start, end):
    """기간 내 리테일팀 실적을 계산합니다."""
    mask1 = (df1['날짜'].dt.date >= start) & (df1['날짜'].dt.date <= end)
    mask2 = (df2['날짜'].dt.date >= start) & (df2['날짜'].dt.date <= end)
    mask5 = (df5['날짜'].dt.date >= start) & (df5['날짜'].dt.date <= end)

    metrics = {
        'mail': int(df5.loc[mask5].shape[0]),
        'apply': int(df1.loc[mask1, '개수'].sum()),
        'distribute': int(df2.loc[mask2, '배분'].sum()),
        'request': int(df2.loc[mask2, '신청'].sum())
    }
    return metrics

def get_corporate_metrics(df3_raw, df4_raw, start, end):
    """기간 내 법인팀 실적을 계산합니다."""
    # 지원 (파이프라인, 지원신청)
    pipeline, apply = 0, 0
    df3 = df3_raw.copy()
    date_col_3 = '신청 요청일'
    if not pd.api.types.is_datetime64_any_dtype(df3[date_col_3]):
        df3[date_col_3] = pd.to_datetime(df3[date_col_3], errors='coerce')
    
    mask3 = (df3[date_col_3].dt.date >= start) & (df3[date_col_3].dt.date <= end)
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

    # 지급 (지급신청)
    distribute = 0
    df4 = df4_raw.copy()
    date_col_4 = '요청일자'
    if not pd.api.types.is_datetime64_any_dtype(df4[date_col_4]):
        df4[date_col_4] = pd.to_datetime(df4[date_col_4], errors='coerce')

    mask4 = (df4[date_col_4].dt.date >= start) & (df4[date_col_4].dt.date <= end)
    df4_period = df4.loc[mask4]
    
    df4_period = df4_period[df4_period['지급신청 완료 여부'].astype(str).str.strip() == '완료']
    unique_df4_period = df4_period.drop_duplicates(subset=['신청번호'])

    mask_bulk_4 = unique_df4_period['접수대수'] > 1
    mask_single_4 = unique_df4_period['접수대수'] == 1
    distribute = int(mask_bulk_4.sum() + unique_df4_period.loc[mask_single_4, '접수대수'].sum())

    return {'pipeline': pipeline, 'apply': apply, 'distribute': distribute}


# --- 실적 계산 ---
retail_metrics = get_retail_metrics(df_1, df_2, df_5, start_date, end_date)
corporate_metrics = get_corporate_metrics(df_3, df_4, start_date, end_date)

# --- 대시보드 표시 ---
col1, col2 = st.columns(2)

with col1:
    st.write("### 1. 리테일 금일/전일 요약")

    # 기준일 및 전일 계산
    selected_date = end_date
    day0 = selected_date
    day1 = (pd.to_datetime(selected_date) - pd.tseries.offsets.BDay(1)).date()

    # --- 3분기 시작일 설정 ---
    year = selected_date.year
    q3_start_default = datetime(year, 6, 24).date()     # 파이프라인/신청 시작일
    q3_start_distribute = datetime(year, 7, 1).date()   # 지급/요청 시작일

    # --- 메일 건수 ---
    cnt_today_mail = (df_5['날짜'].dt.date == day0).sum()
    cnt_yesterday_mail = (df_5['날짜'].dt.date == day1).sum()
    cnt_total_mail = ((df_5['날짜'].dt.date >= q3_start_default) & (df_5['날짜'].dt.date <= day0)).sum()

    # --- 신청 건수 ---
    cnt_today_apply = int(df_1.loc[df_1['날짜'].dt.date == day0, '개수'].sum())
    cnt_yesterday_apply = int(df_1.loc[df_1['날짜'].dt.date == day1, '개수'].sum())
    cnt_total_apply = int(df_1.loc[(df_1['날짜'].dt.date >= q3_start_default) & (df_1['날짜'].dt.date <= day0), '개수'].sum())

    # --- 지급/요청 건수 ---
    cnt_today_distribute = int(df_2.loc[df_2['날짜'].dt.date == day0, '배분'].sum())
    cnt_yesterday_distribute = int(df_2.loc[df_2['날짜'].dt.date == day1, '배분'].sum())
    cnt_total_distribute = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= day0), '배분'].sum())

    cnt_today_request = int(df_2.loc[df_2['날짜'].dt.date == day0, '신청'].sum())
    cnt_yesterday_request = int(df_2.loc[df_2['날짜'].dt.date == day1, '신청'].sum())
    cnt_total_request = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= day0), '신청'].sum())

    # --- 변동 값 계산 ---
    delta_mail = cnt_today_mail - cnt_yesterday_mail
    delta_apply = cnt_today_apply - cnt_yesterday_apply
    delta_distribute = cnt_today_distribute - cnt_yesterday_distribute
    delta_request = cnt_today_request - cnt_yesterday_request

    def format_delta(value):
        if value > 0:
            return f'<span style="color:blue;">+{value}</span>'
        elif value < 0:
            return f'<span style="color:red;">{value}</span>'
        return str(value)

    table_data = pd.DataFrame({
        ('지원', '파이프라인', '메일 건수'): [cnt_yesterday_mail, cnt_today_mail, cnt_total_mail],
        ('지원', '신청완료', '신청 건수'): [cnt_yesterday_apply, cnt_today_apply, cnt_total_apply],
        ('지급', '지급 처리', '지급 배분건'): [cnt_yesterday_distribute, cnt_today_distribute, cnt_total_distribute],
        ('지급', '지급 처리', '지급신청 건수'): [cnt_yesterday_request, cnt_today_request, cnt_total_request]
    }, index=[f'전일 ({day1})', f'금일 ({day0})', '누적 총계 (3분기)'])

    table_data.loc['변동'] = [
        format_delta(delta_mail),
        format_delta(delta_apply),
        format_delta(delta_distribute),
        format_delta(delta_request)
    ]

    html_table = table_data.to_html(classes='custom_table', border=0, escape=False)
    header_tooltips = {
        '메일 건수': '금일 지원신청 요청 메일 수신 건수',
        '신청 건수': '실제로 신청한 건수',
        '지급 배분건': '지급 신청 필요 건수',
        '지급신청 건수': '지급 신청 완료 건수'
    }
    for header, tooltip in header_tooltips.items():
        html_table = html_table.replace(f'<th>{header}</th>', f'<th title="{tooltip}">{header}</th>')

    st.markdown(html_table, unsafe_allow_html=True)

    st.write("------")  # 구분선

    # --- 리테일 월별 요약 ---
    st.write("##### 리테일 월별 요약")
    year = selected_date.year

    # 기간 정의
    q3_start_default = datetime(year, 6, 24).date()     # 파이프라인/신청 시작일
    q3_start_distribute = datetime(year, 7, 1).date()   # 지급 시작일
    july_end = min(selected_date, datetime(year, 7, 31).date())

    august_start = datetime(year, 8, 1).date()
    august_end = selected_date

    # --- 7월 건수 계산 ---
    july_mail_count = int(df_5[(df_5['날짜'].dt.date >= q3_start_default) & (df_5['날짜'].dt.date <= july_end)].shape[0]) if july_end >= q3_start_default else 0
    july_apply_count = int(df_1.loc[(df_1['날짜'].dt.date >= q3_start_default) & (df_1['날짜'].dt.date <= july_end), '개수'].sum()) if july_end >= q3_start_default else 0
    july_distribute_count = int(df_2.loc[(df_2['날짜'].dt.date >= q3_start_distribute) & (df_2['날짜'].dt.date <= july_end), '배분'].sum()) if july_end >= q3_start_distribute else 0

    # --- 8월 건수 계산 ---
    august_mail_count = 0
    august_apply_count = 0
    august_distribute_count = 0
    if selected_date >= august_start:
        mask_august_5 = (df_5['날짜'].dt.date >= august_start) & (df_5['날짜'].dt.date <= august_end)
        mask_august_1 = (df_1['날짜'].dt.date >= august_start) & (df_1['날짜'].dt.date <= august_end)
        mask_august_2 = (df_2['날짜'].dt.date >= august_start) & (df_2['날짜'].dt.date <= august_end)

        august_mail_count = int(df_5.loc[mask_august_5].shape[0])
        august_apply_count = int(df_1.loc[mask_august_1, '개수'].sum())
        august_distribute_count = int(df_2.loc[mask_august_2, '배분'].sum())

    retail_df_data = {
        'Q1': [4436, 4230, 4214],
        'Q2': [9199, 9212, 8946],
        '7월': [july_mail_count, july_apply_count, july_distribute_count],
        '8월': [august_mail_count, august_apply_count, august_distribute_count]
    }
    retail_df = pd.DataFrame(retail_df_data, index=['파이프라인', '신청완료', '지급신청'])
    retail_df['TTL'] = retail_df['7월'] + retail_df['8월']

    q3_target = 10000
    progress_rate = july_mail_count / q3_target if q3_target > 0 else 0
    formatted_progress = f"{progress_rate:.2%}"
    retail_df['Q3 Target'] = [q3_target, '진척률', formatted_progress]

    html_retail = retail_df.to_html(classes='custom_table', border=0, escape=False)
    html_retail = html_retail.replace(
        '<td>진척률</td>',
        '<td style="background-color: #e0f7fa;">진척률</td>'
    )
    st.markdown(html_retail, unsafe_allow_html=True)


with col2:
    st.subheader("🏭 법인팀 실적")
    corp_data = {
        '구분': ['파이프라인 (대수)', '지원 신청 (건)', '지급 신청 (건)'],
        '건수': [corporate_metrics['pipeline'], corporate_metrics['apply'], corporate_metrics['distribute']]
    }
    corp_df = pd.DataFrame(corp_data)
    st.table(corp_df.set_index('구분'))

    # 법인팀 일별 추이 차트
    st.subheader("📈 법인팀 일별 추이")
    df3_copy = df_3.copy()
    df3_copy['신청 요청일'] = pd.to_datetime(df3_copy['신청 요청일'], errors='coerce')
    mask_chart_corp = (df3_copy['신청 요청일'].dt.date >= start_date) & (df3_copy['신청 요청일'].dt.date <= end_date)
    daily_apply_corp = df3_copy[mask_chart_corp].groupby(df3_copy['신청 요청일'].dt.date)['신청대수'].sum().reset_index()
    daily_apply_corp.columns = ['날짜', '신청 대수']

    if not daily_apply_corp.empty:
        chart_corp = alt.Chart(daily_apply_corp).mark_line(point=True, color='orange').encode(
            x=alt.X('날짜:T', title='날짜'),
            y=alt.Y('신청 대수:Q', title='신청 대수'),
            tooltip=['날짜', '신청 대수']
        ).properties(
            title='일별 신청 대수 추이'
        ).interactive()
        st.altair_chart(chart_corp, use_container_width=True)
    else:
        st.info("금일 신청 0건")

# --- 인쇄 버튼 ---
st.markdown('<p class="no-print">', unsafe_allow_html=True)
if st.button("📄 현재 리포트 인쇄하기", key="print_button"):
    st.markdown("<script>window.print();</script>", unsafe_allow_html=True)
st.markdown('</p>', unsafe_allow_html=True)
