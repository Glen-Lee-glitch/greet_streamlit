import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- 0. 데이터프레임(df) 생성 ---
df = pd.read_excel(r"C:\Users\HP\Downloads\Greet_Subsidy.xlsx", sheet_name="DOA 박민정", header=1)
df.drop(columns=['인도일', '알림톡'], inplace=True)
df.rename(columns={'인도일.1': '인도일'}, inplace=True)

df_1 = pd.read_excel(r"C:\Users\HP\Downloads\Greet_Subsidy.xlsx", sheet_name="EV", header=1)
df_time = pd.read_excel(r"C:\Users\HP\Downloads\Greet_Subsidy.xlsx", sheet_name="EV", header=0)
update_time_str = df_time.columns[1]

df_2 = pd.read_excel(r"C:\Users\HP\Downloads\Greet_Subsidy.xlsx", sheet_name="지급신청", header=3)
df_3 = pd.read_excel(r"C:\Users\HP\Downloads\Ent x Greet Lounge Subsidy.xlsx", sheet_name="지원신청", header=0)
df_4 = pd.read_excel(r"C:\Users\HP\Downloads\Ent x Greet Lounge Subsidy.xlsx", sheet_name="지급신청", header=1)

df_5 = pd.read_excel(r"C:\Users\HP\Desktop\GyeonggooLee\greetlounge\greetlounge\피드백\data\pipeline.xlsx")

# --- 모든 날짜 컬럼 전처리 ---
# 스크립트 전반에서 사용되는 날짜 컬럼들을 한 번에 datetime 형태로 변환합니다.
# 이렇게 하면 각 섹션에서 데이터 타입을 다시 변환할 필요가 없어져 오류를 방지할 수 있습니다.
df_5['날짜'] = pd.to_datetime(df_5['날짜'], errors='coerce')
df_1['신청일자'] = pd.to_datetime(df_1['신청일자'], errors='coerce')
df_2['배분일'] = pd.to_datetime(df_2['배분일'], errors='coerce')
df_1['지급신청일자_날짜'] = pd.to_datetime(df_1['지급신청일자'], errors='coerce')

# --- 기준일(필터) UI: 맨 위에 한 번만 배치 ---
from datetime import datetime, timedelta
import pytz

KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()
selected_date = st.date_input('기준 날짜를 선택하세요 (기본값: 금일)', value=today_kst)

# --- 1. 전날, 금일 메일/신청/지급 배분 건수 ---
st.write("### 1. 전날, 금일 메일/신청/지급 배분 건수")

