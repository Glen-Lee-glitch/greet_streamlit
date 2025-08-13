"""
전기자동차 총괄현황 대시보드
독립적인 Streamlit 애플리케이션
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# Streamlit 페이지 설정
st.set_page_config(
    page_title="전기자동차 총괄현황 대시보드",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data
def load_ev_data():
    """전기자동차 총괄현황 데이터 로드"""
    try:
        folder_path = 'C:/Users/HP/Desktop/그리트_공유/파일'
        file_path = folder_path + '/총괄현황(전기자동차 승용).xls'
        
        # 데이터 로드
        df = pd.read_excel(file_path, header=3, engine='xlrd')
        
        # 컬럼명 정의
        columns = [
            '시도', '지역', '차종', '접수방법', '공고_요약', '공고_전체', '공고_우선순위', '공고_법인기관', '공고_택시', '공고_일반',
            '접수_요약', '접수_전체', '접수_우선순위', '접수_법인기관', '접수_택시', '접수_일반',
            '잔여_전체', '잔여_일반', '출고_전체', '출고_일반', '출고잔여_요약', '비고'
        ]
        
        if len(df.columns) == len(columns):
            df.columns = columns
        
        # 출고잔여_요약 컬럼 파싱
        def parse_출고잔여_요약(val):
            try:
                if pd.isna(val):
                    return pd.Series([None, None, None])
                parts = str(val).split('\n')
                전체 = parts[0].strip() if len(parts) > 0 else None
                우선순위 = parts[1].replace('(', '').replace(')', '').strip() if len(parts) > 1 else None
                일반 = parts[3].replace('(', '').replace(')', '').strip() if len(parts) > 3 else None
                return pd.Series([전체, 우선순위, 일반])
            except:
                return pd.Series([None, None, None])
        
        if '출고잔여_요약' in df.columns:
            df[['출고잔여_전체', '출고잔여_우선순위', '출고잔여_일반']] = df['출고잔여_요약'].apply(parse_출고잔여_요약)
            df = df.drop(columns=['출고잔여_요약'])
        
        # 숫자형 컬럼들을 numeric으로 변환
        numeric_cols = ['공고_전체', '공고_우선순위', '공고_법인기관', '공고_택시', '공고_일반',
                       '접수_전체', '접수_우선순위', '접수_법인기관', '접수_택시', '접수_일반',
                       '잔여_전체', '잔여_일반', '출고_일반']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
        
    except Exception as e:
        st.error(f"데이터 로드 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

@st.cache_data
def load_ev_status_data():
    """전기차 신청현황 데이터 로드"""
    try:
        folder_path = 'C:/Users/HP/Desktop/그리트_공유/파일'
        file_path = folder_path + '/전기차 신청현황.xls'
        
        # 첫 번째 표: 신청금액 관련 (df_ev_amount)
        df_amount = pd.read_excel(file_path, header=4, nrows=8, engine='xlrd').iloc[:, :6]
        df_amount.columns = ['단계', '신청대수', '신청국비(만원)', '신청지방비(만원)', '신청추가지원금(만원)', '신청금액합산(만원)']
        
        # 숫자형 컬럼 변환
        numeric_cols1 = ['신청대수', '신청국비(만원)', '신청지방비(만원)', '신청추가지원금(만원)', '신청금액합산(만원)']
        for col in numeric_cols1:
            if col in df_amount.columns:
                # 쉼표 제거 후 숫자 변환
                df_amount[col] = df_amount[col].astype(str).str.replace(',', '').replace('nan', '0')
                df_amount[col] = pd.to_numeric(df_amount[col], errors='coerce').fillna(0)
        
        # 두 번째 표: 진행단계별 (df_ev_step)
        df_step = pd.read_excel(file_path, header=17, nrows=1, engine='xlrd').iloc[:1,:]
        df_step.columns = ['차종', '신청', '승인', '출고', '자격부여', '대상자선정', '지급신청', '지급완료', '취소']
        
        # 숫자형 컬럼 변환
        numeric_cols2 = ['신청', '승인', '출고', '자격부여', '대상자선정', '지급신청', '지급완료', '취소']
        for col in numeric_cols2:
            if col in df_step.columns:
                df_step[col] = pd.to_numeric(df_step[col], errors='coerce').fillna(0)
        
        return df_amount, df_step
        
    except Exception as e:
        st.error(f"전기차 신청현황 데이터 로드 중 오류가 발생했습니다: {e}")
        return pd.DataFrame(), pd.DataFrame()

def create_summary_metrics(df):
    """주요 지표 카드 생성"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_announcement = df['공고_전체'].sum()
        st.metric("총 공고 건수", f"{total_announcement:,}")
    
    with col2:
        total_application = df['접수_전체'].sum()
        st.metric("총 접수 건수", f"{total_application:,}")
    
    with col3:
        total_remaining = df['잔여_전체'].sum()
        st.metric("총 잔여 건수", f"{total_remaining:,}")
    
    with col4:
        total_delivery = df['출고_일반'].sum()
        st.metric("총 출고 건수", f"{total_delivery:,}")

