import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import pickle
import sys

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

# --- 분기 및 날짜 선택 UI ---
col1, col2 = st.columns(2)
with col1:
    # 분기 선택 (전체, 3분기, 2분기)
    selected_quarter = st.selectbox('분기를 선택하세요', ['3분기', '2분기', '전체'])
with col2:
    selected_date = st.date_input('기준 날짜를 선택하세요 (기본값: 금일)', value=today_kst)


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



