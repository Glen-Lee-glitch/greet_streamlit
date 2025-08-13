import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import pickle

# --- 페이지 설정 ---
st.set_page_config(
    page_title="테슬라 EV 데이터 대시보드", 
    page_icon="🚗", 
    layout="wide"
)

# --- 스타일링 ---
st.markdown("""
<style>
    .filter-container {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #dee2e6;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- 데이터 로딩 함수 ---
@st.cache_data(ttl=3600)
def load_tesla_data():
    """
    preprocessed_data.pkl에서 테슬라 EV 데이터를 로드합니다.
    """
    try:
        with open("preprocessed_data.pkl", "rb") as f:
            data = pickle.load(f)
        
        df = data.get("df_tesla_ev", pd.DataFrame())
        df_master = data.get("df_master", pd.DataFrame())
        
        if df.empty:
            st.error("❌ preprocessed_data.pkl에서 테슬라 EV 데이터를 찾을 수 없습니다.")
            st.info("💡 전처리.py를 먼저 실행하여 데이터를 준비해주세요.")
            return pd.DataFrame(), pd.DataFrame()
        
        # 날짜 컬럼이 있는 경우 날짜 필터링 적용
        date_col = next((col for col in df.columns if '신청일자' in col), None)
        if date_col:
            df = df.dropna(subset=[date_col])
        
        return df, df_master

    except FileNotFoundError:
        st.error("❌ 'preprocessed_data.pkl' 파일을 찾을 수 없습니다.")
        st.info("💡 전처리.py를 먼저 실행하여 데이터를 준비해주세요.")
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        st.error(f"❌ 데이터 로드 중 오류: {str(e)}")
        st.info("💡 전처리.py를 먼저 실행하여 데이터를 준비해주세요.")
        return pd.DataFrame(), pd.DataFrame()

def render_comprehensive_analysis(df_filtered):
    """종합 현황 탭 렌더링"""
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

def render_applicant_analysis(df_filtered):
    """신청자 분석 탭 렌더링"""
    st.subheader("신청유형 및 연령대 분석")
    
    applicant_counts = df_filtered['분류된_신청유형'].value_counts()
    
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

def render_writer_analysis(df_filtered):
    """작업자 분석 탭 렌더링"""
    st.subheader("작성자별 작업 현황")
    # 주의사항 한줄(심플)
    st.markdown('<span style="color:#666; font-size:14px;">※ 5월 20일 이전까지는 배은영, 이경구 계정으로 매크로 작업이 많았습니다.</span>', unsafe_allow_html=True)
    
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
        
    else:
        st.warning("⚠️ '작성자' 컬럼을 찾을 수 없습니다.")
        st.info("현재 파일의 컬럼명:", list(df_filtered.columns))

def render_regional_analysis(df_master):
    """지자체별 현황 정리 탭 렌더링"""
    st.markdown("""
    <div style="text-align: center; padding: 20px 0; border-bottom: 2px solid #e0e0e0; margin-bottom: 30px;">
        <h2 style="color: #1f77b4; margin: 0; font-weight: 600;">🏛️ 지자체별 현황 정리</h2>
        <p style="color: #666; margin: 10px 0 0 0; font-size: 16px;">지역별 보조금 현황 및 필요 서류 정보</p>
    </div>
    """, unsafe_allow_html=True)
    
    if df_master.empty or '지역' not in df_master.columns:
        st.warning("지자체 데이터가 없습니다.")
    else:
        region_list = df_master['지역'].dropna().unique().tolist()
        
        st.markdown("##### 📍 분석 대상 지역")
        selected_region = st.selectbox(
            "지역을 선택하세요",
            options=region_list,
            index=0,
            help="분석할 지자체를 선택하세요"
        )
        st.markdown(f"**선택된 지역:** `{selected_region}`")

        # 선택된 지역의 데이터 추출 (한 행)
        filtered = df_master[df_master['지역'] == selected_region].iloc[0]

        # --- 1. 현황 (차량 대수) ---
        st.markdown("### 📊 현황 (차량 대수)")
        st.markdown("---")

        # 먼저 변수들을 계산
        general_status = filtered.get('현황_일반', 0)
        try:
            if pd.isna(general_status) or general_status == '' or str(general_status).strip() == '':
                general_status = 0
            else:
                general_status = int(float(str(general_status).replace(',', '')))
        except (ValueError, TypeError):
            general_status = 0

        priority_status = filtered.get('현황_우선', 0)
        try:
            if pd.isna(priority_status) or priority_status == '' or str(priority_status).strip() == '':
                priority_status = 0
            else:
                priority_status = int(float(str(priority_status).replace(',', '')))
        except (ValueError, TypeError):
            priority_status = 0

        # 그 다음에 HTML 표시
        status_cols = st.columns(2)
        with status_cols[0]:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 20px; border-radius: 15px; color: white; text-align: center;">
                <h4 style="margin: 0 0 10px 0; font-size: 18px;">일반 현황</h4>
                <h2 style="margin: 0; font-size: 32px; font-weight: 700;">{general_status:,} 대</h2>
            </div>
            """.format(general_status=general_status), unsafe_allow_html=True)

        with status_cols[1]:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                        padding: 20px; border-radius: 15px; color: white; text-align: center;">
                <h4 style="margin: 0 0 10px 0; font-size: 18px;">우선 현황</h4>
                <h2 style="margin: 0; font-size: 32px; font-weight: 700;">{priority_status:,} 대</h2>
            </div>
            """.format(priority_status=priority_status), unsafe_allow_html=True)

        st.markdown("---")

        # --- 2. 모델별 보조금 ---
        st.subheader("🚗 모델별 보조금 (단위: 만 원)")

        # 모델명과 컬럼명 매핑
        model_cols = {
            'Model 3 RWD': 'Model 3 RWD_기본',
            'Model 3 RWD (2024)': 'Model 3 RWD(2024)_기본',
            'Model 3 LongRange': 'Model 3 LongRange_기본',
            'Model 3 Performance': 'Model 3 Performance_기본',
            'Model Y New RWD': 'Model Y New RWD_기본',
            'Model Y New LongRange': 'Model Y New LongRange_기본'
        }

        # 보조금 데이터 수집
        subsidy_data = []
        for model_name, col_name in model_cols.items():
            if col_name in filtered.index:
                subsidy_value = filtered[col_name]
                try:
                    if pd.notna(subsidy_value) and subsidy_value != '' and str(subsidy_value).strip() != '':
                        numeric_value = float(str(subsidy_value).replace(',', ''))
                        if numeric_value > 0:
                            subsidy_data.append((model_name, numeric_value))
                except (ValueError, TypeError):
                    continue

        if subsidy_data:
            # 3열 그리드로 표시
            cols = st.columns(3)
            for idx, (model_name, amount) in enumerate(subsidy_data):
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div style="background: #f8f9fa; padding: 10px; border-radius: 8px; 
                                border-left: 3px solid #007bff; margin: 5px 0;">
                        <h6 style="margin: 0 0 5px 0; color: #495057; font-size: 12px; font-weight: 600;">{model_name}</h6>
                        <h4 style="margin: 0; color: #007bff; font-size: 18px; font-weight: 600;">
                            {int(amount):,} 만원
                        </h4>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("해당 지역의 모델별 보조금 정보가 없습니다.")

        st.markdown("---")

        # --- 3. 필요 서류 ---
        st.subheader("📝 필요 서류")
        doc_cols = st.columns(2)

        with doc_cols[0]:
            st.markdown("##### 지원신청서류")
            doc_text_apply = str(filtered.get('지원신청서류', '내용 없음')).replace('\n', '<br>')
            st.markdown(
                f"<div style='background-color:#f0f2f6; border-radius:10px; padding:15px; height: 300px; overflow-y: auto;'>{doc_text_apply}</div>",
                unsafe_allow_html=True
            )

        with doc_cols[1]:
            st.markdown("##### 지급신청서류")
            doc_text_payment = str(filtered.get('지급신청서류', '내용 없음')).replace('\n', '<br>')
            st.markdown(
                f"<div style='background-color:#f0f2f6; border-radius:10px; padding:15px; height: 300px; overflow-y: auto;'>{doc_text_payment}</div>",
                unsafe_allow_html=True
            )

def show_car_region_dashboard(data=None, today_kst=None):
    """
    차량 지역 대시보드를 표시하는 메인 함수
    외부에서 호출할 때 사용
    """
    # 데이터가 외부에서 제공되지 않으면 직접 로드
    if data is None:
        df_original, df_master = load_tesla_data()
    else:
        df_original = data.get("df_tesla_ev", pd.DataFrame())
        df_master = data.get("df_master", pd.DataFrame())

    if df_original.empty:
        st.warning("데이터를 불러올 수 없습니다. 파일을 확인해주세요.")
        return

    # --- 메인 레이아웃 설정 ---
    main_col, filter_col = st.columns([0.75, 0.25])

    # --- 필터 영역 (오른쪽 컬럼) ---
    with filter_col:
        with st.container():
            st.markdown("<div class='filter-container'>", unsafe_allow_html=True)
            st.header("🔍 데이터 필터")
            
            default_end_date = pd.to_datetime('2025-08-06').date()
            
            # 1. 기간 필터
            date_col = next((col for col in df_original.columns if '신청일자' in col), None)
            min_date = df_original[date_col].min().date()
            max_date = df_original[date_col].max().date()

            # 시작일과 종료일을 분리해서 입력
            date_col1, date_col2 = st.columns(2)

            with date_col1:
                start_date = st.date_input(
                    "시작일",
                    value=min_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="start_date_filter"
                )

            with date_col2:
                end_date = st.date_input(
                    "종료일",
                    value=default_end_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="end_date_filter"
                )

            # 날짜 유효성 검사 및 보정
            if start_date > end_date:
                st.warning("⚠️ 시작일이 종료일보다 늦습니다. 자동으로 교체합니다.")
                start_date, end_date = end_date, start_date

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
        tab1, tab2, tab3, tab4 = st.tabs(["📊 종합 현황", "👥 신청자 분석", "👨‍💼 작업자 분석", "🏛️ 지자체별 현황 정리"])

        with tab1:
            render_comprehensive_analysis(df_filtered)

        with tab2:
            render_applicant_analysis(df_filtered)

        with tab3:
            render_writer_analysis(df_filtered)

        with tab4:
            render_regional_analysis(df_master)

# --- 메인 실행 부분 (독립 실행용) ---
if __name__ == "__main__":
    show_car_region_dashboard()
