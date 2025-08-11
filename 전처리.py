import pandas as pd
import pickle
import numpy as np
import sqlite3
from datetime import datetime
import json

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

        # polestar_file 로드 부분을 data.db 사용으로 수정
        try:
            # 데이터베이스에서 폴스타 데이터 로드
            def load_polestar_from_db():
                """data.db에서 폴스타 데이터를 DataFrame으로 로드"""
                try:
                    conn = sqlite3.connect('data.db')
                    
                    # 파이프라인 데이터 조회
                    pipeline_query = '''
                        SELECT 날짜, 파이프라인
                        FROM 파이프라인 
                        WHERE strftime('%Y', 날짜) = '2025'
                        ORDER BY 날짜
                    '''
                    df_pole_pipeline = pd.read_sql_query(pipeline_query, conn)
                    
                    # 지원신청 데이터 조회
                    support_query = '''
                        SELECT 날짜, 지원신청, PAK_내부지원, 접수후취소, 미신청건, 보완
                        FROM 지원신청 
                        WHERE strftime('%Y', 날짜) = '2025'
                        ORDER BY 날짜
                    '''
                    df_pole_apply = pd.read_sql_query(support_query, conn)
                    
                    # 날짜 컬럼 타입 변환
                    if not df_pole_pipeline.empty and '날짜' in df_pole_pipeline.columns:
                        df_pole_pipeline['날짜'] = pd.to_datetime(df_pole_pipeline['날짜'], errors='coerce')
                    if not df_pole_apply.empty and '날짜' in df_pole_apply.columns:
                        df_pole_apply['날짜'] = pd.to_datetime(df_pole_apply['날짜'], errors='coerce')
                    
                    conn.close()
                    return df_pole_pipeline, df_pole_apply
                    
                except sqlite3.Error as e:
                    print(f"데이터베이스에서 폴스타 데이터 로드 중 오류: {e}")
                    return pd.DataFrame(), pd.DataFrame()
                except Exception as e:
                    print(f"폴스타 데이터 처리 중 오류: {e}")
                    return pd.DataFrame(), pd.DataFrame()
            
            df_pole_pipeline, df_pole_apply = load_polestar_from_db()
            print("data.db에서 폴스타 데이터를 로드했습니다.")
            
        except Exception as e:
            print(f"폴스타 데이터 로드 중 오류: {e}")
            df_pole_pipeline = pd.DataFrame()
            df_pole_apply = pd.DataFrame()

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

        # --- 추가: 지자체 정리 master.xlsx 로드
        try:
            df_master = pd.read_excel("master.xlsx")
            df_master = df_master[['지역', '현황_일반', '현황_우선', 'Model 3 RWD_기본', 'Model 3 RWD(2024)_기본', 'Model 3 LongRange_기본', 'Model 3 Performance_기본', 'Model Y New RWD_기본', 'Model Y New LongRange_기본', '지원신청서류', '지급신청서류']]
            print("지자체 정리 데이터를 로드했습니다.")
        except FileNotFoundError:
            print("'master.xlsx' 파일을 찾을 수 없습니다. 지자체 정리 데이터는 빈 DataFrame으로 저장됩니다.")
            df_master = pd.DataFrame()
        except Exception as e:
            print(f"지자체 정리 데이터 로드 중 오류: {e}")
            df_master = pd.DataFrame()

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

        try:
            df_6 = pd.read_excel("2025년 테슬라 EV추출파일.xlsx")
            df_6 = df_6[['지역구분', '신청일자', '주소\n(등록주소지)']]
        except FileNotFoundError:
            df_6 = pd.DataFrame()

        # ---------- 추가: test1.py용 테슬라 EV 데이터 전처리 ----------
        try:
            df_tesla_ev = pd.read_excel("2025년 테슬라 EV추출파일.xlsx")
            
            # 분류 함수들
            def classify_tesla_model(car_type):
                if pd.isna(car_type): return "기타"
                car_type_str = str(car_type).strip()
                if 'Model Y' in car_type_str: return 'Model Y'
                if 'Model 3' in car_type_str: return 'Model 3'
                return "기타"

            def classify_applicant_type(applicant_type):
                if pd.isna(applicant_type): return "기타"
                applicant_str = str(applicant_type).strip()
                if '개인사업자' in applicant_str: return '개인사업자'
                if '단체' in applicant_str or '법인' in applicant_str: return '법인'
                if '개인' in applicant_str: return '개인'
                return "기타"

            def calculate_age(birth_date_str):
                if pd.isna(birth_date_str): return None
                try:
                    birth_date_str = str(birth_date_str).strip()
                    if len(birth_date_str) == 10 and birth_date_str.isdigit(): return None # 법인번호
                    
                    # 다양한 날짜 형식 처리
                    if len(birth_date_str) == 8 and birth_date_str.isdigit():
                        birth_date = datetime.strptime(birth_date_str, '%Y%m%d').date()
                    elif '-' in birth_date_str:
                        birth_date = datetime.strptime(birth_date_str.split(' ')[0], '%Y-%m-%d').date()
                    else:
                        return None
                    
                    today = datetime.now().date()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    return age if 0 <= age <= 120 else None
                except:
                    return None

            def classify_age_group(age):
                if age is None: return "미상"
                if age < 20: return "10대"
                if age < 30: return "20대"
                if age < 40: return "30대"
                if age < 50: return "40대"
                if age < 60: return "50대"
                if age < 70: return "60대"
                return "70대 이상"

            # 전처리 실행
            df_tesla_ev['분류된_차종'] = df_tesla_ev['차종'].apply(classify_tesla_model)
            df_tesla_ev['분류된_신청유형'] = df_tesla_ev['신청유형'].apply(classify_applicant_type)
            
            # 작성자 이름 변환
            if '작성자' in df_tesla_ev.columns:
                df_tesla_ev['작성자'] = df_tesla_ev['작성자'].replace('WU CHANGSHI', '오창실')
            
            # 날짜/시간 컬럼 처리
            date_col = next((col for col in df_tesla_ev.columns if '신청일자' in col), None)
            if date_col:
                df_tesla_ev[date_col] = pd.to_datetime(df_tesla_ev[date_col], errors='coerce')
            
            birth_date_col = next((col for col in df_tesla_ev.columns if '생년월일' in col or '법인' in col), None)
            if birth_date_col:
                df_tesla_ev['나이'] = df_tesla_ev[birth_date_col].apply(calculate_age)
                df_tesla_ev['연령대'] = df_tesla_ev['나이'].apply(classify_age_group)

            print("테슬라 EV 데이터 전처리 완료")
        except FileNotFoundError:
            print("'2025년 테슬라 EV추출파일.xlsx' 파일을 찾을 수 없습니다. 테슬라 EV 데이터는 빈 DataFrame으로 저장됩니다.")
            df_tesla_ev = pd.DataFrame()
        except Exception as e:
            print(f"테슬라 EV 데이터 전처리 중 오류: {e}")
            df_tesla_ev = pd.DataFrame()

        try:
            with open("preprocessed_map.geojson", "r", encoding="utf-8") as f:
                preprocessed_map_geojson = json.load(f)
            print("전처리된 지도 데이터(preprocessed_map.geojson)를 로드했습니다.")
        except FileNotFoundError:
            print("'preprocessed_map.geojson' 파일을 찾을 수 없습니다. 먼저 preprocess_map.py를 실행해주세요.")
            preprocessed_map_geojson = None

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
            "update_time_str": update_time_str,
            "df_master": df_master,
            "df_6": df_6,
            "preprocessed_map_geojson": preprocessed_map_geojson,
            "df_tesla_ev": df_tesla_ev,  # test1.py용 테슬라 EV 데이터
            "df_pole_pipeline": df_pole_pipeline,
            "df_pole_apply": df_pole_apply
        }

        with open("preprocessed_data.pkl", "wb") as f:
            pickle.dump(data_to_save, f)

        print("전처리 완료 및 preprocessed_data.pkl 저장")

    except Exception as e:
        print(f"전처리 중 오류: {e}")


if __name__ == "__main__":
    preprocess_and_save_data() 