# 컬럼 존재 여부 확인
if '날짜' in df_5.columns and 'RN' in df_5.columns and '신청일자' in df_1.columns and '배분일' in df_2.columns and '지급신청일자' in df_1.columns:
    
    # 날짜 변수 설정
    day0 = selected_date
    # '전일'을 주말을 제외한 가장 최근의 영업일로 계산합니다.
    day1 = (pd.to_datetime(selected_date) - pd.tseries.offsets.BDay(1)).date()

    # 날짜별 건수 계산 (파이프라인: df_5)
    cnt_today_mail = (df_5['날짜'].dt.date == day0).sum()
    cnt_yesterday_mail = (df_5['날짜'].dt.date == day1).sum()
    cnt_total_mail = (df_5['날짜'].dt.date <= day0).sum()

    # 전일
    df1_yesterday = df_1[df_1['신청일자'].dt.date == day1]
    rns_from_df5_yesterday = df_5.loc[df_5['날짜'].dt.date == day1, 'RN']
    cnt_yesterday_apply = df1_yesterday.loc[df1_yesterday['제조수입사\n관리번호'].isin(rns_from_df5_yesterday)].shape[0]
    cnt_yesterday_previous = df1_yesterday.loc[~df1_yesterday['제조수입사\n관리번호'].isin(rns_from_df5_yesterday)].shape[0]

    # 금일
    df1_today = df_1[df_1['신청일자'].dt.date == day0]
    rns_from_df5_today = df_5.loc[df_5['날짜'].dt.date == day0, 'RN']
    cnt_today_apply = df1_today.loc[df1_today['제조수입사\n관리번호'].isin(rns_from_df5_today)].shape[0]
    cnt_today_previous = df1_today.loc[~df1_today['제조수입사\n관리번호'].isin(rns_from_df5_today)].shape[0]

    # 누적
    df1_total = df_1[df_1['신청일자'].dt.date <= day0]
    rns_from_df5_total = df_5.loc[df_5['날짜'].dt.date <= day0, 'RN']
    cnt_total_apply = df1_total.loc[df1_total['제조수입사\n관리번호'].isin(rns_from_df5_total)].shape[0]
    cnt_total_previous = df1_total.loc[~df1_total['제조수입사\n관리번호'].isin(rns_from_df5_total)].shape[0]

    # 지급/요청 건수 계산
    cnt_today_distribute = (df_2['배분일'].dt.date == day0).sum()
    cnt_yesterday_distribute = (df_2['배분일'].dt.date == day1).sum()
    cnt_total_distribute = (df_2['배분일'].dt.date <= day0).sum()

    cnt_today_request = (df_1['지급신청일자_날짜'].dt.date == day0).sum()
    cnt_yesterday_request = (df_1['지급신청일자_날짜'].dt.date == day1).sum()
    cnt_total_request = (df_1['지급신청일자_날짜'].dt.date <= day0).sum()
    
    # '신청 불가' 건수 계산
    # 전일
    rns_yesterday = df_5.loc[df_5['날짜'].dt.date == day1, 'RN']
    df_matched_yesterday = df[df['RN'].isin(rns_yesterday)]
    cnt_ineligible_yesterday = int(df_matched_yesterday.loc[~df_matched_yesterday['Greet Note'].astype(str).str.contains('#', na=False), 'RN'].count())

    # 금일
    rns_today = df_5.loc[df_5['날짜'].dt.date == day0, 'RN']
    df_matched_today = df[df['RN'].isin(rns_today)]
    cnt_ineligible_today = int(df_matched_today.loc[~df_matched_today['Greet Note'].astype(str).str.contains('#', na=False), 'RN'].count())

    # 누적
    rns_total = df_5.loc[df_5['날짜'].dt.date <= day0, 'RN']
    df_matched_total = df[df['RN'].isin(rns_total)]
    cnt_ineligible_total = int(df_matched_total.loc[~df_matched_total['Greet Note'].astype(str).str.contains('#', na=False), 'RN'].count())

    # '변동' 행 계산
    delta_mail = cnt_today_mail - cnt_yesterday_mail
    delta_ineligible = cnt_ineligible_today - cnt_ineligible_yesterday
    delta_apply = cnt_today_apply - cnt_yesterday_apply
    delta_previous = cnt_today_previous - cnt_yesterday_previous
    delta_distribute = cnt_today_distribute - cnt_yesterday_distribute
    delta_request = cnt_today_request - cnt_yesterday_request

    # '변동' 값에 대한 스타일링 함수
    def format_delta(value):
        if value > 0:
            return f'<span style="color:blue;">+{value}</span>'
        elif value < 0:
            return f'<span style="color:red;">{value}</span>'
        return str(value)

    # 3단 멀티인덱스 헤더 구조로 데이터프레임 생성
    table_data = pd.DataFrame({
        ('지원', '파이프라인', '메일 건수'): [cnt_yesterday_mail, cnt_today_mail, cnt_total_mail],
        ('지원', '파이프라인', '신청 불가'): [cnt_ineligible_yesterday, cnt_ineligible_today, cnt_ineligible_total],
        ('지원', '신청완료', '신청 건수'): [cnt_yesterday_apply, cnt_today_apply, cnt_total_apply],
        ('지원', '신청완료', '이전 건'): [cnt_yesterday_previous, cnt_today_previous, cnt_total_previous],
        ('지급', '지급 처리', '지급 배분건'): [cnt_yesterday_distribute, cnt_today_distribute, cnt_total_distribute],
        ('지급', '지급 처리', '지급신청 건수'): [cnt_yesterday_request, cnt_today_request, cnt_total_request]
    }, index=[f'전일 ({day1})', f'금일 ({day0})', '누적 총계'])

    # 스타일이 적용된 '변동' 행 추가
    table_data.loc['변동'] = [
        format_delta(delta_mail),
        format_delta(delta_ineligible),
        format_delta(delta_apply),
        format_delta(delta_previous),
        format_delta(delta_distribute),
        format_delta(delta_request)
    ]
    
    # CSS 스타일을 정의하여 테이블을 꾸밉니다.
    st.markdown("""
    <style>
    .custom_table {
        width: 100%;
        border-collapse: collapse;
        text-align: right;
        font-size: 14px;
    }
    .custom_table th, .custom_table td {
        padding: 8px 12px;
        border: 1px solid #e0e0e0;
    }
    .custom_table th {
        background-color: #f8f9fa;
        font-weight: bold;
        text-align: center;
        vertical-align: middle;
    }
    .custom_table tbody th {
        text-align: center;
        font-weight: bold;
        background-color: #f8f9fa;
    }
    .custom_table thead tr:last-child th:first-child::before {
        content: "구분";
    }
    </style>
    """, unsafe_allow_html=True)

    # DataFrame을 HTML로 변환하고, st.markdown을 사용해 출력합니다.
    # escape=False를 설정하여 HTML 태그가 그대로 렌더링되도록 합니다.
    html_table = table_data.to_html(classes='custom_table', border=0, escape=False)
    st.markdown(html_table, unsafe_allow_html=True)

    # --- 콜아웃(설명 박스) 추가 ---
    st.markdown("""
    <style>
    .callout {
        padding: 15px;
        background-color: #f0f2f6; /* 연한 회색 배경 */
        border-radius: 5px;      /* 둥근 모서리 */
        margin-top: 20px;        /* 위쪽 여백 */
        margin-bottom: 20px;     /* 아래쪽 여백 */
        line-height: 1.6;        /* 줄 간격 */
    }
    </style>
    <div class="callout">
    ※ 영업일 기준<br>
    ※ 메일 건수: 테슬라 측에서 요청한 지원 신청 건<br>
    ※ 신청 불가: EV로 신청하지 못한 건<br>
    ※ 신청 건수: (금일 파이프라인 중) 실제로 EV에서 신청한 건<br>
    ※ 이전 건: (이전 일자 파이프라인 중) 실제로 EV에서 신청한 건<br>
    ※ 지급 배분건: 지급 처리 해야 할 건<br>
    ※ 지급신청 건수: 지급 처리 완료 건
    </div>
    """, unsafe_allow_html=True)

    # --- 1-1. 금일 신청 불가 내역 (토글) ---
    with st.expander("금일 신청 불가 내역 보기"):
        # 'Greet Note'에 '#'이 없는 데이터 필터링 및 필요한 컬럼('RN', 'Greet Note') 선택
        ineligible_notes_today = df_matched_today.loc[
            ~df_matched_today['Greet Note'].astype(str).str.contains('#', na=False),
            ['RN', 'Greet Note']
        ].reset_index(drop=True)

        # 결과가 비어있는지 확인 후, 데이터프레임 또는 안내 메시지 출력
        if not ineligible_notes_today.empty:
            st.dataframe(ineligible_notes_today)
        else:
            st.info("금일 신청 불가 내역이 없습니다.")

    # --- 1-2. 기간별 합계 테이블 ---
    st.write("---") # 구분선
    st.write("### 1-1. 기간별 합계")
    
    # 기간 선택 UI
    col1, col2 = st.columns(2)
    with col1:
        start_date_period = st.date_input('기간 시작일', value=(today_kst.replace(day=1)), key='start_date_period')
    with col2:
        end_date_period = st.date_input('기간 종료일', value=today_kst, key='end_date_period')

    if start_date_period > end_date_period:
        st.error("기간 시작일이 종료일보다 늦을 수 없습니다.")
    else:
        # 기간 내 데이터 필터링
        mask_mail = (df_5['날짜'].dt.date >= start_date_period) & (df_5['날짜'].dt.date <= end_date_period)
        mask_apply = (df_1['신청일자'].dt.date >= start_date_period) & (df_1['신청일자'].dt.date <= end_date_period)
        mask_distribute = (df_2['배분일'].dt.date >= start_date_period) & (df_2['배분일'].dt.date <= end_date_period)
        mask_request = (df_1['지급신청일자_날짜'].dt.date >= start_date_period) & (df_1['지급신청일자_날짜'].dt.date <= end_date_period)

        # 기간별 합계 계산
        cnt_period_mail = int(mask_mail.sum())
        cnt_period_apply = int(mask_apply.sum())
        cnt_period_distribute = int(mask_distribute.sum())
        cnt_period_request = int(mask_request.sum())

        # 기간별 합계 데이터프레임 생성
        period_table_data = pd.DataFrame({
            ('지원', '파이프라인', '메일 건수'): [cnt_period_mail],
            ('지원', '신청완료', '신청 건수'): [cnt_period_apply],
            ('지급', '지급 처리', '지급 배분건'): [cnt_period_distribute],
            ('지급', '지급 처리', '지급신청 건수'): [cnt_period_request]
        }, index=[f'합계'])

        # HTML로 변환하여 출력
        period_html_table = period_table_data.to_html(classes='custom_table', border=0)
        st.markdown(period_html_table, unsafe_allow_html=True)

