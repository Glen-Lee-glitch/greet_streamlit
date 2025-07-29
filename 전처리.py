import pandas as pd
import pickle
import numpy as np

def preprocess_and_save_data():
    """
    원본 엑셀 파일들을 읽어와 필요한 전처리를 수행하고,
    처리된 데이터프레임과 변수를 pickle 파일로 저장합니다.
    """
    try:
        # --- 1. 데이터 로딩 (분기 할당 로직 제거) ---
        df = pd.read_excel("Greet_Subsidy.xlsx", sheet_name="DOA 박민정", header=1)
        
        df_1_q3 = pd.read_excel("Greet_Subsidy.xlsx", sheet_name="EV", header=1)
        print("Greet_Subsidy.xlsx의 'EV'(3분기)을 성공적으로 로드했습니다.")
        df_1_q2 = pd.read_excel("EV_Q2.xlsx")
        print("EV_Q2.xlsx(2분기)를 성공적으로 로드했습니다.")
        
        # 예외 처리: 무조건 2분기로 처리해야 할 RN 리스트
        forced_q2_rns = [
            'RN124283213',
            'RN124341831',
            'RN124366419',
            'RN124360770'
        ]
        
        # 3분기 데이터에서 예외 RN들을 먼저 제거
        df_1_q3 = df_1_q3[~df_1_q3['제조수입사\n관리번호'].isin(forced_q2_rns)]
        print(f"3분기 데이터에서 예외 처리 RN {len(forced_q2_rns)}건을 제거했습니다.")
        
        # 나머지 중복 제거 로직 수행
        existing_ids = df_1_q3['제조수입사\n관리번호'].dropna().unique()
        df_1_q2_filtered = df_1_q2[~df_1_q2['제조수입사\n관리번호'].isin(existing_ids)]
        df_1 = pd.concat([df_1_q3, df_1_q2_filtered], ignore_index=True)
        print("EV 데이터를 중복 제거 후 병합하였습니다.")

        df_time = pd.read_excel("Greet_Subsidy.xlsx", sheet_name="EV", header=0)
        
        df_2_q3 = pd.read_excel("Greet_Subsidy.xlsx", sheet_name='지급신청', header=3)
        df_2_q2 = pd.read_excel("Greet_Subsidy_2Q.xlsx", sheet_name='지급신청', header=3)
        df_2 = pd.concat([df_2_q3, df_2_q2], ignore_index=True)
        
        df_3 = pd.read_excel("Ent x Greet Lounge Subsidy.xlsx", sheet_name="지원신청", header=0)
        df_4 = pd.read_excel("Ent x Greet Lounge Subsidy.xlsx", sheet_name="지급신청", header=1)
        
        df_5_q3 = pd.read_excel("pipeline.xlsx", sheet_name='Sheet1')
        df_5_q2 = pd.read_excel("pipeline.xlsx", sheet_name='Sheet2')
        df_5 = pd.concat([df_5_q3, df_5_q2], ignore_index=True)
        
        print("모든 엑셀 파일 로딩 완료.")

        # --- 2. 데이터 전처리 ---
        df.drop(columns=['인도일', '알림톡'], inplace=True)
        df.rename(columns={'인도일.1': '인도일'}, inplace=True)
        update_time_str = df_time.columns[1]

        # 날짜 컬럼 타입 변환
        if '날짜' in df_5.columns:
            df_5['날짜'] = df_5['날짜'].astype(str)
            df_5['날짜'] = df_5['날짜'].str.replace(r'(\\d{1,2})\\s*월\\s*(\\d{1,2})\\s*일', r'\\1-\\2', regex=True)
        df_5['날짜'] = pd.to_datetime(df_5['날짜'], errors='coerce')
        df_1['신청일자'] = pd.to_datetime(df_1['신청일자'], errors='coerce')
        df_2['배분일'] = pd.to_datetime(df_2['배분일'], errors='coerce')
        df_1['지급신청일자_날짜'] = pd.to_datetime(df_1['지급신청일자'], errors='coerce')
        print("데이터 타입 변환 완료.")

        # --- 3. 분기 재정의 ---
        q2_start = pd.to_datetime('2025-04-03').date()
        q2_end = pd.to_datetime('2025-06-20').date()

        df_1['분기'] = np.where(df_1['신청일자'].dt.date.between(q2_start, q2_end), '2분기', '3분기')
        df_2['분기'] = np.where(df_2['배분일'].dt.date.between(q2_start, q2_end), '2분기', '3분기')
        df_5['분기'] = np.where(df_5['날짜'].dt.date.between(q2_start, q2_end), '2분기', '3분기')
        print("새로운 기준에 따라 분기 데이터 재정의 완료.")

        # --- 4. 전처리된 데이터 저장 ---
        data_to_save = {
            "df": df,
            "df_1": df_1,
            "df_2": df_2,
            "df_3": df_3,
            "df_4": df_4,
            "df_5": df_5,
            "update_time_str": update_time_str
        }

        with open("preprocessed_data.pkl", "wb") as f:
            pickle.dump(data_to_save, f)
            
        print("전처리된 데이터가 preprocessed_data.pkl 파일로 성공적으로 저장되었습니다.")

    except Exception as e:
        print(f"데이터 전처리 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    preprocess_and_save_data() 