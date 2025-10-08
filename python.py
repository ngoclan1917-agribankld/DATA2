# python_project_evaluation_app.py - ĐÃ CHỈNH SỬA ĐỂ CẬP NHẬT DỮ LIỆU THIẾU

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

# --- Khởi tạo state chat và data ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "project_data" not in st.session_state:
    st.session_state.project_data = None


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
# Giữ lại cache_data nhưng không cache kết quả lỗi
def extract_project_data(docx_content, api_key):
    """Sử dụng Gemini AI để lọc thông tin tài chính từ nội dung văn bản."""
    # Logic AI Extraction được giữ nguyên, chỉ thay đổi cách gọi hàm
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash'
        
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
# Hàm này giờ nhận các giá trị đã được xác nhận (confirmed data)
def calculate_project_metrics(I0, N, R, C, WACC, Tax):
    """Xây dựng bảng dòng tiền và tính NPV, IRR, PP, DPP từ dữ liệu đã được xác nhận."""
    
    # 1. Kiểm tra LỖI ZERO DIVISION (Đã được khắc phục)
    if N <= 0:
        st.error(f"Lỗi logic: Dòng đời dự án (N) phải là số dương. Giá trị hiện tại là {N} năm.")
        return None, None
    
    # Khởi tạo bảng dòng tiền
    years = np.arange(0, N + 1)
    df_cashflow = pd.DataFrame(index=years)
    df_cashflow.index.name = 'Năm'
    
    # 2. Xây dựng Dòng tiền
    Depreciation = I0 / N 
    
    df_cashflow['Doanh thu (R)'] = R
    df_cashflow['Chi phí (C)'] = C
    df_cashflow.loc[0, ['Doanh thu (R)', 'Chi phí (C)']] = 0 
    
    df_cashflow['EBIT = R - C'] = df_cashflow['Doanh thu (R)'] - df_cashflow['Chi phí (C)']
    
    df_cashflow['Khấu hao'] = Depreciation
    df_cashflow.loc[0, 'Khấu hao'] = 0
    
    df_cashflow['EBT'] = df_cashflow['EBIT = R - C'] - df_cashflow['Khấu hao']
    
    df_cashflow['Thuế TNDN'] = df_cashflow['EBT'].apply(lambda x: x * Tax if x > 0 else 0)
    
    df_cashflow['EAT'] = df_cashflow['EBT'] - df_cashflow['Thuế TNDN']
    
    df_cashflow['Dòng tiền Thuần (CF)'] = df_cashflow['EAT'] + df_cashflow['Khấu hao']
    df_cashflow.loc[0, 'Dòng tiền Thuần (CF)'] = -I0 

    # 3. Tính toán các Chỉ số Hiệu quả
    cf_array = df_cashflow['Dòng tiền Thuần (CF)'].values

    npv_value = np.npv(WACC, cf_array)
    
    try:
        irr_value = np.irr(cf_array)
    except Exception:
        irr_value = np.nan
        
    df_cashflow['CF Chiết khấu'] = df_cashflow['Dòng tiền Thuần (CF)'] / ((1 + WACC) ** df_cashflow.index)
    df_cashflow['CF Tích lũy'] = df_cashflow['Dòng tiền Thuần (CF)'].cumsum()
    df_cashflow['CF Chiết khấu Tích lũy'] = df_cashflow['CF Chiết khấu'].cumsum()
    
    def calculate_payback(cf_accumulated):
        last_negative_year = cf_accumulated[cf_accumulated < 0].index.max()
        
        if pd.isna(last_negative_year) or last_negative_year == N:
            return float(N) 
        
        year = last_negative_year
        cf_truoc = cf_accumulated.loc[year]
        cf_nam_sau = df_cashflow.loc[year + 1, 'Dòng tiền Thuần (CF)'] if year + 1 <= N else 0
        
        if cf_nam_sau == 0:
            return float(N)
        
        payback = year + (abs(cf_truoc) / cf_nam_sau)
        return payback
    
    pp_value = calculate_payback(df_cashflow['CF Tích lũy'])
    dpp_value = calculate_payback(df_cashflow['CF Chiết khấu Tích lũy'])
    
    metrics = {
        'NPV': npv_value,
        'IRR': irr_value,
        'PP': pp_value,
        'DPP': dpp_value,
        'WACC': WACC # Đã được xác nhận
    }
    
    return df_cashflow, metrics