else:
    st.warning("필요한 컬럼('접수메일\\n도착일', 'RN', '신청일자', '배분일', '지급신청일자')을 찾을 수 없습니다.")

# --- 2. 최근 5 영업일 메일/신청 건수 (주말 제외) ---
st.write("---") # 구분선
st.write("### 2. 최근 5 영업일 메일/신청 건수 (주말 제외)")
if '날짜' in df_5.columns and '신청일자' in df_1.columns:
    last_5_bdays_index = pd.bdate_range(end=pd.Timestamp(selected_date), periods=5)
    last_5_bdays_list = last_5_bdays_index.to_list()
    # 메일 건수
    df_recent = df_5[df_5['날짜'].dt.normalize().isin(last_5_bdays_list)]
    mail_counts = df_recent['날짜'].dt.normalize().value_counts().reindex(last_5_bdays_index, fill_value=0).sort_index()
    # 신청 건수
    df1_recent = df_1[df_1['신청일자'].dt.normalize().isin(last_5_bdays_list)]
    apply_counts = df1_recent['신청일자'].dt.normalize().value_counts().reindex(last_5_bdays_index, fill_value=0).sort_index()
    # 날짜 인덱스 문자열 변환
    idx_str = pd.to_datetime(last_5_bdays_index).strftime('%Y-%m-%d')
    # DataFrame for bar chart
    chart_df = pd.DataFrame({
        '날짜': idx_str,
        '메일 건수': mail_counts.values,
        '신청 건수': apply_counts.values
    })
    # melt로 long-form 변환
    chart_long = chart_df.melt(id_vars='날짜', var_name='구분', value_name='건수')
    # Altair 그룹형(날짜별 두 막대) 막대그래프
    bar_chart = alt.Chart(chart_long).mark_bar(size=25).encode(
        x=alt.X('날짜:N', title='날짜', axis=alt.Axis(labelAngle=-45)),
        xOffset='구분:N',  # 날짜별로 두 막대가 나란히!
        y=alt.Y('건수:Q', title='건수'),
        color=alt.Color('구분:N', scale=alt.Scale(domain=['메일 건수', '신청 건수'], range=['#1f77b4', '#2ca02c'])),
        tooltip=['날짜', '구분', '건수']
    ).properties(width=200)
    st.altair_chart(bar_chart, use_container_width=True)
