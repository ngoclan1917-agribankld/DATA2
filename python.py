# python_project_evaluation_app.py - Đã chỉnh sửa lỗi ZeroDivisionError

# ... (Giữ nguyên các đoạn code trên)

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

    # **BƯỚC KHẮC PHỤC LỖI ZERO DIVISION ERROR**
    if N <= 0:
        st.error(f"Lỗi: Dòng đời dự án (N) phải là số dương. Giá trị hiện tại là {N} năm. Vui lòng kiểm tra file Word hoặc dữ liệu đã trích xuất.")
        return None, None, None
    # **KẾT THÚC KHẮC PHỤC**
    
    # Khởi tạo bảng dòng tiền
    years = np.arange(0, N + 1)
    df_cashflow = pd.DataFrame(index=years)
    df_cashflow.index.name = 'Năm'
    
    # 2. Xây dựng Dòng tiền
    
    # Khấu hao (Giả định tuyến tính)
    Depreciation = I0 / N # Lỗi ZeroDivisionError đã được khắc phục tại đây
    
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

# ... (Giữ nguyên các đoạn code dưới)