def create_region_chart(df):
    """시도별 현황 차트"""
    st.subheader("📍 시도별 전기자동차 현황")
    
    # 시도별 집계
    region_summary = df.groupby('시도').agg({
        '공고_전체': 'sum',
        '접수_전체': 'sum',
        '잔여_전체': 'sum',
        '출고_일반': 'sum'
    }).reset_index()
    
    # 차트 옵션
    chart_type = st.selectbox("차트 유형", ["막대 차트", "파이 차트", "선 차트"])
    metric = st.selectbox("표시할 지표", ["공고_전체", "접수_전체", "잔여_전체", "출고_일반"])
    
    if chart_type == "막대 차트":
        fig = px.bar(region_summary, x='시도', y=metric, 
                    title=f"시도별 {metric}",
                    color=metric,
                    color_continuous_scale='viridis')
        fig.update_layout(xaxis_tickangle=-45)
    
    elif chart_type == "파이 차트":
        fig = px.pie(region_summary, values=metric, names='시도',
                    title=f"시도별 {metric} 비율")
    
    else:  # 선 차트
        fig = px.line(region_summary, x='시도', y=metric,
                     title=f"시도별 {metric} 추이",
                     markers=True)
        fig.update_layout(xaxis_tickangle=-45)
    
    st.plotly_chart(fig, use_container_width=True)

def create_category_analysis(df):
    """접수방법별/차종별 분석"""
    st.subheader("📊 카테고리별 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**접수방법별 현황**")
        if '접수방법' in df.columns:
            method_summary = df.groupby('접수방법')['접수_전체'].sum().reset_index()
            fig1 = px.pie(method_summary, values='접수_전체', names='접수방법',
                         title="접수방법별 비율")
            st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.write("**차종별 현황**")
        if '차종' in df.columns:
            car_summary = df.groupby('차종')['접수_전체'].sum().reset_index()
            fig2 = px.bar(car_summary, x='차종', y='접수_전체',
                         title="차종별 접수 현황",
                         color='접수_전체')
            fig2.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True)

