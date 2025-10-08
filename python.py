# python_project_evaluation_app.py

import streamlit as st
import pandas as pd
import numpy as np
import json
from docx import Document
from google import genai
from google.genai.errors import APIError

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Đánh giá Phương án Kinh doanh/Đầu tư",
    layout="wide"
)

# --- Khởi tạo state chat cho Chức năng 4 (Chức năng mới theo yêu cầu cũ) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Styling cho Header ---
st.markdown(
    """
    <div style="text-align: center;">
        <h1 style="color: #0072b1; font-size: 2.2em; text-transform: uppercase; border-bottom: 2px solid #0072b1; padding-bottom: 10px; margin-bottom: 30px;">
            ỨNG DỤNG ĐÁNH GIÁ HIỆU QUẢ DỰ ÁN KINH DOANH 📈
        </h1>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Hàm Hỗ trợ ---

def read_docx_file(uploaded_file):
    """Đọc toàn bộ nội dung văn bản từ file Word (.docx)."""
    document = Document(uploaded_file)
    full_text = []
    for para in document.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

# --- Chức năng 1: Lọc Thông tin Dự án bằng AI ---
@st.cache_data(show_spinner="Đang trích xuất dữ liệu từ file Word...")
def extract_project_data(docx_content, api_key):
    """Sử dụng Gemini AI để lọc thông tin tài chính từ nội dung văn bản."""
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash'
        
        # Yêu cầu AI trích xuất thông tin vào định dạng JSON
        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính. Hãy trích xuất các thông tin sau từ nội dung Phương án Kinh doanh dưới đây và trả về KẾT QUẢ DUY NHẤT dưới dạng đối tượng JSON.

        Nội dung Phương án Kinh doanh:
        ---
        {docx_content}
        ---

        Các trường bắt buộc trong JSON:
        1. Vốn đầu tư (initial_investment): Tổng chi phí ban đầu (Chỉ lấy số, không đơn vị).
        2. Dòng đời dự án (project_life_years): Số năm hoạt động (Chỉ lấy số).
        3. Doanh thu hằng năm (annual_revenue): Doanh thu ổn định hàng năm (Chỉ lấy số, không đơn vị).
        4. Chi phí hằng năm (annual_cost): Chi phí hoạt động hằng năm (Chỉ lấy số, không đơn vị).
        5. WACC (wacc): Chi phí vốn (Chỉ lấy số thập phân, ví dụ: 0.13 cho 13%).
        6. Thuế suất (tax_rate): Thuế suất TNDN (Chỉ lấy số thập phân, ví dụ: 0.20 cho 20%).

        Ví dụ định dạng JSON mong muốn:
        {{
          "initial_investment": 20000000000,
          "project_life_years": 10,
          "annual_revenue": 30000000000,
          "annual_cost": 25000000000,
          "wacc": 0.13,
          "tax_rate": 0.20
        }}
        Nếu không tìm thấy, hãy đặt giá trị là 0.
        """

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        
        # Xử lý để đảm bảo output là JSON hợp lệ
        json_string = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_string)

    except APIError as e:
        st.error(f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}")
        return None
    except json.JSONDecodeError:
        st.error("AI không thể trích xuất dữ liệu thành định dạng JSON hợp lệ. Vui lòng kiểm tra nội dung file Word.")
        return None
    except Exception as e:
        st.error(f"Đã xảy ra lỗi không xác định trong quá trình trích xuất: {e}")
        return None


# --- Chức năng 2 & 3: Xây dựng Dòng tiền và Tính toán Chỉ số ---

