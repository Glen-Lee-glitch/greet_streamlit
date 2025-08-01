import pandas as pd
import pickle
import numpy as np
from datetime import datetime


def preprocess_and_save_data():
    """
    Q3.xlsx, Q2.xlsx 파일에서 필요한 시트를 로드하여 전처리한 뒤
    preprocessed_data.pkl 로 저장합니다.
    """
    try:
        # ---------- 1. 파일 경로 및 시트 로딩 ----------
        q3_file = "Q3.xlsx"
        q2_file = "Q2.xlsx"
        q1_file = "Q1.xlsx"

        # 3분기 시트
        df_1_q3 = pd.read_excel(q3_file, sheet_name="지원_EV")      # 지원 데이터 (3분기)
        df_2_q3 = pd.read_excel(q3_file, sheet_name="지급")         # 지급 데이터 (3분기)
        df_5_q3 = pd.read_excel(q3_file, sheet_name="PipeLine")     # 파이프라인 데이터 (3분기)

        # 2분기 시트
        df_1_q2 = pd.read_excel(q2_file, sheet_name="지원_EV")      # 지원 데이터 (2분기)
        df_2_q2 = pd.read_excel(q2_file, sheet_name="지급")         # 지급 데이터 (2분기)
        df_5_q2 = pd.read_excel(q2_file, sheet_name="PipeLine")     # 파이프라인 데이터 (2분기)

        # 1분기 시트
        df_1_q1 = pd.read_excel(q1_file, sheet_name="지원_EV")      # 지원 데이터 (1분기)
        df_2_q1 = pd.read_excel(q1_file, sheet_name="지급")         # 지급 데이터 (1분기)
        df_5_q1_raw = pd.read_excel(q1_file, sheet_name="PipeLine") # 파이프라인 데이터 (1분기, 집계형)

        df_fail_q3 = pd.read_excel(q3_file, sheet_name="미신청건")
        df_2_fail_q3 = pd.read_excel(q3_file, sheet_name="지급_미지급건")

        # 1분기 PipeLine 시트는 날짜별 '개수'가 누적되어 있어 개수만큼 행을 복제하여 확장합니다.
        df_5_q1_list = []
        if {'날짜', '개수'}.issubset(df_5_q1_raw.columns):
            df_5_q1_raw['날짜'] = pd.to_datetime(df_5_q1_raw['날짜'], errors='coerce')
            df_5_q1_raw = df_5_q1_raw.dropna(subset=['날짜', '개수'])
            for _, row in df_5_q1_raw.iterrows():
                df_5_q1_list.append(pd.DataFrame({'날짜': [row['날짜']]*int(row['개수'])}))
            df_5_q1 = pd.concat(df_5_q1_list, ignore_index=True) if df_5_q1_list else pd.DataFrame(columns=['날짜'])
        else:
            df_5_q1 = df_5_q1_raw.copy()

        print("Q3.xlsx, Q2.xlsx, Q1.xlsx의 시트를 성공적으로 로드했습니다.")

        # ---------- 추가: 테슬라 판매현황 로드 ----------
        tesla_sales_file = "테슬라_판매현황.xlsx"
        try:
            df_sales = pd.read_excel(tesla_sales_file)  # 컬럼: 월, 대수
            # 데이터 타입 변환
            if '월' in df_sales.columns:
                df_sales['월'] = pd.to_numeric(df_sales['월'], errors='coerce')
            if '대수' in df_sales.columns:
                df_sales['대수'] = pd.to_numeric(df_sales['대수'], errors='coerce')
            print("테슬라 판매현황 데이터를 로드했습니다.")
        except FileNotFoundError:
            print("'테슬라_판매현황.xlsx' 파일을 찾을 수 없습니다. 판매현황 데이터는 빈 DataFrame으로 저장됩니다.")
            df_sales = pd.DataFrame()
        except Exception as e:
            print(f"테슬라 판매현황을 불러오는 중 오류: {e}")
            df_sales = pd.DataFrame()

        # ---------- 2. 분기 컬럼 추가 및 병합 ----------
        df_1_q3["분기"] = "3분기"; df_1_q2["분기"] = "2분기"; df_1_q1["분기"] = "1분기"
        df_2_q3["분기"] = "3분기"; df_2_q2["분기"] = "2분기"; df_2_q1["분기"] = "1분기"
        df_5_q3["분기"] = "3분기"; df_5_q2["분기"] = "2분기"; df_5_q1["분기"] = "1분기"

        # 1분기는 2월~3월 데이터만 포함합니다.
        for _df in [df_1_q1, df_2_q1, df_5_q1]:
            if "날짜" in _df.columns:
                _df["날짜"] = pd.to_datetime(_df["날짜"], errors="coerce")
        df_1_q1 = df_1_q1[df_1_q1["날짜"].dt.month.isin([2,3])]
        df_2_q1 = df_2_q1[df_2_q1["날짜"].dt.month.isin([2,3])]
        df_5_q1 = df_5_q1[df_5_q1["날짜"].dt.month.isin([2,3])]

        # 병합
        df_1 = pd.concat([df_1_q3, df_1_q2, df_1_q1], ignore_index=True)
        df_2 = pd.concat([df_2_q3, df_2_q2, df_2_q1], ignore_index=True)
        df_5 = pd.concat([df_5_q3, df_5_q2, df_5_q1], ignore_index=True)

        # ---------- 3. 날짜 컬럼 타입 변환 ----------
        # PipeLine / 지원 / 지급 시트 공통으로 '날짜' 컬럼 존재
        for _df in [df_5, df_1, df_2]:
            if "날짜" in _df.columns:
                _df["날짜"] = pd.to_datetime(_df["날짜"], errors="coerce")

        # 지원 시트에 '지급신청일자'가 있다면 추가 변환 (기존 코드 호환)
        if "지급신청일자" in df_1.columns:
            df_1["지급신청일자_날짜"] = pd.to_datetime(df_1["지급신청일자"], errors="coerce")

        # ---------- 4. 업데이트 시간 ----------
        update_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ---------- 5. 기타 데이터 (변경 없음) ----------
        # 필요 시 다른 엑셀 파일도 그대로 로드합니다.
        try:
            df_3 = pd.read_excel("Ent x Greet Lounge Subsidy.xlsx", sheet_name="지원신청", header=0)
            df_4 = pd.read_excel("Ent x Greet Lounge Subsidy.xlsx", sheet_name="지급신청", header=1)
        except FileNotFoundError:
            # 파일이 없는 경우 빈 DataFrame 생성하여 이후 로직 오류 방지
            df_3 = pd.DataFrame()
            df_4 = pd.DataFrame()

        # ---------- 6. 저장 ----------
        data_to_save = {
            "df": pd.DataFrame(),  # 더 이상 사용되지 않지만 구조 유지
            "df_1": df_1,
            "df_2": df_2,
            "df_3": df_3,
            "df_4": df_4,
            "df_5": df_5,
            "df_sales": df_sales,
            "df_fail_q3": df_fail_q3,
            "df_2_fail_q3": df_2_fail_q3,
            "update_time_str": update_time_str
        }

        with open("preprocessed_data.pkl", "wb") as f:
            pickle.dump(data_to_save, f)

        print("전처리 완료 및 preprocessed_data.pkl 저장")

    except Exception as e:
        print(f"전처리 중 오류: {e}")


if __name__ == "__main__":
    preprocess_and_save_data() 