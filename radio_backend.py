# radio_backend.py
import zmq
import numpy as np
import xmlrpc.client
from config import *

class RadioBackend:
    def __init__(self):
        self.context = zmq.Context()
        
        # 射频频谱 FFT ZMQ 订阅
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(ZMQ_ADDRESS)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, '')
        
        # 音频频谱 FFT ZMQ 订阅
        self.audio_socket = self.context.socket(zmq.SUB)
        self.audio_socket.connect(ZMQ_IQ_ADDRESS)
        self.audio_socket.setsockopt_string(zmq.SUBSCRIBE, '')
        
        # ====== 新增：原始音频波形 ZMQ 订阅 (FT8 使用) ======
        self.raw_audio_socket = self.context.socket(zmq.SUB)
        self.raw_audio_socket.connect("tcp://127.0.0.1:5557") # 对应 GNU Radio 中的 ZMQ PUB Sink 端口
        self.raw_audio_socket.setsockopt_string(zmq.SUBSCRIBE, '')
        # ====================================================
        
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

    def get_latest_audio_fft(self):
        latest_fft = None
        try:
            while True:
                message = self.audio_socket.recv(flags=zmq.NOBLOCK)
                data_complex = np.frombuffer(message, dtype=np.complex64)
                if len(data_complex) >= FFT_SIZE:
                    latest_fft = data_complex[-FFT_SIZE:]
        except zmq.Again:
            pass 
        return latest_fft

    # ====== 新增：获取解调后的原始音频数据 ======
    def get_raw_audio(self):
        """获取解调后的原始音频 float32 数据（每次 1024 个点）"""
        try:
            # 必须使用非阻塞模式 (NOBLOCK)，否则没收到数据时会卡死整个程序
            message = self.raw_audio_socket.recv(flags=zmq.NOBLOCK)
            return np.frombuffer(message, dtype=np.float32)
        except zmq.Again:
            return None
    # ============================================

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

    def set_sdr_samp_rate(self, sr_hz):
        try: self.gr_rpc.set_sdr_samp_rate(sr_hz)
        except Exception as e: print(f"采样率设置失败: {e}")

    def set_squelch(self, squelch_db):
        try:
            self.gr_rpc.set_squelch(squelch_db)
        except Exception as e: print(f"设置静噪失败: {e}")

    def set_audio_value(self, val):
        try:
            self.gr_rpc.set_audio_value(val)
        except Exception as e: 
            print(f"设置音量(audio_value)失败: {e}")

    def set_filter_bw(self, mode_name, low_hz, high_hz):
        try:
            if mode_name == "AM":
                self.gr_rpc.set_am_co_freq(abs(high_hz))
            elif mode_name == "NFM":
                self.gr_rpc.set_nfm_co_freq(abs(high_hz))
            elif mode_name == "WFM":
                self.gr_rpc.set_wfm_co_freq(abs(high_hz))
            elif mode_name == "USB":
                self.gr_rpc.set_usb_co_freq_low(low_hz)
                self.gr_rpc.set_usb_co_freq_high(high_hz)
            elif mode_name == "LSB":
                self.gr_rpc.set_lsb_co_freq_low(low_hz)
                self.gr_rpc.set_lsb_co_freq_high(high_hz)
        except Exception as e:
            print(f"动态设置滤波器带宽失败 ({mode_name}): {e}")

    def close(self):
        self.socket.close()
        self.audio_socket.close()
        # ====== 新增：退出时清理原始音频 socket ======
        self.raw_audio_socket.close() 
        # ============================================
        self.context.term()