def calculate_project_metrics(data):
    """Xây dựng bảng dòng tiền và tính NPV, IRR, PP, DPP."""
    
    # 1. Trích xuất thông số
    try:
        I0 = float(data['initial_investment'])
        N = int(data['project_life_years'])
        R = float(data['annual_revenue'])
        C = float(data['annual_cost'])
        WACC = float(data['wacc'])
        Tax = float(data['tax_rate'])
    except Exception:
        st.error("Dữ liệu trích xuất không hợp lệ. Vui lòng kiểm tra các giá trị.")
        return None, None, None

    # Khởi tạo bảng dòng tiền
    years = np.arange(0, N + 1)
    df_cashflow = pd.DataFrame(index=years)
    df_cashflow.index.name = 'Năm'
    
    # 2. Xây dựng Dòng tiền
    
    # Giả định: Vốn đầu tư (I0) phát sinh ở Năm 0. Dòng tiền dương (R, C) bắt đầu từ Năm 1.
    
    # Khấu hao (Giả định tuyến tính)
    Depreciation = I0 / N
    
    # Tính toán từng năm
    df_cashflow['Doanh thu (R)'] = R
    df_cashflow['Chi phí (C)'] = C
    df_cashflow.loc[0, ['Doanh thu (R)', 'Chi phí (C)']] = 0 # Năm 0 không có hoạt động
    
    # Lãi suất trước thuế (EBIT)
    df_cashflow['EBIT = R - C'] = df_cashflow['Doanh thu (R)'] - df_cashflow['Chi phí (C)']
    
    # Lỗ năm 1 (nếu có) được kết chuyển sang năm 2 để tính thuế (Đơn giản hóa: bỏ qua kết chuyển lỗ)
    df_cashflow['Khấu hao'] = Depreciation
    df_cashflow.loc[0, 'Khấu hao'] = 0
    
    # Lợi nhuận trước thuế (EBT = EBIT - Khấu hao)
    df_cashflow['EBT'] = df_cashflow['EBIT = R - C'] - df_cashflow['Khấu hao']
    
    # Thuế TNDN
    df_cashflow['Thuế TNDN'] = df_cashflow['EBT'].apply(lambda x: x * Tax if x > 0 else 0)
    
    # Lợi nhuận sau thuế (EAT)
    df_cashflow['EAT'] = df_cashflow['EBT'] - df_cashflow['Thuế TNDN']
    
    # Dòng tiền Thuần (CF = EAT + Khấu hao - Đầu tư)
    df_cashflow['Dòng tiền Thuần (CF)'] = df_cashflow['EAT'] + df_cashflow['Khấu hao']
    df_cashflow.loc[0, 'Dòng tiền Thuần (CF)'] = -I0 # Vốn đầu tư ban đầu

    # 3. Tính toán các Chỉ số Hiệu quả

    cf_array = df_cashflow['Dòng tiền Thuần (CF)'].values

    # a. NPV
    npv_value = np.npv(WACC, cf_array)

    # b. IRR (Sử dụng numpy)
    try:
        irr_value = np.irr(cf_array)
    except Exception:
        irr_value = np.nan
        
    # c. PP (Thời gian hoàn vốn) & DPP (Thời gian hoàn vốn có chiết khấu)
    
    # Dòng tiền tích lũy và dòng tiền chiết khấu
    df_cashflow['CF Chiết khấu'] = df_cashflow['Dòng tiền Thuần (CF)'] / ((1 + WACC) ** df_cashflow.index)
    df_cashflow['CF Tích lũy'] = df_cashflow['Dòng tiền Thuần (CF)'].cumsum()
    df_cashflow['CF Chiết khấu Tích lũy'] = df_cashflow['CF Chiết khấu'].cumsum()
    
    # Tính PP và DPP
    def calculate_payback(cf_accumulated):
        # Tìm năm cuối cùng mà CF tích lũy là âm
        last_negative_year = cf_accumulated[cf_accumulated < 0].index.max()
        if pd.isna(last_negative_year) or last_negative_year == N:
            return N # Không hoàn vốn trong thời gian dự án
        
        year = last_negative_year
        # CF_trước = Giá trị âm cuối cùng
        cf_truoc = cf_accumulated.loc[year]
        # CF_năm_sau = Dòng tiền thuần của năm ngay sau đó
        cf_nam_sau = df_cashflow.loc[year + 1, 'Dòng tiền Thuần (CF)'] if year + 1 <= N else 0
        
        # Công thức: PP = Năm_trước + |CF_tích_lũy_âm_trước| / CF_năm_sau
        payback = year + (abs(cf_truoc) / cf_nam_sau)
        return payback
    
    pp_value = calculate_payback(df_cashflow['CF Tích lũy'])
    dpp_value = calculate_payback(df_cashflow['CF Chiết khấu Tích lũy'])
    
    metrics = {
        'NPV': npv_value,
        'IRR': irr_value,
        'PP': pp_value,
        'DPP': dpp_value
    }
    
    return df_cashflow, metrics


# --- Chức năng 4: Yêu cầu AI Phân tích Chỉ số ---

def get_analysis_from_ai(metrics_data, api_key):
    """Gửi các chỉ số hiệu quả dự án cho Gemini AI để phân tích."""
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash'
        
        data_markdown = pd.DataFrame(metrics_data.items(), columns=['Chỉ số', 'Giá trị']).to_markdown(index=False)
        
        prompt = f"""
        Bạn là một chuyên gia thẩm định dự án kinh doanh. Dựa trên các chỉ số hiệu quả đầu tư sau, hãy đưa ra một nhận xét chuyên sâu, khách quan (khoảng 3-4 đoạn) về tính khả thi của dự án.
        
        Dữ liệu Chỉ số Hiệu quả Đầu tư:
        {data_markdown}
        WACC (Chi phí vốn) của doanh nghiệp là: {metrics_data['WACC'] * 100:.2f}%.

        Yêu cầu phân tích:
        1. Đánh giá tính khả thi tổng thể (dựa trên NPV và IRR so với WACC).
        2. Phân tích IRR và NPV.
        3. Nhận xét về rủi ro dựa trên Thời gian hoàn vốn (PP) và Thời gian hoàn vốn có chiết khấu (DPP).
        """

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return response.text

    except APIError as e:
        return f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}"
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"


# =========================================================================
# --- LUỒNG CHÍNH CỦA ỨNG DỤNG ---
# =========================================================================

