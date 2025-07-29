import pickle
import pandas as pd

def inspect_pickle_file(filepath="preprocessed_data.pkl"):
    """
    지정된 pickle 파일을 열고 그 안에 저장된 데이터프레임의
    정보를 출력하여 디버깅을 돕습니다.
    """
    try:
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        
        print(f"'{filepath}' 파일 로드 성공.")
        print("-" * 30)

        if "df_1" in data:
            print("'df_1' 데이터프레임 정보를 확인합니다.")
            df_1 = data["df_1"]
            if isinstance(df_1, pd.DataFrame):
                print("df_1의 컬럼 목록:")
                print(df_1.columns.to_list())
                
                if '분기' in df_1.columns:
                    print("\n'분기' 컬럼이 존재합니다.")
                    print("분기별 데이터 개수:")
                    print(df_1['분기'].value_counts())
                else:
                    print("\n[오류 원인] '분기' 컬럼이 존재하지 않습니다.")
                
            else:
                print("'df_1'은 데이터프레임이 아닙니다.")
        else:
            print("'df_1' 키가 파일에 존재하지 않습니다.")

    except FileNotFoundError:
        print(f"오류: '{filepath}' 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"파일을 읽는 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    inspect_pickle_file() 