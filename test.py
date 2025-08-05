import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import altair as alt
import pickle
import sys
from datetime import datetime, timedelta
import pytz
import folium
from streamlit_folium import folium_static

# --- 페이지 설정 및 기본 스타일 ---
st.set_page_config(layout="wide")
st.markdown("""
<style>
    /* 기본 테이블 스타일 */
    .custom_table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }
    .custom_table th, .custom_table td {
        border: 1px solid #e0e0e0;
        padding: 8px;
        text-align: center;
    }
    .custom_table th {
        background-color: #f7f7f9;
        font-weight: bold;
    }
    .custom_table tr:nth-child(even) {
        background-color: #fafafa;
    }
    /* 사이드바 스타일 */
    .css-1d391kg {
        padding-top: 3rem;
    }
    /* 인쇄 또는 PDF 생성 시 불필요한 UI 숨기기 */
    @media print {
        /* 사이드바와 모든 no-print 클래스 요소 숨기기 */
        div[data-testid="stSidebar"], .no-print {
            display: none !important;
        }
        /* 메인 콘텐츠 영역 패딩 조절 */
        .main .block-container {
            padding: 1rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)


# --- 데이터 및 메모 로딩 함수 ---
@st.cache_data(ttl=3600)
def load_data():
    """전처리된 데이터 파일을 로드합니다."""
    try:
        with open("preprocessed_data.pkl", "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        st.error("전처리된 데이터 파일(preprocessed_data.pkl)을 찾을 수 없습니다.")
        st.info("먼저 '전처리.py'를 실행하여 데이터 파일을 생성해주세요.")
        sys.exit()

def load_memo():
    """저장된 메모를 로드합니다."""
    try:
        with open("memo.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def create_korea_map_data():
    """간단한 한국 지도 데이터를 생성합니다."""
    # 한국의 주요 지역 데이터 (간소화된 버전)
    import numpy as np
    korea_data = {
        'region': [
            '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시', '울산광역시',
            '세종특별자치시', '경기도', '강원도', '충청북도', '충청남도', '전라북도', '전라남도', '경상북도', '경상남도', '제주특별자치도'
        ],
        'lat': [
            37.5665, 35.1796, 35.8714, 37.4563, 35.1595, 36.3504, 35.5384,
            36.4870, 37.4138, 37.8228, 36.8000, 36.5184, 35.7175, 34.8679, 36.4919, 35.4606, 33.4996
        ],
        'lon': [
            126.9780, 129.0756, 128.6014, 126.7052, 126.8526, 127.3845, 129.3114,
            127.2822, 127.5183, 128.1555, 127.7000, 126.8000, 127.1530, 126.9910, 128.8889, 128.2132, 126.5312
        ],
        'value': np.random.randint(10, 1000, size=17).tolist()  # 10~999 사이 랜덤값
    }
    return pd.DataFrame(korea_data)

def create_simple_map_data(selected_region=None):
    """st.map을 위한 간단한 지도 데이터를 생성합니다."""
    # 기본 서울 중심 데이터
    myData = {'lat': [37.56668], 'lon': [126.9784]}
    
    # 선택된 지역이 있으면 해당 지역의 좌표로 변경
    if selected_region and selected_region != "전체":
        korea_map_df = create_korea_map_data()
        region_data = korea_map_df[korea_map_df['region'] == selected_region]
        if not region_data.empty:
            myData['lat'] = [region_data['lat'].values[0]]
            myData['lon'] = [region_data['lon'].values[0]]
    
    # 고정된 포인트 수로 랜덤 포인트 추가
    point_count = 10  # 고정된 포인트 수
    
    # 선택된 지역 주변에 랜덤 포인트 추가
    for _ in range(point_count - 1):
        myData['lat'].append(myData['lat'][0] + np.random.randn() / 50.0)
        myData['lon'].append(myData['lon'][0] + np.random.randn() / 50.0)
    
    return myData

def create_admin_map_data(df_admin_coords, selected_sido=None, selected_sigungu=None):
    """행정구역별 위경도 좌표 데이터를 사용하여 지도 데이터를 생성합니다."""
    if df_admin_coords.empty:
        # 데이터가 없으면 기본 서울 중심 데이터 반환
        return {'lat': [37.56668], 'lon': [126.9784], 'size': [100]}
    
    # 필터링된 데이터
    filtered_data = df_admin_coords.copy()
    
    if selected_sido and selected_sido != "전체":
        filtered_data = filtered_data[filtered_data['시도'] == selected_sido]
    
    if selected_sigungu and selected_sigungu != "전체":
        # 시군구 데이터를 문자열로 변환하여 비교
        filtered_data = filtered_data[filtered_data['시군구'].astype(str) == selected_sigungu]
    
    if filtered_data.empty:
        # 필터링 결과가 없으면 기본 서울 중심 데이터 반환
        return {'lat': [37.56668], 'lon': [126.9784], 'size': [100]}
    
    # 위도, 경도 데이터 추출
    lat_list = filtered_data['위도'].tolist()
    lon_list = filtered_data['경도'].tolist()
    
    # 각 시군구별로 랜덤 데이터 생성 (10~1000 사이)
    size_list = []
    for i in range(len(filtered_data)):
        # 시군구별로 고유한 랜덤값 생성 (시드 고정으로 일관성 유지)
        sigungu_name = str(filtered_data.iloc[i]['시군구'])
        np.random.seed(hash(sigungu_name) % 2**32)  # 시군구명을 시드로 사용
        random_value = np.random.randint(10, 1001)  # 10~1000 사이 랜덤값
        size_list.append(random_value)
    
    # 각 시군구별로 고유한 랜덤 크기 데이터만 사용 (추가 포인트 생성 제거)
    
    return {'lat': lat_list, 'lon': lon_list, 'size': size_list}

def classify_region_type(region_name):
    """지역명을 시도와 시군구로 분류합니다."""
    # 시도 목록 (광역시, 특별시, 도, 특별자치도)
    sido_list = [
        '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시', '대전광역시', '울산광역시',
        '세종특별자치시', '경기도', '강원도', '충청북도', '충청남도', '전라북도', '전라남도', '경상북도', '경상남도', '제주특별자치도'
    ]
    
    # 시도인지 확인
    for sido in sido_list:
        if sido in str(region_name):
            return '시도', sido
    
    # 시군구인 경우
    return '시군구', region_name

def create_ev_map_data(df_ev, selected_region=None):
    """EV 데이터를 사용하여 지도 데이터를 생성합니다."""
    if df_ev.empty:
        return {'lat': [37.56668], 'lon': [126.9784], 'size': [100]}
    
    # 필터링된 데이터
    filtered_data = df_ev.copy()
    
    if selected_region and selected_region != "전체":
        filtered_data = filtered_data[filtered_data['지역구분'] == selected_region]
    
    if filtered_data.empty:
        return {'lat': [37.56668], 'lon': [126.9784], 'size': [100]}
    
    # 위도, 경도 컬럼이 있는지 확인하고 없으면 기본값 사용
    lat_col = None
    lon_col = None
    
    # 가능한 위도 컬럼명들
    lat_candidates = ['위도', 'latitude', 'lat', 'LAT', 'Latitude']
    lon_candidates = ['경도', 'longitude', 'lon', 'LON', 'Longitude']
    
    for col in lat_candidates:
        if col in filtered_data.columns:
            lat_col = col
            break
    
    for col in lon_candidates:
        if col in filtered_data.columns:
            lon_col = col
            break
    
    # 위도, 경도 컬럼이 없으면 지역구분별로 대표 좌표 생성
    if lat_col is None or lon_col is None:
        # 한국 주요 지역별 대표 좌표
        region_coords = {
            '서울': (37.5665, 126.9780),
            '부산': (35.1796, 129.0756),
            '대구': (35.8714, 128.6014),
            '인천': (37.4563, 126.7052),
            '광주': (35.1595, 126.8526),
            '대전': (36.3504, 127.3845),
            '울산': (35.5384, 129.3114),
            '세종': (36.4870, 127.2822),
            '경기': (37.4138, 127.5183),
            '강원': (37.8228, 128.1555),
            '충북': (36.8000, 127.7000),
            '충남': (36.5184, 126.8000),
            '전북': (35.7175, 127.1530),
            '전남': (34.8679, 126.9910),
            '경북': (36.4919, 128.8889),
            '경남': (35.4606, 128.2132),
            '제주': (33.4996, 126.5312)
        }
        
        # 지역구분별로 대표 좌표와 count 데이터 생성
        region_data = []
        for region in filtered_data['지역구분'].unique():
            region_count = filtered_data[filtered_data['지역구분'] == region]['count'].iloc[0]
            
            # 지역명에서 키워드 찾기
            coord_key = None
            for key in region_coords.keys():
                if key in str(region):
                    coord_key = key
                    break
            
            if coord_key:
                lat, lon = region_coords[coord_key]
            else:
                # 기본 서울 좌표 사용
                lat, lon = region_coords['서울']
            
            region_data.append({
                'lat': lat,
                'lon': lon,
                'size': region_count,
                'region': region
            })
        
        # 데이터프레임으로 변환
        map_df = pd.DataFrame(region_data)
        return {
            'lat': map_df['lat'].tolist(),
            'lon': map_df['lon'].tolist(),
            'size': map_df['size'].tolist(),
            'region': map_df['region'].tolist()
        }
    else:
        # 위도, 경도 컬럼이 있는 경우
        lat_list = filtered_data[lat_col].tolist()
        lon_list = filtered_data[lon_col].tolist()
        size_list = filtered_data['count'].tolist()
        region_list = filtered_data['지역구분'].tolist()
        
        return {
            'lat': lat_list,
            'lon': lon_list,
            'size': size_list,
            'region': region_list
        }


# --- 데이터 로딩 ---
data = load_data()
df = data["df"]
df_1 = data["df_1"]
df_2 = data["df_2"]
df_3 = data["df_3"]
df_4 = data["df_4"]
df_5 = data["df_5"]
df_sales = data["df_sales"]
df_admin_coords = data.get("df_admin_coords", pd.DataFrame())  # 행정구역별 위경도 좌표 데이터
df_fail_q3 = data["df_fail_q3"]
df_2_fail_q3 = data["df_2_fail_q3"]
update_time_str = data["update_time_str"]

df_ev = pd.read_excel('C:/Users/HP/Desktop/그리트_공유/08_05_1658_EV_merged.xlsx')

# --- 시간대 설정 ---
KST = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(KST).date()

# --- EV 데이터 분석 및 시각화 ---
st.markdown("---")
st.header("🔋 EV 지역별 신청 분포")


if 'count' not in df_ev.columns:
    region_counts = df_ev['지역구분'].value_counts()
    df_ev['count'] = df_ev['지역구분'].map(region_counts)

# EV 데이터 지도 시각화
try:
    # 상위 10개 지역 추출
    top_10_regions = df_ev.groupby('지역구분')['count'].sum().sort_values(ascending=False).head(10)
    
    # 상위 10개 지역의 데이터만 필터링
    top_10_data = df_ev[df_ev['지역구분'].isin(top_10_regions.index)]
    
    # 한국 주요 지역별 대표 좌표 (더 많은 지역 추가)
    region_coords = {
        '서울특별시': (37.5665, 126.9780),
        '부산광역시': (35.1796, 129.0756),
        '대구광역시': (35.8714, 128.6014),
        '인천광역시': (37.4563, 126.7052),
        '광주광역시': (35.1595, 126.8526),
        '대전광역시': (36.3504, 127.3845),
        '울산광역시': (35.5384, 129.3114),
        '세종특별자치시': (36.4870, 127.2822),
        '경기도': (37.4138, 127.5183),
        '강원도': (37.8228, 128.1555),
        '충청북도': (36.8000, 127.7000),
        '충청남도': (36.5184, 126.8000),
        '전라북도': (35.7175, 127.1530),
        '전라남도': (34.8679, 126.9910),
        '경상북도': (36.4919, 128.8889),
        '경상남도': (35.4606, 128.2132),
        '제주특별자치도': (33.4996, 126.5312),
        # 시군구 추가
        '수원시': (37.2636, 127.0286),
        '고양시': (37.6584, 126.8320),
        '용인시': (37.2411, 127.1776),
        '성남시': (37.4449, 127.1389),
        '부천시': (37.5035, 126.7660),
        '안산시': (37.3219, 126.8309),
        '안양시': (37.3943, 126.9568),
        '남양주시': (37.6364, 127.2165),
        '화성시': (37.1995, 126.8319),
        '평택시': (36.9920, 127.1128),
        '의정부시': (37.7381, 127.0337),
        '시흥시': (37.3799, 126.8031),
        '파주시': (37.8154, 126.7929),
        '김포시': (37.6154, 126.7158),
        '광주시': (37.4294, 127.2551),
        '광명시': (37.4794, 126.8646),
        '군포시': (37.3616, 126.9352),
        '하남시': (37.5392, 127.2148),
        '오산시': (37.1498, 127.0772),
        '이천시': (37.2720, 127.4350),
        '안성시': (37.0080, 127.2797),
        '의왕시': (37.3446, 126.9683),
        '양평군': (37.4912, 127.4875),
        '여주시': (37.2984, 127.6370),
        '과천시': (37.4291, 126.9879),
        '연천군': (38.0966, 127.0747),
        '가평군': (37.8315, 127.5105),
        '포천시': (37.8949, 127.2002),
        '동두천시': (37.9036, 127.0606),
        '청주시': (36.6424, 127.4890),
        '천안시': (36.8151, 127.1139),
        '전주시': (35.8242, 127.1480),
        '창원시': (35.2278, 128.6817),
        '포항시': (36.0320, 129.3650),
        '구미시': (36.1195, 128.3446),
        '진주시': (35.1806, 128.1087),
        '동탄시': (37.1995, 127.1128),
        '양산시': (35.3386, 129.0346),
        '김해시': (35.2284, 128.8894),
        '원주시': (37.3422, 127.9202),
        '춘천시': (37.8813, 127.7300),
        '강릉시': (37.7519, 128.8761),
        '태백시': (37.1641, 128.9856),
        '속초시': (38.1040, 128.5970),
        '삼척시': (37.4499, 129.1652),
        '홍천군': (37.6970, 127.8885),
        '횡성군': (37.4911, 127.9852),
        '영월군': (37.1837, 128.4617),
        '평창군': (37.3705, 128.3905),
        '정선군': (37.3807, 128.6609),
        '철원군': (38.1466, 127.3132),
        '화천군': (38.1064, 127.7082),
        '양구군': (38.1074, 127.9897),
        '인제군': (38.0695, 128.1707),
        '고성군': (38.3785, 128.4675),
        '양양군': (38.0754, 128.6191),
        '동해시': (37.5236, 129.1143),
        '제천시': (37.1326, 128.1910),
        '보은군': (36.4894, 127.7290),
        '옥천군': (36.3064, 127.5714),
        '영동군': (36.1750, 127.7764),
        '증평군': (36.7850, 127.5810),
        '진천군': (36.8550, 127.4350),
        '괴산군': (36.8157, 127.7867),
        '음성군': (36.9404, 127.6907),
        '단양군': (36.9845, 128.3655),
        '충주시': (36.9910, 127.9260),
        '계룡시': (36.2747, 127.2489),
        '공주시': (36.4464, 127.1190),
        '논산시': (36.1871, 127.0987),
        '당진시': (36.8933, 126.6280),
        '금산군': (36.1084, 127.4880),
        '부여군': (36.2754, 126.9090),
        '서천군': (36.0803, 126.6919),
        '청양군': (36.4594, 126.8020),
        '홍성군': (36.6009, 126.6650),
        '예산군': (36.6814, 126.8450),
        '태안군': (36.7459, 126.2980),
        '서산시': (36.7849, 126.4500),
        '아산시': (36.7897, 127.0015),
        '천안시': (36.8151, 127.1139),
        '익산시': (35.9483, 126.9579),
        '군산시': (35.9674, 126.7369),
        '정읍시': (35.5699, 126.8560),
        '남원시': (35.4164, 127.3904),
        '김제시': (35.8034, 126.8808),
        '완주군': (35.9048, 127.1627),
        '진안군': (35.7915, 127.4252),
        '무주군': (36.0070, 127.6608),
        '장수군': (35.6474, 127.5205),
        '임실군': (35.6174, 127.2890),
        '순창군': (35.3744, 127.1376),
        '고창군': (35.4358, 126.7020),
        '부안군': (35.7316, 126.7330),
        '목포시': (34.8118, 126.3928),
        '여수시': (34.7604, 127.6622),
        '순천시': (34.9506, 127.4872),
        '나주시': (35.0156, 126.7108),
        '광양시': (34.9404, 127.6959),
        '담양군': (35.3214, 126.9880),
        '곡성군': (35.2820, 127.2920),
        '구례군': (35.2024, 127.4629),
        '고흥군': (34.6124, 127.2850),
        '보성군': (34.7324, 127.0810),
        '화순군': (35.0644, 126.9860),
        '장흥군': (34.6814, 126.9070),
        '강진군': (34.6424, 126.7670),
        '해남군': (34.5734, 126.5980),
        '영암군': (34.8004, 126.6960),
        '무안군': (34.9904, 126.4810),
        '함평군': (35.0664, 126.5190),
        '영광군': (35.2774, 126.5120),
        '장성군': (35.3014, 126.7870),
        '완도군': (34.3114, 126.7550),
        '진도군': (34.4864, 126.2630),
        '신안군': (34.7904, 126.3780),
        '경주시': (35.8562, 129.2247),
        '김천시': (36.1398, 128.1136),
        '안동시': (36.5684, 128.7294),
        '구미시': (36.1195, 128.3446),
        '영주시': (36.8059, 128.6240),
        '영천시': (35.9733, 128.9384),
        '상주시': (36.4109, 128.1590),
        '문경시': (36.5864, 128.1860),
        '경산시': (35.8254, 128.7410),
        '군위군': (36.2424, 128.5720),
        '의성군': (36.3524, 128.6970),
        '청송군': (36.4354, 129.0570),
        '영양군': (36.6654, 129.1120),
        '영덕군': (36.4154, 129.3650),
        '청도군': (35.6474, 128.7430),
        '고령군': (35.7264, 128.2620),
        '성주군': (35.9184, 128.2880),
        '칠곡군': (35.9954, 128.4010),
        '예천군': (36.6574, 128.4560),
        '봉화군': (36.8934, 128.7320),
        '울진군': (36.9934, 129.4000),
        '울릉군': (37.4844, 130.9020),
        '통영시': (34.8544, 128.4330),
        '사천시': (35.0034, 128.0640),
        '김해시': (35.2284, 128.8894),
        '밀양시': (35.5034, 128.7480),
        '거제시': (34.8804, 128.6210),
        '양산시': (35.3386, 129.0346),
        '의령군': (35.3224, 128.2610),
        '함안군': (35.2724, 128.4060),
        '창녕군': (35.5444, 128.5010),
        '고성군': (34.9734, 128.3230),
        '남해군': (34.8374, 127.8920),
        '하동군': (35.0674, 127.7510),
        '산청군': (35.4154, 127.8730),
        '함양군': (35.5204, 127.7270),
        '거창군': (35.6864, 127.9090),
        '합천군': (35.5664, 128.1650),
        '제주시': (33.4996, 126.5312),
        '서귀포시': (33.2546, 126.5600)
    }
    
    # 상위 10개 지역의 지도 데이터 생성
    map_data = []
    for region in top_10_regions.index:
        count_value = top_10_regions[region]
        
        # 지역명에서 좌표 찾기
        coord_key = None
        for key in region_coords.keys():
            if key in str(region):
                coord_key = key
                break
        
        if coord_key:
            lat, lon = region_coords[coord_key]
        else:
            # 기본 서울 좌표 사용
            lat, lon = region_coords['서울특별시']
        
        map_data.append({
            'lat': lat,
            'lon': lon,
            'size': count_value,
            'region': region
        })
    
    # 지도 데이터프레임 생성
    map_df = pd.DataFrame(map_data)
    
    # count 값에 따라 원 크기 조정 (최소 100, 최대 1000으로 확대)
    min_count = map_df['size'].min()
    max_count = map_df['size'].max()
    
    # 원 크기 정규화 (100~1000 범위로 확대)
    normalized_sizes = []
    for size in map_df['size']:
        if max_count == min_count:
            normalized_size = 500
        else:
            normalized_size = 100 + (size - min_count) / (max_count - min_count) * 900
        normalized_sizes.append(normalized_size)
    
    map_df['size'] = normalized_sizes
    
    # Folium 지도 생성
    st.subheader("🔋 EV 신청 상위 10개 지역 분포")
    
    # 한국 중심 좌표
    center_lat, center_lon = 36.5, 127.5
    
    # Folium 지도 생성 (간단한 스타일)
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles='CartoDB positron'  # 더 깔끔한 지도 스타일
    )
    
    # 각 지역에 원 추가
    for idx, row in map_df.iterrows():
        # 원 크기 계산 (최소 10, 최대 100으로 대폭 확대)
        radius = 10 + (row['size'] - min_count) / (max_count - min_count) * 90
        
        # 색상 계산 (count 값에 따라 색상 변화)
        color_intensity = int(255 * (row['size'] - min_count) / (max_count - min_count))
        color = f'#{255-color_intensity:02x}0000'  # 빨간색 계열
        
        # 원 추가
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=radius,
            popup=f"<b>{row['region']}</b><br>Count: {row['size']:,}",
            color='darkred',
            fill=True,
            fillColor=color,
            fillOpacity=0.8,
            weight=3
        ).add_to(m)
    
    # 지도 표시
    folium_static(m, width=800, height=600)
    
    # 상위 10개 지역 정보 표시
    st.subheader("🏆 상위 10개 지역 현황")
    display_data = map_df.copy()
    display_data['원본_count'] = top_10_regions.values
    display_data['원_반지름'] = [10 + (size - min_count) / (max_count - min_count) * 90 for size in map_df['size']]
    display_data = display_data[['region', '원본_count', '원_반지름']]
    display_data.columns = ['지역명', 'Count 값', '원 반지름']
    st.dataframe(display_data, use_container_width=True)
    
    # 통계 정보
    st.info(f"**총 표시 지역:** {len(map_data)}개")
    st.info(f"**Count 범위:** 최소 {min_count:,}, 최대 {max_count:,}")
    st.info(f"**원 반지름 범위:** 최소 10px, 최대 {10 + 90:.0f}px")
    
    # 범례 추가
    st.subheader("📊 범례")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**원 크기:** Count 값이 클수록 원이 큼")
    with col2:
        st.markdown("**색상:** Count 값이 클수록 진한 빨간색")
    with col3:
        st.markdown("**팝업:** 원을 클릭하면 상세 정보 표시")

except Exception as e:
    st.error(f"EV 지도 데이터 처리 중 오류가 발생했습니다: {e}")

    # 기존 간단한 지도 데이터로 대체
    st.subheader("📍 기본 지도 (임시)")
    korea_map_df = create_korea_map_data()
    
    if not korea_map_df.empty:
        try:
            # 지역 선택 UI
            col1, col2 = st.columns([2, 1])
            with col1:
                selected_region = st.selectbox("지역 선택", ["전체"] + korea_map_df['region'].tolist())
            
            # st.map을 위한 간단한 데이터 생성 (sample_value 제거)
            map_data = create_simple_map_data(selected_region)
            
            # 지도 표시
            st.map(data=map_data, zoom=6)
            
            # 선택된 지역 정보 표시
            if selected_region != "전체":
                selected_data = korea_map_df[korea_map_df['region'] == selected_region]
                st.info(f"**선택된 지역:** {selected_region}")
                st.info(f"**위도:** {selected_data['lat'].values[0]:.4f}")
                st.info(f"**경도:** {selected_data['lon'].values[0]:.4f}")
                st.info(f"**생성된 포인트 수:** {len(map_data['lat'])}")

        except Exception as e:
            st.error(f"지도 데이터 처리 중 오류가 발생했습니다: {e}")
            st.write("**전체 지도 데이터:**")
            st.dataframe(korea_map_df)
    else:
        st.warning("지도 데이터를 표시할 수 없습니다. 데이터가 비어있습니다.")




