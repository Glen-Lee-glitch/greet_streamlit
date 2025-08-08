import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime
import pytz

# 페이지 설정
st.set_page_config(
    page_title="폴스타 2025 데이터",
    page_icon="📊",
    layout="wide"
)

# CSS 스타일 추가
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
    /* st.metric 스타일 커스텀 */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04);
    }
    div[data-testid="metric-container"] > div:nth-child(2) { /* 값(value) 스타일 */
        font-size: 2rem;
        font-weight: 600;
        color: #1E3A8A; /* 진한 파란색 */
    }
    div[data-testid="metric-container"] > div:nth-child(3) > div { /* 증감(delta) 스타일 */
        font-size: 1rem;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# 한국 시간대 설정
kst = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(kst)

# 제목
st.title(f"📊 폴스타 2025 보고서 - {today_kst.strftime('%Y년 %m월 %d일')}")

# --- 8월 현황 요약 (개선된 UI) ---
col_title, col_select = st.columns([3, 1])
with col_title:
    st.subheader("📈 현황 요약")
with col_select:
    selected_month = st.selectbox(
        "조회 월",
        ["8월", "7월", "6월", "5월", "4월", "3월", "2월", "1월"],
        index=0,
        label_visibility="collapsed"
    )

# 현재 월인지 확인 (8월이 현재 월이라고 가정)
is_current_month = selected_month == "8월"

# 폴스타 월별 요약 테이블의 데이터를 참고하여 월별 데이터 준비
month_data = {
    "8월": {
        "pipeline_today": 5, "pipeline_month_total": 125,  # 8월은 예시 데이터 (실제로는 DB에서 가져와야 함)
        "apply_today": 3, "apply_month_total": 88,
        "unreceived_today": 4, "unreceived_total": 75,
        "supplement_today": 4, "supplement_total": 43,
        "cancel_today": 9, "cancel_total": 80
    },
    "7월": {
        "pipeline_today": 0, "pipeline_month_total": 140,  # 폴스타 월별 요약의 7월 데이터
        "apply_today": 0, "apply_month_total": 83,
        "unreceived_today": 0, "unreceived_total": 48,
        "supplement_today": 0, "supplement_total": 9,
        "cancel_today": 0, "cancel_total": 0
    },
    "6월": {
        "pipeline_today": 0, "pipeline_month_total": 47,  # 폴스타 월별 요약의 6월 데이터
        "apply_today": 0, "apply_month_total": 29,
        "unreceived_today": 0, "unreceived_total": 11,
        "supplement_today": 0, "supplement_total": 7,
        "cancel_today": 0, "cancel_total": 0
    },
    "5월": {
        "pipeline_today": 0, "pipeline_month_total": 332,  # 폴스타 월별 요약의 5월 데이터
        "apply_today": 0, "apply_month_total": 246,
        "unreceived_today": 0, "unreceived_total": 63,
        "supplement_today": 0, "supplement_total": 23,
        "cancel_today": 0, "cancel_total": 0
    },
    "4월": {
        "pipeline_today": 0, "pipeline_month_total": 182,  # 폴스타 월별 요약의 4월 데이터
        "apply_today": 0, "apply_month_total": 146,
        "unreceived_today": 0, "unreceived_total": 16,
        "supplement_today": 0, "supplement_total": 20,
        "cancel_today": 0, "cancel_total": 0
    },
    "3월": {
        "pipeline_today": 0, "pipeline_month_total": 279,  # 폴스타 월별 요약의 3월 데이터
        "apply_today": 0, "apply_month_total": 249,
        "unreceived_today": 0, "unreceived_total": 20,
        "supplement_today": 0, "supplement_total": 10,
        "cancel_today": 0, "cancel_total": 0
    },
    "2월": {
        "pipeline_today": 0, "pipeline_month_total": 52,  # 폴스타 월별 요약의 2월 데이터
        "apply_today": 0, "apply_month_total": 27,
        "unreceived_today": 0, "unreceived_total": 25,
        "supplement_today": 0, "supplement_total": 0,
        "cancel_today": 0, "cancel_total": 0
    },
    "1월": {
        "pipeline_today": 0, "pipeline_month_total": 72,  # 폴스타 월별 요약의 1월 데이터
        "apply_today": 0, "apply_month_total": 0,
        "unreceived_today": 0, "unreceived_total": 68,
        "supplement_today": 0, "supplement_total": 4,
        "cancel_today": 0, "cancel_total": 0
    }
}

# 선택된 월의 데이터 가져오기
current_data = month_data[selected_month]

# st.metric을 사용하여 카드 형태로 표시
if is_current_month:
    # 현재 월(8월)일 때는 모든 카드 표시
    summary_cols = st.columns(5)
    with summary_cols[0]:
        st.metric(label="파이프라인", value=f"{current_data['pipeline_month_total']} 건", delta=f"{current_data['pipeline_today']} 건 (당일)")
    with summary_cols[1]:
        st.metric(label="지원신청", value=f"{current_data['apply_month_total']} 건", delta=f"{current_data['apply_today']} 건 (당일)")
    with summary_cols[2]:
        # 미접수, 보완, 취소는 증가가 부정적인 의미이므로 delta_color="inverse" 사용 (빨간색으로 표시)
        st.metric(label="미접수", value=f"{current_data['unreceived_total']} 건", delta=f"{current_data['unreceived_today']} 건 (당일)", delta_color="inverse")
    with summary_cols[3]:
        st.metric(label="보완필요", value=f"{current_data['supplement_total']} 건", delta=f"{current_data['supplement_today']} 건 (당일)", delta_color="inverse")
    with summary_cols[4]:
        st.metric(label="취소", value=f"{current_data['cancel_total']} 건", delta=f"{current_data['cancel_today']} 건 (당일)", delta_color="inverse")
else:
    # 이전 월일 때는 파이프라인과 지원신청만 표시
    summary_cols = st.columns(2)
    with summary_cols[0]:
        st.metric(label="파이프라인", value=f"{current_data['pipeline_month_total']} 건")
    with summary_cols[1]:
        st.metric(label="지원신청", value=f"{current_data['apply_month_total']} 건")

# 상세 내역을 보여주기 위한 Expander (기존 테이블 유지)
with st.expander("상세 내역 보기"):
    row_idx = ['파이프라인', '지원신청', '폴스타 내부지원', '접수 후 취소']
    
    # 선택된 월의 상세 데이터 (실제로는 DB에서 가져와야 함)
    if selected_month == "8월":
        # 8월 상세 데이터
        second_data = {
            '전월 이월수량': [86, 54, 32, 0],
            '당일': [current_data['pipeline_today'], current_data['apply_today'], 1, 0],
            '당월_누계': [current_data['pipeline_month_total'], current_data['apply_month_total'], 45, 2]
        }
        third_data = [
            [2, 2, 4, 0, 6, 3], # 당일
            [45, 30, 28, 15, 55, 25] # 누계
        ]
    else:
        # 이전 월들은 당일 데이터가 0
        second_data = {
            '전월 이월수량': [0, 0, 0, 0],
            '당일': [0, 0, 0, 0],
            '당월_누계': [current_data['pipeline_month_total'], current_data['apply_month_total'], 0, 0]
        }
        third_data = [
            [0, 0, 0, 0, 0, 0], # 당일
            [current_data['unreceived_total'], 0, current_data['supplement_total'], 0, current_data['cancel_total'], 0] # 누계
        ]
    
    second_df = pd.DataFrame(second_data, index=row_idx)
    second_html = second_df.to_html(classes='custom_table', border=0, escape=False)

    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        st.subheader(f"{selected_month} 현황 (상세)")
        st.markdown(second_html, unsafe_allow_html=True)
    with exp_col2:
        st.subheader("미접수/보완/취소 현황 (상세)")
        
        # 데이터를 세 개의 작은 DataFrame으로 분리
        unreceived_df = pd.DataFrame(
            [third_data[0][0:2], third_data[1][0:2]],
            columns=['서류미비', '대기요청'],
            index=['당일', '누계']
        )
        supplement_df = pd.DataFrame(
            [third_data[0][2:4], third_data[1][2:4]],
            columns=['서류미비', '미처리'],
            index=['당일', '누계']
        )
        cancel_df = pd.DataFrame(
            [third_data[0][4:6], third_data[1][4:6]],
            columns=['단순취소', '내부지원전환'],
            index=['당일', '누계']
        )

        # 각 카테고리별로 테이블 표시
        st.markdown("<p class='detail-subheader'>미접수량</p>", unsafe_allow_html=True)
        st.markdown(unreceived_df.to_html(classes='custom_table', border=0, escape=False), unsafe_allow_html=True)
        
        st.markdown("<p class='detail-subheader'>보완 잔여 수량</p>", unsafe_allow_html=True)
        st.markdown(supplement_df.to_html(classes='custom_table', border=0, escape=False), unsafe_allow_html=True)

        st.markdown("<p class='detail-subheader'>취소</p>", unsafe_allow_html=True)
        st.markdown(cancel_df.to_html(classes='custom_table', border=0, escape=False), unsafe_allow_html=True)


st.markdown("---")

# --- 폴스타 월별 요약 (개선된 UI) ---
st.subheader("폴스타 월별 요약")

# 데이터프레임 생성
row_idx = ['파이프라인', '지원신청', '폴스타 내부지원', '접수 후 취소']
pol_data = {
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
pol_df = pd.DataFrame(pol_data, index=row_idx)

# NaN 값을 '-'로 치환
html_pol = pol_df.fillna('-').to_html(classes='custom_table', border=0, escape=False)

# <thead> 바로 뒤에 <tr><th>청구<br>세금계산서</th> ... 삽입
html_pol = re.sub(
    r'(<thead>\s*<tr>)',
    r'\1<th rowspan="2">청구<br>세금계산서</th>',
    html_pol,
    count=1
)

# ['1~6월 합계'] 행(7번째 컬럼) 연주황색(#ffe0b2) 배경, ['7~12월 합계'] 행(14번째 컬럼) 연주황색(#ffe0b2) 배경, ['2025 총합'] 열 연파랑색(#e3f2fd) 배경
# <tr>에서 <th>1~6월 합계</th>가 포함된 행 전체의 <td>에 스타일 적용
html_pol = re.sub(
    r'(<tr>\s*<th>1~6월 합계</th>)(.*?)(</tr>)',
    lambda m: m.group(1) + re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', m.group(2)) + m.group(3),
    html_pol,
    flags=re.DOTALL
)
# <th>1~6월 합계</th>에도 배경색 적용
html_pol = html_pol.replace('<th>1~6월 합계</th>', '<th style="background-color:#ffe0b2;">1~6월 합계</th>')

# <tr>에서 <th>7~12월 합계</th>가 포함된 행 전체의 <td>에 스타일 적용
html_pol = re.sub(
    r'(<tr>\s*<th>7~12월 합계</th>)(.*?)(</tr>)',
    lambda m: m.group(1) + re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', m.group(2)) + m.group(3),
    html_pol,
    flags=re.DOTALL
)
# <th>7~12월 합계</th>에도 배경색 적용
html_pol = html_pol.replace('<th>7~12월 합계</th>', '<th style="background-color:#ffe0b2;">7~12월 합계</th>')

# ['2025 총합'] 열(마지막 컬럼) 연파랑색(#e3f2fd) 배경
# <thead>의 마지막 <th>에 스타일 적용
html_pol = re.sub(
    r'(<th[^>]*>2025 총합</th>)',
    r'<th style="background-color:#e3f2fd;">2025 총합</th>',
    html_pol
)

# <tbody>의 각 행에서 마지막 <td>에 스타일 적용 (2025 총합 데이터 셀)
html_pol = re.sub(
    r'(<tr>.*?)(<td[^>]*>[^<]*</td>)(\s*</tr>)',
    lambda m: re.sub(
        r'(<td[^>]*>)([^<]*)(</td>)$',
        r'<td style="background-color:#e3f2fd;">\2</td>',
        m.group(0)
    ),
    html_pol,
    flags=re.DOTALL
)

# <tbody>의 각 행에서 '2025 총합'에 해당하는 <td>에도 배경색 적용 (헤더뿐 아니라 데이터까지)
# 위에서 이미 마지막 <td>에 칠했으나, 혹시 순서가 바뀌거나 컬럼 추가시 대비해 '2025 총합' 텍스트가 들어간 <td>도 칠함
html_pol = re.sub(
    r'(<td[^>]*>)([^<]*2025 총합[^<]*)(</td>)',
    r'<td style="background-color:#e3f2fd;">\2</td>',
    html_pol
)

# <tbody>의 각 행에서 '1~6월 합계' 컬럼(즉, 7번째 컬럼)과 '7~12월 합계' 컬럼(즉, 14번째 컬럼)에 해당하는 <td>에도 배경색 적용
def color_sum_column(match):
    row = match.group(0)
    # <td>들을 찾아서 색칠
    tds = re.findall(r'(<td[^>]*>[^<]*</td>)', row)
    if len(tds) >= 14:  # 7번째와 14번째 <td>에 색칠
        # 7번째 <td> (1~6월 합계)
        tds[6] = re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', tds[6])
        # 14번째 <td> (7~12월 합계)
        tds[13] = re.sub(r'<td([^>]*)>', r'<td\1 style="background-color:#ffe0b2;">', tds[13])
        # 다시 조립
        row_new = row
        for i, td in enumerate(tds):
            # 첫 번째 등장하는 <td>만 순서대로 교체
            row_new = re.sub(r'(<td[^>]*>[^<]*</td>)', lambda m: td if m.start() == 0 else m.group(0), row_new, count=1)
        return row_new
    else:
        return row
html_pol = re.sub(r'<tr>(.*?)</tr>', color_sum_column, html_pol, flags=re.DOTALL)

st.markdown(html_pol, unsafe_allow_html=True)

st.markdown("---")

# --- 메모 영역 ---
st.subheader("메모")
st.text_area(
    "메모를 입력하세요", 
    height=150, 
    placeholder="여기에 메모를 입력하세요...",
    label_visibility="collapsed" # subheader가 있으므로 label은 숨김
)
