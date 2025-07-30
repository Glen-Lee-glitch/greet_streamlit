import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import pickle
import sys

# --- 메모 파일 경로 및 로딩 ---
MEMO_FILE = "memo.txt"

# 세션 상태에 메모가 없으면 파일에서 로드
if 'memo_content' not in st.session_state:
    try:
        with open(MEMO_FILE, "r", encoding="utf-8") as f:
            st.session_state.memo_content = f.read()
    except FileNotFoundError:
        st.session_state.memo_content = "" # 파일이 없으면 빈 문자열로 시작

# --- 0. 데이터프레임(df) 생성 ---
# 전처리된 데이터를 로드합니다.
try:
    with open("preprocessed_data.pkl", "rb") as f:
        data = pickle.load(f)
    
    df = data["df"]
    df_1 = data["df_1"]
    df_2 = data["df_2"]
    df_3 = data["df_3"]
    df_4 = data["df_4"]
    df_5 = data["df_5"]
    update_time_str = data["update_time_str"]
except FileNotFoundError:
    st.error("전처리된 데이터 파일(preprocessed_data.pkl)을 찾을 수 없습니다.")
    st.info("먼저 '전처리.py'를 실행하여 데이터 파일을 생성해주세요.")
    # 앱 실행을 중단하여 더 이상 진행되지 않도록 함
    sys.exit()


# (이전 날짜 컬럼 전처리 로직 삭제)

# --- 기준일(필터) UI: 맨 위에 한 번만 배치 ---
from datetime import datetime, timedelta
import pytz

st.set_page_config(layout="wide")
# --- 인쇄용 스타일 추가 ---
st.markdown("""
<style>
@media print {
    /* 인쇄 시 적용될 스타일 */
    .main .block-container {
        max-width: 100%;
        padding: 1rem;
    }
    /* Streamlit의 불필요한 UI 요소들을 숨깁니다. */
    header, .stToolbar, .stActionButton, .stDeployButton {
        display: none !important;
    }
    /* 페이지가 어색하게 나뉘는 것을 방지합니다. */
    .stApp > div {
        page-break-inside: avoid;
    }
    /* 모든 텍스트를 검은색으로 강제하여 가독성을 높입니다. */
    * {
        color: black !important;
    }
    /* 차트 크기 조정 */
    .stAltairChart {
        width: 100% !important;
    }
}
</style>
""", unsafe_allow_html=True)

KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()

# --- 분기 및 날짜 선택 UI ---
col1, col2 = st.columns(2)
with col1:
    # 분기 선택 (전체, 3분기, 2분기)
    selected_quarter = st.selectbox('분기를 선택하세요', ['3분기', '2분기', '전체'])
with col2:
    selected_date = st.date_input('기준 날짜를 선택하세요 (기본값: 금일)', value=today_kst)

# 구분선
st.write("---")

