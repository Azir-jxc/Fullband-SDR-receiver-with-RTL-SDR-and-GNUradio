# ft8_worker.py
import time
import numpy as np
import sys
import types
import threading
from PyQt5.QtCore import QThread, pyqtSignal

# =========================================================
# 1. 离线边缘设备时钟同步魔法 (Monkey Patch)
# =========================================================
_original_time = time.time
_time_offset = 0.0

def patched_time():
    return _original_time() + _time_offset

time.time = patched_time

def manual_time_sync():
    global _time_offset
    current_raw = _original_time()
    remainder = current_raw % 15.0
    if remainder > 7.5:
        _time_offset = 15.0 - remainder
    else:
        _time_offset = -remainder
    print(f" [校时] 对齐成功！系统余数: {remainder:.3f}s -> 注入补偿: {_time_offset:.3f}s")

# =========================================================
# 2. 完美的虚拟声卡引擎 (异步泵 + 实时强制排空版)
# =========================================================
_global_backend = None

class MockStream:
    def __init__(self, **kwargs):
        self.buffer = np.array([], dtype=np.float32)
        self.target_rate = kwargs.get('rate', 12000)
        self.format = kwargs.get('format', 8)
        self.frames_per_buffer = kwargs.get('frames_per_buffer', 480) 
        self.stream_callback = kwargs.get('stream_callback', None)    
        
        self._running = False
        self._debug_counter = 0

    def _drain_zmq_backlog(self):
        """【关键魔法】：启动前强制排空 ZMQ 管道里的积压垃圾，确保时间戳绝对对齐！"""
        global _global_backend
        if _global_backend is None: return
        count = 0
        while True:
            try:
                # 疯狂拉取直到拿不到数据为止 (触发 zmq.Again 返回 None)
                if _global_backend.get_raw_audio() is None: break
                count += 1
            except Exception:
                break
        if count > 0:
            print(f"🧹 [虚拟声卡] ：已冲刷掉 {count} 块积压的历史音频")

    def read(self, num_frames, exception_on_overflow=False):
        global _global_backend
        import time as _sys_time
        max_wait = 0.5 
        start_wait = _sys_time.perf_counter()
        
        while len(self.buffer) < num_frames and self._running:
            raw = None
            if _global_backend is not None:
                try: 
                    raw = _global_backend.get_raw_audio()
                except Exception: 
                    pass
            
            if raw is not None and len(raw) > 0:
                self.buffer = np.concatenate((self.buffer, raw))
                
                self._debug_counter += 1
                if self._debug_counter % 50 == 1:
                    peak_amp = np.max(np.abs(self.buffer)) if len(self.buffer) > 0 else 0.0
                    # print(f" [ZMQ 音频泵] 缓冲: {len(self.buffer):04d} | 峰值电平: {peak_amp:.3f} | 指针推进中...")
            else:
                if _sys_time.perf_counter() - start_wait > max_wait: 
                    print("⚠️ [ZMQ 音频泵] 断流警告！尝试填充维持相位...")
                    break
                _sys_time.sleep(0.005)
                
        if len(self.buffer) >= num_frames:
            chunk = self.buffer[:num_frames]
            self.buffer = self.buffer[num_frames:]
        else:
            missing = num_frames - len(self.buffer)
            last_val = self.buffer[-1] if len(self.buffer) > 0 else 0.0
            pad = np.full(missing, last_val, dtype=np.float32)
            chunk = np.concatenate((self.buffer, pad))
            self.buffer = np.array([], dtype=np.float32)
            
        if self.format == 8:
            # 既然有 AGC 护航，直接去掉 tanh，改用纯粹的线性缩放 + 硬截断
            chunk = np.clip(chunk, -1.0, 1.0)
            return np.int16(chunk * 32767.0).tobytes()
        # if self.format == 8:
        #     chunk = np.tanh(chunk)
        #     return np.int16(chunk * 32767.0).tobytes()
        else:
            return np.float32(chunk).tobytes()

    def start_stream(self): 
        # 1. 启动前先排空管道！
        self._drain_zmq_backlog()
        
        self._running = True
        # 2. 启动数据泵
        if self.stream_callback:
            self._pump_thread = threading.Thread(target=self._pump, daemon=True)
            self._pump_thread.start()

    def _pump(self):
        import time
        while self._running:
            chunk_bytes = self.read(self.frames_per_buffer)
            if chunk_bytes and self._running and self.stream_callback:
                try:
                    self.stream_callback(chunk_bytes, self.frames_per_buffer, None, 0)
                except Exception as e:
                    print(f"⚠️ [虚拟声卡] 回调注入失败: {e}")
            else:
                time.sleep(0.01)

    def stop_stream(self): self._running = False
    def close(self): self.stop_stream()
    def is_active(self): return self._running

