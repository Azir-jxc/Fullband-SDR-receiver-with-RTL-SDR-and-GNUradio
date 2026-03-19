# main_ui.py
import sys
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

from config import *
from radio_backend import RadioBackend

pg.setConfigOption('background', '#F5F5F5')
pg.setConfigOption('foreground', '#333333')

class SpectrumAnalyzer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SDR 触摸屏接收机 UI")
        self.resize(800, 480)

        self.backend = RadioBackend()
        self.current_center_freq_hz = 0.0

        # --- 平均长度循环控制变量 ---
        self.avg_lengths = [1, 5, 10, 25]
        self.avg_index = 1 # 默认指向 5
        self.alpha = 2.0 / (self.avg_lengths[self.avg_index] + 1.0)
        self.averaged_power_db = None
        
        self.last_dial_value = 0
        self.is_dragging = False # 拖拽状态锁，防止底层同步打断拖拽

        # 预先计算好相对基带频率 (固定不变)
        self.base_freqs = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1/SAMPLE_RATE)) / 1e6

        self.setup_ui()

        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start(50)

        self.sync_timer = QtCore.QTimer()
        self.sync_timer.timeout.connect(self.sync_status)
        self.sync_timer.start(1000)
        self.sync_status()

    def setup_ui(self):
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        layout = QtWidgets.QVBoxLayout(main_widget)

        # --- 第一行：绝对频率控制 ---
        freq_layout = QtWidgets.QHBoxLayout()
        freq_layout.setSpacing(15)
        self.freq_label = QtWidgets.QLabel("当前频率: 连接中...")
        self.freq_label.setMinimumWidth(200)
        self.freq_input = QtWidgets.QLineEdit()
        self.freq_input.setPlaceholderText("输入频率 (MHz)")
        self.freq_input.setMinimumHeight(40)
        self.set_freq_btn = QtWidgets.QPushButton("设置频率")
        self.set_freq_btn.setMinimumHeight(40)
        self.set_freq_btn.clicked.connect(self.on_set_frequency_clicked)

        freq_layout.addWidget(self.freq_label)
        freq_layout.addWidget(self.freq_input)
        freq_layout.addWidget(self.set_freq_btn)
        freq_layout.addStretch()

        # --- 第二行：循环平均按键 + 调频旋钮 ---
        ctrl_layout = QtWidgets.QHBoxLayout()
        ctrl_layout.setSpacing(15)

        # 1. 循环切换平均长度按键
        self.avg_cycle_btn = QtWidgets.QPushButton(f"平均长度: {self.avg_lengths[self.avg_index]}")
        self.avg_cycle_btn.setMinimumSize(120, 40)
        self.avg_cycle_btn.clicked.connect(self.cycle_averaging)
        ctrl_layout.addWidget(self.avg_cycle_btn)

        ctrl_layout.addStretch() # 把旋钮推到最右侧

        # 2. 频率微调旋钮 (QDial)
        dial_label = QtWidgets.QLabel("Freq")
        dial_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        ctrl_layout.addWidget(dial_label)

        self.freq_dial = QtWidgets.QDial()
        self.freq_dial.setRange(0, 359) 
        self.freq_dial.setWrapping(True) 
        self.freq_dial.setNotchesVisible(True) 
        self.freq_dial.setFixedSize(60, 60) 
        self.freq_dial.valueChanged.connect(self.on_dial_rotated)
        self.last_dial_value = self.freq_dial.value() 
        
        ctrl_layout.addWidget(self.freq_dial)

        layout.addLayout(freq_layout)
        layout.addLayout(ctrl_layout)

        # --- 绘图区 ---
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setTitle("实时 FFT 功率谱", color='#333333', size='14pt')
        self.plot_widget.setLabel('left', 'Power', units='dB')
        # 改名：现在显示的是绝对频率
        self.plot_widget.setLabel('bottom', 'Absolute Frequency', units='MHz')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setYRange(-100, 10)
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.setMenuEnabled(False)

        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='#0078D7', width=2))

        # --- 中心红线交互 ---
        self.center_line = pg.InfiniteLine(pos=0, movable=True, pen=pg.mkPen('#E81123', width=3), hoverPen=pg.mkPen('#F7630C', width=5))
        self.line_label = pg.InfLineLabel(self.center_line, text="Freq", position=0.85, color='#E81123', fill='#F5F5F5')
        self.plot_widget.addItem(self.center_line)
        self.center_line.sigDragged.connect(self.on_line_dragged)
        self.center_line.sigPositionChangeFinished.connect(self.on_line_dropped)

        layout.addWidget(self.plot_widget)

    # --- 交互与逻辑方法 ---
    def cycle_averaging(self):
        """处理循环平均按键点击"""
        self.avg_index = (self.avg_index + 1) % len(self.avg_lengths)
        length = self.avg_lengths[self.avg_index]
        self.avg_cycle_btn.setText(f"平均长度: {length}")
        
        if length == 1:
            self.alpha = 1.0
        else:
            self.alpha = 2.0 / (length + 1.0)
            
        self.averaged_power_db = None # 清空历史缓存，快速响应

    def on_dial_rotated(self, value):
        delta = value - self.last_dial_value
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360
            
        self.last_dial_value = value
        if delta == 0:
            return

        freq_shift_mhz = delta * (10.0 / 30.0)
        target_hz = self.current_center_freq_hz + (freq_shift_mhz * 1e6)

        try:
            self.backend.set_center_freq(target_hz)
            self.averaged_power_db = None 
            self.sync_status()
        except Exception:
            pass 

    def on_line_dragged(self):
        self.is_dragging = True
        # 因为 X 轴已经是绝对频率，线所在的位置就是目标绝对频率
        target_freq_mhz = self.center_line.value()
        self.line_label.setFormat(f"调谐至: {target_freq_mhz:.3f} MHz")

    def on_line_dropped(self):
        self.is_dragging = False
        target_freq_mhz = self.center_line.value()
        target_hz = target_freq_mhz * 1e6
        
        # 防误触：如果拖拽距离太小（比如不到 5kHz），就直接弹回中心不发送指令
        if abs(target_hz - self.current_center_freq_hz) < 5000: 
            self.center_line.setValue(self.current_center_freq_hz / 1e6)
            self.line_label.setFormat(f"中心: {self.current_center_freq_hz / 1e6:.3f} MHz")
            return
            
        try:
            self.backend.set_center_freq(target_hz)
            self.averaged_power_db = None 
            self.sync_status()
        except Exception as e:
            print(f"拖拽调谐失败: {e}")
            self.center_line.setValue(self.current_center_freq_hz / 1e6)

    def on_set_frequency_clicked(self):
        try:
            target_freq_hz = float(self.freq_input.text()) * 1e6 
            self.backend.set_center_freq(target_freq_hz)
            self.sync_status()
            self.freq_input.clear()
            self.averaged_power_db = None 
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "错误", "请输入有效的数字！")
        except Exception as e:
            print(f"调用失败: {e}")

    def sync_status(self):
        try:
            self.current_center_freq_hz = self.backend.get_center_freq()
            freq_mhz = self.current_center_freq_hz / 1e6
            self.freq_label.setText(f"当前频率: {freq_mhz:.3f} MHz")
            
            # 动态更新 X 轴的显示范围，使其紧随中心频率
            self.plot_widget.setXRange(self.base_freqs[0] + freq_mhz, self.base_freqs[-1] + freq_mhz, padding=0)
            
            # 只有在没有手动拖拽线的时候，才让线回到中心
            if not self.is_dragging:
                self.center_line.setValue(freq_mhz)
                self.line_label.setFormat(f"中心: {freq_mhz:.3f} MHz")
        except Exception:
            pass 

    def update_plot(self):
        latest_fft = self.backend.get_latest_fft()
        
        if latest_fft is not None:
            magnitude = np.abs(latest_fft) / FFT_SIZE
            power_db = 20 * np.log10(magnitude + 1e-12) + CALIBRATION_OFFSET
            
            if self.averaged_power_db is None:
                self.averaged_power_db = power_db
            else:
                self.averaged_power_db = (self.alpha * power_db) + ((1.0 - self.alpha) * self.averaged_power_db)
            
            # 将相对频率加上中心频率，算出当前画面帧真实的绝对 X 轴数组
            current_x = self.base_freqs + (self.current_center_freq_hz / 1e6)
            self.curve.setData(current_x, self.averaged_power_db)

    def closeEvent(self, event):
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