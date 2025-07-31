import pickle
import pandas as pd

# 1) preprocessed_data.pkl 로드
with open("preprocessed_data.pkl", "rb") as f:
    data_dict = pickle.load(f)

df_1 = data_dict["df_1"]  # 지원 데이터(2·3분기 모두 포함)

# 2) 3분기 원본만 추출
df_1_q3 = df_1[df_1["분기"] == "3분기"].copy()

# 3) '분기' 열은 필요 없으면 제거
df_1_q3.drop(columns=["분기"], inplace=True)

# 4) 새 파일로 저장
out_file = "지원_EV_복구.xlsx"
with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
    df_1_q3.to_excel(writer, sheet_name="지원_EV", index=False)

print(f"복원 완료: {out_file}")