class MockPyAudio:
    paInt16 = 8
    paFloat32 = 1
    def get_device_count(self): return 1
    def get_device_info_by_index(self, i): 
        return {'name': 'ZMQ 完美虚拟声卡', 'maxInputChannels': 1, 'defaultSampleRate': 12000}
    def get_default_input_device_info(self): return self.get_device_info_by_index(0)
    def open(self, *args, **kwargs): return MockStream(**kwargs)
    def terminate(self): pass

# 欺骗模块系统
fake_pyaudio = types.ModuleType('pyaudio')
fake_pyaudio.PyAudio = MockPyAudio
fake_pyaudio.paInt16 = 8
fake_pyaudio.paFloat32 = 1
fake_pyaudio.paContinue = 0
sys.modules['pyaudio'] = fake_pyaudio

# =========================================================
# 3. 终极防弹衣：拦截 PyFT8 的崩溃报错与状态偷渡
# =========================================================
from PyFT8.receiver import Receiver, AudioIn

_active_ft8_thread = None

orig_search = Receiver.search
def safe_search(self, *args, **kwargs):
    try: 
        cands = orig_search(self, *args, **kwargs)
        if _active_ft8_thread is not None:
            _active_ft8_thread.sig_status_update.emit(f"🔍 周期扫描完成 -> 发现 {len(cands)} 个候选信号")
        return cands
    except ValueError: 
        if _active_ft8_thread is not None:
            _active_ft8_thread.sig_status_update.emit("⚠️ 扫描崩溃 (无有效数据)")
        return [] 
Receiver.search = safe_search

orig_get_busy_profile = Receiver.get_busy_profile
def safe_get_busy_profile(self, *args, **kwargs):
    try: 
        return orig_get_busy_profile(self, *args, **kwargs)
    except ValueError: 
        return (np.array([]), 0) 
Receiver.get_busy_profile = safe_get_busy_profile

# =========================================================
# 4. 守护线程
# =========================================================
class FT8DecoderThread(QThread):
    sig_message_decoded = pyqtSignal(object)  
    sig_status_update = pyqtSignal(str)       

    def __init__(self, backend, sample_rate=12000):
        super().__init__()
        self.backend = backend
        
        global _active_ft8_thread
        _active_ft8_thread = self
        
        global _global_backend
        _global_backend = self.backend
        
        self.running = True
        self.rx = None
        self.audio_in = None

    def on_decode(self, candidate):
        self.sig_message_decoded.emit(candidate)

    def on_busy_profile(self, busy_profile, cycle): pass

    def run(self):
        self.sig_status_update.emit("FT8 解码引擎已就绪 (防崩溃护甲已装备) 🛡️...")
        try:
            self.audio_in = AudioIn(3500) 
            self.audio_in.start_streamed_audio(0)
            self.rx = Receiver(self.audio_in, [200, 3100], self.on_decode, self.on_busy_profile, verbose=True)
        except Exception as e:
            self.sig_status_update.emit(f"FT8 初始化失败: {e}")
            return

        while self.running:
            self.msleep(200)

    def stop(self):
        self.running = False
        if self.audio_in:
            self.audio_in.running = False 
            
        if self.rx:
            self.rx.stop()
            
        global _active_ft8_thread
        _active_ft8_thread = None
        
        self.wait()