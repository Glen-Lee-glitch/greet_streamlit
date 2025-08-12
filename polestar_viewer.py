import streamlit as st
import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
import re
import altair as alt

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
    
    # 오늘 날짜를 기본값으로 설정 (today_kst 대신 datetime.now() 사용)
    from datetime import datetime
    default_date = datetime.now().date()
    
    d_col, margin_col = st.columns([4, 6])
    with d_col:

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
    
    # 전일 데이터 계산
    yesterday_date = selected_date - timedelta(days=1)
    yesterday_data = calculate_daily_summary(df_pole_pipeline, df_pole_apply, yesterday_date)
    
    # 누적 총계 계산 (6월 1일부터 선택된 날짜까지)
    from datetime import datetime as dt
    year = selected_date.year
    cumulative_start = dt(year, 6, 1).date()
    
    # 누적 파이프라인 계산
    total_pipeline = 0
    if not df_pole_pipeline.empty and '날짜' in df_pole_pipeline.columns:
        cumulative_pipeline = df_pole_pipeline[
            (df_pole_pipeline['날짜'].dt.date >= cumulative_start) & 
            (df_pole_pipeline['날짜'].dt.date <= selected_date)
        ]
        total_pipeline = cumulative_pipeline['파이프라인'].sum()
    
    # 누적 지원신청 및 기타 계산
    total_apply = total_unreceived = total_supplement = total_cancel = 0
    if not df_pole_apply.empty and '날짜' in df_pole_apply.columns:
        cumulative_apply = df_pole_apply[
            (df_pole_apply['날짜'].dt.date >= cumulative_start) & 
            (df_pole_apply['날짜'].dt.date <= selected_date)
        ]
        total_apply = cumulative_apply['지원신청'].sum()
        total_unreceived = cumulative_apply['미신청건'].sum()
        total_supplement = cumulative_apply['보완'].sum()
        total_cancel = cumulative_apply['접수후취소'].sum()
    
    # 변동량 계산
    delta_pipeline = current_date_data['pipeline_today'] - yesterday_data['pipeline_today']
    delta_apply = current_date_data['apply_today'] - yesterday_data['apply_today']
    delta_unreceived = current_date_data['unreceived_today'] - yesterday_data['unreceived_today']
    delta_supplement = current_date_data['supplement_today'] - yesterday_data['supplement_today']
    delta_cancel = current_date_data['cancel_today'] - yesterday_data['cancel_today']
    
    def format_delta(value):
        if value > 0: return f'<span style="color:blue;">+{value}</span>'
        elif value < 0: return f'<span style="color:red;">{value}</span>'
        return str(value)

    col1, col2 = st.columns([4, 6])
    with col1:
        st.subheader("📊 폴스타 금일/전일 요약")

        table_data = pd.DataFrame({
            ('지원', '파이프라인', '파이프라인 건수'): [yesterday_data['pipeline_today'], current_date_data['pipeline_today'], total_pipeline],
            ('지원', '신청', '지원신청 건수'): [yesterday_data['apply_today'], current_date_data['apply_today'], total_apply],
            ('지원', '신청', '미접수건'): [yesterday_data['unreceived_today'], current_date_data['unreceived_today'], total_unreceived],
            ('지원', '신청', '보완필요건'): [yesterday_data['supplement_today'], current_date_data['supplement_today'], total_supplement],
            ('지원', '신청', '취소건'): [yesterday_data['cancel_today'], current_date_data['cancel_today'], total_cancel]
        }, index=[f'전일 ({yesterday_date})', f'금일 ({selected_date})', '누적 총계 (8월~)'])
        
        # 변동(Delta) 행 추가
        table_data.loc['변동'] = [
            format_delta(delta_pipeline),
            format_delta(delta_apply),
            format_delta(delta_unreceived),
            format_delta(delta_supplement),
            format_delta(delta_cancel)
        ]
        
        html_table = table_data.to_html(classes='custom_table', border=0, escape=False)
        st.markdown(html_table, unsafe_allow_html=True)
        
    with col2:
        st.subheader("📝 특이사항 메모")

        def load_polestar_memo(path: str):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except FileNotFoundError:
                return None

        def save_polestar_memo(path: str, content: str):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        memo_path = "polestar_memo.txt"
        memo_content = load_polestar_memo(memo_path)

        if memo_content is not None:
            # 파일이 있으면 읽어서 보여주기(수정 불가)
            st.markdown(
                f"<div style='background-color:#e0f7fa; padding:16px; border-radius:8px; margin-bottom:8px; white-space:pre-wrap; font-size:16px;'><b>{memo_content}</b></div>",
                unsafe_allow_html=True,
            )
        else:
            # 파일이 없으면 입력창 제공 및 저장
            memo_input = st.text_area(
                "특이사항 메모를 입력하세요. (저장 시 polestar_memo.txt로 저장됩니다)",
                height=180,
                key="polestar_memo_input"
            )
            if st.button("메모 저장"):
                save_polestar_memo(memo_path, memo_input)

    st.markdown("<hr style='margin-top:1rem;margin-bottom:1rem;'>", unsafe_allow_html=True)

    # 폴스타 월별 요약을 리테일 형태로 변경
    col3, col4 = st.columns([4, 6])
    
    with col3:
        # 폴스타 월별 요약 헤더 및 기간 선택
        header_col, sel_col = st.columns([4, 2])
        with header_col:
            st.write("##### 폴스타 월별 요약")
        with sel_col:
            polestar_period_option = st.selectbox(
                '기간 선택',
                ['3Q', '7월', '8월', '9월', '전체', '1Q', '2Q'] + [f'{m}월' for m in range(1, 13) if m not in [7, 8, 9]],
                index=0,
                key='polestar_period'
            )

        # 기간별 데이터 계산
        year = selected_date.year
        
        # 기본 월별 데이터 (실제 데이터에서 계산해야 할 부분 - 현재는 샘플 데이터 사용)
        monthly_data = {
            '1월': [72, 0, 68, 4],
            '2월': [52, 27, 25, 0],
            '3월': [279, 249, 20, 10],
            '4월': [182, 146, 16, 20],
            '5월': [332, 246, 63, 23],
            '6월': [47, 29, 11, 7],
            '7월': [140, 83, 48, 9],
            '8월': [0, 0, 0, 0],  # 실제 데이터로 대체 필요
            '9월': [0, 0, 0, 0],  # 실제 데이터로 대체 필요
            '10월': [0, 0, 0, 0],
            '11월': [0, 0, 0, 0],
            '12월': [0, 0, 0, 0]
        }
        
        summary_row_index = ['파이프라인', '지원신청', '폴스타 내부지원', '접수 후 취소']
        
        # 기간별 데이터 필터링
        if polestar_period_option == '3Q':
            # 3분기 (7~9월) 표시
            q3_data = {
                '7': monthly_data['7월'],
                '8': monthly_data['8월'],
                '9': monthly_data['9월']
            }
            # 합계 계산
            q3_total = [sum(q3_data[m][i] for m in ['7', '8', '9']) for i in range(4)]
            q3_data['계'] = q3_total
            
            polestar_df = pd.DataFrame(q3_data, index=summary_row_index)
            
        elif polestar_period_option == '1Q':
            # 1분기 (1~3월) 표시
            q1_data = {
                '1': monthly_data['1월'],
                '2': monthly_data['2월'], 
                '3': monthly_data['3월']
            }
            q1_total = [sum(q1_data[m][i] for m in ['1', '2', '3']) for i in range(4)]
            q1_data['계'] = q1_total
            
            polestar_df = pd.DataFrame(q1_data, index=summary_row_index)
            
        elif polestar_period_option == '2Q':
            # 2분기 (4~6월) 표시
            q2_data = {
                '4': monthly_data['4월'],
                '5': monthly_data['5월'],
                '6': monthly_data['6월']
            }
            q2_total = [sum(q2_data[m][i] for m in ['4', '5', '6']) for i in range(4)]
            q2_data['계'] = q2_total
            
            polestar_df = pd.DataFrame(q2_data, index=summary_row_index)
            
        elif polestar_period_option == '전체':
            # 전체 분기별 요약 표시
            q1_total = [sum(monthly_data[f'{m}월'][i] for m in [1, 2, 3]) for i in range(4)]
            q2_total = [sum(monthly_data[f'{m}월'][i] for m in [4, 5, 6]) for i in range(4)]
            q3_total = [sum(monthly_data[f'{m}월'][i] for m in [7, 8, 9]) for i in range(4)]
            total_all = [q1_total[i] + q2_total[i] + q3_total[i] for i in range(4)]
            
            polestar_summary_data = {
                'Q1': q1_total,
                'Q2': q2_total,
                'Q3': q3_total,
                '계': total_all
            }
            polestar_df = pd.DataFrame(polestar_summary_data, index=summary_row_index)
            
        elif polestar_period_option.endswith('월'):
            # 개별 월 선택
            month_num = polestar_period_option[:-1]
            try:
                month_name = f'{int(month_num)}월'
                if month_name in monthly_data:
                    month_data = {month_num: monthly_data[month_name]}
                    polestar_df = pd.DataFrame(month_data, index=summary_row_index)
                else:
                    # 데이터가 없는 월
                    month_data = {month_num: [0, 0, 0, 0]}
                    polestar_df = pd.DataFrame(month_data, index=summary_row_index)
            except ValueError:
                # 잘못된 월 형식
                polestar_df = pd.DataFrame({'선택 월': [0, 0, 0, 0]}, index=summary_row_index)
        
        # HTML 변환 및 스타일링
        html_polestar = polestar_df.to_html(classes='custom_table', border=0, escape=False)
        
        # 리테일과 동일한 스타일링 적용
        if polestar_period_option == '전체':
            # Q1, Q2, Q3 컬럼 헤더 하이라이트
            html_polestar = re.sub(
                r'(<th[^>]*>Q1</th>)',
                r'<th style="background-color: #ffe0b2;">Q1</th>',
                html_polestar
            )
            html_polestar = re.sub(
                r'(<th[^>]*>Q2</th>)',
                r'<th style="background-color: #ffe0b2;">Q2</th>',
                html_polestar
            )
            html_polestar = re.sub(
                r'(<th[^>]*>Q3</th>)',
                r'<th style="background-color: #ffe0b2;">Q3</th>',
                html_polestar
            )
        else:
            # "계" 컬럼 하이라이트 (개별 분기/월 선택 시)
            html_polestar = re.sub(
                r'(<th[^>]*>계</th>)',
                r'<th style="background-color: #ffe0b2;">계</th>',
                html_polestar
            )
            
            # "계" 행의 데이터 셀들도 하이라이트
            html_polestar = re.sub(
                r'(<tr>\s*<th>계</th>)(.*?)(</tr>)',
                lambda m: m.group(1) + re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', m.group(2)) + m.group(3),
                html_polestar,
                flags=re.DOTALL
            )
        
        st.markdown(html_polestar, unsafe_allow_html=True)
    
    with col4:
        # 폴스타 월별 추이 그래프 (지원신청 데이터 기준)
        st.write("##### 폴스타 월별 추이")
        
        # col3에서 사용한 월별 데이터를 그대로 활용 (지원신청 컬럼)
        # 1월~7월까지의 지원신청 데이터
        months_to_show = [2, 3, 4, 5, 6, 7]
        apply_counts = [27, 249, 146, 246, 29, 83]  # 월별 지원신청 수 (monthly_data에서 가져옴)
        
        # 차트용 데이터프레임 생성
        polestar_chart_df = pd.DataFrame(
            {
                '월': months_to_show,
                '지원신청 건수': apply_counts
            }
        )
        polestar_chart_df['월 라벨'] = polestar_chart_df['월'].astype(str) + '월'
        
        # 막대 그래프 (지원신청)
        bar_polestar = alt.Chart(polestar_chart_df).mark_bar(size=25, color='#ff7f0e').encode(
            x=alt.X('월 라벨:N', title='월', sort=[f"{m}월" for m in months_to_show], axis=alt.Axis(labelAngle=0)),
            y=alt.Y('지원신청 건수:Q', title='건수')
        )
        
        # 선 그래프 + 포인트
        line_polestar = alt.Chart(polestar_chart_df).mark_line(color='#d62728', strokeWidth=2).encode(
            x='월 라벨:N',
            y='지원신청 건수:Q'
        )
        point_polestar = alt.Chart(polestar_chart_df).mark_point(color='#d62728', size=60).encode(
            x='월 라벨:N',
            y='지원신청 건수:Q'
        )
        
        # 값 레이블 텍스트
        text_polestar = alt.Chart(polestar_chart_df).mark_text(dy=-10, color='black').encode(
            x='월 라벨:N',
            y='지원신청 건수:Q',
            text=alt.Text('지원신청 건수:Q')
        )
        
        polestar_combo_chart = (bar_polestar + line_polestar + point_polestar + text_polestar).properties(
            title=f"{selected_date.year}년 폴스타 지원신청 추이 (1월~7월)"
        )
        st.altair_chart(polestar_combo_chart, use_container_width=True)


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