# --- Tải File và Lọc Dữ liệu (Chức năng 1) ---
st.subheader("1. Tải File Word (.docx) và Lọc Thông tin Dự án")
uploaded_file = st.file_uploader(
    "Tải file Word Phương án Kinh doanh/Đầu tư (chứa Vốn đầu tư, Dòng đời, Doanh thu, Chi phí, WACC, Thuế)",
    type=['docx']
)

if uploaded_file is not None:
    
    # Nút bấm để kích hoạt tác vụ lọc AI
    if st.button("LỌC DỮ LIỆU TÀI CHÍNH BẰNG AI 🔎"):
        api_key = st.secrets.get("GEMINI_API_KEY") 
        if not api_key:
            st.error("Lỗi: Không tìm thấy Khóa API 'GEMINI_API_KEY'. Vui lòng cấu hình trong Streamlit Secrets.")
            st.stop()
            
        docx_content = read_docx_file(uploaded_file)
        
        # Lọc dữ liệu
        st.session_state['project_data'] = extract_project_data(docx_content, api_key)

    # Hiển thị dữ liệu đã lọc nếu có
    if 'project_data' in st.session_state and st.session_state['project_data']:
        data = st.session_state['project_data']
        
        st.success("✅ Dữ liệu đã được trích xuất thành công:")
        col1, col2 = st.columns(2)
        
        # Hiển thị dưới dạng bảng đơn giản
        display_data = {
            "Vốn đầu tư (I0)": f"{data['initial_investment']:,.0f} VNĐ",
            "Dòng đời dự án (N)": f"{data['project_life_years']} năm",
            "Doanh thu/năm (R)": f"{data['annual_revenue']:,.0f} VNĐ",
            "Chi phí/năm (C)": f"{data['annual_cost']:,.0f} VNĐ",
            "WACC (k)": f"{data['wacc'] * 100:.2f}%",
            "Thuế suất (T)": f"{data['tax_rate'] * 100:.2f}%"
        }
        
        with col1:
            st.dataframe(pd.DataFrame(list(display_data.items())[:3], columns=['Chỉ tiêu', 'Giá trị']), hide_index=True)
        with col2:
             st.dataframe(pd.DataFrame(list(display_data.items())[3:], columns=['Chỉ tiêu', 'Giá trị']), hide_index=True)


        # --- Xây dựng Dòng tiền & Tính Chỉ số (Chức năng 2 & 3) ---
        
        df_cashflow, metrics = calculate_project_metrics(data)

        if df_cashflow is not None:
            
            st.subheader("2. Bảng Dòng tiền Dự án (Cash Flow)")
            st.dataframe(df_cashflow.style.format('{:,.0f}'), use_container_width=True)
            
            st.subheader("3. Các Chỉ số Đánh giá Hiệu quả Dự án")
            
            # Chuẩn bị dữ liệu hiển thị cho metrics
            metrics_display = {
                'NPV (Giá trị hiện tại ròng)': f"{metrics['NPV']:,.0f} VNĐ",
                'IRR (Tỷ suất sinh lời nội bộ)': f"{metrics['IRR'] * 100:.2f}%" if metrics['IRR'] not in [np.nan, np.inf, -np.inf] else "Không tính được",
                'PP (Thời gian hoàn vốn)': f"{metrics['PP']:.2f} năm",
                'DPP (Thời gian hoàn vốn có chiết khấu)': f"{metrics['DPP']:.2f} năm"
            }
            
            # Thêm WACC vào metrics để AI phân tích
            metrics['WACC'] = data['wacc']

            col_met1, col_met2, col_met3, col_met4 = st.columns(4)
            with col_met1: st.metric(list(metrics_display.keys())[0], list(metrics_display.values())[0], delta="> 0 (Khả thi)" if metrics['NPV'] > 0 else "< 0 (Không khả thi)")
            with col_met2: st.metric(list(metrics_display.keys())[1], list(metrics_display.values())[1], delta=f"Lớn hơn WACC ({metrics['WACC'] * 100:.2f}%)" if metrics['IRR'] > metrics['WACC'] else f"Nhỏ hơn WACC ({metrics['WACC'] * 100:.2f}%)")
            with col_met3: st.metric(list(metrics_display.keys())[2], list(metrics_display.values())[2])
            with col_met4: st.metric(list(metrics_display.keys())[3], list(metrics_display.values())[3])

            
            # --- Yêu cầu AI Phân tích (Chức năng 4) ---
            st.subheader("4. Yêu cầu AI Phân tích Chỉ số Hiệu quả")
            
            if st.button("PHÂN TÍCH CHUYÊN SÂU BẰNG GEMINI AI 🤖"):
                if api_key:
                    with st.spinner('Đang gửi dữ liệu và chờ Gemini thẩm định...'):
                        ai_result = get_analysis_from_ai(metrics, api_key)
                        st.markdown("**Kết quả Phân tích của Chuyên gia AI:**")
                        st.info(ai_result)
                else:
                     st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")

else:
    st.info("Ứng dụng đang chờ bạn tải file Phương án Kinh doanh (.docx) để bắt đầu quá trình đánh giá.")
