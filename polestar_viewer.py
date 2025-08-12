import streamlit as st
import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
import re

def show_polestar_viewer(data, today_kst):
    """폴스타 뷰어 대시보드를 표시합니다."""
    
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
    
    # 월별 집계 계산 함수를 일별 데이터도 포함하도록 수정
    @st.cache_data
    def calculate_daily_summary(pipeline_df, apply_df, selected_date):
        """선택된 날짜의 데이터를 계산"""
        selected_date = pd.to_datetime(selected_date).date()
        
        # 파이프라인 당일 데이터
        pipeline_today = 0
        if not pipeline_df.empty and '날짜' in pipeline_df.columns:
            today_pipeline = pipeline_df[pipeline_df['날짜'].dt.date == selected_date]
            pipeline_today = today_pipeline['파이프라인'].sum()
        
        # 지원신청 당일 데이터
        apply_today = pak_today = cancel_today = unreceived_today = supplement_today = 0
        if not apply_df.empty and '날짜' in apply_df.columns:
            today_apply = apply_df[apply_df['날짜'].dt.date == selected_date]
            apply_today = today_apply['지원신청'].sum()
            pak_today = today_apply['PAK_내부지원'].sum()
            cancel_today = today_apply['접수후취소'].sum()
            unreceived_today = today_apply['미신청건'].sum()
            supplement_today = today_apply['보완'].sum()
        
        # 월 누계 데이터 (선택된 날짜가 속한 월의 1일부터 선택된 날짜까지)
        month_start = selected_date.replace(day=1)
        month_end = selected_date
        
        # 파이프라인 월 누계
        pipeline_month_total = 0
        if not pipeline_df.empty and '날짜' in pipeline_df.columns:
            month_pipeline = pipeline_df[
                (pipeline_df['날짜'].dt.date >= month_start) & 
                (pipeline_df['날짜'].dt.date <= month_end)
            ]
            pipeline_month_total = month_pipeline['파이프라인'].sum()
        
        # 지원신청 월 누계
        apply_month_total = pak_month_total = cancel_month_total = unreceived_total = supplement_total = 0
        if not apply_df.empty and '날짜' in pipeline_df.columns:
            month_apply = apply_df[
                (apply_df['날짜'].dt.date >= month_start) & 
                (apply_df['날짜'].dt.date <= month_end)
            ]
            apply_month_total = month_apply['지원신청'].sum()
            pak_month_total = month_apply['PAK_내부지원'].sum()
            cancel_month_total = month_apply['접수후취소'].sum()
            unreceived_total = month_apply['미신청건'].sum()
            supplement_total = month_apply['보완'].sum()
        
        return {
            'pipeline_today': pipeline_today,
            'pipeline_month_total': pipeline_month_total,
            'apply_today': apply_today,
            'apply_month_total': apply_month_total,
            'unreceived_today': unreceived_today,
            'unreceived_total': unreceived_total,
            'supplement_today': supplement_today,
            'supplement_total': supplement_total,
            'cancel_today': cancel_today,
            'cancel_total': cancel_month_total,
            'pak_month_total': pak_month_total,
            'cancel_month_total': cancel_month_total
        }
    
    # 제목 영역
    st.title(f"📊 폴스타 2025 보고서 - {today_kst.strftime('%Y년 %m월 %d일')}")
    st.markdown("---")
    
    # 현황 요약 (날짜 선택)
    header_col, select_col = st.columns([3, 1])
    with header_col:
        st.subheader("📈 현황 요약")
    with select_col:
        # 오늘 날짜를 기본값으로 설정 (today_kst 대신 datetime.now() 사용)
        from datetime import datetime
        default_date = datetime.now().date()
        
        # 날짜 선택 위젯 (최근 30일 범위에서 선택 가능)
        selected_date = st.date_input(
            '날짜 선택',
            value=default_date,
            min_value=default_date - timedelta(days=30),
            max_value=default_date,
            key='polestar_date'
        )

    # 선택된 날짜의 데이터 계산
    current_date_data = calculate_daily_summary(df_pole_pipeline, df_pole_apply, selected_date)
    
    # 선택된 날짜가 현재 월인지 확인
    selected_month = selected_date.month
    current_month = today_kst.month
    is_current_month_selected = (selected_month == current_month)

    # 상단 요약 카드 - 항상 당일 데이터와 월 누계를 표시
    metric_columns = st.columns(5)
    with metric_columns[0]:
        st.metric(label="파이프라인", value=f"{current_date_data['pipeline_month_total']} 건", delta=f"{current_date_data['pipeline_today']} 건 (당일)")
    with metric_columns[1]:
        st.metric(label="지원신청", value=f"{current_date_data['apply_month_total']} 건", delta=f"{current_date_data['apply_today']} 건 (당일)")
    with metric_columns[2]:
        st.metric(label="미접수", value=f"{current_date_data['unreceived_total']} 건", delta=f"{current_date_data['unreceived_today']} 건 (당일)", delta_color="inverse")
    with metric_columns[3]:
        st.metric(label="보완필요", value=f"{current_date_data['supplement_total']} 건", delta=f"{current_date_data['supplement_today']} 건 (당일)", delta_color="inverse")
    with metric_columns[4]:
        st.metric(label="취소", value=f"{current_date_data['cancel_total']} 건", delta=f"{current_date_data['cancel_today']} 건 (당일)", delta_color="inverse")

    # 상세 내역 부분 - 선택된 날짜에 맞는 데이터 사용
    with st.expander("상세 내역 보기"):
        detail_row_index = ['지원신청', '폴스타 내부지원', '접수 후 취소']
        
        # 선택된 날짜가 속한 월의 데이터 사용
        detailed_second_data = {
            '전월 이월수량': [0, 0, 0],  # 전월 이월수량은 별도 계산 필요
            '당일': [current_date_data['apply_today'], 
                    current_date_data['pak_month_total'] - (current_date_data['apply_month_total'] - current_date_data['apply_today']), 
                    current_date_data['cancel_today']],
            '당월_누계': [current_date_data['apply_month_total'], 
                        current_date_data['pak_month_total'], 
                        current_date_data['cancel_month_total']]
        }
        
        second_detail_df = pd.DataFrame(detailed_second_data, index=detail_row_index)
        second_detail_html = second_detail_df.to_html(classes='custom_table', border=0, escape=False)

        expander_col1, expander_col2 = st.columns(2)
        with expander_col1:
            st.subheader(f"{selected_date.strftime('%Y년 %m월 %d일')} 현황 (상세)")
            st.markdown(second_detail_html, unsafe_allow_html=True)
        with expander_col2:
            st.subheader("미접수/보완 현황 (상세)")

            # 간단한 테이블로 표시
            detail_summary_df = pd.DataFrame({
                '구분': ['미접수', '보완'],
                '수량': [
                    current_date_data['unreceived_total'],
                    current_date_data['supplement_total']
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


# 독립 실행을 위한 메인 함수
def main():
    """폴스타 뷰어를 독립적으로 실행하기 위한 메인 함수"""
    import pickle
    import pytz
    from datetime import datetime
    
    # 페이지 설정
    st.set_page_config(
        page_title="폴스타 뷰어",
        page_icon="📊",
        layout="wide"
    )
    
    # 기본 스타일 추가
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
    </style>
    """, unsafe_allow_html=True)
    
    # 데이터 로딩
    @st.cache_data(ttl=3600)
    def load_data():
        """전처리된 데이터 파일을 로드합니다."""
        try:
            with open("preprocessed_data.pkl", "rb") as f:
                return pickle.load(f)
        except FileNotFoundError:
            st.error("전처리된 데이터 파일(preprocessed_data.pkl)을 찾을 수 없습니다.")
            st.info("먼저 '전처리.py'를 실행하여 데이터 파일을 생성해주세요.")
            return {}
    
    # 시간대 설정
    KST = pytz.timezone('Asia/Seoul')
    today_kst = datetime.now(KST).date()
    
    # 데이터 로드
    data = load_data()
    
    if data:
        # 폴스타 뷰어 실행
        show_polestar_viewer(data, today_kst)
    else:
        st.error("데이터를 로드할 수 없습니다.")
        st.stop()


# 스크립트가 직접 실행될 때만 main 함수 호출
if __name__ == "__main__":
    main()


