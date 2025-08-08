import json
from shapely.geometry import shape
from shapely.ops import unary_union
import pandas as pd

def create_preprocessed_map(geojson_path, output_path):
    """
    원본 GeoJSON 파일을 로드하여 '시도' 및 '시군구' 단위로 경계를 병합하고,
    최적화된 새 GeoJSON 파일을 생성합니다.
    """
    try:
        # 1. 원본 GeoJSON 파일 로드
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        print("✅ 원본 GeoJSON 파일 로드 완료")

        # --- 2. GeoJSON 그룹화 ---
        sido_geoms_for_merge = {} 
        sgg_geoms_for_merge = {}  

        metro_sido_list = [
            '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시', 
            '울산광역시', '세종특별자치시', '제주특별자치도'
        ]
        general_si_with_gu = ['고양시', '성남시', '수원시', '안산시', '안양시', '용인시', '창원시', '청주시', '포항시', '천안시', '전주시']

        for feature in geojson_data['features']:
            properties = feature['properties']
            sido = properties.get('sidonm', '')
            sgg = properties.get('sggnm', '')
            if not (sido and sgg and feature.get('geometry')):
                continue

            geom = shape(feature['geometry'])

            if sido in metro_sido_list:
                if sido not in sido_geoms_for_merge:
                    sido_geoms_for_merge[sido] = []
                sido_geoms_for_merge[sido].append(geom)
            else:
                base_sgg = sgg
                for city in general_si_with_gu:
                    if city in sgg:
                        base_sgg = city
                        break
                key = f"{sido} {base_sgg}"
                if key not in sgg_geoms_for_merge:
                    sgg_geoms_for_merge[key] = []
                sgg_geoms_for_merge[key].append(geom)

        # --- 3. 지오메트리 병합 ---
        base_map_geoms = {}
        print("⏳ 경계 병합 작업 시작...")
        for sido, geoms in sido_geoms_for_merge.items():
            if geoms: base_map_geoms[sido] = unary_union(geoms)
        for sgg, geoms in sgg_geoms_for_merge.items():
            if geoms: base_map_geoms[sgg] = unary_union(geoms)
        print("✅ 경계 병합 완료")

        # --- 4. 최종 GeoJSON 생성 ---
        merged_features = []
        for region_key, geom in base_map_geoms.items():
            feature = {
                'type': 'Feature',
                'geometry': geom.__geo_interface__,
                'properties': {'sggnm': region_key} # key만 저장
            }
            merged_features.append(feature)

        final_geojson = {'type': 'FeatureCollection', 'features': merged_features}

        # --- 5. 결과 파일 저장 ---
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(final_geojson, f)
        
        print(f"🎉 전처리 완료! 최적화된 지도 파일 '{output_path}'이 생성되었습니다.")

    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    # 이 스크립트를 실행하여 preprocessed_map.geojson 파일을 생성합니다.
    create_preprocessed_map('HangJeongDong_ver20250401.geojson', 'preprocessed_map.geojson')