# --- Chức năng 4: Yêu cầu AI Phân tích Chỉ số ---

def get_analysis_from_ai(metrics_data, api_key):
    # Logic AI Analysis được giữ nguyên
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
    "Tải file Word Phương án Kinh doanh/Đầu tư",
    type=['docx']
)

# Nút bấm để kích hoạt tác vụ lọc AI
if st.button("LỌC DỮ LIỆU TÀI CHÍNH BẰNG AI 🔎", key="btn_ai_extract"):
    if uploaded_file is None:
        st.warning("Vui lòng tải lên file Word trước khi thực hiện lọc.")
    else:
        api_key = st.secrets.get("GEMINI_API_KEY") 
        if not api_key:
            st.error("Lỗi: Không tìm thấy Khóa API 'GEMINI_API_KEY'. Vui lòng cấu hình trong Streamlit Secrets.")
            st.session_state.project_data = None # Xóa dữ liệu cũ nếu lỗi API
        else:
            docx_content = read_docx_file(uploaded_file)
            st.session_state.project_data = extract_project_data(docx_content, api_key)


# --- KHUNG CẬP NHẬT DỮ LIỆU THIẾU/CHỈNH SỬA ---
if st.session_state.project_data is not None:
    st.success("✅ Dữ liệu đã được trích xuất. Vui lòng kiểm tra và chỉnh sửa nếu cần:")
    data = st.session_state.project_data
    
    with st.form("data_update_form"):
        col1, col2 = st.columns(2)
        
        # Cột 1: Vốn đầu tư, Doanh thu, Chi phí
        with col1:
            st.markdown("**Các giá trị tiền tệ (VNĐ):**")
            I0 = st.number_input("Vốn đầu tư (I0)", value=float(data.get('initial_investment', 0)), min_value=0.0, step=100000000.0, format='%f')
            R = st.number_input("Doanh thu hằng năm (R)", value=float(data.get('annual_revenue', 0)), min_value=0.0, step=100000000.0, format='%f')
            C = st.number_input("Chi phí hằng năm (C)", value=float(data.get('annual_cost', 0)), min_value=0.0, step=100000000.0, format='%f')
            
        # Cột 2: Dòng đời, WACC, Thuế
        with col2:
            st.markdown("**Các giá trị tỷ lệ (%)/Số năm:**")
            N = st.number_input("Dòng đời dự án (N)", value=int(data.get('project_life_years', 0)), min_value=1, step=1)
            WACC_percent = st.number_input("WACC (%)", value=float(data.get('wacc', 0.13)) * 100, min_value=0.0, max_value=100.0, step=0.1, format='%.2f')
            Tax_percent = st.number_input("Thuế suất TNDN (%)", value=float(data.get('tax_rate', 0.20)) * 100, min_value=0.0, max_value=100.0, step=0.1, format='%.2f')

        # Nút xác nhận
        submitted = st.form_submit_button("Xác nhận và Bắt đầu Tính toán")

    # Nếu người dùng xác nhận
    if submitted:
        # Chuyển đổi về đúng định dạng
        I0 = float(I0)
        N = int(N)
        R = float(R)
        C = float(C)
        WACC = WACC_percent / 100
        Tax = Tax_percent / 100

        # Lưu lại dữ liệu đã xác nhận để sử dụng
        st.session_state['confirmed_data'] = {
            'I0': I0, 'N': N, 'R': R, 'C': C, 'WACC': WACC, 'Tax': Tax
        }
        
        # Bắt đầu tính toán
        st.session_state['calculate_triggered'] = True
    else:
        st.session_state['calculate_triggered'] = False


