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
df_fail_q3 = data["df_fail_q3"]
df_2_fail_q3 = data["df_2_fail_q3"]
update_time_str = data["update_time_str"]

# --- 시간대 설정 ---
KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()

# --- 사이드바: 조회 옵션 설정 ---
with st.sidebar:
    st.header("👁️ 뷰어 옵션")
    viewer_option = st.radio("뷰어 유형을 선택하세요.", ('내부', '테슬라'), key="viewer_option")
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
        min_date_1 = df_1['날짜'].min().date() if not df_1.empty else today_kst
        min_date_5 = df_5['날짜'].min().date() if not df_5.empty else today_kst
        start_date = min(min_date_1, min_date_5)
        end_date = today_kst
        title = "전체 누적 리포트"

    # 월별 요약 표시 옵션
    show_monthly_summary_option = st.radio(
        "월별 요약 펼치기",
        ('보이기', '숨기기'),
        index=0,
        key="show_monthly_summary_option"
    )
    show_monthly_summary = (show_monthly_summary_option == '보이기')

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

    st.write("---")

    # ----- 리테일 월별 요약 헤더 및 기간 선택 -----
    if show_monthly_summary:
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
            period_option = '전체'
    else:
        period_option = '전체'
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

    if period_option != '전체':
        df5_p = filter_by_period(df_5)
        df1_p = filter_by_period(df_1)
        df2_p = filter_by_period(df_2)
        mail_total = int(df5_p.shape[0])
        apply_total = int(df1_p['개수'].sum())
        distribute_total = int(df2_p['배분'].sum())
        # 단일 라벨로 표시하기 위해 7월 컬럼에 총합 넣고 8월은 '-' 처리
        retail_df_data = {'선택기간': [mail_total, apply_total, distribute_total], ' ': ['-','-','-']}
    else:
        retail_df_data = {'Q1': [4436, 4230, 4214], 'Q2': [9199, 9212, 8946], '7월': [july_mail_count, july_apply_count, july_distribute_count], '8월': [august_mail_count, august_apply_count, august_distribute_count]}
    retail_df = pd.DataFrame(retail_df_data, index=['파이프라인', '신청', '지급신청'])
    if period_option == '전체':
        retail_df['TTL'] = retail_df['7월'] + retail_df['8월']
    else:
        retail_df['TTL'] = retail_df.iloc[:,0]

    if period_option in ('전체', '3Q', '3분기'):
        q3_target = 10000
        progress_rate = (july_mail_count + august_mail_count) / q3_target if q3_target > 0 else 0
        retail_df['Q3 Target'] = [f"{q3_target:,}", '진척률', f"{progress_rate:.2%}"]
    html_retail = retail_df.to_html(classes='custom_table', border=0, escape=False).replace('<td>진척률</td>', '<td style="background-color: #e0f7fa;">진척률</td>')
    if show_monthly_summary:
        st.markdown(html_retail, unsafe_allow_html=True)

    # --- 리테일 월별 추이 그래프 (내부 뷰어 전용) ---
    if viewer_option == '내부' and show_monthly_summary and period_option == '전체':
        current_month = selected_date.month
        start_month = 2  # 2월부터
        months_to_show = list(range(start_month, current_month + 1))
        if months_to_show:
            df_5_monthly = df_5[(df_5['날짜'].dt.year == selected_date.year) & (df_5['날짜'].dt.month.isin(months_to_show))]
            df_1_monthly = df_1[(df_1['날짜'].dt.year == selected_date.year) & (df_1['날짜'].dt.month.isin(months_to_show))]
            mail_counts = df_5_monthly.groupby(df_5_monthly['날짜'].dt.month).size()
            apply_counts = df_1_monthly.groupby(df_1_monthly['날짜'].dt.month)['개수'].sum()
            chart_df = pd.DataFrame(
                {'메일 건수': mail_counts, '신청 건수': apply_counts},
                index=pd.Index(months_to_show, name='월')
            ).fillna(0).astype(int).reset_index()
            chart_df['월'] = chart_df['월'].astype(str) + '월'
            chart_long = chart_df.melt(id_vars='월', var_name='구분', value_name='건수')
            bar_chart = alt.Chart(chart_long).mark_bar(size=25).encode(
                x=alt.X('월:N', title='월', sort=[f"{m}월" for m in months_to_show]),
                xOffset='구분:N',
                y=alt.Y('건수:Q', title='건수'),
                color=alt.Color('구분:N', scale=alt.Scale(domain=['메일 건수', '신청 건수'], range=['#1f77b4', '#2ca02c'])),
                tooltip=['월', '구분', '건수']
            ).properties(title=f"{selected_date.year}년 월별 추이 ({start_month}월~{current_month}월)")
            st.altair_chart(bar_chart, use_container_width=True)

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

    if show_monthly_summary:
        st.write("---")
        st.write("##### 법인팀 월별 요약")
    
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
        '7월': [july_pipeline, july_apply, july_distribute],
        '8월': [august_pipeline, august_apply, august_distribute]
    }
    corp_df = pd.DataFrame(corp_df_data, index=['파이프라인', '지원신청', '지급신청'])
    corp_df['TTL'] = corp_df['7월'] + corp_df['8월']

    # --- 'Q3 Target' 및 진척률 추가 ---
    q3_target_corp = 1500
    ttl_apply_corp = corp_df.loc['지원신청', 'TTL']
    progress_rate_corp = ttl_apply_corp / q3_target_corp if q3_target_corp > 0 else 0
    formatted_progress_corp = f"{progress_rate_corp:.2%}"

    corp_df['Q3 Target'] = ''
    corp_df.loc['파이프라인', 'Q3 Target'] = f"{q3_target_corp}"
    corp_df.loc['지원신청', 'Q3 Target'] = '진척률'
    corp_df.loc['지급신청', 'Q3 Target'] = formatted_progress_corp

    # --- HTML로 변환 및 스타일 적용 ---
    html_corp = corp_df.to_html(classes='custom_table', border=0, escape=False)
    html_corp = html_corp.replace(
        '<td>진척률</td>',
        '<td style="background-color: #e0f7fa;">진척률</td>'
    ).replace(
        f'<td>{formatted_progress_corp}</td>',
        f'<td>{formatted_progress_corp}</td>'
    )

    if show_monthly_summary:
        st.markdown(html_corp, unsafe_allow_html=True)

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

    # 특이사항 메모에 넣을 내용



    # 특이사항 메모 (자동 추가)
    st.subheader("미신청건")

    # 오늘 기준 자동 추출된 특이사항 라인들
    auto_special_lines = extract_special_memo(df_fail_q3, selected_date)
    if not auto_special_lines:
        auto_special_lines = ["미신청건 없음"]
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

    # 기타 메모
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

st.markdown("---")

# --- 인쇄 및 PDF 저장 버튼 ---
# 'no-print' 클래스를 버튼과 안내 메시지를 감싸는 컨테이너에 적용
st.markdown('<div class="no-print">', unsafe_allow_html=True)

# if st.button("📄 리포트 인쇄 및 PDF 저장", type="primary"):
#     components.html(
#         """
#         <script>
#             // 컴포넌트 iframe 안이므로 상위 창을 대상으로 print 실행
#             window.parent.print();
#         </script>
#         """,
#         height=0,    # 공간 차지 X
#         width=0
#     )
