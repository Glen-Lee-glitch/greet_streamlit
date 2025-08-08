import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import pytz
import plotly.express as px

# --- 페이지 설정 ---
st.set_page_config(
    page_title="인터랙티브 테슬라 대시보드",
    page_icon="🚗",
    layout="wide"
)

# --- CSS 스타일 ---
st.markdown("""
<style>
    /* 메트릭 컨테이너 스타일 */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04);
    }
    /* 메트릭 값 스타일 */
    div[data-testid="metric-container"] > div:nth-child(2) {
        font-size: 2.2rem;
        font-weight: 600;
        color: #1E3A8A;
    }
    /* 탭 스타일 */
    button[data-baseweb="tab"] {
        font-size: 1.1rem;
        font-weight: 500;
    }
    /* 필터 영역 스타일 */
    .filter-container {
        background-color: #F8F9FA;
        padding: 20px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# --- 데이터 로딩 및 전처리 함수 ---
@st.cache_data
def load_and_process_data():
    """
    preprocessed_data.pkl에서 테슬라 EV 데이터를 로드합니다.
    이 함수는 한 번만 실행되어 결과가 캐시됩니다.
    """
    try:
        import pickle
        
        with open("preprocessed_data.pkl", "rb") as f:
            data = pickle.load(f)
        
        df = data.get("df_tesla_ev", pd.DataFrame())
        
        if df.empty:
            st.error("❌ preprocessed_data.pkl에서 테슬라 EV 데이터를 찾을 수 없습니다.")
            st.info("💡 전처리.py를 먼저 실행하여 데이터를 준비해주세요.")
            return pd.DataFrame()
        
        # 날짜 컬럼이 있는 경우 날짜 필터링 적용
        date_col = next((col for col in df.columns if '신청일자' in col), None)
        if date_col:
            df = df.dropna(subset=[date_col])
        
        return df

    except FileNotFoundError:
        st.error("❌ 'preprocessed_data.pkl' 파일을 찾을 수 없습니다.")
        st.info("💡 전처리.py를 먼저 실행하여 데이터를 준비해주세요.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ 데이터 로드 중 오류: {str(e)}")
        st.info("💡 전처리.py를 먼저 실행하여 데이터를 준비해주세요.")
        return pd.DataFrame()

# --- 데이터 로드 ---
df_original = load_and_process_data()

if not df_original.empty:
    # --- 메인 레이아웃 설정 ---
    main_col, filter_col = st.columns([0.75, 0.25])

    # --- 필터 영역 (오른쪽 컬럼) ---
    with filter_col:
        with st.container():
            st.markdown("<div class='filter-container'>", unsafe_allow_html=True)
            st.header("🔍 데이터 필터")
            
            # 1. 기간 필터
            date_col = next((col for col in df_original.columns if '신청일자' in col), None)
            min_date = df_original[date_col].min().date()
            max_date = df_original[date_col].max().date()
            
            start_date, end_date = st.date_input(
                "신청일자 범위",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="date_range_filter"
            )

            # 2. 차종 필터
            model_options = df_original['분류된_차종'].unique().tolist()
            selected_models = st.multiselect(
                "차종 선택",
                options=model_options,
                default=model_options,
                key="model_filter"
            )

            # 3. 신청유형 필터
            applicant_options = df_original['분류된_신청유형'].unique().tolist()
            selected_applicants = st.multiselect(
                "신청유형 선택",
                options=applicant_options,
                default=applicant_options,
                key="applicant_filter"
            )
            st.markdown("</div>", unsafe_allow_html=True)

    # --- 필터링된 데이터 생성 ---
    df_filtered = df_original[
        (df_original[date_col].dt.date >= start_date) &
        (df_original[date_col].dt.date <= end_date) &
        (df_original['분류된_차종'].isin(selected_models)) &
        (df_original['분류된_신청유형'].isin(selected_applicants))
    ]

    # --- 메인 대시보드 (왼쪽 컬럼) ---
    with main_col:
        st.title("🚗 테슬라 EV 데이터 대시보드")
        st.markdown(f"**조회 기간:** `{start_date}` ~ `{end_date}`")
        st.markdown("---")

        # --- 탭 구성 ---
        tab1, tab2, tab3 = st.tabs(["📊 종합 현황", "👥 신청자 분석", "👨‍💼 작업자 분석"])

        with tab1:
            st.subheader("핵심 지표")
            
            total_count = len(df_filtered)
            model_counts = df_filtered['분류된_차종'].value_counts()
            applicant_counts = df_filtered['분류된_신청유형'].value_counts()

            metric_cols = st.columns(4)
            metric_cols[0].metric("총 신청 대수", f"{total_count:,} 대")
            metric_cols[1].metric("Model Y", f"{model_counts.get('Model Y', 0):,} 대")
            metric_cols[2].metric("Model 3", f"{model_counts.get('Model 3', 0):,} 대")
            metric_cols[3].metric("개인 신청 비율", f"{(applicant_counts.get('개인', 0) / total_count * 100 if total_count > 0 else 0):.1f} %")

            st.markdown("<br>", unsafe_allow_html=True)
            
            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                st.subheader("차종별 분포")
                if not model_counts.empty:
                    fig_model = px.pie(
                        values=model_counts.values, 
                        names=model_counts.index, 
                        hole=0.4,
                        color_discrete_sequence=px.colors.sequential.Blues_r
                    )
                    fig_model.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_model, use_container_width=True)
                else:
                    st.info("데이터 없음")

            with chart_col2:
                st.subheader("차종 × 신청유형 교차 분석")
                cross_tab = pd.crosstab(df_filtered['분류된_차종'], df_filtered['분류된_신청유형'])
                st.dataframe(cross_tab, use_container_width=True)

        with tab2:
            st.subheader("신청유형 및 연령대 분석")
            
            analysis_cols = st.columns(2)
            with analysis_cols[0]:
                st.markdown("##### 📋 신청유형별 분포")
                if not applicant_counts.empty:
                    fig_applicant = px.pie(
                        values=applicant_counts.values,
                        names=applicant_counts.index,
                        hole=0.4,
                        color_discrete_sequence=px.colors.sequential.Greens_r
                    )
                    fig_applicant.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_applicant, use_container_width=True)
                else:
                    st.info("데이터 없음")

            if '연령대' in df_filtered.columns:
                with analysis_cols[1]:
                    st.markdown("##### 📋 연령대별 분포 (개인/개인사업자)")
                    personal_df = df_filtered[df_filtered['분류된_신청유형'].isin(['개인', '개인사업자'])]
                    age_group_counts = personal_df['연령대'].value_counts()
                    
                    if not age_group_counts.empty:
                        fig_age = px.pie(
                            values=age_group_counts.values,
                            names=age_group_counts.index,
                            hole=0.4,
                            color_discrete_sequence=px.colors.sequential.Oranges_r
                        )
                        fig_age.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_age, use_container_width=True)
                    else:
                        st.info("데이터 없음")

        with tab3:
            st.subheader("작성자별 작업 현황")
            
            if '작성자' in df_filtered.columns:
                # 작성자별 통계
                writer_counts = df_filtered['작성자'].value_counts()
                
                # 상위 10명만 표시 (너무 많으면 차트가 복잡해짐)
                top_writers = writer_counts.head(10)
                others_count = writer_counts.iloc[10:].sum() if len(writer_counts) > 10 else 0
                
                if others_count > 0:
                    # 상위 10명 + 기타로 구성
                    display_data = pd.concat([
                        top_writers,
                        pd.Series({'기타': others_count})
                    ])
                else:
                    display_data = top_writers
                
                # 메트릭 표시
                metric_cols = st.columns(4)
                metric_cols[0].metric("총 작성자 수", f"{len(writer_counts):,} 명")
                metric_cols[1].metric("최다 작성자", f"{writer_counts.iloc[0] if not writer_counts.empty else 0:,} 건")
                metric_cols[2].metric("평균 작성 건수", f"{writer_counts.mean():.1f} 건")
                metric_cols[3].metric("상위 10명 비율", f"{(top_writers.sum() / len(df_filtered) * 100):.1f} %")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # 파이차트
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    st.markdown("##### 📊 작성자별 작업 분포")
                    if not display_data.empty:
                        fig_writer = px.pie(
                            values=display_data.values,
                            names=display_data.index,
                            hole=0.4,
                            color_discrete_sequence=px.colors.sequential.Purples_r
                        )
                        fig_writer.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_writer, use_container_width=True)
                    else:
                        st.info("데이터 없음")
                
                with chart_col2:
                    st.markdown("##### 📋 상위 작성자 현황")
                    writer_stats_df = pd.DataFrame({
                        '작성자': top_writers.index,
                        '작성 건수': top_writers.values,
                        '비율(%)': (top_writers.values / len(df_filtered) * 100).round(1)
                    })
                    
                    st.dataframe(
                        writer_stats_df,
                        use_container_width=True,
                        hide_index=True
                    )
                
                # 작성자별 차종 분석
                st.markdown("---")
                st.subheader("작성자별 차종 분석")
                
                if not writer_counts.empty:
                    # 상위 5명 작성자의 차종별 분석
                    top_5_writers = writer_counts.head(5).index
                    writer_model_data = df_filtered[df_filtered['작성자'].isin(top_5_writers)]
                    
                    if not writer_model_data.empty:
                        writer_model_cross = pd.crosstab(
                            writer_model_data['작성자'], 
                            writer_model_data['분류된_차종'],
                            margins=True,
                            margins_name='합계'
                        )
                        
                        st.dataframe(
                            writer_model_cross,
                            use_container_width=True
                        )
                    else:
                        st.info("분석할 데이터가 없습니다.")
                else:
                    st.info("작성자 데이터가 없습니다.")
            else:
                st.warning("⚠️ '작성자' 컬럼을 찾을 수 없습니다.")
                st.info("현재 파일의 컬럼명:", list(df_filtered.columns))

else:
    st.warning("데이터를 불러올 수 없습니다. 파일을 확인해주세요.")