# --- HIỂN THỊ KẾT QUẢ VÀ PHÂN TÍCH (Chức năng 2, 3, 4) ---
if 'calculate_triggered' in st.session_state and st.session_state['calculate_triggered']:
    
    data_conf = st.session_state['confirmed_data']
    
    df_cashflow, metrics = calculate_project_metrics(
        data_conf['I0'], data_conf['N'], data_conf['R'], data_conf['C'], 
        data_conf['WACC'], data_conf['Tax']
    )

    if df_cashflow is not None and metrics is not None:
        
        st.subheader("2. Bảng Dòng tiền Dự án (Cash Flow)")
        cols_to_display = ['Doanh thu (R)', 'Chi phí (C)', 'EAT', 'Khấu hao', 'Dòng tiền Thuần (CF)', 'CF Chiết khấu']
        st.dataframe(df_cashflow[cols_to_display].style.format('{:,.0f}'), use_container_width=True)
        
        # --- Chức năng 3: Tính Chỉ số ---
        st.subheader("3. Các Chỉ số Đánh giá Hiệu quả Dự án")
        
        # Cập nhật WACC cho hiển thị và phân tích
        WACC_val = data_conf['WACC']
        N_val = data_conf['N']
        
        metrics_display = {
            'NPV (Giá trị hiện tại ròng)': f"{metrics['NPV']:,.0f} VNĐ",
            'IRR (Tỷ suất sinh lời nội bộ)': f"{metrics['IRR'] * 100:.2f}%" if not np.isnan(metrics['IRR']) else "Không tính được",
            'PP (Thời gian hoàn vốn)': f"{metrics['PP']:.2f} năm" if metrics['PP'] < N_val else f"{N_val} năm (Không hoàn vốn kịp)",
            'DPP (Thời gian hoàn vốn có chiết khấu)': f"{metrics['DPP']:.2f} năm" if metrics['DPP'] < N_val else f"{N_val} năm (Không hoàn vốn kịp)"
        }
        
        col_met1, col_met2, col_met3, col_met4 = st.columns(4)
        with col_met1: st.metric(list(metrics_display.keys())[0], list(metrics_display.values())[0], delta="> 0 (Khả thi)" if metrics['NPV'] > 0 else "< 0 (Không khả thi)")
        with col_met2: st.metric(list(metrics_display.keys())[1], list(metrics_display.values())[1], delta=f"Lớn hơn WACC ({WACC_val * 100:.2f}%)" if metrics['IRR'] > WACC_val else f"Nhỏ hơn WACC ({WACC_val * 100:.2f}%)")
        with col_met3: st.metric(list(metrics_display.keys())[2], list(metrics_display.values())[2])
        with col_met4: st.metric(list(metrics_display.keys())[3], list(metrics_display.values())[3])

        
        # --- Chức năng 4: Yêu cầu AI Phân tích ---
        st.subheader("4. Yêu cầu AI Phân tích Chỉ số Hiệu quả")
        
        if st.button("PHÂN TÍCH CHUYÊN SÂU BẰNG GEMINI AI 🤖", key="btn_ai_analyze"):
            api_key = st.secrets.get("GEMINI_API_KEY") 
            if api_key:
                with st.spinner('Đang gửi dữ liệu và chờ Gemini thẩm định...'):
                    ai_result = get_analysis_from_ai(metrics, api_key)
                    st.markdown("**Kết quả Phân tích của Chuyên gia AI:**")
                    st.info(ai_result)
            else:
                 st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")

elif uploaded_file is None:
    st.info("Ứng dụng đang chờ bạn tải file Phương án Kinh doanh (.docx) để bắt đầu quá trình đánh giá.")
