import pandas as pd
import datetime

### 파이프라인 붙이기
df_pipeline = pd.read_excel("Q3.xlsx", sheet_name="PipeLine")

today_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d")

df_pipeline_today = pd.read_excel("pipeline.xlsx", sheet_name="Sheet3")

# --- 컬럼명 정리 ---
df_pipeline_today.columns = df_pipeline_today.columns.str.strip()

# 'RN' 컬럼 존재 여부 확인
if 'RN' not in df_pipeline_today.columns:
    raise KeyError("'RN' 컬럼을 찾을 수 없습니다. pipeline.xlsx Sheet3의 헤더를 확인하세요.")

# df_pipeline_today의 'RN' 값에 대해 '날짜'는 모두 today_date로 하여 DataFrame 생성
df_new = pd.DataFrame({
    '날짜': today_date,
    'RN': df_pipeline_today['RN']
})

# 기존 df_pipeline에 새 데이터(df_new) 붙이기
df_pipeline = pd.concat([df_pipeline, df_new], ignore_index=True)

# 중복 'RN' 제거 (기존 데이터 우선 유지)
df_pipeline = df_pipeline.drop_duplicates(subset=['RN'], keep='first').reset_index(drop=True)

# Q3.xlsx의 기존 시트는 그대로 두고, PipeLine 시트만 덮어쓰기
with pd.ExcelWriter("Q3.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    df_pipeline.to_excel(writer, sheet_name="PipeLine", index=False)


### EV 최신 정보 붙이기
# 1) 오늘 신청 건수 계산
_ev_df = pd.read_excel("C:/Users/HP/Desktop/그리트_공유/07_31_1758_EV_merged.xlsx", sheet_name="Sheet1")
_today_ev_count = _ev_df[_ev_df['신청일자'] == today_date].shape[0]

df_ev_new = pd.DataFrame({
    '날짜': [today_date],
    '개수': [_today_ev_count]
})

# 2) 기존 '지원_EV' 시트 읽기 (없으면 빈 DF)
try:
    df_ev = pd.read_excel("Q3.xlsx", sheet_name="지원_EV")
except ValueError:
    df_ev = pd.DataFrame(columns=['날짜', '개수'])

# 3) 새 데이터 붙이고 중복 제거 (기존 데이터 우선 유지)
df_ev = pd.concat([df_ev, df_ev_new], ignore_index=True)
df_ev = df_ev.drop_duplicates(subset=['날짜'], keep='first').reset_index(drop=True)

# 4) 다시 Q3.xlsx에 저장
with pd.ExcelWriter("Q3.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    df_ev.to_excel(writer, sheet_name="지원_EV", index=False)


# 3) 지급 신청 건수 최신화
# '지급신청일자'에 시분초가 포함되어 있으므로, 날짜 부분만 비교하여 필터링

df_distribution = pd.read_excel("C:/Users/HP/Desktop/그리트_공유/07_31_1758_EV_merged.xlsx", sheet_name="Sheet1")

df_payment = _ev_df[
    pd.to_datetime(_ev_df['지급신청일자'], errors='coerce').dt.strftime('%Y-%m-%d') == today_date
]

c_payment = df_payment['지급신청일자'].shape[0]

df_payment_new = pd.DataFrame({
    '날짜': [today_date],
    '배분': [pd.NA],
    '신청': [c_payment],
    '지급 잔여': [pd.NA]
})

# 4) 기존 '지급' 시트 읽기 (없으면 빈 DF)
try:
    df_pay_sheet = pd.read_excel("Q3.xlsx", sheet_name="지급")
    # 필요한 4개 컬럼만 유지, 없으면 추가
    expected_cols = ['날짜', '배분', '신청', '지급 잔여']
    for col in expected_cols:
        if col not in df_pay_sheet.columns:
            df_pay_sheet[col] = pd.NA
    df_pay_sheet = df_pay_sheet[expected_cols]
except ValueError:
    df_pay_sheet = pd.DataFrame(columns=['날짜', '배분', '신청', '지급 잔여'])

# 5) 새 데이터 붙이고 중복 제거 (기존 데이터 우선 유지)
df_pay_sheet = pd.concat([df_pay_sheet, df_payment_new], ignore_index=True)
df_pay_sheet = df_pay_sheet.drop_duplicates(subset=['날짜'], keep='first').reset_index(drop=True)

# 6) 다시 Q3.xlsx에 저장 (지급 시트만 교체)
with pd.ExcelWriter("Q3.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    df_pay_sheet.to_excel(writer, sheet_name="지급", index=False)





