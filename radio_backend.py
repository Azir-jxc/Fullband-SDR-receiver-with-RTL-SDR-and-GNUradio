# radio_backend.py
import zmq
import numpy as np
import xmlrpc.client
from config import *

class RadioBackend:
    def __init__(self):
        # 1. 初始化 ZMQ 数据接收通道
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(ZMQ_ADDRESS)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, '')
        
        # 2. 初始化 XMLRPC 控制通道
        self.gr_rpc = xmlrpc.client.ServerProxy(XMLRPC_ADDRESS)

    def get_latest_fft(self):
        """非阻塞式读取 ZMQ 缓冲区，只返回最新的一帧有效数据"""
        latest_fft = None
        try:
            while True:
                message = self.socket.recv(flags=zmq.NOBLOCK)
                data_complex = np.frombuffer(message, dtype=np.complex64)
                if len(data_complex) >= FFT_SIZE:
                    latest_fft = data_complex[-FFT_SIZE:]
        except zmq.Again:
            pass # 缓冲区读空了，跳出循环
            
        return latest_fft

 # 替换原有的 set/get_center_freq
    def set_sdr_freq(self, freq_hz):
        """设置 SDR 硬件中心频率"""
        try:
            self.gr_rpc.set_sdr_freq(freq_hz)
        except Exception as e:
            pass # 避免拖拽时终端被报错淹没

    def get_sdr_freq(self):
        try: return self.gr_rpc.get_sdr_freq()
        except: return 0.0

    def set_target_freq(self, freq_hz):
        """设置解调目标频率 (软件 VFO)"""
        try:
            self.gr_rpc.set_target_freq(freq_hz)
        except Exception as e:
            pass

    def get_target_freq(self):
        try: return self.gr_rpc.get_target_freq()
        except: return 0.0
        
    def set_demod_mode(self, mode_index):
        """向 GRC 发送改变解调模式指令 (需在 GRC 设变量 demod_mode)"""
        try:
            self.gr_rpc.set_demod_mode(mode_index)
        except Exception as e:
            print(f"模式切换失败: {e}")
    def close(self):
        """安全释放网络资源"""
        self.socket.close()
        self.context.term()
    # ... 在 radio_backend.py 中追加这个方法
    def set_gain_rf(self, gain):
        try:
            self.gr_rpc.set_gain_rf(gain)
        except Exception as e:
            print(f"RF增益设置失败: {e}")

    def set_gain_if(self, gain):
        try:
            self.gr_rpc.set_gain_if(gain)
        except Exception as e:
            print(f"IF增益设置失败: {e}")

    def set_gain_bb(self, gain):
        try:
            self.gr_rpc.set_gain_bb(gain)
        except Exception as e:
            print(f"BB增益设置失败: {e}")
            
    # 获取初始增益值（可选，用于UI初始化）
    def get_gain_rf(self):
        try: return self.gr_rpc.get_gain_rf()
        except: return 20 # 默认值
    def get_gain_if(self):
        try: return self.gr_rpc.get_gain_if()
        except: return 20
    def get_gain_bb(self):
        try: return self.gr_rpc.get_gain_bb()
        except: return 20