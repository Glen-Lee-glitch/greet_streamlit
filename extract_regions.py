import os, json
import pandas as pd

# GeoJSON 파일 읽기
with open('HangJeongDong_ver20250401.geojson', 'r', encoding='utf-8') as f:
    seoul_geo = json.load(f)

# 지역 정보 추출
regions_data = []

for feature in seoul_geo['features']:
    properties = feature['properties']
    
    # 지역 정보 추출
    region_info = {
        'OBJECTID': properties.get('OBJECTID', ''),
        'adm_nm': properties.get('adm_nm', ''),  # 행정구역명
        'adm_cd': properties.get('adm_cd', ''),  # 행정구역코드
        'adm_cd2': properties.get('adm_cd2', ''),  # 행정구역코드2
        'sgg': properties.get('sgg', ''),  # 시군구코드
        'sido': properties.get('sido', ''),  # 시도코드
        'sidonm': properties.get('sidonm', ''),  # 시도명
        'sggnm': properties.get('sggnm', '')  # 시군구명
    }
    
    regions_data.append(region_info)

# DataFrame 생성
df = pd.DataFrame(regions_data)

# 엑셀 파일로 저장
output_file = 'seoul_regions_info.xlsx'
df.to_excel(output_file, index=False, engine='openpyxl')

print(f"지역 정보가 {output_file} 파일로 저장되었습니다.")
print(f"총 {len(df)}개의 지역 정보가 추출되었습니다.")

# 데이터 미리보기
print("\n=== 데이터 미리보기 ===")
print(df.head())

# 컬럼별 정보 요약
print("\n=== 컬럼별 정보 ===")
print(f"총 행 수: {len(df)}")
print(f"총 열 수: {len(df.columns)}")
print("\n컬럼 목록:")
for col in df.columns:
    print(f"- {col}")