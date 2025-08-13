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
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
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
        color: #059669;
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
        # 시도별 집계
        region_summary = df_overview.groupby('시도').agg({
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
        region_summary.columns = ['시도', '총 공고', '접수 완료', '남은 대수', '출고 완료', '접수율(%)', '출고율(%)']
        
        st.markdown('<div class="status-table">', unsafe_allow_html=True)
        st.dataframe(
            region_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "시도": st.column_config.TextColumn("시도", width="small"),
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

def create_key_metrics(df_step, df_overview):
    """주요 지표 카드"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_applications = df_step['신청'].iloc[0] if not df_step.empty and '신청' in df_step.columns else 0
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.875rem; opacity: 0.9;">총 신청</div>
            <div class="highlight-number">{total_applications:,}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_approved = df_step['승인'].iloc[0] if not df_step.empty and '승인' in df_step.columns else 0
        approval_rate = (total_approved / total_applications * 100) if total_applications > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.875rem; opacity: 0.9;">승인 완료</div>
            <div class="highlight-number">{total_approved:,}</div>
            <div style="font-size: 0.75rem; opacity: 0.8;">승인률: {approval_rate:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        total_delivered = df_step['출고'].iloc[0] if not df_step.empty and '출고' in df_step.columns else 0
        delivery_rate = (total_delivered / total_approved * 100) if total_approved > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.875rem; opacity: 0.9;">출고 완료</div>
            <div class="highlight-number">{total_delivered:,}</div>
            <div style="font-size: 0.75rem; opacity: 0.8;">출고율: {delivery_rate:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        total_regions = len(df_overview['시도'].unique()) if not df_overview.empty else 0
        total_overview_applications = df_overview['접수_전체'].sum() if not df_overview.empty else 0
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.875rem; opacity: 0.9;">전국 현황</div>
            <div class="highlight-number">{total_overview_applications:,}</div>
            <div style="font-size: 0.75rem; opacity: 0.8;">{total_regions}개 시도</div>
        </div>
        """, unsafe_allow_html=True)

def create_simple_charts(df_overview, df_step):
    """간단한 시각화"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="sub-header">📊 상위 지역 현황</div>', unsafe_allow_html=True)
        if not df_overview.empty:
            top_regions = df_overview.groupby('시도')['접수_전체'].sum().nlargest(8)
            
            fig = px.bar(
                x=top_regions.values,
                y=top_regions.index,
                orientation='h',
                title="접수 건수 상위 8개 시도",
                labels={'x': '접수 건수', 'y': '시도'},
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

def main():
    """메인 애플리케이션"""
    # 헤더
    st.markdown('<h1 class="main-header">⚡ 전기차 보조금 현황 확인</h1>', unsafe_allow_html=True)
    
    # 데이터 로드
    df_overview, df_amount, df_step = load_all_data()
    
    if df_overview.empty and df_amount.empty and df_step.empty:
        st.error("데이터를 로드할 수 없습니다. 파일 경로를 확인해주세요.")
        return
    
    # 주요 지표
    create_key_metrics(df_step, df_overview)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 메인 현황 테이블
    create_main_status_table(df_step)
    
    # 지역별 현황
    create_region_overview_table(df_overview)
    
    # 금액별 현황
    create_amount_breakdown_table(df_amount)
    
    # 간단한 차트
    create_simple_charts(df_overview, df_step)
    
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