def create_detailed_comparison(df):
    """상세 비교 분석"""
    st.subheader("🔍 상세 비교 분석")
    
    # 상위 지역 선택
    top_regions = df.groupby('시도')['접수_전체'].sum().nlargest(10).index.tolist()
    selected_regions = st.multiselect("비교할 시도 선택", top_regions, default=top_regions[:5])
    
    if selected_regions:
        filtered_df = df[df['시도'].isin(selected_regions)]
        
        # 다중 지표 비교
        comparison_data = filtered_df.groupby('시도').agg({
            '공고_전체': 'sum',
            '접수_전체': 'sum',
            '잔여_전체': 'sum',
            '출고_일반': 'sum'
        }).reset_index()
        
        # 서브플롯 생성
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('공고 현황', '접수 현황', '잔여 현황', '출고 현황'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # 각 서브플롯에 데이터 추가
        metrics = ['공고_전체', '접수_전체', '잔여_전체', '출고_일반']
        positions = [(1,1), (1,2), (2,1), (2,2)]
        
        for metric, (row, col) in zip(metrics, positions):
            fig.add_trace(
                go.Bar(x=comparison_data['시도'], y=comparison_data[metric], name=metric),
                row=row, col=col
            )
        
        fig.update_layout(height=600, showlegend=False, title_text="선택 지역 다중 지표 비교")
        st.plotly_chart(fig, use_container_width=True)

def create_data_table(df):
    """데이터 테이블"""
    st.subheader("📋 상세 데이터")
    
    # 필터링 옵션
    col1, col2 = st.columns(2)
    
    with col1:
        selected_sido = st.multiselect("시도 필터", df['시도'].unique())
    
    with col2:
        if '차종' in df.columns:
            selected_car = st.multiselect("차종 필터", df['차종'].unique())
        else:
            selected_car = []
    
    # 데이터 필터링
    filtered_df = df.copy()
    if selected_sido:
        filtered_df = filtered_df[filtered_df['시도'].isin(selected_sido)]
    if selected_car and '차종' in df.columns:
        filtered_df = filtered_df[filtered_df['차종'].isin(selected_car)]
    
    # 표시할 컬럼 선택
    display_cols = st.multiselect(
        "표시할 컬럼 선택",
        df.columns.tolist(),
        default=['시도', '지역', '차종', '공고_전체', '접수_전체', '잔여_전체', '출고_일반']
    )
    
    if display_cols:
        st.dataframe(filtered_df[display_cols], use_container_width=True)
        
        # 다운로드 버튼
        csv = filtered_df[display_cols].to_csv(index=False)
        st.download_button(
            label="CSV 다운로드",
            data=csv,
            file_name="ev_overview_data.csv",
            mime="text/csv"
        )

def create_ev_status_dashboard(df_amount, df_step):
    """전기차 신청현황 대시보드"""
    st.header("⚡ 전기차 신청현황 분석")
    
    # 신청현황 요약 메트릭
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_applications = df_step['신청'].sum() if not df_step.empty else 0
        st.metric("총 신청 건수", f"{total_applications:,}")
    
    with col2:
        total_approved = df_step['승인'].sum() if not df_step.empty else 0
        approval_rate = (total_approved / total_applications * 100) if total_applications > 0 else 0
        st.metric("총 승인 건수", f"{total_approved:,}", f"승인률: {approval_rate:.1f}%")
    
    with col3:
        total_delivered = df_step['출고'].sum() if not df_step.empty else 0
        delivery_rate = (total_delivered / total_approved * 100) if total_approved > 0 else 0
        st.metric("총 출고 건수", f"{total_delivered:,}", f"출고율: {delivery_rate:.1f}%")
    
    with col4:
        total_completed = df_step['지급완료'].sum() if not df_step.empty else 0
        completion_rate = (total_completed / total_delivered * 100) if total_delivered > 0 else 0
        st.metric("지급완료 건수", f"{total_completed:,}", f"완료율: {completion_rate:.1f}%")
    
    st.markdown("---")
    
    # 두 개의 컬럼으로 차트 배치
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 단계별 신청금액 현황")
        
        if not df_amount.empty:
            # 차트 타입 선택
            chart_type = st.selectbox("차트 유형", ["막대 차트", "파이 차트"], key="amount_chart")
            metric_choice = st.selectbox("표시할 지표", 
                                       ["신청대수", "신청국비(만원)", "신청지방비(만원)", "신청추가지원금(만원)", "신청금액합산(만원)"],
                                       key="amount_metric")
            
            if chart_type == "막대 차트":
                fig1 = px.bar(df_amount, x='단계', y=metric_choice,
                             title=f"단계별 {metric_choice}",
                             color=metric_choice,
                             color_continuous_scale='Blues')
                fig1.update_layout(xaxis_tickangle=-45)
            else:
                fig1 = px.pie(df_amount, values=metric_choice, names='단계',
                             title=f"단계별 {metric_choice} 비율")
            
            st.plotly_chart(fig1, use_container_width=True)
            
            # 데이터 테이블
            st.write("**상세 데이터**")
            st.dataframe(df_amount, use_container_width=True)
    
    with col2:
        st.subheader("🔄 진행단계별 현황")
        
        if not df_step.empty and len(df_step) > 0:
            # 진행단계 데이터 준비
            process_cols = ['신청', '승인', '출고', '자격부여', '대상자선정', '지급신청', '지급완료', '취소']
            process_data = []
            
            for col in process_cols:
                if col in df_step.columns:
                    value = df_step[col].iloc[0] if not pd.isna(df_step[col].iloc[0]) else 0
                    process_data.append({'단계': col, '건수': value})
            
            process_df = pd.DataFrame(process_data)
            
            # 프로세스 플로우 차트
            fig2 = px.funnel(process_df, x='건수', y='단계',
                           title="신청 프로세스 플로우",
                           color='건수')
            st.plotly_chart(fig2, use_container_width=True)
            
            # 원형 차트로 비율 표시
            fig3 = px.pie(process_df, values='건수', names='단계',
                         title="각 단계별 비율")
            st.plotly_chart(fig3, use_container_width=True)
    
    # 추가 분석 섹션
    st.markdown("---")
    st.subheader("📊 종합 분석")
    
    # 전체 프로세스 효율성 차트
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**프로세스 변환률**")
        if not df_step.empty:
            conversion_data = []
            base_value = df_step['신청'].iloc[0] if '신청' in df_step.columns else 0
            
            for col in ['승인', '출고', '지급완료']:
                if col in df_step.columns and base_value > 0:
                    value = df_step[col].iloc[0] if not pd.isna(df_step[col].iloc[0]) else 0
                    rate = (value / base_value) * 100
                    conversion_data.append({'단계': col, '변환률(%)': rate})
            
            if conversion_data:
                conversion_df = pd.DataFrame(conversion_data)
                fig4 = px.bar(conversion_df, x='단계', y='변환률(%)',
                             title="신청 대비 각 단계 변환률",
                             color='변환률(%)',
                             color_continuous_scale='RdYlGn')
                st.plotly_chart(fig4, use_container_width=True)
    
    with col2:
        st.write("**금액별 효율성**")
        if not df_amount.empty:
            # 단계별 평균 단가 계산
            efficiency_data = []
            for _, row in df_amount.iterrows():
                if row['신청대수'] > 0:
                    avg_amount = row['신청금액합산(만원)'] / row['신청대수']
                    efficiency_data.append({
                        '단계': row['단계'],
                        '평균단가(만원)': avg_amount
                    })
            
            if efficiency_data:
                efficiency_df = pd.DataFrame(efficiency_data)
                fig5 = px.line(efficiency_df, x='단계', y='평균단가(만원)',
                              title="단계별 평균 지원금액",
                              markers=True)
                fig5.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig5, use_container_width=True)

