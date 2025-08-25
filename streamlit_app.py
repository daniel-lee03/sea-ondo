import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import io

# 기상청 API 허브에서 제공하는 해양관측 지점 정보
# 실제 API 문서나 사이트에서 전체 목록을 확인하고 필요한 지점을 추가할 수 있습니다.
STATION_INFO = {
    '22101': '덕적도',
    '22102': '칠발도',
    '22103': '거문도',
    '22104': '거제도',
    '22105': '동해',
    '22106': '울릉도',
    '22107': '포항',
    '22108': '마라도',
    '22183': '외연도',
    '22184': '울산',
    '22185': '인천',
    '22186': '신안',
    '22187': '서귀포',
    '22188': '추자도',
    '22189': '통영',
    '22190': '울진',
}

# API로부터 받은 텍스트 데이터를 파싱하여 Pandas DataFrame으로 변환하는 함수
def parse_kma_data(text_data):
    """
    기상청 API 응답 텍스트를 파싱하여 DataFrame으로 변환합니다.
    - 주석(#)으로 시작하는 줄은 건너뜁니다.
    - 데이터는 공백 또는 쉼표로 구분되어 있을 수 있습니다.
    """
    # 주석 부분을 제외하고 데이터 라인만 추출
    lines = [line for line in text_data.splitlines() if not line.strip().startswith('#')]
    
    if not lines:
        return pd.DataFrame()

    # 데이터 부분을 StringIO를 이용해 파일처럼 다루어 pandas로 읽기
    # 구분자가 일정하지 않을 수 있으므로 정규식 '\s*,\s*|\s+'를 사용하여 공백과 쉼표 모두 처리
    data_io = io.StringIO("\n".join(lines))
    
    # API 응답 형식에 따라 컬럼 이름을 직접 지정
    # [TM, STN, WD, WS, GST, PA, PR, PT, TA, TD, HM, PV, RN, R15, RI, R6, R12, R24, WC, WH, WP, WVE, WVL, TW]
    # 순서대로: 시간, 지점, 풍향, 풍속, 돌풍, 기압, 현지기압, 기압변화량, 기온, 이슬점, 습도, 수증기압, 강수량, ..., 파고, 수온
    columns = [
        "TM", "STN", "WD", "WS", "GST_WD", "GST_WS", "PA", "PS", 
        "PT", "TA", "TD", "HM", "PV", "RN", "R15", "R60", 
        "R12", "R24", "WC", "WH", "WP", "WVE", "WVL", "TW"
    ]

    try:
        # read_csv는 강력한 파싱 엔진을 가지고 있어 복잡한 공백/쉼표 조합을 잘 처리합니다.
        df = pd.read_csv(data_io, header=None, delim_whitespace=True, names=columns)
        return df
    except Exception as e:
        st.error(f"데이터를 파싱하는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()


# --- Streamlit UI 구성 ---

st.set_page_config(page_title="해수온 조회 서비스", page_icon="🌊")

# 제목과 설명
st.title("🌊 기상청 API 활용 해수온 조회")
st.markdown("""
이 웹 페이지는 **기상청 API 허브**의 [해양기상부이 관측자료](https://apihub.kma.go.kr/kma-api/openapi/selectApiList.do?pgmNo=21#)를 이용하여<br>
선택한 날짜와 지점의 시간별 **해수면 온도(수온)** 변화를 보여줍니다.
""", unsafe_allow_html=True)
st.markdown("---")


# --- 사이드바: 사용자 입력 ---
st.sidebar.header("조회 조건 설정")

# 1. API 인증키 입력
auth_key = st.sidebar.text_input("기상청 API 인증키를 입력하세요", type="password", help="기상청 API 허브에서 발급받은 인증키를 붙여넣으세요.")

# 2. 관측 지점 선택
station_id = st.sidebar.selectbox(
    '관측 지점을 선택하세요',
    options=list(STATION_INFO.keys()),
    format_func=lambda x: f"{STATION_INFO[x]} ({x})" # 드롭다운에 '덕적도 (22101)' 형식으로 표시
)

# 3. 날짜 선택
selected_date = st.sidebar.date_input(
    "조회할 날짜를 선택하세요",
    datetime.now()
)

# 4. 데이터 조회 버튼
if st.sidebar.button("해수온 데이터 조회하기"):
    if not auth_key:
        st.error("API 인증키를 먼저 입력해주세요.")
    else:
        with st.spinner('데이터를 불러오는 중입니다... 잠시만 기다려주세요.'):
            # API 요청을 위한 URL 구성
            # tm 값은 YYYYMMDD 형식으로 조회할 날짜를 지정
            request_url = (
                "https://apihub.kma.go.kr/api/typ01/url/sea_obs_h.php?"
                f"tm={selected_date.strftime('%Y%m%d')}&"
                f"stn={station_id}&"
                "help=0&" # 도움말 내용은 제외
                f"authKey={auth_key}"
            )
            
            try:
                # API 호출
                response = requests.get(request_url, timeout=10)
                
                # 응답 상태 코드 확인
                if response.status_code == 200:
                    # EUC-KR로 인코딩된 응답을 디코딩
                    response.encoding = 'euc-kr'
                    data_text = response.text
                    
                    # 데이터 파싱
                    df = parse_kma_data(data_text)
                    
                    if not df.empty and 'TW' in df.columns and 'TM' in df.columns:
                        # 필요한 컬럼(시간, 수온)만 선택 및 전처리
                        result_df = df[['TM', 'TW']].copy()
                        
                        # 데이터 타입 변환
                        # errors='coerce'는 변환할 수 없는 값을 NaT/NaN으로 만듦
                        result_df['TM'] = pd.to_datetime(result_df['TM'], format='%Y%m%d%H%M', errors='coerce')
                        result_df['TW'] = pd.to_numeric(result_df['TW'], errors='coerce')
                        
                        # 유효하지 않은 데이터 제거
                        result_df.dropna(inplace=True)
                        
                        if not result_df.empty:
                            st.success(f"**{STATION_INFO[station_id]}** 지점의 **{selected_date.strftime('%Y년 %m월 %d일')}** 해수온 데이터를 성공적으로 조회했습니다.")

                            # 데이터프레임 시각화
                            st.subheader("📊 시간별 해수온 변화 그래프")
                            
                            # Streamlit 차트를 위해 인덱스를 시간으로 설정
                            chart_df = result_df.set_index('TM')
                            st.line_chart(chart_df['TW'])

                            # 데이터 테이블 표시
                            st.subheader("📝 상세 데이터 테이블")
                            st.dataframe(result_df.rename(columns={'TM': '관측 시간', 'TW': '수온 (°C)'}))

                        else:
                            st.warning("해당 날짜에 유효한 수온 데이터가 없습니다.")

                    else:
                        st.error("API 응답에서 수온 데이터를 찾을 수 없거나 데이터가 비어있습니다.")
                        st.code(data_text, language='text')

                else:
                    st.error(f"API 요청에 실패했습니다. (상태 코드: {response.status_code})")
                    st.code(response.text, language='text')

            except requests.exceptions.RequestException as e:
                st.error(f"네트워크 오류가 발생했습니다: {e}")

# 초기 안내 메시지
else:
    st.info("왼쪽 사이드바에서 인증키를 입력하고 조회 조건을 설정한 후 버튼을 클릭하세요.")