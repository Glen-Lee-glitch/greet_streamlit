import streamlit as st
from datetime import datetime
import calendar
import html
import pandas as pd

def get_custom_tooltip_css():
    """커스텀 툴팁을 위한 CSS 스타일을 반환합니다."""
    return """
    <style>
        .tooltip-container {
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 48px;
            width: 100%;
        }

        .tooltip-text {
            visibility: hidden;
            width: 180px;
            background-color: #333;
            color: #fff;
            text-align: left;
            border-radius: 6px;
            padding: 10px;
            position: absolute;
            z-index: 10;
            bottom: 125%; /* 툴팁 위치를 날짜 위로 조정 */
            left: 50%;
            margin-left: -90px; /* 툴팁을 중앙에 위치시키기 위해 너비의 절반만큼 이동 */
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 14px; /* 폰트 크기 증가 */
            white-space: pre-wrap; /* 줄바꿈 문자(\n)를 인식하도록 설정 */
            box-shadow: 0px 0px 10px rgba(0,0,0,0.5);
            cursor: default;
        }

        /* 툴팁의 꼬리표(화살표) 스타일 */
        .tooltip-text::after {
            content: "";
            position: absolute;
            top: 100%;
            left: 50%;
            margin-left: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: #333 transparent transparent transparent;
        }

        /* 컨테이너에 마우스를 올렸을 때 툴팁을 보이게 함 */
        .tooltip-container:hover .tooltip-text {
            visibility: visible;
            opacity: 1;
        }
    </style>
    """

def create_mini_calendar(tooltip_data: dict = None, number_data: dict = None):
    """
    Streamlit 컬럼에 넣기 좋은 작은 월간 캘린더 UI를 생성합니다.
    - st.session_state를 사용하여 상태를 관리합니다.
    - 현재 날짜를 하이라이트하여 표시합니다.
    - 날짜에 마우스를 올리면 커스텀 UI 툴팁으로 데이터를 보여줍니다.

    Args:
        tooltip_data (dict, optional): {day: "tooltip_text"} 형태의 툴팁 데이터. Defaults to None.
        number_data (dict, optional): {day: [num1, num2]} 형태의 숫자 데이터. Defaults to None.
    """
    # rerun 시에도 CSS가 매번 주입되도록 세션 상태 체크 로직 제거
    st.markdown(get_custom_tooltip_css(), unsafe_allow_html=True)

    # session_state에 날짜가 없으면 초기화합니다.
    # 키를 고유하게 만들어 다른 위젯과 충돌하지 않도록 합니다.
    if 'mini_calendar_date' not in st.session_state:
        st.session_state.mini_calendar_date = datetime.now()
    
    current_date = st.session_state.mini_calendar_date

    # --- 헤더 ---
    header_cols = st.columns([1, 2, 1])
    
    with header_cols[0]:
        if st.button("◀", key="mini_cal_prev", use_container_width=True):
            if current_date.month == 1:
                st.session_state.mini_calendar_date = current_date.replace(year=current_date.year - 1, month=12, day=1)
            else:
                st.session_state.mini_calendar_date = current_date.replace(month=current_date.month - 1, day=1)
            st.rerun()

    with header_cols[1]:
        st.markdown(
            f"<p style='text-align: center; font-weight: bold; font-size: 1em; margin-bottom:0;'>{current_date.year}년 {current_date.month}월</p>",
            unsafe_allow_html=True
        )

    with header_cols[2]:
        if st.button("▶", key="mini_cal_next", use_container_width=True):
            if current_date.month == 12:
                st.session_state.mini_calendar_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                st.session_state.mini_calendar_date = current_date.replace(month=current_date.month + 1, day=1)
            st.rerun()

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    # --- 캘린더 그리드 ---
    days = ["월", "화", "수", "목", "금", "토", "일"]
    day_cols = st.columns(7)
    for i, day_name in enumerate(days):
        day_cols[i].markdown(
            f"<p style='text-align: center; font-size: 0.8em; font-weight:bold;'>{day_name}</p>",
            unsafe_allow_html=True
        )

    cal = calendar.monthcalendar(current_date.year, current_date.month)
    
    today = datetime.now()

    for week in cal:
        week_cols = st.columns(7)
        for i, day in enumerate(week):
            with week_cols[i]:
                if day == 0:
                    st.markdown("<p style='text-align: center; color: transparent; font-size: 0.8em;'>0</p>", unsafe_allow_html=True)
                else:
                    is_today = (
                        day == today.day and
                        current_date.month == today.month and
                        current_date.year == today.year
                    )
                    
                    # 1. 툴팁 데이터 처리
                    tooltip_text = ""
                    if tooltip_data and day in tooltip_data:
                        text = str(tooltip_data[day])
                        tooltip_text = html.escape(text, quote=True)
                    
                    tooltip_span = f"<span class='tooltip-text'>{tooltip_text}</span>" if tooltip_text else ""

                    # 2. 날짜 아래 숫자 데이터 처리
                    extra_html = ""
                    placeholder_html = "<div style='height: 1.2em; font-size: 0.7em;'></div>" # 높이 살짝 증가

                    if number_data and day in number_data and isinstance(number_data[day], (int, float)):
                        extra_html = f"<div style='color: red; font-size: 0.7em; text-align: center; margin-top: 2px;'>{number_data[day]}</div>"
                    else:
                        extra_html = placeholder_html
                    
                    day_style = (
                        "text-align: center; font-size: 0.8em; background-color: #FF4B4B; "
                        "color: white; border-radius: 50%; width: 24px; height: 24px; "
                        "line-height: 24px; margin: auto;"
                    ) if is_today else (
                        "text-align: center; font-size: 0.8em; margin: 0; cursor: help; height: 24px; line-height: 24px;"
                    )

                    # --- 수정된 HTML 구조 ---
                    day_html = f"""
                        <div class='tooltip-container'>
                            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                                <div style='{day_style}'>
                                    {day}
                                </div>
                                {extra_html}
                            </div>
                            {tooltip_span}
                        </div>
                    """
                    st.markdown(day_html, unsafe_allow_html=True)

