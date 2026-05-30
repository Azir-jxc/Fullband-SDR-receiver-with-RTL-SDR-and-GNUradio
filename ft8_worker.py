# ft8_worker.py
import time
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

# =========================================================
# 离线边缘设备时钟同步魔法 (Monkey Patch)
# 拦截系统的 time.time()，为 FT8 提供补偿后的纯净时间
# =========================================================
_original_time = time.time
_time_offset = 0.0

def patched_time():
    """返回补偿后的时间"""
    return _original_time() + _time_offset

# 强行替换全局的 time.time 函数
time.time = patched_time

def manual_time_sync():
    """
    手动对齐 15 秒周期边界。
    假设用户是在真实时间的 00, 15, 30, 45 秒准时按下此按钮的。
    """
    global _time_offset
    current_raw = _original_time()
    
    # 获取当前系统时间的 15 秒余数 (范围 0 ~ 14.999)
    remainder = current_raw % 15.0
    
    # 寻找最近的 15 秒边界进行对齐
    if remainder > 7.5:
        # 说明系统时间慢了，或者用户按早了
        _time_offset = 15.0 - remainder
    else:
        # 说明系统时间快了，或者用户按晚了
        _time_offset = -remainder
        
    print(f"⏱️ [离线校时] 咔哒！对齐成功！系统余数: {remainder:.3f}s -> 注入补偿: {_time_offset:.3f}s")


# 【注意】必须在完成 time 替换之后，再导入 PyFT8，这样它内部调用的 time.time 全是我们伪造的
from PyFT8.receiver import Receiver

class ZmqAudioIn:
    """纯软件 ZMQ 音频桥接类 (终极伪装版)"""
    def __init__(self, sample_rate=48000):
        self.sample_rate = sample_rate
        self.buffer = np.array([], dtype=np.float32)
        
        self.df = self.sample_rate / 8192.0  
        self.nFreqs = int(3100 / self.df) + 1 
        
        # 伪造内部瀑布图的“假账本”
        self.dBgrid_main = np.zeros((1, self.nFreqs), dtype=np.float32)
        self.dBgrid_main_ptr = 0

    def push_data(self, data):
        self.buffer = np.concatenate((self.buffer, data))
        self.dBgrid_main_ptr += 1 

    def read_audio_chunk(self, chunk_size):
        if len(self.buffer) >= chunk_size:
            chunk = self.buffer[:chunk_size]
            self.buffer = self.buffer[chunk_size:]
            return chunk
        return np.zeros(chunk_size, dtype=np.float32)

    def sync_pointer_to_wall_clock(self):
        """15秒周期灵魂同步"""
        self.buffer = np.array([], dtype=np.float32)
        self.dBgrid_main_ptr = 0

class FT8DecoderThread(QThread):
    sig_message_decoded = pyqtSignal(object)  
    sig_status_update = pyqtSignal(str)       

    def __init__(self, backend, sample_rate=48000):
        super().__init__()
        self.backend = backend
        self.audio_in = ZmqAudioIn(sample_rate=sample_rate)
        self.running = True
        self.rx = None

    def on_decode(self, candidate):
        self.sig_message_decoded.emit(candidate)

    def on_busy_profile(self, busy_profile, cycle):
         pass

    def run(self):
        self.sig_status_update.emit("FT8 解码器已启动，等待音频流...")
        try:
            self.rx = Receiver(self.audio_in, [200, 3100], self.on_decode, self.on_busy_profile)
        except Exception as e:
            self.sig_status_update.emit(f"FT8 接收器初始化失败: {e}")
            return

        while self.running:
            raw_audio = self.backend.get_raw_audio()
            if raw_audio is not None:
                self.audio_in.push_data(raw_audio)
            else:
                self.msleep(10)

    def stop(self):
        self.running = False
        self.wait()