import pandas as pd
import pickle
import sys

# --- 데이터 로드 ---
try:
    with open("preprocessed_data.pkl", "rb") as f:
        data = pickle.load(f)
    df_1 = data["df_1"]
    print("데이터 로드 완료: preprocessed_data.pkl")
except FileNotFoundError:
    print("오류: 전처리된 데이터 파일(preprocessed_data.pkl)을 찾을 수 없습니다.")
    print("먼저 '전처리.py'를 실행하여 데이터 파일을 생성해주세요.")
    sys.exit()

# '제조수입사\n관리번호'(RN)를 기준으로 중복된 데이터 확인
# keep=False 옵션은 중복된 모든 행을 True로 표시합니다.
duplicates_mask = df_1.duplicated(subset=['제조수입사\n관리번호'], keep=False)
df_duplicates = df_1[duplicates_mask]

if df_duplicates.empty:
    print("df_1 (EV 시트) 데이터에는 중복된 신청 건이 없습니다.")
else:
    print(f"총 {len(df_duplicates)}개의 중복된 행을 발견했습니다.")
    
    # 보기 쉽게 관리번호(RN)와 신청일자 순으로 정렬합니다.
    df_duplicates_sorted = df_duplicates.sort_values(by=['제조수입사\n관리번호', '신청일자'])

    # --- 엑셀 파일로 저장 ---
    output_filename = "중복_신청건_내역.xlsx"
    try:
        df_duplicates_sorted.to_excel(output_filename, index=False)
        print(f"성공: 중복된 신청 건 내역이 '{output_filename}' 파일로 저장되었습니다.")
        # 중복된 고유 RN 개수도 함께 출력
        unique_duplicated_rns = df_duplicates_sorted['제조수입사\n관리번호'].nunique()
        print(f"중복이 발생한 고유 관리번호(RN)의 개수는 {unique_duplicated_rns}개입니다.")

    except Exception as e:
        print(f"오류: 엑셀 파일 저장 중 문제가 발생했습니다 - {e}") 