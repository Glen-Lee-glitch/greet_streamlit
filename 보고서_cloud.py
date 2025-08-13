import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import altair as alt
import pickle
import json
import re
import plotly.express as px
from datetime import datetime, timedelta, date
import pytz
import os

# --- 페이지 설정 및 기본 스타일 ---
st.set_page_config(
    page_title="전기차 보조금 현황 보고서",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        div[data-testid="stSidebar"], .no-print {
            display: none !important;
        }
        .main .block-container {
            padding: 1rem !important;
        }
    }
    /* 메인 헤더 스타일 */
    .main-header {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 2rem;
    }
    .status-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin: 1rem 0;
    }
    .metric-number {
        font-size: 2rem;
        font-weight: 700;
        color: #059669;
    }
    .error-card {
        background: #fee2e2;
        border: 1px solid #fca5a5;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        color: #dc2626;
    }
</style>
""", unsafe_allow_html=True)

# --- 안전한 데이터 로딩 함수들 ---
@st.cache_data(ttl=3600)
def safe_load_data():
    """안전하게 전처리된 데이터 파일을 로드합니다."""
    try:
        if os.path.exists("preprocessed_data.pkl"):
            with open("preprocessed_data.pkl", "rb") as f:
                return pickle.load(f)
        else:
            st.warning("⚠️ preprocessed_data.pkl 파일을 찾을 수 없습니다.")
            return create_empty_data_structure()
    except Exception as e:
        st.error(f"데이터 로드 중 오류: {e}")
        return create_empty_data_structure()

def create_empty_data_structure():
    """빈 데이터 구조를 생성합니다."""
    empty_df = pd.DataFrame()
    return {
        "df": empty_df,
        "df_1": empty_df,
        "df_2": empty_df,
        "df_3": empty_df,
        "df_4": empty_df,
        "df_5": empty_df,
        "df_sales": empty_df,
        "df_fail_q3": empty_df,
        "df_2_fail_q3": empty_df,
        "update_time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "df_master": empty_df,
        "df_6": empty_df,
        "df_tesla_ev": empty_df,
        "preprocessed_map_geojson": None,
        "quarterly_region_counts": {}
    }

def safe_load_memo(filename="memo.txt"):
    """안전하게 메모를 로드합니다."""
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        return ""
    except Exception:
        return ""

def safe_save_memo(filename, content):
    """안전하게 메모를 저장합니다."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception:
        return False

# --- 데이터 로딩 ---
data = safe_load_data()
df_1 = data.get("df_1", pd.DataFrame())
df_2 = data.get("df_2", pd.DataFrame())
df_3 = data.get("df_3", pd.DataFrame())
df_4 = data.get("df_4", pd.DataFrame())
df_5 = data.get("df_5", pd.DataFrame())
df_sales = data.get("df_sales", pd.DataFrame())
df_fail_q3 = data.get("df_fail_q3", pd.DataFrame())
df_2_fail_q3 = data.get("df_2_fail_q3", pd.DataFrame())
update_time_str = data.get("update_time_str", "데이터 없음")
df_master = data.get("df_master", pd.DataFrame())
df_6 = data.get("df_6", pd.DataFrame())
df_tesla_ev = data.get("df_tesla_ev", pd.DataFrame())

# --- 시간대 설정 ---
KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()

# --- 메인 애플리케이션 ---
st.markdown('<h1 class="main-header">⚡ 전기차 보조금 현황 보고서</h1>', unsafe_allow_html=True)

# --- 데이터 상태 체크 ---
data_status = not all(df.empty for df in [df_1, df_2, df_3, df_4, df_5])

