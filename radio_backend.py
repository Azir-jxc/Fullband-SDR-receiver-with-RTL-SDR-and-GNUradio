# radio_backend.py
import zmq
import numpy as np
import xmlrpc.client
from config import *

class RadioBackend:
    def __init__(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(ZMQ_ADDRESS)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, '')
        
        self.gr_rpc = xmlrpc.client.ServerProxy(XMLRPC_ADDRESS)

    def get_latest_fft(self):
        latest_fft = None
        try:
            while True:
                message = self.socket.recv(flags=zmq.NOBLOCK)
                data_complex = np.frombuffer(message, dtype=np.complex64)
                if len(data_complex) >= FFT_SIZE:
                    latest_fft = data_complex[-FFT_SIZE:]
        except zmq.Again:
            pass 
        return latest_fft

    def set_sdr_freq(self, freq_hz):
        try: self.gr_rpc.set_sdr_freq(freq_hz)
        except Exception: pass

    def get_sdr_freq(self):
        try: return self.gr_rpc.get_sdr_freq()
        except: return 0.0

    def set_target_freq(self, freq_hz):
        try: self.gr_rpc.set_target_freq(freq_hz)
        except Exception: pass

    def get_target_freq(self):
        try: return self.gr_rpc.get_target_freq()
        except: return 0.0

    def set_demod_mode(self, mode_index):
        try: self.gr_rpc.set_demod_mode(mode_index)
        except Exception as e: print(f"模式切换失败: {e}")

    def set_gain_rf(self, gain):
        try: self.gr_rpc.set_gain_rf(gain)
        except Exception: pass

    def set_gain_if(self, gain):
        try: self.gr_rpc.set_gain_if(gain)
        except Exception: pass

    def set_gain_bb(self, gain):
        try: self.gr_rpc.set_gain_bb(gain)
        except Exception: pass
            
    def get_gain_rf(self):
        try: return self.gr_rpc.get_gain_rf()
        except: return 20
    def get_gain_if(self):
        try: return self.gr_rpc.get_gain_if()
        except: return 20
    def get_gain_bb(self):
        try: return self.gr_rpc.get_gain_bb()
        except: return 20

    # ================= 新增：采样率与直采模式配置 =================
    def set_sdr_samp_rate(self, sr_hz):
        try:
            self.gr_rpc.set_sdr_samp_rate(sr_hz)
        except Exception as e:
            print(f"采样率设置失败: {e}")

    def set_direct_samp_mode(self, mode_idx):
        """
        根据用户选择的模式，构造设备参数字符串发给 GRC
        """
        try:
            arg_str = f"rtl=0,direct_samp={mode_idx}"
            # 此处的 set_dev_args 对应 GRC 中你新建的 dev_args 变量
            self.gr_rpc.set_dev_args(arg_str) 
        except Exception as e:
            print(f"直采模式设置失败 (请确认 GRC 中是否已建立名为 dev_args 的变量): {e}")

    def close(self):
        self.socket.close()
        self.context.term()