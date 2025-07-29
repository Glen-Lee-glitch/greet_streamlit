import pandas as pd
import pickle
import sys

# --- 데이터 로드 ---
try:
    with open("preprocessed_data.pkl", "rb") as f:
        data = pickle.load(f)
    df_5 = data["df_5"]
    print("데이터 로드 완료: preprocessed_data.pkl")
except FileNotFoundError:
    print("오류: 전처리된 데이터 파일(preprocessed_data.pkl)을 찾을 수 없습니다.")
    print("먼저 '전처리.py'를 실행하여 데이터 파일을 생성해주세요.")
    sys.exit()

# --- 분기 데이터 필터링 ---
# '분기' 컬럼이 '2분기' 또는 '3분기'인 데이터만 선택합니다.
df_quarters = df_5[df_5['분기'].isin(['2분기', '3분기'])].copy()

if df_quarters.empty:
    print("2분기 또는 3분기에 해당하는 파이프라인 데이터가 없습니다.")
else:
    # 날짜 기준으로 정렬하여 보기 쉽게 만듭니다.
    # '날짜' 컬럼이 datetime 타입이 아닐 경우를 대비하여 변환합니다.
    df_quarters['날짜'] = pd.to_datetime(df_quarters['날짜'], errors='coerce')
    df_quarters.sort_values(by='날짜', inplace=True)

    # --- 엑셀 파일로 저장 ---
    output_filename = "분기별_파이프라인_데이터.xlsx"
    try:
        # 엑셀 파일로 저장합니다. 인덱스는 저장하지 않습니다.
        df_quarters.to_excel(output_filename, index=False)
        print(f"성공: 분기별 데이터가 '{output_filename}' 파일로 저장되었습니다.")
        print(f"총 {len(df_quarters)}개의 데이터가 저장되었습니다.")
    except Exception as e:
        print(f"오류: 엑셀 파일 저장 중 문제가 발생했습니다 - {e}") 