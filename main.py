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
        
        # 双轨频率状态变量 (分离硬件中心与解调目标)
        self.tuning_mode = "CENTRAL" # "CENTRAL" (中央调谐) 或 "FREE" (自由调谐)
        self.sdr_freq_hz = 0.0       # 底层 RTL-SDR 实际中心频率
        self.target_freq_hz = 0.0    # 软件解调的目标频率 (红线位置)
        self.updating_view = False   # 防止视图更新触发死循环
        
        # 频率拖拽防抖定时器 (防止高频拖拽引发 XMLRPC 阻塞卡死 UI)
        self.drag_tune_timer = QtCore.QTimer()
        self.drag_tune_timer.setSingleShot(True)
        self.drag_tune_timer.timeout.connect(self.apply_dragged_freq)
        self.pending_sdr_freq_hz = None

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
        
        # 默认 UI 状态设置：允许拖拽 X 轴，锁定红线
        self.ui.plot_widget.setMouseEnabled(x=True, y=False)
        self.ui.center_line.setMovable(False)

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
        
        # 绑定解调模式与调谐模式切换
        self.ui.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self.ui.tuning_mode_btn.clicked.connect(self.toggle_tuning_mode)
        
        # 绑定增益面板展开/收起与滑块
        self.ui.gain_toggle_btn.toggled.connect(self.toggle_gain_panel)
        self.ui.rf_slider.valueChanged.connect(self.on_rf_changed)
        self.ui.if_slider.valueChanged.connect(self.on_if_changed)
        self.ui.bb_slider.valueChanged.connect(self.on_bb_changed)
        
        # 绑定背景拖拽和平移事件 (用于中央调谐)
        self.ui.plot_widget.getViewBox().sigXRangeChanged.connect(self.on_xrange_changed)
        # 绑定背景点击事件 (用于自由调谐)
        self.ui.plot_widget.scene().sigMouseClicked.connect(self.on_plot_clicked)

    # ================= 增益控制逻辑 =================
    def toggle_gain_panel(self, checked):
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
        
    # ================= 模式与滤波器控制 =================
    def on_mode_changed(self):
        mode_name = self.ui.mode_combo.currentText()
        mode_index = DEMOD_MODES[mode_name][0]
        try:
            self.backend.set_demod_mode(mode_index)
        except Exception as e:
            print(f"模式切换失败: {e}")
        self.update_filter_region()

    def update_filter_region(self, center_freq_mhz=None):
        if center_freq_mhz is None:
            center_freq_mhz = self.ui.center_line.value()
        mode_name = self.ui.mode_combo.currentText()
        _, low_hz, high_hz = DEMOD_MODES[mode_name]
        
        region_min = center_freq_mhz + (low_hz / 1e6)
        region_max = center_freq_mhz + (high_hz / 1e6)
        self.ui.filter_region.setRegion([region_min, region_max])

    def cycle_averaging(self):
        self.avg_index = (self.avg_index + 1) % len(self.avg_lengths)
        length = self.avg_lengths[self.avg_index]
        self.ui.avg_cycle_btn.setText(f"平均长度: {length}")
        self.alpha = 1.0 if length == 1 else 2.0 / (length + 1.0)
        self.averaged_power_db = None 

    # ================= 调谐模式与交互逻辑 =================
    def toggle_tuning_mode(self):
        if self.tuning_mode == "CENTRAL":
            self.tuning_mode = "FREE"
            self.ui.tuning_mode_btn.setText("模式: 自由调谐")
            self.ui.plot_widget.setMouseEnabled(x=False, y=False) # 锁定背景
            self.ui.center_line.setMovable(True)                  # 激活红线拖动
        else:
            self.tuning_mode = "CENTRAL"
            self.ui.tuning_mode_btn.setText("模式: 中央调谐")
            self.ui.plot_widget.setMouseEnabled(x=True, y=False)  # 激活背景拖动
            self.ui.center_line.setMovable(False)                 # 锁定红线
            
            # 切换回中央模式时，立即将硬件频率对齐到当前的解调目标
            self.safe_set_sdr_and_target_freq(self.target_freq_hz)

    def on_plot_clicked(self, event):
        """自由调谐模式下，点击频谱直接跳转解调频率"""
        if self.tuning_mode == "FREE" and event.button() == QtCore.Qt.LeftButton:
            pos = event.scenePos()
            if self.ui.plot_widget.sceneBoundingRect().contains(pos):
                mouse_point = self.ui.plot_widget.plotItem.vb.mapSceneToView(pos)
                clicked_freq_hz = mouse_point.x() * 1e6
                self.safe_set_target_freq(clicked_freq_hz)

    def on_xrange_changed(self, view_box, view_range):
        """中央调谐模式下，拖拽背景时触发"""
        if self.tuning_mode == "CENTRAL" and not self.updating_view:
            new_center_mhz = (view_range[0] + view_range[1]) / 2.0
            target_hz = max(MIN_FREQ_HZ, min(MAX_FREQ_HZ, new_center_mhz * 1e6))
            
            # 1. 立即更新内部变量和 UI，保证视觉无延迟
            self.sdr_freq_hz = target_hz
            self.target_freq_hz = target_hz
            self.ui.center_line.setValue(new_center_mhz)
            self.update_filter_region(new_center_mhz)
            self.ui.freq_label.setText(f"当前频率: {new_center_mhz:.3f} MHz")
            
            # 同步移动瀑布图底层数据映射，防止错位
            self.updating_view = True
            self.ui.waterfall_widget.setXRange(view_range[0], view_range[1], padding=0)
            rect = QtCore.QRectF(view_range[0], 0, (view_range[1] - view_range[0]), WATERFALL_ROWS)
            self.ui.waterfall_image.setRect(rect)
            self.updating_view = False
            
            # 2. 启动/重置 50ms 防抖定时器，推迟网络请求
            self.pending_sdr_freq_hz = target_hz
            self.drag_tune_timer.start(50) 

    def apply_dragged_freq(self):
        """防抖定时器触发，实际发送 XMLRPC 指令"""
        if self.pending_sdr_freq_hz:
            self.backend.set_sdr_freq(self.pending_sdr_freq_hz)
            self.backend.set_target_freq(self.pending_sdr_freq_hz)

    def safe_set_sdr_and_target_freq(self, target_hz):
        """绝对调谐：同时改变硬件和解调中心 (如通过输入框设置)"""
        clamped_hz = max(MIN_FREQ_HZ, min(MAX_FREQ_HZ, target_hz))
        try:
            self.backend.set_sdr_freq(clamped_hz)
            self.backend.set_target_freq(clamped_hz)
            self.sdr_freq_hz = clamped_hz
            self.target_freq_hz = clamped_hz
            self.averaged_power_db = None  
            
            # 强制立即刷新视图
            self.updating_view = True
            mhz = clamped_hz / 1e6
            min_f = self.base_freqs[0] + mhz
            max_f = self.base_freqs[-1] + mhz
            self.ui.plot_widget.setXRange(min_f, max_f, padding=0)
            self.ui.waterfall_widget.setXRange(min_f, max_f, padding=0)
            rect = QtCore.QRectF(min_f, 0, (max_f - min_f), WATERFALL_ROWS)
            self.ui.waterfall_image.setRect(rect)
            self.ui.center_line.setValue(mhz)
            self.update_filter_region(mhz)
            self.updating_view = False
            
            self.ui.freq_label.setText(f"当前频率: {mhz:.3f} MHz")
        except Exception as e:
            print(f"绝对调谐失败: {e}")

    def safe_set_target_freq(self, target_hz):
        """自由调谐：仅在当前带宽内移动解调红线"""
        # 限制红线不能飞出当前 SDR 的采样带宽外
        min_valid = self.sdr_freq_hz - (SAMPLE_RATE / 2.0)
        max_valid = self.sdr_freq_hz + (SAMPLE_RATE / 2.0)
        clamped_hz = max(min_valid, min(max_valid, target_hz))
        
        try:
            self.backend.set_target_freq(clamped_hz)
            self.target_freq_hz = clamped_hz
            self.ui.center_line.setValue(clamped_hz / 1e6)
            self.update_filter_region(clamped_hz / 1e6)
            self.ui.freq_label.setText(f"当前频率: {(clamped_hz / 1e6):.3f} MHz")
        except Exception as e:
            print(f"解调目标调谐失败: {e}")

    # ================= 原有组件事件 =================
    def on_dial_rotated(self, value):
        delta = value - self.last_dial_value
        if delta > 180: delta -= 360
        elif delta < -180: delta += 360
        self.last_dial_value = value
        if delta == 0: return

        freq_shift_mhz = delta * (10.0 / 30.0)
        if self.tuning_mode == "CENTRAL":
            self.safe_set_sdr_and_target_freq(self.sdr_freq_hz + (freq_shift_mhz * 1e6))
        else:
            self.safe_set_target_freq(self.target_freq_hz + (freq_shift_mhz * 1e6))

    def on_line_dragged(self):
        if self.tuning_mode == "FREE":
            self.is_dragging = True
            target_freq_mhz = self.ui.center_line.value()
            self.ui.line_label.setFormat(f"调谐至: {target_freq_mhz:.3f} MHz")
            self.update_filter_region(target_freq_mhz)

    def on_line_dropped(self):
        if self.tuning_mode == "FREE":
            self.is_dragging = False
            target_hz = self.ui.center_line.value() * 1e6
            self.safe_set_target_freq(target_hz)

    def on_set_frequency_clicked(self):
        try:
            target_hz = float(self.ui.freq_input.text()) * 1e6 
            self.safe_set_sdr_and_target_freq(target_hz)
            self.ui.freq_input.clear()
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "错误", "请输入有效的数字！")

    # ================= 状态同步与绘图 =================
    def sync_status(self):
        """定期从后端拉取状态，但不去粗暴打断用户的拖拽动画"""
        try:
            self.sdr_freq_hz = self.backend.get_sdr_freq()
            self.target_freq_hz = self.backend.get_target_freq()
            
            # 只在偏移过大（例如后台被意外修改）时，才强制拉回视图，防止拖动时发生画面抖动
            current_view_center = (self.ui.plot_widget.viewRange()[0][0] + self.ui.plot_widget.viewRange()[0][1]) / 2.0
            if abs(current_view_center - (self.sdr_freq_hz / 1e6)) > 0.005 and not self.updating_view:
                self.safe_set_sdr_and_target_freq(self.sdr_freq_hz)
                
            self.ui.freq_label.setText(f"当前频率: {(self.target_freq_hz / 1e6):.3f} MHz")
        except Exception:
            pass 

    def update_plot(self):
        """核心绘图循环"""
        latest_fft = self.backend.get_latest_fft() 
        
        if latest_fft is not None:
            magnitude = np.abs(latest_fft) / FFT_SIZE
            power_db = 20 * np.log10(magnitude + 1e-12) + CALIBRATION_OFFSET
            
            if self.averaged_power_db is None:
                self.averaged_power_db = power_db
            else:
                self.averaged_power_db = (self.alpha * power_db) + ((1.0 - self.alpha) * self.averaged_power_db)
            
            # 关键：频谱的 X 轴永远绑定 SDR 的底层硬件中心频率
            current_x = self.base_freqs + (self.sdr_freq_hz / 1e6)
            self.ui.curve.setData(current_x, self.averaged_power_db)
            
            self.waterfall_data = np.roll(self.waterfall_data, -1, axis=0)
            self.waterfall_data[-1, :] = self.averaged_power_db
            self.ui.waterfall_image.setImage(self.waterfall_data.T, autoLevels=False)

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