def main():
    """메인 애플리케이션"""
    st.title("🚗 전기자동차 총괄현황 대시보드")
    st.markdown("---")
    
    # 데이터 로드
    df = load_ev_data()
    df_amount, df_step = load_ev_status_data()
    
    if df.empty:
        st.error("총괄현황 데이터를 로드할 수 없습니다. 파일 경로를 확인해주세요.")
        return
    
    # 사이드바
    st.sidebar.title("🎛️ 대시보드 컨트롤")
    st.sidebar.markdown("### 데이터 정보")
    st.sidebar.info(f"총 {len(df)}개 지역의 데이터")
    st.sidebar.info(f"마지막 업데이트: 2025년")
    
    # 페이지 선택 (신청현황 탭 추가)
    page = st.sidebar.selectbox(
        "페이지 선택",
        ["개요", "지역별 분석", "카테고리별 분석", "상세 비교", "신청현황 분석", "데이터 테이블"]
    )
    
    # 신청현황 분석 페이지가 아닌 경우 기존 총괄현황 지표 표시
    if page != "신청현황 분석":
        create_summary_metrics(df)
        st.markdown("---")
    
    # 선택된 페이지에 따른 컨텐츠 표시
    if page == "개요":
        st.header("📈 전기자동차 현황 개요")
        
        # 전체 현황 차트
        col1, col2 = st.columns(2)
        
        with col1:
            # 시도별 상위 10개 지역
            top_regions = df.groupby('시도')['접수_전체'].sum().nlargest(10)
            fig1 = px.bar(x=top_regions.index, y=top_regions.values,
                         title="접수 건수 상위 10개 시도",
                         labels={'x': '시도', 'y': '접수 건수'})
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # 공고 vs 접수 비교
            comparison_df = df.groupby('시도')[['공고_전체', '접수_전체']].sum().reset_index()
            fig2 = px.scatter(comparison_df, x='공고_전체', y='접수_전체',
                             text='시도', title="공고 대비 접수 현황",
                             labels={'공고_전체': '공고 건수', '접수_전체': '접수 건수'})
            fig2.update_traces(textposition="top center")
            st.plotly_chart(fig2, use_container_width=True)
    
    elif page == "지역별 분석":
        create_region_chart(df)
    
    elif page == "카테고리별 분석":
        create_category_analysis(df)
    
    elif page == "상세 비교":
        create_detailed_comparison(df)
    
    elif page == "신청현황 분석":
        # 새로운 전기차 신청현황 탭
        if df_amount.empty and df_step.empty:
            st.error("전기차 신청현황 데이터를 로드할 수 없습니다. 파일 경로를 확인해주세요.")
        else:
            create_ev_status_dashboard(df_amount, df_step)
    
    elif page == "데이터 테이블":
        create_data_table(df)

if __name__ == "__main__":
    main()
