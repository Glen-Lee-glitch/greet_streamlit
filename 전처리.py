import pandas as pd
import pickle

def preprocess_and_save_data():
    """
    원본 엑셀 파일들을 읽어와 필요한 전처리를 수행하고,
    처리된 데이터프레임과 변수를 pickle 파일로 저장합니다.
    """
    try:
        # --- 1. 데이터 로딩 ---
        df = pd.read_excel("Greet_Subsidy.xlsx", sheet_name="DOA 박민정", header=1)

        # --- 'EV' 데이터(df_1) 처리 ---
        df_1_q3 = None
        df_1_q2 = None

        # 3분기 데이터 로드
        try:
            df_1_q3 = pd.read_excel("Greet_Subsidy.xlsx", sheet_name="EV", header=1)
            df_1_q3['분기'] = '3분기'
            print("Greet_Subsidy.xlsx의 'EV'(3분기)을 성공적으로 로드했습니다.")
        except Exception as e:
            print(f"경고: Greet_Subsidy.xlsx의 'EV' 시트를 읽는 중 오류가 발생했습니다: {e}")

        # 2분기 데이터 로드
        try:
            df_1_q2 = pd.read_excel("EV_Q2.xlsx")
            df_1_q2['분기'] = '2분기'
            print("EV_Q2.xlsx(2분기)를 성공적으로 로드했습니다.")
        except FileNotFoundError:
            print("정보: EV_Q2.xlsx 파일을 찾을 수 없습니다.")
        except Exception as e:
            print(f"경고: EV_Q2.xlsx를 읽는 중 오류가 발생했습니다: {e}")

        # 데이터 병합
        if df_1_q3 is not None and df_1_q2 is not None:
            existing_ids = df_1_q3['제조수입사\n관리번호'].dropna().unique()
            df_1_q2_filtered = df_1_q2[~df_1_q2['제조수입사\n관리번호'].isin(existing_ids)]
            df_1 = pd.concat([df_1_q3, df_1_q2_filtered], ignore_index=True)
            print("EV 데이터를 중복 제거 후 병합하였습니다.")
        elif df_1_q3 is not None:
            df_1 = df_1_q3
        elif df_1_q2 is not None:
            df_1 = df_1_q2
        else:
            df_1 = pd.DataFrame(columns=['신청일자', '지급신청일자', '제조수입사\n관리번호', '분기'])
            print("경고: 'EV' 데이터를 읽지 못했습니다.")

        df_time = pd.read_excel("Greet_Subsidy.xlsx", sheet_name="EV", header=0)
        
        # '지급신청' 데이터(df_2) 로딩 및 분기 병합
        df_2_list = []
        try:
            df_2_q3 = pd.read_excel("Greet_Subsidy.xlsx", sheet_name='지급신청', header=3)
            df_2_q3['분기'] = '3분기'
            df_2_list.append(df_2_q3)
            print("Greet_Subsidy.xlsx의 '지급신청'(3분기)을 성공적으로 로드했습니다.")
        except Exception as e:
            print(f"경고: Greet_Subsidy.xlsx의 '지급신청' 시트를 읽는 중 오류가 발생했습니다: {e}")

        try:
            df_2_q2 = pd.read_excel("Greet_Subsidy_2Q.xlsx", sheet_name='지급신청', header=3)
            df_2_q2['분기'] = '2분기'
            df_2_list.append(df_2_q2)
            print("Greet_Subsidy_2Q.xlsx의 '지급신청'(2분기)을 성공적으로 로드했습니다.")
        except FileNotFoundError:
            print("정보: Greet_Subsidy_2Q.xlsx 파일을 찾을 수 없습니다.")
        except Exception as e:
            print(f"경고: Greet_Subsidy_2Q.xlsx의 '지급신청' 시트를 읽는 중 오류가 발생했습니다: {e}")
            
        if df_2_list:
            df_2 = pd.concat(df_2_list, ignore_index=True)
        else:
            df_2 = pd.DataFrame(columns=['배분일', '분기'])
            print("경고: '지급신청' 데이터를 읽지 못했습니다.")

        df_3 = pd.read_excel("Ent x Greet Lounge Subsidy.xlsx", sheet_name="지원신청", header=0)
        df_4 = pd.read_excel("Ent x Greet Lounge Subsidy.xlsx", sheet_name="지급신청", header=1)
        
        # pipeline.xlsx의 두 시트(3분기, 2분기)를 읽어와 병합
        df_5_list = []
        try:
            df_5_q3 = pd.read_excel("pipeline.xlsx", sheet_name='Sheet1')
            df_5_q3['분기'] = '3분기'
            df_5_list.append(df_5_q3)
            print("pipeline.xlsx의 Sheet1(3분기)을 성공적으로 로드했습니다.")
        except Exception as e:
            print(f"경고: pipeline.xlsx의 Sheet1을 읽는 중 오류가 발생했습니다: {e}")

        try:
            df_5_q2 = pd.read_excel("pipeline.xlsx", sheet_name='Sheet2')
            df_5_q2['분기'] = '2분기'
            df_5_list.append(df_5_q2)
            print("pipeline.xlsx의 Sheet2(2분기)를 성공적으로 로드했습니다.")
        except Exception as e:
            print(f"정보: pipeline.xlsx에 Sheet2가 없습니다. ({e})")
        
        if df_5_list:
            df_5 = pd.concat(df_5_list, ignore_index=True)
        else:
            # 파일을 전혀 읽지 못한 경우, 오류 방지를 위해 빈 데이터프레임 생성
            df_5 = pd.DataFrame(columns=['날짜', 'RN', '분기'])
            print("경고: pipeline.xlsx에서 데이터를 읽지 못했습니다.")

        print("엑셀 파일 로딩 완료.")

        # --- 2. 데이터 전처리 ---
        # df 전처리
        df.drop(columns=['인도일', '알림톡'], inplace=True)
        df.rename(columns={'인도일.1': '인도일'}, inplace=True)

        # update_time_str 추출
        update_time_str = df_time.columns[1]

        # 날짜 컬럼 타입 변환
        df_5['날짜'] = pd.to_datetime(df_5['날짜'], errors='coerce')
        df_1['신청일자'] = pd.to_datetime(df_1['신청일자'], errors='coerce')
        df_2['배분일'] = pd.to_datetime(df_2['배분일'], errors='coerce')
        df_1['지급신청일자_날짜'] = pd.to_datetime(df_1['지급신청일자'], errors='coerce')
        print("데이터 전처리 완료.")

        # --- 3. 전처리된 데이터 저장 ---
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

    except FileNotFoundError as e:
        print(f"오류: 파일을 찾을 수 없습니다. {e.filename} 파일이 스크립트와 동일한 경로에 있는지 확인하세요.")
    except Exception as e:
        print(f"데이터 전처리 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    preprocess_and_save_data() 