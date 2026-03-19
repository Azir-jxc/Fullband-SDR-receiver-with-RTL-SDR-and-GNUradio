# main.py
import sys
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

from config import *
from radio_backend import RadioBackend
from ui_layout import Ui_MainWindow

# 设置 pyqtgraph 全局主题颜色为明亮模式
pg.setConfigOption('background', '#F5F5F5')
pg.setConfigOption('foreground', '#333333')

class SpectrumAnalyzer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 1. 加载并组装 UI 界面
        self.ui = Ui_MainWindow()
        self.ui.setup_ui(self)

        # 2. 初始化核心变量和底层通信
        self.backend = RadioBackend()
        self.current_center_freq_hz = 0.0

        # 平均长度配置
        self.avg_lengths = [1, 5, 10, 25]
        self.avg_index = 1
        self.alpha = 2.0 / (self.avg_lengths[self.avg_index] + 1.0)
        self.averaged_power_db = None
        self.ui.avg_cycle_btn.setText(f"平均长度: {self.avg_lengths[self.avg_index]}")
        
        # 旋钮与拖拽状态
        self.last_dial_value = self.ui.freq_dial.value()
        self.is_dragging = False

        # FFT 频率轴基准
        self.base_freqs = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1/SAMPLE_RATE)) / 1e6
        
        # 初始化瀑布图二维数据矩阵 (行数 x FFT点数)
        self.waterfall_data = np.zeros((WATERFALL_ROWS, FFT_SIZE))

        # 3. 绑定所有事件
        self.bind_events()

        # 4. 启动定时器 (100ms 刷新率，兼顾性能与流畅度)
        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start(100) 

        self.sync_timer = QtCore.QTimer()
        self.sync_timer.timeout.connect(self.sync_status)
        self.sync_timer.start(1000)
        
        # 启动时主动拉取一次状态并初始化阴影
        self.sync_status()
        self.on_mode_changed()

    def bind_events(self):
   
        """将 UI 控件与具体的处理函数连接起来"""
        self.ui.set_freq_btn.clicked.connect(self.on_set_frequency_clicked)
        self.ui.avg_cycle_btn.clicked.connect(self.cycle_averaging)
        self.ui.freq_dial.valueChanged.connect(self.on_dial_rotated)
        self.ui.center_line.sigDragged.connect(self.on_line_dragged)
        self.ui.center_line.sigPositionChangeFinished.connect(self.on_line_dropped)
        
        # 绑定解调模式切换下拉框
        self.ui.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
 # ... (保留原有绑定) ...
        self.ui.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        
        # 绑定增益面板展开/收起
        self.ui.gain_toggle_btn.toggled.connect(self.toggle_gain_panel)
        
        # 绑定滑块数值变化
        self.ui.rf_slider.valueChanged.connect(self.on_rf_changed)
        self.ui.if_slider.valueChanged.connect(self.on_if_changed)
        self.ui.bb_slider.valueChanged.connect(self.on_bb_changed)
    # ================= 业务逻辑与事件处理 =================
    # ================= 增益控制逻辑 =================
    def toggle_gain_panel(self, checked):
        """控制增益面板的显示与隐藏，并更改按钮箭头方向"""
        self.ui.gain_panel.setVisible(checked)
        if checked:
            self.ui.gain_toggle_btn.setText("增益设置 ▲")
        else:
            self.ui.gain_toggle_btn.setText("增益设置 ▼")

    def on_rf_changed(self, value):
        self.ui.rf_label.setText(f"RF: {value} dB")
        self.backend.set_gain_rf(value)

    def on_if_changed(self, value):
        self.ui.if_label.setText(f"IF: {value} dB")
        self.backend.set_gain_if(value)

    def on_bb_changed(self, value):
        self.ui.bb_label.setText(f"BB: {value} dB")
        self.backend.set_gain_bb(value)
        
    def on_mode_changed(self):
        """处理解调模式切换，通知后台并更新 UI 阴影"""
        mode_name = self.ui.mode_combo.currentText()
        mode_index = DEMOD_MODES[mode_name][0]
        
        try:
            self.backend.set_demod_mode(mode_index)
        except AttributeError:
            # 防止 radio_backend 中还没来得及加 set_demod_mode 导致崩溃
            print("提示: 请确保在 radio_backend.py 中实现了 set_demod_mode() 方法")
        except Exception as e:
            print(f"模式切换失败: {e}")
            
        self.update_filter_region()

    def update_filter_region(self, center_freq_mhz=None):
        """根据当前模式和中心频率，重新计算并绘制阴影区域的位置"""
        if center_freq_mhz is None:
            center_freq_mhz = self.ui.center_line.value()
            
        mode_name = self.ui.mode_combo.currentText()
        _, low_hz, high_hz = DEMOD_MODES[mode_name]
        
        # 将 Hz 偏移转换为 MHz 绝对坐标
        region_min = center_freq_mhz + (low_hz / 1e6)
        region_max = center_freq_mhz + (high_hz / 1e6)
        self.ui.filter_region.setRegion([region_min, region_max])

    def safe_set_freq(self, target_hz):
        """统一的频率设置入口，包含边界保护"""
        clamped_hz = max(MIN_FREQ_HZ, min(MAX_FREQ_HZ, target_hz))
        try:
            self.backend.set_center_freq(clamped_hz)
            self.averaged_power_db = None  
            self.sync_status()             
        except Exception as e:
            print(f"调谐失败: {e}")

    def cycle_averaging(self):
        self.avg_index = (self.avg_index + 1) % len(self.avg_lengths)
        length = self.avg_lengths[self.avg_index]
        self.ui.avg_cycle_btn.setText(f"平均长度: {length}")
        self.alpha = 1.0 if length == 1 else 2.0 / (length + 1.0)
        self.averaged_power_db = None 

    def on_dial_rotated(self, value):
        delta = value - self.last_dial_value
        if delta > 180: delta -= 360
        elif delta < -180: delta += 360
            
        self.last_dial_value = value
        if delta == 0: return

        # 每 30 度转动对应 10MHz
        freq_shift_mhz = delta * (10.0 / 30.0)
        target_hz = self.current_center_freq_hz + (freq_shift_mhz * 1e6)
        self.safe_set_freq(target_hz)

    def on_line_dragged(self):
        self.is_dragging = True
        target_freq_mhz = self.ui.center_line.value()
        self.ui.line_label.setFormat(f"调谐至: {target_freq_mhz:.3f} MHz")
        # 拖拽时，让阴影区域跟着红线实时移动
        self.update_filter_region(target_freq_mhz)

    def on_line_dropped(self):
        self.is_dragging = False
        target_hz = self.ui.center_line.value() * 1e6
        
        if abs(target_hz - self.current_center_freq_hz) < 5000: 
            self.ui.center_line.setValue(self.current_center_freq_hz / 1e6)
            self.ui.line_label.setFormat(f"中心: {self.current_center_freq_hz / 1e6:.3f} MHz")
            self.update_filter_region(self.current_center_freq_hz / 1e6)
            return
            
        self.safe_set_freq(target_hz)

    def on_set_frequency_clicked(self):
        try:
            target_freq_hz = float(self.ui.freq_input.text()) * 1e6 
            self.safe_set_freq(target_freq_hz)
            self.ui.freq_input.clear()
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "错误", "请输入有效的数字！")

    def sync_status(self):
        """定期或者在主动调谐后，同步后台实际频率到前端 UI"""
        try:
            self.current_center_freq_hz = self.backend.get_center_freq()
            freq_mhz = self.current_center_freq_hz / 1e6
            self.ui.freq_label.setText(f"当前频率: {freq_mhz:.3f} MHz")
            
            # 保持频谱图和瀑布图的 X 轴范围同步
            min_f = self.base_freqs[0] + freq_mhz
            max_f = self.base_freqs[-1] + freq_mhz
            self.ui.plot_widget.setXRange(min_f, max_f, padding=0)
            self.ui.waterfall_widget.setXRange(min_f, max_f, padding=0)
            
            # 缩放并定位瀑布图的图像区域
            rect = QtCore.QRectF(min_f, 0, (max_f - min_f), WATERFALL_ROWS)
            self.ui.waterfall_image.setRect(rect)
            
            if not self.is_dragging:
                self.ui.center_line.setValue(freq_mhz)
                self.ui.line_label.setFormat(f"中心: {freq_mhz:.3f} MHz")
                self.update_filter_region(freq_mhz)
        except Exception:
            pass 

    def update_plot(self):
        """核心绘图循环：处理 GRC 传来的频域数据"""
        # 数据已经是 GRC 处理好的 FFT 数据
        latest_fft = self.backend.get_latest_fft() 
        
        if latest_fft is not None:
            # 1. 直接计算幅度与功率 dB，无需再次 FFT
            magnitude = np.abs(latest_fft) / FFT_SIZE
            power_db = 20 * np.log10(magnitude + 1e-12) + CALIBRATION_OFFSET
            
            # 2. 指数移动平均平滑处理
            if self.averaged_power_db is None:
                self.averaged_power_db = power_db
            else:
                self.averaged_power_db = (self.alpha * power_db) + ((1.0 - self.alpha) * self.averaged_power_db)
            
            # 3. 刷新上半部频谱线
            current_x = self.base_freqs + (self.current_center_freq_hz / 1e6)
            self.ui.curve.setData(current_x, self.averaged_power_db)
            
            # 4. 刷新下半部瀑布图 (实现自上而下的流动)
            # 将矩阵向上移一行，最新的数据放在最后一行 (屏幕最上方)
            self.waterfall_data = np.roll(self.waterfall_data, -1, axis=0)
            self.waterfall_data[-1, :] = self.averaged_power_db
            
            # 使用 .T 矩阵转置，让 X 轴对应频率，Y 轴对应时间
            self.ui.waterfall_image.setImage(self.waterfall_data.T, autoLevels=False)

    def closeEvent(self, event):
        """窗口关闭时的资源回收"""
        self.plot_timer.stop()
        self.sync_timer.stop()
        self.backend.close()
        event.accept()

if __name__ == '__main__':
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    
    app = QtWidgets.QApplication(sys.argv)
    
    font = app.font()
    font.setPointSize(12)
    app.setFont(font)
    
    main_window = SpectrumAnalyzer()
    main_window.show()
    sys.exit(app.exec_())