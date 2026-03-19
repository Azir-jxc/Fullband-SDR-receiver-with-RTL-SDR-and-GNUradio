# config.py

# --- 通讯参数配置 ---
ZMQ_ADDRESS = "tcp://127.0.0.1:5555"
XMLRPC_ADDRESS = "http://127.0.0.1:8080"
ZMQ_IQ_ADDRESS = "tcp://127.0.0.1:5556"     # 新增：原始 IQ 数据流

# --- 信号参数配置 ---
SAMPLE_RATE = 2.4e6  # 2.4 MHz
FFT_SIZE = 1024
CALIBRATION_OFFSET = 0 

# --- 接收机与 UI 参数 ---
MIN_FREQ_HZ = 22e6    
MAX_FREQ_HZ = 2000e6  
WATERFALL_ROWS = 100  

# --- 新增：解调模式与滤波器带宽配置 (Hz) ---
# 格式: "模式名称": (GRC Selector Index, 滤波器下限, 滤波器上限)
DEMOD_MODES = {
    "AM":  (0, -5000, 5000),     # LPF Cutoff 5k
    "NFM": (1, -7500, 7500),     # LPF Cutoff 7.5k
    "WFM": (2, -75000, 75000),   # 根据流图 LPF 为 15k (常规 FM 广播通常是 +/-75k，可在此自行调整)
    "USB": (3, -200, 2800),      # BPF -200 ~ 2.8k
    "LSB": (4, -2800, 200)       # BPF -2.8k ~ 200
}