def data_processing(df_source: pd.DataFrame, year: int, month: int):
    """
    주어진 데이터프레임을 가공하여 캘린더에 표시할 데이터를 생성합니다.
    (기존: 'Q3.xlsx' 파일 직접 읽기 -> 변경: DataFrame을 인자로 받기)
    """
    df = df_source.copy()

    # 'Greet Note' 컬럼명을 유연하게 찾기 (보고서.py의 로직과 통일)
    lowered_cols = {c.lower().replace(' ', ''): c for c in df.columns}
    note_col = next((orig for key, orig in lowered_cols.items() if 'greetnote' in key or '노트' in key), None)
    
    if note_col is None:
        return {}, {} # 노트 컬럼이 없으면 빈 데이터 반환

    # 1. 날짜 관련 데이터만 필터링
    filtered_df = df[df[note_col].apply(lambda x: isinstance(x, str) and '/' in x and '-' in x)].copy()

    # 2. 정규표현식으로 날짜와 내용(도시명 등) 추출
    extract_pattern = r'(\d{1,2}\s*/\s*\d{1,2})([^,]+)'
    extracted_data = filtered_df[note_col].str.extract(extract_pattern)

    if extracted_data.shape[1] < 2:
        return {}, {}
    
    # 추출된 월/일 정보를 숫자 형태로 변환하여 새로운 컬럼에 저장
    filtered_df['month'] = pd.to_numeric(extracted_data[0].str.split('/').str[0], errors='coerce')
    filtered_df['day'] = pd.to_numeric(extracted_data[0].str.split('/').str[1], errors='coerce')
    
    # 추출된 문자열 데이터 저장
    filtered_df['date_str'] = extracted_data[0].str.replace(r'\s', '')
    # [수정] 그룹 인덱스를 2에서 1로 변경
    filtered_df['note_content'] = extracted_data[1].str.strip().str.lstrip('-').str.strip()

    filtered_df.dropna(subset=['month', 'day', 'date_str', 'note_content'], inplace=True)

    if filtered_df.empty:
        return {}, {}

    # month와 day 컬럼을 정수형으로 변환
    filtered_df['month'] = filtered_df['month'].astype(int)
    filtered_df['day'] = filtered_df['day'].astype(int)

    # --- 추가된 로직: 현재 캘린더의 '월'과 일치하는 데이터만 필터링 ---
    monthly_df = filtered_df[filtered_df['month'] == month].copy()

    # 3. 날짜와 내용 기준으로 그룹화하여 건수 집계 (툴팁용)
    tooltip_counts = monthly_df.groupby(['date_str', 'note_content']).size()

    # 4. 툴팁 딕셔너리 생성
    tooltip_data = {}
    for (date_str, content), count in tooltip_counts.items():
        try:
            day = int(date_str.split('/')[1])
            tooltip_text = f"{date_str}-{content}: {count}건"
            
            if day in tooltip_data:
                tooltip_data[day] += f"\n{tooltip_text}"
            else:
                tooltip_data[day] = tooltip_text
        except (IndexError, ValueError):
            continue

    # 5. 날짜 아래에 표시할 숫자 데이터 집계
    daily_counts = monthly_df.groupby('day').size()
    number_data = daily_counts.to_dict()

    return number_data, tooltip_data

# --- 예시 사용법 ---
if __name__ == "__main__":
    st.set_page_config(layout="wide")
    st.title("툴팁 기능이 추가된 미니 캘린더")
    
    st.write("`st.columns` 안에 미니 캘린더를 넣고, 날짜 위에 마우스를 올려보세요.")
    
    cols = st.columns([1, 1, 2])
    
    # 현재 캘린더의 연도와 월 가져오기
    # st.session_state에서 현재 날짜를 가져와 data_processing에 전달
    cal_date = st.session_state.get('mini_calendar_date', datetime.now())
    
    try:
        # 테스트를 위해 'Q3.xlsx' 파일 로드
        df_excel = pd.read_excel('Q3.xlsx', sheet_name='미신청건')
        processed_number_data, processed_tooltip_data = data_processing(df_excel, cal_date.year, cal_date.month)
    except FileNotFoundError:
        st.error("'Q3.xlsx' 파일을 찾을 수 없습니다. 이 스크립트를 단독으로 테스트하려면 파일이 필요합니다.")
        processed_number_data, processed_tooltip_data = {}, {}

    # --- 디버깅 코드 추가 ---
    st.write("Number Data:", processed_number_data)
    st.write("Tooltip Data:", processed_tooltip_data)
    # --- 여기까지 ---
    
    with cols[0]:
        st.header("캘린더")
        create_mini_calendar(
            tooltip_data=processed_tooltip_data,
            number_data=processed_number_data
        )
        
    with cols[1]:
        st.header("다른 컨텐츠")
        st.write("이곳에 다른 컴포넌트나 내용을 추가할 수 있습니다.")
        st.image("https://static.streamlit.io/examples/cat.jpg")

    with cols[2]:
        st.header("또 다른 컨텐츠")
        st.info("미니 캘린더는 다른 UI 요소들과 잘 어울립니다.")