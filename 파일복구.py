import pickle
import pandas as pd

# 1) preprocessed_data.pkl 로드
with open("preprocessed_data.pkl", "rb") as f:
    data_dict = pickle.load(f)

# 2) 각 시트별 3분기 데이터 추출
df_1_q3 = data_dict["df_1"]
df_2_q3 = data_dict["df_2"]
df_5_q3 = data_dict["df_5"]
df_fail_q3 = data_dict["df_fail_q3"]
df_2_fail_q3 = data_dict["df_2_fail_q3"]

# 3) 3분기만 필터링 (df_1, df_2, df_5)
df_1_q3 = df_1_q3[df_1_q3["분기"] == "3분기"].copy()
df_2_q3 = df_2_q3[df_2_q3["분기"] == "3분기"].copy()
df_5_q3 = df_5_q3[df_5_q3["분기"] == "3분기"].copy()

# 4) '분기' 컬럼 제거 (원본 Q3.xlsx에는 없음)
for df in [df_1_q3, df_2_q3, df_5_q3]:
    if "분기" in df.columns:
        df.drop(columns=["분기"], inplace=True)

# 5) 엑셀 파일로 저장
out_file = "Q3_복구.xlsx"
with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
    df_1_q3.to_excel(writer, sheet_name="지원_EV", index=False)
    df_2_q3.to_excel(writer, sheet_name="지급", index=False)
    df_5_q3.to_excel(writer, sheet_name="PipeLine", index=False)
    df_fail_q3.to_excel(writer, sheet_name="미신청건", index=False)
    df_2_fail_q3.to_excel(writer, sheet_name="지급_미지급건", index=False)

print(f"Q3.xlsx 복구 완료: {out_file}")