else:
    st.warning("'접수메일\\n도착일' 또는 '신청일자' 컬럼을 찾을 수 없습니다.")


# --- 3. 월간 요일별 메일/신청 건수 ---
st.write("---") # 구분선
st.write("### 3. 월간 요일별 메일/신청 건수")
if '날짜' in df_5.columns and '신청일자' in df_1.columns:

    # 선택된 날짜가 속한 월의 데이터만 필터링
    df_monthly = df_5[df_5['날짜'].dt.month == selected_date.month].copy()
    df1_monthly = df_1[df_1['신청일자'].dt.month == selected_date.month].copy()

    # 요일 정보 추가 (0=월, 1=화, ..., 6=일)
    df_monthly['요일'] = df_monthly['날짜'].dt.dayofweek
    df1_monthly['요일'] = df1_monthly['신청일자'].dt.dayofweek

    # 월요일(0)부터 금요일(4)까지의 데이터만 필터링
    df_monthly_weekday = df_monthly[df_monthly['요일'] <= 4]
    df1_monthly_weekday = df1_monthly[df1_monthly['요일'] <= 4]
    
    # 요일별 건수 계산
    mail_counts = df_monthly_weekday['요일'].value_counts()
    apply_counts = df1_monthly_weekday['요일'].value_counts()
    
    # 요일 순서대로 정렬하고, 없는 요일은 0으로 채우기 위한 데이터프레임 생성
    day_map = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금'}
    weekdays_str = ['월', '화', '수', '목', '금']
    
    summary_data = pd.DataFrame({
        '메일 건수': mail_counts,
        '신청 건수': apply_counts
    })
    summary_data.index = summary_data.index.map(day_map)
    summary_data = summary_data.reindex(weekdays_str, fill_value=0).reset_index().rename(columns={'index': '요일'})
    
    # melt로 long-form 변환
    chart_long = summary_data.melt(id_vars='요일', var_name='구분', value_name='건수')

    # Altair 그룹형 막대그래프
    # Layer 1: Bars
    bar_chart = alt.Chart(chart_long).mark_bar(size=25).encode(
        x=alt.X('요일:N', title='요일', sort=weekdays_str), # 요일 순서 고정
        xOffset='구분:N',
        y=alt.Y('건수:Q', title='건수'),
        color=alt.Color('구분:N', scale=alt.Scale(domain=['메일 건수', '신청 건수'], range=['#1f77b4', '#2ca02c'])),
        tooltip=['요일', '구분', '건수']
    )

    # ✨✨✨ 핵심 변경사항: 텍스트 레이블을 막대 '위'에 표시하도록 수정 ✨✨✨
    # Layer 2: Text labels OUTSIDE the bars, at the top
    text = bar_chart.mark_text(
        align='center',
        baseline='bottom', # 텍스트의 하단을 기준으로 정렬 (막대 상단에 위치)
        dy=-5,  # 막대 상단에서 5px 위로 오프셋하여 공간 확보
        color='black' # 배경과 대비되는 색상으로 변경
    ).encode(
        text=alt.Text('건수:Q', format='.0f')
    ).transform_filter(
        alt.datum.건수 > 0 # 건수가 0인 막대에는 텍스트를 표시하지 않음
    )
    
    # Combine layers and set properties
    final_chart = (bar_chart + text).properties(
        width=alt.Step(40)  # 막대 그룹 간의 간격 조절
    )
    
    st.altair_chart(final_chart, use_container_width=True)
