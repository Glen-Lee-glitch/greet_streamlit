"""
전기차 보조금 현황 대시보드 (longrange.gg 스타일)
깔끔한 테이블 중심의 직관적인 인터페이스
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

# Streamlit 페이지 설정
st.set_page_config(
    page_title="전기차 보조금 현황",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS 스타일링 (longrange.gg 스타일 참고)
st.markdown("""
<style>
    .main-header {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #374151;
        margin: 1.5rem 0 1rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: #1f2937;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #cbd5e1;
        height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .status-table {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        margin: 1rem 0;
    }
    .highlight-number {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e40af;
    }
    .region-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .footer-info {
        text-align: center;
        color: #6b7280;
        font-size: 0.875rem;
        margin-top: 2rem;
        padding: 1rem;
        border-top: 1px solid #e5e7eb;
    }
</style>
""", unsafe_allow_html=True)



@st.cache_data
def load_tesla_data():
    """테슬라 EV 데이터 로드"""
    try:
        tesla_file = '2025년 테슬라 EV추출파일.xlsx'
        df_tesla = pd.read_excel(tesla_file, engine='openpyxl')
        return df_tesla
    except Exception as e:
        st.error(f"테슬라 데이터 로드 오류: {e}")
        return pd.DataFrame()

@st.cache_data
def load_all_data():
    """모든 데이터 로드"""
    try:
        folder_path = 'C:/Users/HP/Desktop/그리트_공유/파일'
        
        # 총괄현황 데이터
        overview_file = folder_path + '/총괄현황(전기자동차 승용).xls'
        df_overview = pd.read_excel(overview_file, header=3, engine='xlrd')
        
        columns = [
            '시도', '지역', '차종', '접수방법', '공고_요약', '공고_전체', '공고_우선순위', '공고_법인기관', '공고_택시', '공고_일반',
            '접수_요약', '접수_전체', '접수_우선순위', '접수_법인기관', '접수_택시', '접수_일반',
            '잔여_전체', '잔여_일반', '출고_전체', '출고_일반', '출고잔여_요약', '비고'
        ]
        
        if len(df_overview.columns) == len(columns):
            df_overview.columns = columns
        
        # 숫자형 컬럼 변환
        numeric_cols = ['공고_전체', '공고_우선순위', '공고_일반', '접수_전체', '접수_우선순위', '접수_일반',
                    '잔여_전체', '잔여_일반', '출고_일반']
        
        for col in numeric_cols:
            if col in df_overview.columns:
                df_overview[col] = pd.to_numeric(df_overview[col], errors='coerce').fillna(0)
        
        # 신청현황 데이터
        status_file = folder_path + '/전기차 신청현황.xls'
        df_amount = pd.read_excel(status_file, header=4, nrows=8, engine='xlrd').iloc[:, :6]
        df_amount.columns = ['단계', '신청대수', '신청국비(만원)', '신청지방비(만원)', '신청추가지원금(만원)', '신청금액합산(만원)']
        
        df_step = pd.read_excel(status_file, header=17, nrows=1, engine='xlrd').iloc[:1,:]
        df_step.columns = ['차종', '신청', '승인', '출고', '자격부여', '대상자선정', '지급신청', '지급완료', '취소']
        
        # 숫자형 변환
        amount_cols = ['신청대수', '신청국비(만원)', '신청지방비(만원)', '신청추가지원금(만원)', '신청금액합산(만원)']
        for col in amount_cols:
            if col in df_amount.columns:
                df_amount[col] = df_amount[col].astype(str).str.replace(',', '').replace('nan', '0')
                df_amount[col] = pd.to_numeric(df_amount[col], errors='coerce').fillna(0)
        
        step_cols = ['신청', '승인', '출고', '자격부여', '대상자선정', '지급신청', '지급완료', '취소']
        for col in step_cols:
            if col in df_step.columns:
                df_step[col] = pd.to_numeric(df_step[col], errors='coerce').fillna(0)
        
        return df_overview, df_amount, df_step
        
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def create_main_status_table(df_step):
    """메인 현황 테이블 (longrange.gg 스타일)"""
    st.markdown('<div class="sub-header">⚡ 접수, 출고 현황</div>', unsafe_allow_html=True)
    st.markdown('<p style="color: #6b7280; font-size: 0.875rem;">(): 전일 대비 변동량</p>', unsafe_allow_html=True)
    
    if not df_step.empty:
        # 메인 현황 데이터 준비
        total_count = df_step['신청'].iloc[0] if '신청' in df_step.columns else 0
        received = df_step['접수_완료'].iloc[0] if '접수_완료' in df_step.columns else df_step['승인'].iloc[0]
        delivered = df_step['출고'].iloc[0] if '출고' in df_step.columns else 0
        remaining = total_count - delivered if total_count > delivered else 0
        
        # 테이블 데이터
        status_data = {
            '대상': ['전체'],
            '총 대수': [f"{total_count:,}"],
            '접수 완료': [f"{received:,} (-)"],
            '출고 완료': [f"{delivered:,} (-)"],
            '남은 대수': [f"{remaining:,}"]
        }
        
        status_df = pd.DataFrame(status_data)
        
        # 스타일링된 테이블
        st.markdown('<div class="status-table">', unsafe_allow_html=True)
        st.dataframe(
            status_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "대상": st.column_config.TextColumn("대상", width="small"),
                "총 대수": st.column_config.TextColumn("총 대수", width="medium"),
                "접수 완료": st.column_config.TextColumn("접수 완료", width="medium"),
                "출고 완료": st.column_config.TextColumn("출고 완료", width="medium"),
                "남은 대수": st.column_config.TextColumn("남은 대수", width="medium"),
            }
        )
        st.markdown('</div>', unsafe_allow_html=True)

def create_region_overview_table(df_overview):
    """지역별 보조금 현황 테이블"""
    st.markdown('<div class="sub-header">🗺️ 지역별 전기차 보조금 현황</div>', unsafe_allow_html=True)
    
    if not df_overview.empty:
        # 지역별 집계
        region_summary = df_overview.groupby('지역').agg({
            '공고_전체': 'sum',
            '접수_전체': 'sum',
            '잔여_전체': 'sum',
            '출고_일반': 'sum'
        }).round(0).astype(int)
        
        # 비율 계산
        region_summary['접수율(%)'] = ((region_summary['접수_전체'] / region_summary['공고_전체']) * 100).round(1)
        region_summary['출고율(%)'] = ((region_summary['출고_일반'] / region_summary['접수_전체']) * 100).round(1)
        
        # 결측값 처리
        region_summary = region_summary.fillna(0)
        
        # 상위 10개 지역만 표시
        region_summary = region_summary.sort_values('접수_전체', ascending=False).head(10).reset_index()
        
        # 컬럼명 한글화
        region_summary.columns = ['지역', '총 공고', '접수 완료', '남은 대수', '출고 완료', '접수율(%)', '출고율(%)']
        
        st.markdown('<div class="status-table">', unsafe_allow_html=True)
        st.dataframe(
            region_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "지역": st.column_config.TextColumn("지역", width="small"),
                "총 공고": st.column_config.NumberColumn("총 공고", format="%d"),
                "접수 완료": st.column_config.NumberColumn("접수 완료", format="%d"),
                "남은 대수": st.column_config.NumberColumn("남은 대수", format="%d"),
                "출고 완료": st.column_config.NumberColumn("출고 완료", format="%d"),
                "접수율(%)": st.column_config.NumberColumn("접수율(%)", format="%.1f%%"),
                "출고율(%)": st.column_config.NumberColumn("출고율(%)", format="%.1f%%"),
            }
        )
        st.markdown('</div>', unsafe_allow_html=True)

def create_amount_breakdown_table(df_amount):
    """금액별 현황 테이블"""
    st.markdown('<div class="sub-header">💰 단계별 지원금액 현황</div>', unsafe_allow_html=True)
    
    if not df_amount.empty:
        # 데이터 정리
        display_df = df_amount.copy()
        
        # 숫자 포맷팅
        numeric_columns = ['신청대수', '신청국비(만원)', '신청지방비(만원)', '신청추가지원금(만원)', '신청금액합산(만원)']
        for col in numeric_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) and x != 0 else "0")
        
        st.markdown('<div class="status-table">', unsafe_allow_html=True)
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "단계": st.column_config.TextColumn("단계", width="medium"),
                "신청대수": st.column_config.TextColumn("신청대수", width="small"),
                "신청국비(만원)": st.column_config.TextColumn("국비(만원)", width="medium"),
                "신청지방비(만원)": st.column_config.TextColumn("지방비(만원)", width="medium"),
                "신청추가지원금(만원)": st.column_config.TextColumn("추가지원금(만원)", width="medium"),
                "신청금액합산(만원)": st.column_config.TextColumn("합계(만원)", width="medium"),
            }
        )
        st.markdown('</div>', unsafe_allow_html=True)

def create_tesla_comparison_table(df_overview, df_tesla):
    """테슬라 대비 전체 접수 현황 비교 테이블"""
    st.markdown('<div class="sub-header">🚗 테슬라 vs 전체 접수 현황 비교</div>', unsafe_allow_html=True)
    
    if not df_overview.empty and not df_tesla.empty:
        # 전체 접수 현황 (지역별)
        total_by_region = df_overview.groupby('지역')['접수_전체'].sum().reset_index()
        total_by_region.columns = ['지역', '전체_접수']
        
        # 테슬라 접수 현황 (지역구분별)
        if '지역구분' in df_tesla.columns:
            tesla_by_region = df_tesla['지역구분'].value_counts().reset_index()
            tesla_by_region.columns = ['지역', '테슬라_접수']
        else:
            st.warning("테슬라 파일에 '지역구분' 컬럼이 없습니다. 컬럼명을 확인해주세요.")
            return
        
        # 두 데이터 병합
        comparison_df = pd.merge(total_by_region, tesla_by_region, on='지역', how='outer').fillna(0)
        
        # 테슬라 점유율 계산
        comparison_df['테슬라_점유율(%)'] = (comparison_df['테슬라_접수'] / comparison_df['전체_접수'] * 100).round(2)
        comparison_df['테슬라_점유율(%)'] = comparison_df['테슬라_점유율(%)'].replace([np.inf, -np.inf], 0)
        
        # 상위 15개 지역만 표시 (테슬라 접수 기준)
        comparison_df = comparison_df.sort_values('테슬라_접수', ascending=False).head(15)
        
        # 숫자 포맷팅
        comparison_df['전체_접수'] = comparison_df['전체_접수'].astype(int)
        comparison_df['테슬라_접수'] = comparison_df['테슬라_접수'].astype(int)
        
        st.markdown('<div class="status-table">', unsafe_allow_html=True)
        st.dataframe(
            comparison_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "지역": st.column_config.TextColumn("지역", width="medium"),
                "전체_접수": st.column_config.NumberColumn("전체 접수", format="%d"),
                "테슬라_접수": st.column_config.NumberColumn("테슬라 접수", format="%d"),
                "테슬라_점유율(%)": st.column_config.NumberColumn("테슬라 점유율(%)", format="%.2f%%"),
            }
        )
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("비교할 데이터가 없습니다.")


def create_simple_charts(df_overview, df_step):
    """간단한 시각화"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="sub-header">📊 상위 지역 현황</div>', unsafe_allow_html=True)
        if not df_overview.empty:
            top_regions = df_overview[df_overview['지역'] != '한국환경공단'].groupby('지역')['접수_전체'].sum().nlargest(8) 
            
            fig = px.bar(
                x=top_regions.values,
                y=top_regions.index,
                orientation='h',
                title="접수 건수 상위 8개 지역",
                labels={'x': '접수 건수', 'y': '지역'},
                color=top_regions.values,
                color_continuous_scale='viridis'
            )
            fig.update_layout(
                height=400,
                showlegend=False,
                title_font_size=16,
                title_x=0.5
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown('<div class="sub-header">🔄 진행 단계별 현황</div>', unsafe_allow_html=True)
        if not df_step.empty:
            # 주요 단계만 표시
            key_stages = ['신청', '승인', '출고', '지급완료']
            stage_data = []
            
            for stage in key_stages:
                if stage in df_step.columns:
                    value = df_step[stage].iloc[0] if not pd.isna(df_step[stage].iloc[0]) else 0
                    stage_data.append({'단계': stage, '건수': value})
            
            if stage_data:
                stage_df = pd.DataFrame(stage_data)
                fig = px.funnel(
                    stage_df, 
                    x='건수', 
                    y='단계',
                    title="신청 프로세스 현황",
                    color='건수'
                )
                fig.update_layout(
                    height=400,
                    title_font_size=16,
                    title_x=0.5
                )
                st.plotly_chart(fig, use_container_width=True)

def create_tesla_charts(df_overview, df_tesla):
    """테슬라 관련 시각화"""
    st.header("📊 지역별 테슬라 vs 전체 접수 현황")
    if not df_overview.empty and not df_tesla.empty and '지역구분' in df_tesla.columns:
        # 전체 접수 현황 (지역별) - '한국환경공단' 제외
        total_by_region = df_overview[df_overview['지역'] != '한국환경공단'].groupby('지역')['접수_전체'].sum().reset_index()
        total_by_region.columns = ['지역', '전체_접수']

        # 테슬라 접수 현황 (지역구분별) - '한국환경공단' 제외
        tesla_by_region = df_tesla[df_tesla['지역구분'] != '한국환경공단']['지역구분'].value_counts().reset_index()
        tesla_by_region.columns = ['지역', '테슬라_접수']

        # 두 데이터 병합
        comparison_df = pd.merge(total_by_region, tesla_by_region, on='지역', how='left').fillna(0)

        # 상위 10개 지역만 선택 (전체 접수 기준)
        top_regions = comparison_df.nlargest(10, '전체_접수')
        
        fig = go.Figure()

        # 전체 접수 막대 (배경)
        fig.add_trace(go.Bar(
            x=top_regions['지역'],
            y=top_regions['전체_접수'],
            name='전체 접수',
            marker_color='lightblue',
            opacity=0.7
        ))

        # 테슬라 접수 막대 (전면)
        fig.add_trace(go.Bar(
            x=top_regions['지역'],
            y=top_regions['테슬라_접수'],
            name='테슬라 접수',
            marker_color='#1e40af'
        ))

        fig.update_layout(
            title="지역별 테슬라 접수 현황 (상위 10개 지역)",
            xaxis_title="지역",
            yaxis_title="접수 건수",
            barmode='overlay',  # 막대를 겹치게 표시
            height=500,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)

def parse_delivery_data(delivery_string):
    """출고 데이터 문자열을 파싱하여 전체와 택시 값을 추출"""
    if pd.isna(delivery_string) or delivery_string == '':
        return 0, 0
    
    try:
        # 줄바꿈으로 분리
        lines = str(delivery_string).split('\n')
        
        # 전체 값 (첫 번째 줄)
        total_value = int(lines[0].strip()) if len(lines) > 0 else 0
        
        # 택시 값 (네 번째 줄, 괄호 제거)
        taxi_value = 0
        if len(lines) > 3:
            taxi_line = lines[3].strip()
            if taxi_line.startswith('(') and taxi_line.endswith(')'):
                taxi_value = int(taxi_line[1:-1])
        
        return total_value, taxi_value
    except:
        return 0, 0

def create_total_overview_dashboard_1(df_step, df_overview, df_amount, df_tesla):
    """총 현황 대시보드 (왼쪽 영역)"""
    st.subheader("📊 테슬라 전국 총 현황")
    
    # 전체 접수 완료 계산 (모든 지역의 접수_전체 - 접수_택시)
    total_received_all = 0
    if not df_overview.empty:
        # 한국환경공단 제외하고 계산
        filtered_overview = df_overview[df_overview['지역'] != '한국환경공단']
        total_received_all = int(filtered_overview['접수_전체'].sum() - filtered_overview['접수_택시'].sum())
    
    # 출고 데이터 파싱
    total_delivery = 0
    taxi_delivery = 0
    if not df_overview.empty and '출고_전체' in df_overview.columns:
        # 한국환경공단 제외하고 모든 지역의 출고 데이터 합계
        filtered_overview = df_overview[df_overview['지역'] != '한국환경공단']
        for delivery_data in filtered_overview['출고_전체']:
            total, taxi = parse_delivery_data(delivery_data)
            total_delivery += total
            taxi_delivery += taxi
    
    delivery_excluding_taxi = total_delivery - taxi_delivery
    
    # 주요 지표 카드 (2x2 형태)
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card" style="height: 100px;">
            <div style="font-size: 0.75rem; opacity: 0.9;">전체 신청</div>
            <div style="font-size: 1.8rem; font-weight: 700; color: #1e40af;">{total_received_all:,}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="metric-card" style="height: 100px;">
            <div style="font-size: 0.75rem; opacity: 0.9;">전체 출고</div>
            <div style="font-size: 1.8rem; font-weight: 700; color: #1e40af;">{delivery_excluding_taxi:,}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("<br>" * 1, unsafe_allow_html=True)
    # 두 번째 줄
    col3, col4 = st.columns(2)
    
    with col3:
        tesla_applications = df_step['신청'].iloc[0] if not df_step.empty and '신청' in df_step.columns else 0
        st.markdown(f"""
        <div class="metric-card" style="height: 100px;">
            <div style="font-size: 0.75rem; opacity: 0.9;">테슬라 총 신청</div>
            <div style="font-size: 1.8rem; font-weight: 700; color: #1e40af;">{tesla_applications:,}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        tesla_delivered = df_step['출고'].iloc[0] if not df_step.empty and '출고' in df_step.columns else 0
        st.markdown(f"""
        <div class="metric-card" style="height: 100px;">
            <div style="font-size: 0.75rem; opacity: 0.9;">테슬라 출고</div>
            <div style="font-size: 1.8rem; font-weight: 700; color: #1e40af;">{tesla_delivered:,}</div>
        </div>
        """, unsafe_allow_html=True)
    
def create_total_overview_dashboard_2(df_step, df_overview, df_amount, df_tesla):
    # 테슬라 현황 (간소화)
    if not df_tesla.empty:
        st.subheader("🚗 테슬라 현황")
        total_tesla = len(df_tesla)
        total_all = df_overview['접수_전체'].sum() if not df_overview.empty else 0
        tesla_share = (total_tesla / total_all * 100) if total_all > 0 else 0
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("테슬라 접수(취소 포함)", f"{total_tesla:,}건")
        with col2:
            st.metric("점유율", f"{tesla_share:.1f}%")
    
def create_total_overview_dashboard_3(df_step, df_overview, df_amount, df_tesla):
    # 프로세스 현황 차트 (간소화)
    if not df_step.empty:
        st.subheader("🔄 진행 단계")
        key_stages = ['신청', '승인', '출고', '지급완료']
        stage_data = []
        
        for stage in key_stages:
            if stage in df_step.columns:
                value = df_step[stage].iloc[0] if not pd.isna(df_step[stage].iloc[0]) else 0
                stage_data.append({'단계': stage, '건수': value})
        
        if stage_data:
            stage_df = pd.DataFrame(stage_data)
            fig = px.funnel(
                stage_df, 
                x='건수', 
                y='단계',
                title="신청 프로세스 현황",
                color='건수'
            )
            fig.update_layout(
                height=300, 
                title_font_size=14
            )
            # 데이터 레이블 형식 변경 (천 단위 구분 쉼표 사용, k 표기 제거)
            fig.update_traces(
                textinfo='label+value',
                texttemplate='%{value:,.0f}',
                textfont_size=12
            )
            st.plotly_chart(fig, use_container_width=True)

def create_regional_dashboard_top_1(df_overview, df_tesla):
    """지역별 대시보드 (오른쪽 영역) - 지역 선택 및 상단 메트릭, 선택된 지역 반환"""
    st.subheader("🗺️ 지역별 상세 현황")
    st.info("💡 **테슬라가 아닌 모든 전기차 보조금 현황입니다**")

    selected_region = None
    received_final = 0  # 하단에서 활용할 변수도 반환
    if not df_overview.empty:
        # '한국환경공단' 제외한 지역 목록
        regions = df_overview[df_overview['지역'] != '한국환경공단']['지역'].unique()
        selected_region = st.selectbox("📍 지역 선택", regions, index=0)

        # 선택된 지역의 상세 정보
        region_data = df_overview[df_overview['지역'] == selected_region]

        if not region_data.empty:
            # 새로운 집계 방식: 전체 - 택시
            total_announcement = int(region_data['공고_전체'].sum())
            taxi_announcement = int(region_data['공고_택시'].sum())
            announcement_final = total_announcement - taxi_announcement

            total_received = int(region_data['접수_전체'].sum())
            taxi_received = int(region_data['접수_택시'].sum())
            received_final = total_received - taxi_received

            remaining = int(region_data['잔여_전체'].sum())

            
            top_col1, top_col2 = st.columns([6.5,3.5])
            
            with top_col1:
                st.subheader(f"🚗 {selected_region} 총 현황")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(
                        f"""
                        <div style='text-align:center;'>
                            <span style='font-size:1.2rem; font-weight:bold;'>총 공고</span><br>
                            <span style='font-size:2rem; font-weight:bold; color:#1e40af'>{announcement_final:,}건</span>
                        </div>
                        """, unsafe_allow_html=True
                    )
                with col2:
                    st.markdown(
                        f"""
                        <div style='text-align:center;'>
                            <span style='font-size:1.2rem; font-weight:bold;'>접수 완료</span><br>
                            <span style='font-size:2rem; font-weight:bold; color:#1e40af'>{received_final:,}건</span>
                        </div>
                        """, unsafe_allow_html=True
                    )
                with col3:
                    st.markdown(
                        f"""
                        <div style='text-align:center;'>
                            <span style='font-size:1.2rem; font-weight:bold;'>남은 대수</span><br>
                            <span style='font-size:2rem; font-weight:bold; color:#1e40af'>{remaining:,}건</span>
                        </div>
                        """, unsafe_allow_html=True
                    )

            with top_col2:
                # 해당 지역 테슬라 현황
                if (
                    selected_region is not None
                    and not df_tesla.empty
                    and '지역구분' in df_tesla.columns
                ):
                    tesla_count = len(df_tesla[df_tesla['지역구분'] == selected_region])
                    tesla_share_region = (tesla_count / received_final * 100) if received_final > 0 else 0

                    st.subheader(f"🚗 {selected_region} 테슬라 현황")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(
                            f"""
                            <div style='text-align:center;'>
                                <span style='font-size:1.1rem; font-weight:bold;'>테슬라 접수</span><br>
                                <span style='font-size:1.7rem; font-weight:bold; color:#e11d48'>{tesla_count:,}건</span>
                            </div>
                            """, unsafe_allow_html=True
                        )
                    with col2:
                        st.markdown(
                            f"""
                            <div style='text-align:center;'>
                                <span style='font-size:1.1rem; font-weight:bold;'>지역 점유율</span><br>
                                <span style='font-size:1.7rem; font-weight:bold; color:#e11d48'>{tesla_share_region:.1f}%</span>
                            </div>
                            """, unsafe_allow_html=True
                        )

    return selected_region, received_final

def render_region_tesla_summary(selected_region, received_final, df_tesla):
	st.subheader(f"🚗 {selected_region} 테슬라 현황")
	if (
		selected_region is None
		or df_tesla.empty
		or '지역구분' not in df_tesla.columns
	):
		st.info("표시할 데이터가 없습니다.")
		return

	tesla_count = len(df_tesla[df_tesla['지역구분'] == selected_region])
	tesla_share_region = (tesla_count / received_final * 100) if received_final > 0 else 0.0

	col1, col2 = st.columns(2)
	with col1:
		st.metric("테슬라 접수", f"{tesla_count:,}건")
	with col2:
		st.metric("지역 점유율", f"{tesla_share_region:.1f}%")

def render_region_total_vs_tesla_chart(df_overview, df_tesla):
	st.subheader("📊 지역별 총 접수 vs 테슬라 접수")
	if df_overview.empty or df_tesla.empty or '지역구분' not in df_tesla.columns:
		st.info("표시할 데이터가 없습니다.")
		return

	total_by_region = df_overview[df_overview['지역'] != '한국환경공단'] \
		.groupby('지역')['접수_전체'].sum().reset_index()
	total_by_region['total_excluding_taxi'] = df_overview[df_overview['지역'] != '한국환경공단'] \
		.groupby('지역')['접수_택시'].sum().values
	total_by_region['접수_택시제외'] = total_by_region['접수_전체'] - total_by_region['total_excluding_taxi']

	tesla_by_region = df_tesla[df_tesla['지역구분'] != '한국환경공단']['지역구분'] \
		.value_counts().reset_index()
	tesla_by_region.columns = ['지역', '테슬라_접수']

	comparison_df = pd.merge(
		total_by_region[['지역', '접수_택시제외']],
		tesla_by_region,
		on='지역',
		how='left'
	).fillna(0)

	top_regions = comparison_df.nlargest(10, '접수_택시제외')

	fig = go.Figure()
	fig.add_trace(go.Bar(
		x=top_regions['지역'],
		y=top_regions['접수_택시제외'],
		name='전체 접수(택시제외)',
		marker_color='lightblue',
		opacity=0.7
	))
	fig.add_trace(go.Bar(
		x=top_regions['지역'],
		y=top_regions['테슬라_접수'],
		name='테슬라 접수',
		marker_color='#1e40af'
	))
	fig.update_layout(
		title="지역별 총 접수 vs 테슬라 접수 (상위 10개 지역)",
		xaxis_title="지역",
		yaxis_title="접수 건수",
		barmode='overlay',
		height=400,
		showlegend=True,
		legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
		title_font_size=14
	)
	st.plotly_chart(fig, use_container_width=True)

def render_low_remaining_list(df_overview):
	st.subheader("📉 잔여 비율 낮은 지역")
	st.caption("공고 대비 잔여 대수가 적은 순으로 정렬")
	if df_overview.empty:
		st.info("표시할 데이터가 없습니다.")
		return

	filtered_overview = df_overview[df_overview['지역'] != '한국환경공단'].copy()
	remaining_analysis = filtered_overview.groupby('지역').agg({
		'공고_전체': 'sum',
		'잔여_전체': 'sum'
	}).reset_index()

	remaining_analysis['잔여_비율'] = (remaining_analysis['잔여_전체'] / remaining_analysis['공고_전체'] * 100).round(1)
	remaining_analysis = remaining_analysis[remaining_analysis['공고_전체'] > 0]
	all_remaining = remaining_analysis.sort_values('잔여_비율').reset_index(drop=True)

	all_remaining = all_remaining.rename(columns={
		'지역': '지역',
		'잔여_전체': '잔여 대수',
		'잔여_비율': '잔여 비율(%)'
	})
	all_remaining['잔여 대수'] = all_remaining['잔여 대수'].astype(int)

	display_cols = ['지역', '잔여 대수', '잔여 비율(%)']
	st.dataframe(
		all_remaining[display_cols],
		use_container_width=True,
		hide_index=True,
		height=450,
		column_config={
			"지역": st.column_config.TextColumn("지역", width="medium"),
			"잔여 대수": st.column_config.NumberColumn("잔여 대수", format="%d"),
			"잔여 비율(%)": st.column_config.NumberColumn("잔여 비율(%)", format="%.1f%%"),
		}
	)


def create_regional_dashboard_bottom(df_overview, df_tesla):
    # 6:4 비율로 분할 - 세로 섹션들과 사이드 리스트
    main_content, side_list = st.columns([6, 4])

    with main_content:
        # 지역별 총 접수 vs 테슬라 접수 차트
        st.subheader("📊 지역별 총 접수 vs 테슬라 접수")

        # 전체 접수 현황 (지역별) - '한국환경공단' 제외
        total_by_region = df_overview[df_overview['지역'] != '한국환경공단'].groupby('지역')['접수_전체'].sum().reset_index()
        total_by_region['total_excluding_taxi'] = df_overview[df_overview['지역'] != '한국환경공단'].groupby('지역')['접수_택시'].sum().values
        total_by_region['접수_택시제외'] = total_by_region['접수_전체'] - total_by_region['total_excluding_taxi']

        # 테슬라 접수 현황 (지역구분별) - '한국환경공단' 제외
        if not df_tesla.empty and '지역구분' in df_tesla.columns:
            tesla_by_region = df_tesla[df_tesla['지역구분'] != '한국환경공단']['지역구분'].value_counts().reset_index()
            tesla_by_region.columns = ['지역', '테슬라_접수']

            # 두 데이터 병합
            comparison_df = pd.merge(total_by_region[['지역', '접수_택시제외']], tesla_by_region, on='지역', how='left').fillna(0)

            # 상위 10개 지역만 선택 (전체 접수 기준)
            top_regions = comparison_df.nlargest(10, '접수_택시제외')

            fig = go.Figure()

            # 전체 접수 막대 (배경)
            fig.add_trace(go.Bar(
                x=top_regions['지역'],
                y=top_regions['접수_택시제외'],
                name='전체 접수(택시제외)',
                marker_color='lightblue',
                opacity=0.7
            ))

            # 테슬라 접수 막대 (전면)
            fig.add_trace(go.Bar(
                x=top_regions['지역'],
                y=top_regions['테슬라_접수'],
                name='테슬라 접수',
                marker_color='#1e40af'
            ))

            fig.update_layout(
                title="지역별 총 접수 vs 테슬라 접수 (상위 10개 지역)",
                xaxis_title="지역",
                yaxis_title="접수 건수",
                barmode='overlay',  # 막대를 겹치게 표시
                height=400,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                title_font_size=14
            )

            st.plotly_chart(fig, use_container_width=True)

    with side_list:
        # 잔여 비율이 낮은 지역 리스트
        st.subheader("📉 잔여 비율 낮은 지역")
        st.caption("공고 대비 잔여 대수가 적은 순으로 정렬")

        if not df_overview.empty:
            # 한국환경공단 제외하고 계산
            filtered_overview = df_overview[df_overview['지역'] != '한국환경공단'].copy()

            # 지역별 집계
            remaining_analysis = filtered_overview.groupby('지역').agg({
                '공고_전체': 'sum',
                '잔여_전체': 'sum'
            }).reset_index()

            # 잔여 비율 계산 (공고 대비)
            remaining_analysis['잔여_비율'] = (remaining_analysis['잔여_전체'] / remaining_analysis['공고_전체'] * 100).round(1)

            # 공고가 0인 지역 제외
            remaining_analysis = remaining_analysis[remaining_analysis['공고_전체'] > 0]

            # 잔여 비율이 낮은 순으로 정렬 (모든 지자체)
            all_remaining = remaining_analysis.sort_values('잔여_비율').reset_index(drop=True)

            # 컬럼명 정리
            all_remaining = all_remaining.rename(columns={
                '지역': '지역',
                '잔여_전체': '잔여 대수',
                '잔여_비율': '잔여 비율(%)'
            })

            # 숫자 포맷팅
            all_remaining['잔여 대수'] = all_remaining['잔여 대수'].astype(int)

            # 표시할 컬럼만 선택
            display_cols = ['지역', '잔여 대수', '잔여 비율(%)']

            st.dataframe(
                all_remaining[display_cols],
                use_container_width=True,
                hide_index=True,
                height=450,
                column_config={
                    "지역": st.column_config.TextColumn("지역", width="medium"),
                    "잔여 대수": st.column_config.NumberColumn("잔여 대수", format="%d"),
                    "잔여 비율(%)": st.column_config.NumberColumn("잔여 비율(%)", format="%.1f%%"),
                }
            )

def main():
    """메인 애플리케이션"""
    # 헤더
    # st.markdown('<h1 class="main-header">⚡ 전기차 보조금 현황 확인</h1>', unsafe_allow_html=True)
    
    # 데이터 로드
    df_overview, df_amount, df_step = load_all_data()
    df_tesla = load_tesla_data()
    
    if df_overview.empty and df_amount.empty and df_step.empty:
        st.error("데이터를 로드할 수 없습니다. 파일 경로를 확인해주세요.")
        return
    
    # 1행: [테슬라 전국 총 현황]  |  [지역별 상세 현황]
    row1_left, row1_right = st.columns([3, 7])
    with row1_left:
        create_total_overview_dashboard_1(df_step, df_overview, df_amount, df_tesla)
    with row1_right:
        selected_region, received_final = create_regional_dashboard_top_1(df_overview, df_tesla)

    # 행과 행 사이 “일직선” 구분선
    st.divider()  # 구버전이면: st.markdown("<hr style='margin:8px 0;border:none;border-top:1px solid #e5e7eb;'>", unsafe_allow_html=True)

    # 2행: [테슬라 현황 + 진행단계]  |  [지역별 총 접수 vs 테슬라 접수 + 잔여 비율 낮은 지역]
    row2_left, row2_right = st.columns([3, 7])
    with row2_left:
        create_total_overview_dashboard_2(df_step, df_overview, df_amount, df_tesla)
        create_total_overview_dashboard_3(df_step, df_overview, df_amount, df_tesla)

    with row2_right:
        create_regional_dashboard_bottom(df_overview, df_tesla, selected_region, received_final)
    
    # 푸터
    st.markdown(f"""
    <div class="footer-info">
        자료 출처: 무공해차 통합누리집 | 최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        <br>
        <small>참고: <a href="https://longrange.gg/location/1100" target="_blank">longrange.gg</a></small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
