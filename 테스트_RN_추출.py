import pandas as pd
import pickle
import sys
from datetime import datetime

# --- 설정값 ---
# 테스트하려는 기준 날짜와 분기를 설정해주세요.
# 보고서 앱에서 '3808'이라는 숫자를 확인했을 때 선택했던 값과 동일하게 맞춰주세요.
SELECTED_DATE_STR = '2025-07-28'
SELECTED_QUARTER = '3분기' # '전체', '2분기', '3분기' 중 하나를 선택

# --- 데이터 로드 ---
try:
    with open("preprocessed_data.pkl", "rb") as f:
        data = pickle.load(f)
    df_1 = data["df_1"]
    df_5 = data["df_5"]
    print("데이터 로드 완료: preprocessed_data.pkl")
except FileNotFoundError:
    print("오류: 전처리된 데이터 파일(preprocessed_data.pkl)을 찾을 수 없습니다.")
    print("먼저 '전처리.py'를 실행하여 데이터 파일을 생성해주세요.")
    sys.exit()

# --- 보고서.py 로직 재현 ---

# 1. 날짜 객체 생성
try:
    selected_date = datetime.strptime(SELECTED_DATE_STR, '%Y-%m-%d').date()
except ValueError:
    print(f"오류: 날짜 형식이 잘못되었습니다. 'YYYY-MM-DD' 형식으로 입력해주세요: {SELECTED_DATE_STR}")
    sys.exit()

# 2. 선택된 분기에 따라 df_1 필터링
if SELECTED_QUARTER == '전체':
    df_1_filtered = df_1.copy()
    print("분기: '전체'를 기준으로 데이터를 필터링합니다.")
elif SELECTED_QUARTER in ['2분기', '3분기']:
    print(f"분기: '{SELECTED_QUARTER}'를 기준으로 데이터를 필터링합니다.")
    # 지원(파이프라인) 기준으로 해당 분기의 RN 목록 가져오기
    rns_in_quarter = df_5[df_5['분기'] == SELECTED_QUARTER]['RN'].unique()
    
    # 해당 RN을 기준으로 df_1 필터링
    df_1_filtered = df_1[df_1['제조수입사\n관리번호'].isin(rns_in_quarter)].copy()
    print(f"'{SELECTED_QUARTER}'에 해당하는 지원(파이프라인) RN {len(rns_in_quarter)}개를 기준으로 신청 데이터를 필터링했습니다.")
else:
    print(f"오류: 잘못된 분기 값입니다. '전체', '2분기', '3분기' 중 하나를 선택하세요: {SELECTED_QUARTER}")
    sys.exit()


# 3. '신청 건수'의 '누적 총계'에 해당하는 데이터 추출
# '신청일자' 컬럼이 datetime 타입이 아닐 경우를 대비하여 변환
if not pd.api.types.is_datetime64_any_dtype(df_1_filtered['신청일자']):
    df_1_filtered.loc[:, '신청일자'] = pd.to_datetime(df_1_filtered['신청일자'], errors='coerce')

# 날짜가 없는 행(NaT)을 제외하고 필터링
mask = (df_1_filtered['신청일자'].notna()) & (df_1_filtered['신청일자'].dt.date <= selected_date)
target_data = df_1_filtered[mask]

count = len(target_data)
print(f"\n'{SELECTED_DATE_STR}' 기준, '{SELECTED_QUARTER}' 분기의 누적 신청 건수는 총 {count} 건입니다.")
if count != 3808:
    print(f"경고: 요청하신 3808건과 일치하지 않습니다. 설정된 날짜({SELECTED_DATE_STR})와 분기('{SELECTED_QUARTER}')가 맞는지 확인해주세요.")


# 4. RN 목록 추출 및 저장
if not target_data.empty:
    rns_to_export = target_data[['제조수입사\n관리번호', '신청일자']].copy()
    rns_to_export.rename(columns={'제조수입사\n관리번호': 'RN'}, inplace=True)
    
    # 중복된 RN이 있을 수 있으므로, 고유 RN 개수도 확인
    unique_rn_count = rns_to_export['RN'].nunique()
    print(f"추출된 데이터의 고유 RN 개수는 {unique_rn_count}개 입니다.")

    output_filename = f"신청건수_{SELECTED_QUARTER}_{SELECTED_DATE_STR}_RN_목록.xlsx"
    try:
        rns_to_export.to_excel(output_filename, index=False)
        print(f"\n성공: RN 목록이 '{output_filename}' 파일로 저장되었습니다.")
    except Exception as e:
        print(f"\n오류: 엑셀 파일 저장 중 문제가 발생했습니다 - {e}")
else:
    print("\n추출할 데이터가 없습니다.") 