else:
    st.warning("'접수메일\\n도착일' 또는 '신청일자' 컬럼을 찾을 수 없습니다.")

# --- 4. 현재 EV 신청단계 별 건수 ---
st.write("---") # 구분선
st.write("### 4. 현재 EV 신청단계 별 건수")
st.write(f"**업데이트 시간: {update_time_str}**")

# df_1 (EV 시트)에 필요한 컬럼들이 있는지 확인
if '신청단계' in df_1.columns and '지역구분' in df_1.columns:
    # '지역구분'이 비어있지 않은 데이터만 필터링
    df_filtered = df_1.dropna(subset=['지역구분'])

    # 필터링된 데이터에서 '신청단계'의 값별로 개수를 셉니다 (NaN 값도 포함).
    stage_counts = df_filtered['신청단계'].value_counts(dropna=False)
    
    # Series의 이름을 '건수'로 지정합니다.
    stage_counts.name = '건수'
    
    # 결측값(NaN)이 있다면 인덱스 이름을 '미지정'으로 변경합니다.
    if np.nan in stage_counts.index:
        stage_counts = stage_counts.rename(index={np.nan: '미지정'})

    # Streamlit 테이블로 표시합니다.
    st.table(stage_counts)
else:
    st.warning("EV 시트(df_1)에서 '신청단계' 또는 '지역구분' 컬럼을 찾을 수 없습니다.")