# --- 1. 전날, 금일 메일/신청/지급 배분 건수 & 3. 법인팀 요약 ---
# 컬럼 존재 여부 확인 (새 구조)
if '날짜' in df_5.columns and '날짜' in df_1.columns and '날짜' in df_2.columns:
    
    # --- 선택된 분기에 따라 df_5, df_1, df_2 필터링 (새 구조) ---
    if selected_quarter == '전체':
        df_5_filtered = df_5
        df_1_filtered = df_1
        df_2_filtered = df_2
    else:
        df_5_filtered = df_5[df_5['분기'] == selected_quarter]
        df_1_filtered = df_1[df_1['분기'] == selected_quarter]
        df_2_filtered = df_2[df_2['분기'] == selected_quarter]

    # 날짜 변수 설정
    day0 = selected_date
    # '전일'을 주말을 제외한 가장 최근의 영업일로 계산합니다.
    day1 = (pd.to_datetime(selected_date) - pd.tseries.offsets.BDay(1)).date()

    col1, col2 = st.columns([6, 4])

    with col1:
        st.write("### 1. 전날, 금일 메일/신청/지급 배분 건수")
        
        # --- 메일 건수 계산 ---
        cnt_today_mail = (df_5_filtered['날짜'].dt.date == day0).sum()
        cnt_yesterday_mail = (df_5_filtered['날짜'].dt.date == day1).sum()
        cnt_total_mail = (df_5_filtered['날짜'].dt.date <= day0).sum()

        # --- 신청 건수 계산 (지원_EV sheet, '개수' 합계) ---
        cnt_today_apply = int(df_1_filtered.loc[df_1_filtered['날짜'].dt.date == day0, '개수'].sum())
        cnt_yesterday_apply = int(df_1_filtered.loc[df_1_filtered['날짜'].dt.date == day1, '개수'].sum())
        cnt_total_apply = int(df_1_filtered.loc[df_1_filtered['날짜'].dt.date <= day0, '개수'].sum())

        # 지급/요청 건수 계산 (지급 시트)
        cnt_today_distribute = int(df_2_filtered.loc[df_2_filtered['날짜'].dt.date == day0, '배분'].sum())
        cnt_yesterday_distribute = int(df_2_filtered.loc[df_2_filtered['날짜'].dt.date == day1, '배분'].sum())
        cnt_total_distribute = int(df_2_filtered.loc[df_2_filtered['날짜'].dt.date <= day0, '배분'].sum())

        cnt_today_request = int(df_2_filtered.loc[df_2_filtered['날짜'].dt.date == day0, '신청'].sum())
        cnt_yesterday_request = int(df_2_filtered.loc[df_2_filtered['날짜'].dt.date == day1, '신청'].sum())
        cnt_total_request = int(df_2_filtered.loc[df_2_filtered['날짜'].dt.date <= day0, '신청'].sum())
        
        # '변동' 행 계산
        delta_mail = cnt_today_mail - cnt_yesterday_mail
        delta_apply = cnt_today_apply - cnt_yesterday_apply
        delta_distribute = cnt_today_distribute - cnt_yesterday_distribute
        delta_request = cnt_today_request - cnt_yesterday_request

        # '변동' 값에 대한 스타일링 함수
        def format_delta(value):
            if value > 0:
                return f'<span style="color:blue;">+{value}</span>'
            elif value < 0:
                return f'<span style="color:red;">{value}</span>'
            return str(value)

        # 3단 멀티인덱스 헤더 구조로 데이터프레임 생성 (간소화)
        table_data = pd.DataFrame({
            ('지원', '파이프라인', '메일 건수'): [cnt_yesterday_mail, cnt_today_mail, cnt_total_mail],
            ('지원', '신청완료', '신청 건수'): [cnt_yesterday_apply, cnt_today_apply, cnt_total_apply],
            ('지급', '지급 처리', '지급 배분건'): [cnt_yesterday_distribute, cnt_today_distribute, cnt_total_distribute],
            ('지급', '지급 처리', '지급신청 건수'): [cnt_yesterday_request, cnt_today_request, cnt_total_request]
        }, index=[f'전일 ({day1})', f'금일 ({day0})', '누적 총계'])

        # 스타일이 적용된 '변동' 행 추가
        table_data.loc['변동'] = [
            format_delta(delta_mail),
            format_delta(delta_apply),
            format_delta(delta_distribute),
            format_delta(delta_request)
        ]
        
        html_table = table_data.to_html(classes='custom_table', border=0, escape=False)

        header_tooltips = {
            '메일 건수': 'PipeLine 시트에서 기준일자별 RN 행 수',
            '신청 건수': '지원_EV 시트의 집계값(개수)',
            '지급 배분건': '지급 시트의 배분 합계',
            '지급신청 건수': '지급 시트의 신청 합계'
        }

        for header, tooltip in header_tooltips.items():
            html_table = html_table.replace(f'<th>{header}</th>', f'<th title="{tooltip}">{header}</th>')

        st.markdown(html_table, unsafe_allow_html=True)

        with st.expander("설명 보기/숨기기 (클릭)"):
            설명_리스트 = "\n".join(
                [f"- **{header}**: {tooltip.replace(chr(10), '<br>')}" for header, tooltip in header_tooltips.items()]
            )
            st.markdown(f"""
            {설명_리스트}
            <br>
            *각 표의 헤더에 마우스를 올리면 더 상세한 설명을 볼 수 있습니다.*
            """, unsafe_allow_html=True)
            
    with col2:
        st.write("### 3. 법인팀 요약")

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
                new_bulk_count = int(mask_bulk.sum())
                new_single_sum = int(df_cumulative.loc[mask_single, '신청대수'].sum())
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
                df_today = df_cumulative[df_cumulative[date_col].dt.date == end_date]
                unique_df_today = df_today.drop_duplicates(subset=['신청번호'])
                mask_bulk = unique_df_cumulative['접수대수'] > 1
                mask_single = unique_df_cumulative['접수대수'] == 1
                give_bulk_sum = int(unique_df_cumulative.loc[mask_bulk, '접수대수'].sum())
                give_bulk_count = int(mask_bulk.sum())
                give_single_sum = int(unique_df_cumulative.loc[mask_single, '접수대수'].sum())
                today_bulk_count = int((unique_df_today['접수대수'] > 1).sum())
                today_single_count = int((unique_df_today['접수대수'] == 1).sum())
                return give_bulk_sum, give_single_sum, give_bulk_count, today_bulk_count, today_single_count

            new_bulk_sum, new_single_sum, new_bulk_count, new_today_bulk_count, new_today_single_count = process_new(df_3, selected_date)
            give_bulk_sum, give_single_sum, give_bulk_count, give_today_bulk_count, give_today_single_count = process_give(df_4, selected_date)
         
            row_names = ['벌크', '낱개', 'TTL']
            columns = pd.MultiIndex.from_tuples([
                ('지원', '파이프라인', '대수'), ('지원', '신청(건)', '당일'), ('지원', '신청(건)', '누계'),
                ('지급', '파이프라인', '대수'), ('지급', '신청(건)', '당일'), ('지급', '신청(건)', '누계')
            ], names=['', '분류', '항목'])
            df_total = pd.DataFrame(0, index=row_names, columns=columns)
            df_total.loc['벌크', ('지원', '파이프라인', '대수')] = new_bulk_sum
            df_total.loc['낱개', ('지원', '파이프라인', '대수')] = new_single_sum
            df_total.loc['TTL', ('지원', '파이프라인', '대수')] = new_bulk_sum + new_single_sum
            df_total.loc['벌크', ('지원', '신청(건)', '당일')] = new_today_bulk_count
            df_total.loc['낱개', ('지원', '신청(건)', '당일')] = new_today_single_count
            df_total.loc['TTL', ('지원', '신청(건)', '당일')] = new_today_bulk_count + new_today_single_count
            df_total.loc['벌크', ('지원', '신청(건)', '누계')] = new_bulk_count
            df_total.loc['낱개', ('지원', '신청(건)', '누계')] = new_single_sum
            df_total.loc['TTL', ('지원', '신청(건)', '누계')] = new_bulk_count + new_single_sum
            df_total.loc['벌크', ('지급', '파이프라인', '대수')] = give_bulk_sum
            df_total.loc['낱개', ('지급', '파이프라인', '대수')] = give_single_sum
            df_total.loc['TTL', ('지급', '파이프라인', '대수')] = give_bulk_sum + give_single_sum
            df_total.loc['벌크', ('지급', '신청(건)', '당일')] = give_today_bulk_count
            df_total.loc['낱개', ('지급', '신청(건)', '당일')] = give_today_single_count
            df_total.loc['TTL', ('지급', '신청(건)', '당일')] = give_today_bulk_count + give_today_single_count
            df_total.loc['벌크', ('지급', '신청(건)', '누계')] = give_bulk_count
            df_total.loc['낱개', ('지급', '신청(건)', '누계')] = give_single_sum
            df_total.loc['TTL', ('지급', '신청(건)', '누계')] = give_bulk_count + give_single_sum
             
            html_table_4 = df_total.to_html(classes='custom_table', border=0)
            st.markdown(html_table_4, unsafe_allow_html=True)

            st.write("### 법인팀 메모")
            new_memo = st.text_area(
                "메모를 입력하거나 수정하세요. (내용은 자동으로 저장됩니다)",
                value=st.session_state.memo_content, height=100, key="memo_input"
            )

            if new_memo != st.session_state.memo_content:
                st.session_state.memo_content = new_memo
                with open(MEMO_FILE, "w", encoding="utf-8") as f:
                    f.write(new_memo)
                st.toast("메모가 저장되었습니다!")
        else:
            st.warning("3번 테이블에 필요한 컬럼이 df_3 또는 df_4에 존재하지 않습니다.")

    # --- 2. 기간별 합계 테이블 ---
    st.write("---")
    st.write("### 2. 기간별 합계")
    
    col1_period, col2_period = st.columns(2)
    with col1_period:
        start_date_period = st.date_input('기간 시작일', value=(today_kst.replace(day=1)), key='start_date_period')
    with col2_period:
        end_date_period = st.date_input('기간 종료일', value=today_kst, key='end_date_period')

    if start_date_period > end_date_period:
        st.error("기간 시작일이 종료일보다 늦을 수 없습니다.")
    else:
        mask_mail = (df_5['날짜'].dt.date >= start_date_period) & (df_5['날짜'].dt.date <= end_date_period)
        mask_apply = (df_1['날짜'].dt.date >= start_date_period) & (df_1['날짜'].dt.date <= end_date_period)
        mask_distribute = (df_2['날짜'].dt.date >= start_date_period) & (df_2['날짜'].dt.date <= end_date_period)
        mask_request = mask_distribute

        cnt_period_mail = int(mask_mail.sum())
        cnt_period_apply = int(df_1.loc[mask_apply, '개수'].sum())
        cnt_period_distribute = int(df_2.loc[mask_distribute, '배분'].sum())
        cnt_period_request = int(df_2.loc[mask_request, '신청'].sum())

        period_table_data = pd.DataFrame({
            ('지원', '파이프라인', '메일 건수'): [cnt_period_mail],
            ('지원', '신청완료', '신청 건수'): [cnt_period_apply],
            ('지급', '지급 처리', '지급 배분건'): [cnt_period_distribute],
            ('지급', '지급 처리', '지급신청 건수'): [cnt_period_request]
        }, index=[f'합계'])

        period_html_table = period_table_data.to_html(classes='custom_table', border=0)
        st.markdown(period_html_table, unsafe_allow_html=True)

    # --- 4. 분기별 메일/신청 건수 ---
    st.write("---")
    st.write("### 4. 분기별 메일/신청 건수")
    if '날짜' in df_5.columns and '날짜' in df_1.columns and '분기' in df_5.columns and '분기' in df_1.columns:
        mail_counts_by_quarter = df_5.groupby('분기').size()
        q2_mail_count = mail_counts_by_quarter.get('2분기', 0)
        q3_mail_count = mail_counts_by_quarter.get('3분기', 0)
        apply_counts_by_quarter = df_1.groupby('분기')['개수'].sum()
        q2_apply_count = apply_counts_by_quarter.get('2분기', 0)
        q3_apply_count = apply_counts_by_quarter.get('3분기', 0)
        quarter_chart_df = pd.DataFrame({
            '분기': ['2분기', '3분기'],
            '메일 건수': [q2_mail_count, q3_mail_count],
            '신청 건수': [q2_apply_count, q3_apply_count]
        })
        quarter_chart_long = quarter_chart_df.melt(id_vars='분기', var_name='구분', value_name='건수')
        quarter_bar_chart = alt.Chart(quarter_chart_long).mark_bar(size=40).encode(
            x=alt.X('분기:N', title='분기'),
            xOffset='구분:N',
            y=alt.Y('건수:Q', title='건수'),
            color=alt.Color('구분:N', scale=alt.Scale(domain=['메일 건수', '신청 건수'], range=['#1f77b4', '#2ca02c'])),
            tooltip=['분기', '구분', '건수']
        ).properties(title='분기별 메일/신청 건수 합계')
        st.altair_chart(quarter_bar_chart, use_container_width=True)
    else:
        st.warning("차트를 표시하는 데 필요한 '날짜' 또는 '분기' 컬럼을 찾을 수 없습니다.")

    # --- 5. 월별 데이터 (4월~) ---
    st.write("---")
    st.write("### 5. 월별 데이터 (4월~)")
    if '날짜' in df_5.columns and '날짜' in df_1.columns:
        current_month = selected_date.month
        start_month = 4 
        months_to_show = list(range(start_month, current_month + 1))
        if not months_to_show:
            st.info("4월 이후의 데이터가 없습니다.")
        else:
            chart_title = f"{selected_date.year}년 월별 합계 ({start_month}월~{current_month}월)"
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
            ).properties(title=chart_title)
            st.altair_chart(bar_chart, use_container_width=True)
    else:
        st.warning("차트를 표시하는 데 필요한 '날짜' 컬럼을 찾을 수 없습니다.")

else:
    st.warning("필요한 컬럼('날짜', '개수', '배분', '신청')이 존재하지 않습니다.")


    





