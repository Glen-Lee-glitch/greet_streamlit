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