# --- 5. 법인팀 요약 ---
st.write("---") # 구분선
st.write("### 4. 법인팀 요약")

# 필요한 컬럼 목록 정의
required_cols_df3 = ['신청 요청일', '접수 완료', '신청대수']
required_cols_df4 = ['요청일자', '지급신청 완료 여부', '신청번호', '접수대수']

# 모든 컬럼이 존재하는지 확인
has_all_cols = all(col in df_3.columns for col in required_cols_df3) and \
               all(col in df_4.columns for col in required_cols_df4)

if has_all_cols:
    # --- 데이터 처리 함수 (manager.py 로직 기반) ---
    def process_new(df, end_date):
        df = df.copy()
        date_col = '신청 요청일'
        # 날짜 타입 변환
        if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        
        # 기준일까지 필터링 (누계 계산용)
        df_cumulative = df[df[date_col].notna() & (df[date_col].dt.date <= end_date)]
        # '접수 완료' 필터
        df_cumulative = df_cumulative[df_cumulative['접수 완료'].astype(str).str.strip().isin(['O', 'ㅇ'])]
        # 기타 필터
        b_col_name = df_cumulative.columns[1]
        df_cumulative = df_cumulative[df_cumulative[b_col_name].notna() & (df_cumulative[b_col_name] != "")]
        
        # 당일 데이터 필터링
        df_today = df_cumulative[df_cumulative[date_col].dt.date == end_date]

        # 누계 계산
        mask_bulk = df_cumulative['신청대수'] > 1
        mask_single = df_cumulative['신청대수'] == 1
        new_bulk_sum = int(df_cumulative.loc[mask_bulk, '신청대수'].sum())
        new_bulk_count = int(mask_bulk.sum())
        new_single_sum = int(df_cumulative.loc[mask_single, '신청대수'].sum())

        # 당일 건수 계산
        today_bulk_count = int((df_today['신청대수'] > 1).sum())
        today_single_count = int((df_today['신청대수'] == 1).sum())

        return new_bulk_sum, new_single_sum, new_bulk_count, today_bulk_count, today_single_count

    def process_give(df, end_date):
        df = df.copy()
        date_col = '요청일자'
        # 날짜 타입 변환
        if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
         
        # 기준일까지 필터링 (누계 계산용)
        df_cumulative = df[df[date_col].notna() & (df[date_col].dt.date <= end_date)]
        # '지급신청 완료 여부' 필터
        df_cumulative = df_cumulative[df_cumulative['지급신청 완료 여부'].astype(str).str.strip() == '완료']
        # 중복 제거
        unique_df_cumulative = df_cumulative.drop_duplicates(subset=['신청번호'])

        # 당일 데이터 필터링
        df_today = df_cumulative[df_cumulative[date_col].dt.date == end_date]
        unique_df_today = df_today.drop_duplicates(subset=['신청번호'])
         
        # 누계 계산
        mask_bulk = unique_df_cumulative['접수대수'] > 1
        mask_single = unique_df_cumulative['접수대수'] == 1
        give_bulk_sum = int(unique_df_cumulative.loc[mask_bulk, '접수대수'].sum())
        give_bulk_count = int(mask_bulk.sum())
        give_single_sum = int(unique_df_cumulative.loc[mask_single, '접수대수'].sum())

        # 당일 건수 계산
        today_bulk_count = int((unique_df_today['접수대수'] > 1).sum())
        today_single_count = int((unique_df_today['접수대수'] == 1).sum())

        return give_bulk_sum, give_single_sum, give_bulk_count, today_bulk_count, today_single_count

    # --- 데이터 처리 실행 ---
    new_bulk_sum, new_single_sum, new_bulk_count, new_today_bulk_count, new_today_single_count = process_new(df_3, selected_date)
    give_bulk_sum, give_single_sum, give_bulk_count, give_today_bulk_count, give_today_single_count = process_give(df_4, selected_date)
 
    # --- 요약 DataFrame 생성 (3단 멀티인덱스) ---
    row_names = ['벌크', '낱개', 'TTL']
     
    columns = pd.MultiIndex.from_tuples([
        ('지원', '파이프라인', '대수'),
        ('지원', '신청(건)', '당일'),
        ('지원', '신청(건)', '누계'),
        ('지급', '파이프라인', '대수'),
        ('지급', '신청(건)', '당일'),
        ('지급', '신청(건)', '누계')
    ], names=['', '분류', '항목']) # 헤더 이름 지정
 
    df_total = pd.DataFrame(0, index=row_names, columns=columns)
 
    # 지원 데이터 채우기
    df_total.loc['벌크', ('지원', '파이프라인', '대수')] = new_bulk_sum
    df_total.loc['낱개', ('지원', '파이프라인', '대수')] = new_single_sum
    df_total.loc['TTL', ('지원', '파이프라인', '대수')] = new_bulk_sum + new_single_sum
     
    df_total.loc['벌크', ('지원', '신청(건)', '당일')] = new_today_bulk_count
    df_total.loc['낱개', ('지원', '신청(건)', '당일')] = new_today_single_count
    df_total.loc['TTL', ('지원', '신청(건)', '당일')] = new_today_bulk_count + new_today_single_count

    df_total.loc['벌크', ('지원', '신청(건)', '누계')] = new_bulk_count
    df_total.loc['낱개', ('지원', '신청(건)', '누계')] = new_single_sum
     
    # 지급 데이터 채우기
    df_total.loc['벌크', ('지급', '파이프라인', '대수')] = give_bulk_sum
    df_total.loc['낱개', ('지급', '파이프라인', '대수')] = give_single_sum
    df_total.loc['TTL', ('지급', '파이프라인', '대수')] = give_bulk_sum + give_single_sum
     
    df_total.loc['벌크', ('지급', '신청(건)', '당일')] = give_today_bulk_count
    df_total.loc['낱개', ('지급', '신청(건)', '당일')] = give_today_single_count
    df_total.loc['TTL', ('지급', '신청(건)', '당일')] = give_today_bulk_count + give_today_single_count

    df_total.loc['벌크', ('지급', '신청(건)', '누계')] = give_bulk_count
    df_total.loc['낱개', ('지급', '신청(건)', '누계')] = give_single_sum
     
    # '당일' 컬럼은 manager.py에 계산 로직이 없으므로 0으로 유지됩니다.
     
    # Streamlit에 HTML 테이블로 표시
    html_table_4 = df_total.to_html(classes='custom_table', border=0)
    st.markdown(html_table_4, unsafe_allow_html=True)

else:
    st.warning("4번 테이블에 필요한 컬럼이 df_3 또는 df_4에 존재하지 않습니다.")