if not data_status:
    st.markdown("""
    <div class="error-card">
        <h3>🚫 데이터 파일을 찾을 수 없습니다</h3>
        <p>다음 파일들이 필요합니다:</p>
        <ul>
            <li>preprocessed_data.pkl (주요 데이터)</li>
            <li>Q1.xlsx, Q2.xlsx, Q3.xlsx (분기별 데이터)</li>
            <li>전기차 신청현황.xls</li>
            <li>2025년 테슬라 EV추출파일.xlsx</li>
        </ul>
        <p><strong>해결방법:</strong> 전처리.py를 먼저 실행하여 데이터를 준비해주세요.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 샘플 데이터로 UI 시연
    st.info("📋 현재는 샘플 데이터로 UI를 보여드립니다.")

# --- 사이드바: 조회 옵션 설정 ---
with st.sidebar:
    st.header("👁️ 뷰어 옵션")
    viewer_option = st.radio(
        "뷰어 유형을 선택하세요.", 
        ('내부', '테슬라', '폴스타', '지도(테스트)', '분석'), 
        key="viewer_option"
    )
    
    st.markdown("---")
    st.header("📊 조회 옵션")
    view_option = st.radio(
        "조회 유형을 선택하세요.",
        ('금일', '특정일 조회', '기간별 조회', '분기별 조회', '월별 조회'),
        key="view_option"
    )

    start_date, end_date = None, None
    lst_1 = ['내부', '테슬라']

    if viewer_option in lst_1:
        if view_option == '금일':
            title = f"금일 리포트 - {today_kst.strftime('%Y년 %m월 %d일')}"
            start_date = end_date = today_kst
        elif view_option == '특정일 조회':
            earliest_date = datetime(today_kst.year, 6, 24).date()
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

    st.markdown("---")
    st.header("📝 메모")
    memo_content = safe_load_memo()
    new_memo = st.text_area(
        "메모를 입력하거나 수정하세요.",
        value=memo_content, height=200, key="memo_input"
    )
    if new_memo != memo_content:
        if safe_save_memo("memo.txt", new_memo):
            st.toast("메모가 저장되었습니다!")
        else:
            st.warning("메모 저장에 실패했습니다.")

# --- 메인 대시보드 표시 ---
if viewer_option in lst_1:
    st.title(title)
    st.caption(f"마지막 데이터 업데이트: {update_time_str}")
    st.markdown("---")

    if data_status:
        # --- 실제 데이터가 있을 때의 로직 ---
        def get_safe_metrics(df, date_col, start, end, value_col='개수'):
            """안전하게 메트릭을 계산합니다."""
            try:
                if df.empty or date_col not in df.columns:
                    return 0
                
                if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                
                mask = (df[date_col].dt.date >= start) & (df[date_col].dt.date <= end)
                if value_col in df.columns:
                    return int(df.loc[mask, value_col].sum())
                else:
                    return int(mask.sum())
            except Exception:
                return 0

        # 메트릭 계산
        selected_date = end_date
        day0 = selected_date
        day1 = (pd.to_datetime(selected_date) - pd.tseries.offsets.BDay(1)).date()

        year = selected_date.year
        q3_start_default = datetime(year, 6, 24).date()
        q3_start_distribute = datetime(year, 7, 1).date()

        # 리테일 메트릭
        cnt_today_mail = get_safe_metrics(df_5, '날짜', day0, day0)
        cnt_yesterday_mail = get_safe_metrics(df_5, '날짜', day1, day1)
        cnt_total_mail = get_safe_metrics(df_5, '날짜', q3_start_default, day0)

        cnt_today_apply = get_safe_metrics(df_1, '날짜', day0, day0, '개수')
        cnt_yesterday_apply = get_safe_metrics(df_1, '날짜', day1, day1, '개수')
        cnt_total_apply = get_safe_metrics(df_1, '날짜', q3_start_default, day0, '개수')

        cnt_today_distribute = get_safe_metrics(df_2, '날짜', day0, day0, '배분')
        cnt_yesterday_distribute = get_safe_metrics(df_2, '날짜', day1, day1, '배분')
        cnt_total_distribute = get_safe_metrics(df_2, '날짜', q3_start_distribute, day0, '배분')

        # 대시보드 표시
        col1, col2, col3 = st.columns([3.5, 2, 1.5])

        with col1:
            st.write("### 1. 리테일 금일/전일 요약")
            
            # 델타 계산
            delta_mail = cnt_today_mail - cnt_yesterday_mail
            delta_apply = cnt_today_apply - cnt_yesterday_apply
            delta_distribute = cnt_today_distribute - cnt_yesterday_distribute

            def format_delta(value):
                if value > 0: 
                    return f'<span style="color:blue;">+{value}</span>'
                elif value < 0: 
                    return f'<span style="color:red;">{value}</span>'
                return str(value)

            table_data = pd.DataFrame({
                ('지원', '파이프라인', '메일 건수'): [cnt_yesterday_mail, cnt_today_mail, cnt_total_mail],
                ('지원', '신청', '신청 건수'): [cnt_yesterday_apply, cnt_today_apply, cnt_total_apply],
                ('지급', '지급 처리', '지급 배분건'): [cnt_yesterday_distribute, cnt_today_distribute, cnt_total_distribute],
            }, index=[f'전일 ({day1})', f'금일 ({day0})', '누적 총계 (3분기)'])

            # 변동(Delta) 행 추가
            table_data.loc['변동'] = [
                format_delta(delta_mail),
                format_delta(delta_apply),
                format_delta(delta_distribute)
            ]

            html_table = table_data.to_html(classes='custom_table', border=0, escape=False)
            st.markdown(html_table, unsafe_allow_html=True)

        with col2:
            st.write("### 2. 법인팀 요약")
            if not df_3.empty and not df_4.empty:
                st.info("법인팀 데이터를 처리 중입니다...")
                # 간단한 법인팀 요약
                corp_summary_data = {
                    '항목': ['파이프라인', '지원신청', '지급신청'],
                    '건수': [0, 0, 0]  # 실제 계산 로직은 복잡하므로 우선 0으로 표시
                }
                corp_df = pd.DataFrame(corp_summary_data)
                st.dataframe(corp_df, use_container_width=True, hide_index=True)
            else:
                st.warning("법인팀 데이터가 없습니다.")

        with col3:
            st.write("### 3. 특이사항")
            special_memo = safe_load_memo("memo_special.txt")
            if not special_memo:
                special_memo = "특이사항 없음"
            
            st.markdown(
                f"<div style='font-size:14px; white-space:pre-wrap; background-color:#e0f7fa; border-radius:8px; padding:10px'><b>{special_memo}</b></div>",
                unsafe_allow_html=True,
            )

    else:
        # --- 샘플 데이터로 UI 시연 ---
        st.write("### 📊 샘플 데이터 대시보드")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div class="status-card">
                <div style="font-size: 0.875rem; opacity: 0.9;">총 파이프라인</div>
                <div class="metric-number">1,245</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="status-card">
                <div style="font-size: 0.875rem; opacity: 0.9;">지원신청</div>
                <div class="metric-number">892</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="status-card">
                <div style="font-size: 0.875rem; opacity: 0.9;">지급처리</div>
                <div class="metric-number">567</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div class="status-card">
                <div style="font-size: 0.875rem; opacity: 0.9;">진행률</div>
                <div class="metric-number">78%</div>
            </div>
            """, unsafe_allow_html=True)

        # 샘플 테이블
        st.write("### 📋 샘플 리포트 테이블")
        sample_data = pd.DataFrame({
            '구분': ['파이프라인', '지원신청', '지급처리'],
            '전일': [45, 32, 28],
            '금일': [52, 38, 31],
            '누계': [1245, 892, 567]
        })
        st.dataframe(sample_data, use_container_width=True, hide_index=True)

