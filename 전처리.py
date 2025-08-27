import pandas as pd
import pickle
import numpy as np
import sqlite3
from datetime import datetime
import json
import subprocess
import os

conn = sqlite3.connect('data.db')

def git_push_generated_files():
    """전처리 스크립트로 생성된 데이터 파일들을 Git에 자동으로 커밋하고 푸시합니다."""
    
    files_to_push = ["preprocessed_data.pkl"]
    existing_files_to_push = [f for f in files_to_push if os.path.exists(f)]

    if not existing_files_to_push:
        print("푸시할 데이터 파일이 존재하지 않습니다.")
        return

    try:
        # 1. 변경 사항 확인
        status_command = ["git", "status", "--porcelain"] + existing_files_to_push
        status_result = subprocess.run(
            status_command,
            capture_output=True, text=True, check=True, encoding='utf-8'
        )

        # 변경 사항이 없으면 함수 종료
        if not status_result.stdout.strip():
            print(f"{', '.join(existing_files_to_push)} 파일에 변경 사항이 없어 Git push를 건너뜁니다.")
            return

        # 2. Git 작업 수행
        print(f"{', '.join(existing_files_to_push)} 파일 변경 사항을 감지하여 Git에 푸시합니다.")
        
        # Git Pull
        print("원격 저장소의 변경 사항을 먼저 가져옵니다 (git pull)...")
        subprocess.run(["git", "pull"], check=True)
        
        # Git Add
        add_command = ["git", "add"] + existing_files_to_push
        subprocess.run(add_command, check=True)
        
        # Git Commit
        commit_message = "docs: 데이터 파일 자동 업데이트 (preprocessed_data.pkl 등)"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        
        # Git Push
        print("원격 저장소로 푸시합니다 (git push)...")
        subprocess.run(["git", "push"], check=True)
        
        print("데이터 파일이 성공적으로 GitHub에 푸시되었습니다.")

    except subprocess.CalledProcessError as e:
        error_output = e.stderr or e.stdout
        print(f"Git 작업 중 오류 발생: {e.stdout.decode('utf-8', errors='ignore')} {e.stderr.decode('utf-8', errors='ignore')}")
    except FileNotFoundError:
        print("Git command를 찾을 수 없습니다. Git이 설치되어 있고 PATH에 등록되어 있는지 확인하세요.")

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
        # df_1_q3 = pd.read_excel(q3_file, sheet_name="지원_EV")      # 지원 데이터 (3분기)
        df_1_q3 = pd.read_sql_query('SELECT * FROM 테슬라_지원신청', conn)
        # df_2_q3 = pd.read_excel(q3_file, sheet_name="지급")         # 지급 데이터 (3분기)
        df_2_q3 = pd.read_sql_query('SELECT * FROM 테슬라_지급', conn)
        # df_5_q3 = pd.read_excel(q3_file, sheet_name="PipeLine")     # 파이프라인 데이터 (3분기)
        df_5_q3 = pd.read_sql_query('SELECT * FROM pipeline', conn)

        # 2분기 시트
        df_1_q2 = pd.read_excel(q2_file, sheet_name="지원_EV")      # 지원 데이터 (2분기)
        df_2_q2 = pd.read_excel(q2_file, sheet_name="지급")         # 지급 데이터 (2분기)
        df_5_q2 = pd.read_excel(q2_file, sheet_name="PipeLine")     # 파이프라인 데이터 (2분기)

        # 1분기 시트
        df_1_q1 = pd.read_excel(q1_file, sheet_name="지원_EV")      # 지원 데이터 (1분기)
        df_2_q1 = pd.read_excel(q1_file, sheet_name="지급")         # 지급 데이터 (1분기)
        df_5_q1_raw = pd.read_excel(q1_file, sheet_name="PipeLine") # 파이프라인 데이터 (1분기, 집계형)

        df_fail_q3 = pd.read_excel(q3_file, sheet_name="미신청건")
        df_2_fail_q3 = pd.read_sql_query("SELECT 날짜, 지급_잔여 AS 미신청건 FROM 테슬라_지급", conn)

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

        # ---------- 추가: 전기차 신청현황 로드 ----------
        ev_status_file = "전기차 신청현황.xls"
        try:
            # 첫 번째 표: 신청금액 관련 데이터 (header=4, 데이터 8행, 칼럼수 6개로 제한)
            df_ev_amount = pd.read_excel(ev_status_file, header=4, nrows=8).iloc[:, :6]
            df_ev_amount.columns = ['단계', '신청대수', '신청국비(만원)', '신청지방비(만원)', '신청추가지원금(만원)', '신청금액합산(만원)']
            
            # 두 번째 표: 단계별 진행현황 데이터 (header=17, 데이터 1행)
            df_ev_step = pd.read_excel(ev_status_file, header=17, nrows=1).iloc[:1,:]
            df_ev_step.columns = ['차종', '신청', '승인', '출고', '자격부여', '대상자선정', '지급신청', '지급완료', '취소']
            
            print("전기차 신청현황 데이터를 로드했습니다.")
        except FileNotFoundError:
            print("'전기차 신청현황.xls' 파일을 찾을 수 없습니다. 전기차 신청현황 데이터는 빈 DataFrame으로 저장됩니다.")
            df_ev_amount = pd.DataFrame()
            df_ev_step = pd.DataFrame()
        except Exception as e:
            print(f"전기차 신청현황을 불러오는 중 오류: {e}")
            df_ev_amount = pd.DataFrame()
            df_ev_step = pd.DataFrame()

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
            # 필요한 컬럼만 선별(존재하는 경우에만)
            df6_keep_cols = ['지역구분', '신청일자', '주소\n(등록주소지)', '성별', '생년월일\n(법인등록번호)']
            existing_cols = [c for c in df6_keep_cols if c in df_6.columns]
            df_6 = df_6[existing_cols]

            # df_6용 연령/연령대 계산 유틸
            def _calculate_age_generic(birth_value):
                if pd.isna(birth_value):
                    return None
                try:
                    birth_str = str(birth_value).strip()
                    # 10자리 전부 숫자인 경우(법인등록번호 패턴) 제외
                    if len(birth_str) == 10 and birth_str.isdigit():
                        return None
                    if len(birth_str) == 8 and birth_str.isdigit():
                        birth_date = datetime.strptime(birth_str, '%Y%m%d').date()
                    elif '-' in birth_str:
                        birth_date = datetime.strptime(birth_str.split(' ')[0], '%Y-%m-%d').date()
                    else:
                        return None
                    today = datetime.now().date()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    return age if 0 <= age <= 120 else None
                except Exception:
                    return None

            def _classify_age_group_generic(age):
                if age is None:
                    return "미상"
                if age < 20:
                    return "10대"
                if age < 30:
                    return "20대"
                if age < 40:
                    return "30대"
                if age < 50:
                    return "40대"
                if age < 60:
                    return "50대"
                if age < 70:
                    return "60대"
                return "70대 이상"

            # 날짜 파싱 및 연령대 생성
            if '신청일자' in df_6.columns:
                df_6['신청일자'] = pd.to_datetime(df_6['신청일자'], errors='coerce')
            birth_col = '생년월일\n(법인등록번호)'
            if birth_col in df_6.columns:
                df_6['나이'] = df_6[birth_col].apply(_calculate_age_generic)
                df_6['연령대'] = df_6['나이'].apply(_classify_age_group_generic)
        except FileNotFoundError:
            df_6 = pd.DataFrame()

        def precompute_quarterly_counts(df_6):
            """분기별 지역 카운트를 미리 계산하여 저장"""
            if df_6.empty:
                return {}
            
            # 신청일자 컬럼 처리
            df_6_copy = df_6.copy()
            df_6_copy['신청일자'] = pd.to_datetime(df_6_copy['신청일자'], errors='coerce')
            
            quarterly_counts = {
                '전체': df_6_copy['지역구분'].value_counts().to_dict(),
                '1Q': df_6_copy[df_6_copy['신청일자'].dt.month.isin([1,2,3])]['지역구분'].value_counts().to_dict(),
                '2Q': df_6_copy[df_6_copy['신청일자'].dt.month.isin([4,5,6])]['지역구분'].value_counts().to_dict(),
                '3Q': df_6_copy[df_6_copy['신청일자'].dt.month.isin([7,8,9])]['지역구분'].value_counts().to_dict(),
                '4Q': df_6_copy[df_6_copy['신청일자'].dt.month.isin([10,11,12])]['지역구분'].value_counts().to_dict()
            }
            return quarterly_counts

        quarterly_region_counts = precompute_quarterly_counts(df_6)

        # ---------- 추가: 그리트_공유 폴더 데이터 로드 ----------
        def load_grit_shared_data():
            """그리트_공유 폴더에서 전기차 보조금 관련 데이터 로드"""
            try:
                folder_path = 'C:/Users/HP/Desktop/그리트_공유/파일'
                
                # 총괄현황 데이터
                overview_file = folder_path + '/총괄현황(전기자동차 승용).xls'
                df_overview = pd.read_excel(overview_file, header=3, engine='xlrd')
                
                # 컬럼명 설정
                columns = [
                    '시도', '지역', '차종', '접수방법', '공고_요약', '공고_전체', '공고_우선순위', '공고_법인기관', '공고_택시', '공고_일반',
                    '접수_요약', '접수_전체', '접수_우선순위', '접수_법인기관', '접수_택시', '접수_일반',
                    '잔여_전체', '잔여_일반', '출고_전체', '출고_일반', '출고잔여_요약', '비고'
                ]
                
                if len(df_overview.columns) == len(columns):
                    df_overview.columns = columns
                
                # 숫자형 컬럼 변환
                numeric_cols = ['공고_전체', '공고_우선순위', '공고_일반', '접수_전체', '접수_우선순위', '접수_일반',
                               '잔여_전체', '잔여_일반', '출고_일반']
                
                for col in numeric_cols:
                    if col in df_overview.columns:
                        df_overview[col] = pd.to_numeric(df_overview[col], errors='coerce').fillna(0)
                
                # 신청현황 데이터
                status_file = folder_path + '/전기차 신청현황.xls'
                df_amount = pd.read_excel(status_file, header=4, nrows=8, engine='xlrd').iloc[:, :6]
                df_amount.columns = ['단계', '신청대수', '신청국비(만원)', '신청지방비(만원)', '신청추가지원금(만원)', '신청금액합산(만원)']
                
                df_step = pd.read_excel(status_file, header=17, nrows=1, engine='xlrd').iloc[:1,:]
                df_step.columns = ['차종', '신청', '승인', '출고', '자격부여', '대상자선정', '지급신청', '지급완료', '취소']
                
                # 숫자형 변환
                amount_cols = ['신청대수', '신청국비(만원)', '신청지방비(만원)', '신청추가지원금(만원)', '신청금액합산(만원)']
                for col in amount_cols:
                    if col in df_amount.columns:
                        df_amount[col] = df_amount[col].astype(str).str.replace(',', '').replace('nan', '0')
                        df_amount[col] = pd.to_numeric(df_amount[col], errors='coerce').fillna(0)
                
                step_cols = ['신청', '승인', '출고', '자격부여', '대상자선정', '지급신청', '지급완료', '취소']
                for col in step_cols:
                    if col in df_step.columns:
                        df_step[col] = pd.to_numeric(df_step[col], errors='coerce').fillna(0)
                
                return df_overview, df_amount, df_step
                
            except Exception as e:
                print(f"그리트_공유 데이터 로드 오류: {e}")
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # 그리트_공유 폴더 데이터 로드 실행
        df_grit_overview, df_grit_amount, df_grit_step = load_grit_shared_data()
        print("그리트_공유 폴더 데이터를 로드했습니다.")

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
            "df_pole_apply": df_pole_apply,
            "quarterly_region_counts": quarterly_region_counts,
            "df_ev_amount": df_ev_amount,  # 전기차 신청금액 현황
            "df_ev_step": df_ev_step,      # 전기차 단계별 진행현황
            "df_grit_overview": df_grit_overview,  # 그리트_공유 총괄현황 데이터
            "df_grit_amount": df_grit_amount,      # 그리트_공유 신청금액 데이터  
            "df_grit_step": df_grit_step           # 그리트_공유 단계별 진행현황 데이터
        }

        with open("preprocessed_data.pkl", "wb") as f:
            pickle.dump(data_to_save, f)

        print("전처리 완료 및 preprocessed_data.pkl 저장")

        # ---------- 추가 저장: df_6, df_tesla_ev를 개별 pkl로 저장(간단 최적화 포함) ----------
        try:
            # df_6 최적화 및 저장
            if 'df_6' in data_to_save:
                df_6_opt = data_to_save['df_6'].copy()
                if not df_6_opt.empty:
                    # 날짜 파싱 및 카테고리 변환으로 메모리 최적화
                    if '신청일자' in df_6_opt.columns:
                        df_6_opt['신청일자'] = pd.to_datetime(df_6_opt['신청일자'], errors='coerce')
                    for col in ['지역구분', '주소\n(등록주소지)', '성별', '연령대']:
                        if col in df_6_opt.columns:
                            df_6_opt[col] = df_6_opt[col].astype('category')
                    df_6_opt.to_pickle("df_6.pkl.gz", compression="gzip")
                    print("df_6.pkl.gz 저장(압축, 경량화) 완료")

            # df_tesla_ev 최적화 및 저장
            if 'df_tesla_ev' in data_to_save:
                df_tesla_ev_opt = data_to_save['df_tesla_ev'].copy()
                if not df_tesla_ev_opt.empty:
                    # 범주형 컬럼은 카테고리로 변환하여 크기 축소
                    for col in ['작성자', '분류된_차종', '분류된_신청유형', '연령대']:
                        if col in df_tesla_ev_opt.columns:
                            df_tesla_ev_opt[col] = df_tesla_ev_opt[col].astype('category')
                    df_tesla_ev_opt.to_pickle("df_tesla_ev.pkl.gz", compression="gzip")
                    print("df_tesla_ev.pkl.gz 저장(압축, 경량화) 완료")
        except Exception as e:
            print(f"개별 pkl 저장 중 오류: {e}")

        # 모든 파일 저장 후 Git에 푸시
        git_push_generated_files()

    except Exception as e:
        print(f"전처리 중 오류: {e}")


if __name__ == "__main__":
    preprocess_and_save_data() 