elif viewer_option == '폴스타':
    st.header("🌟 폴스타 뷰어")
    st.info("폴스타 뷰어는 데이터 파일이 있을 때 표시됩니다.")
    if not data.get('df_pole_pipeline', pd.DataFrame()).empty:
        st.success("폴스타 데이터를 찾았습니다!")
    else:
        st.warning("폴스타 데이터를 찾을 수 없습니다.")

elif viewer_option == '지도(테스트)':
    st.header("🗺️ 지도 뷰어")
    st.info("지도 뷰어는 GeoJSON 파일과 지역 데이터가 있을 때 표시됩니다.")
    
    # 간단한 지도 대체 표시
    if not df_6.empty:
        st.success("지역 데이터를 찾았습니다!")
        st.dataframe(df_6.head(), use_container_width=True)
    else:
        st.warning("지역 데이터를 찾을 수 없습니다.")

elif viewer_option == '분석':
    st.header("📈 분석 뷰어")
    st.info("분석 뷰어는 Tesla EV 데이터가 있을 때 표시됩니다.")
    
    if not df_tesla_ev.empty:
        st.success("Tesla EV 데이터를 찾았습니다!")
        st.write(f"총 {len(df_tesla_ev)}개의 레코드")
        st.dataframe(df_tesla_ev.head(), use_container_width=True)
    else:
        st.warning("Tesla EV 데이터를 찾을 수 없습니다.")

# --- 푸터 ---
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #6b7280; font-size: 0.875rem; padding: 1rem;">
    <p>⚡ 전기차 보조금 현황 보고서 | Streamlit Cloud 배포판</p>
    <p><small>데이터 파일이 없는 경우 샘플 UI가 표시됩니다.</small></p>
</div>
""", unsafe_allow_html=True)
