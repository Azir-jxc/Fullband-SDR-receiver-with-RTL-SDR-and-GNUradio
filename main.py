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

        # 2. 初始化底层通信
        self.backend = RadioBackend()
        
        # 核心频率状态变量
        self.tuning_mode = "CENTRAL" # "CENTRAL" (中央拖拽) 或 "FREE" (自由点击)
        self.sdr_freq_hz = 0.0       # 底层 RTL-SDR 硬件中心频率
        self.target_freq_hz = 0.0    # 软件解调目标频率 (红线 VFO)
        self.updating_view = False   # 视图更新锁，防止死循环
        
        # FFT 频率轴基准
        self.base_freqs = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1/SAMPLE_RATE)) / 1e6
        # 初始化瀑布图数据
        self.waterfall_data = np.zeros((WATERFALL_ROWS, FFT_SIZE))

        # 3. ++ 关键修复：同步硬件状态并强制初始化 UI 坐标系 ++
        # 必须在绑定事件和启动定时器之前完成，防止出现 junk 坐标映射导致频率跳变
        self.initialize_hardware_state()

        # 4. 初始化业务逻辑变量
        # 频率拖拽防抖定时器
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
        
        self.last_dial_value = self.ui.freq_dial.value()

        # 5. 绑定所有事件
        self.bind_events()
        
        # 默认 UI 交互状态：允许拖拽 X 轴，锁定红线
        self.ui.plot_widget.setMouseEnabled(x=True, y=False)
        self.ui.center_line.setMovable(False)

        # 6. 启动定时器
        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start(100) # 10fps 绘图

        self.sync_timer = QtCore.QTimer()
        self.sync_timer.timeout.connect(self.sync_status)
        self.sync_timer.start(1000) # 1s 状态同步

    def initialize_hardware_state(self):
        """[修复 Bug 专用] 在启动时同步后端频率，并强制设定 UI 的初始视图范围"""
        try:
            # A. 从后端获取当前真实的硬件频率和解调频率
            self.sdr_freq_hz = self.backend.get_sdr_freq()
            self.target_freq_hz = self.backend.get_target_freq()
            
            # 容错：如果后端返回 0，使用配置文件的默认值
            if self.sdr_freq_hz == 0: self.sdr_freq_hz = 100e6 
            if self.target_freq_hz == 0: self.target_freq_hz = self.sdr_freq_hz
            
            # B. 强行初始化 UI 的视图坐标系，防止跳到 MIN_FREQ (如 22M)
            mhz = self.sdr_freq_hz / 1e6
            tmhz = self.target_freq_hz / 1e6
            
            self.updating_view = True # 加锁
            
            # 设置频谱和瀑布图的 X 轴初始范围
            min_f = self.base_freqs[0] + mhz
            max_f = self.base_freqs[-1] + mhz
            self.ui.plot_widget.setXRange(min_f, max_f, padding=0)
            self.ui.waterfall_widget.setXRange(min_f, max_f, padding=0)
            
            # 初始化瀑布图映射矩形
            rect = QtCore.QRectF(min_f, 0, (max_f - min_f), WATERFALL_ROWS)
            self.ui.waterfall_image.setRect(rect)
            
            # 设置红线和阴影位置
            self.ui.center_line.setValue(tmhz)
            self.update_filter_region(tmhz)
            
            # 更新文本标签
            self.ui.freq_label.setText(f"当前频率: {tmhz:.3f} MHz")
            
            self.updating_view = False # 解锁
            print(f"UI 频率坐标系初始化完成: SDR={mhz:.3f}MHz, Target={tmhz:.3f}MHz")
            
        except Exception as e:
            print(f"初始化硬件状态失败 (请确认 GNU Radio 是否启动): {e}")

    def bind_events(self):
        self.ui.set_freq_btn.clicked.connect(self.on_set_frequency_clicked)
        self.ui.avg_cycle_btn.clicked.connect(self.cycle_averaging)
        self.ui.freq_dial.valueChanged.connect(self.on_dial_rotated)
        # 绑定红线停止拖拽事件 (自由调谐时使用)
        self.ui.center_line.sigPositionChangeFinished.connect(self.on_line_dropped)
        
        # 绑定模式切换
        self.ui.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self.ui.tuning_mode_btn.clicked.connect(self.toggle_tuning_mode)
        
        # 绑定增益
        self.ui.gain_toggle_btn.toggled.connect(self.toggle_gain_panel)
        self.ui.rf_slider.valueChanged.connect(self.on_rf_changed)
        self.ui.if_slider.valueChanged.connect(self.on_if_changed)
        self.ui.bb_slider.valueChanged.connect(self.on_bb_changed)
        
        # 绑定背景拖拽和平移事件 (用于中央调谐)
        self.ui.plot_widget.getViewBox().sigXRangeChanged.connect(self.on_xrange_changed)
        # 绑定背景点击事件 (用于自由调谐)
        self.ui.plot_widget.scene().sigMouseClicked.connect(self.on_plot_clicked)

    # ================= 业务逻辑与交互 (略作修整，去除老旧代码) =================
    def toggle_gain_panel(self, checked):
        self.ui.gain_panel.setVisible(checked)
        self.ui.gain_toggle_btn.setText("增益设置 ▲" if checked else "增益设置 ▼")

    def on_rf_changed(self, value):
        self.ui.rf_label.setText(f"RF: {value} dB"); self.backend.set_gain_rf(value)
    def on_if_changed(self, value):
        self.ui.if_label.setText(f"IF: {value} dB"); self.backend.set_gain_if(value)
    def on_bb_changed(self, value):
        self.ui.bb_label.setText(f"BB: {value} dB"); self.backend.set_gain_bb(value)
        
    def on_mode_changed(self):
        mode_name = self.ui.mode_combo.currentText()
        mode_index = DEMOD_MODES[mode_name][0]
        try: self.backend.set_demod_mode(mode_index)
        except Exception: pass
        self.update_filter_region()

    def update_filter_region(self, center_freq_mhz=None):
        if center_freq_mhz is None: center_freq_mhz = self.ui.center_line.value()
        mode_name = self.ui.mode_combo.currentText()
        _, low_hz, high_hz = DEMOD_MODES[mode_name]
        self.ui.filter_region.setRegion([center_freq_mhz + (low_hz / 1e6), center_freq_mhz + (high_hz / 1e6)])

    def cycle_averaging(self):
        self.avg_index = (self.avg_index + 1) % len(self.avg_lengths)
        length = self.avg_lengths[self.avg_index]
        self.ui.avg_cycle_btn.setText(f"平均长度: {length}")
        self.alpha = 1.0 if length == 1 else 2.0 / (length + 1.0)
        self.averaged_power_db = None 

    # ================= 调谐模式核心逻辑 (修复跳变) =================
    def toggle_tuning_mode(self):
        if self.tuning_mode == "CENTRAL":
            self.tuning_mode = "FREE"
            self.ui.tuning_mode_btn.setText("模式: 自由调谐")
            self.ui.plot_widget.setMouseEnabled(x=False, y=False) # 锁定背景
            self.ui.center_line.setMovable(True)                  # 激活红线
        else:
            self.tuning_mode = "CENTRAL"
            self.ui.tuning_mode_btn.setText("模式: 中央调谐")
            self.ui.plot_widget.setMouseEnabled(x=True, y=False)  # 激活背景
            self.ui.center_line.setMovable(False)                 # 锁定红线
            
            # 切换回中央模式时，确保硬件中心与当前解调目标对齐 (此时同步会改变 UI 视图，需要加锁)
            self.safe_set_sdr_and_target_freq(self.target_freq_hz)

    def on_plot_clicked(self, event):
        """自由调谐模式：点击跳转"""
        if self.tuning_mode == "FREE" and event.button() == QtCore.Qt.LeftButton:
            pos = event.scenePos()
            if self.ui.plot_widget.sceneBoundingRect().contains(pos):
                mouse_point = self.ui.plot_widget.plotItem.vb.mapSceneToView(pos)
                clicked_freq_hz = mouse_point.x() * 1e6
                self.safe_set_target_freq(clicked_freq_hz)

    def on_xrange_changed(self, view_box, view_range):
        """中央调谐模式：拖拽背景平移"""
        if self.tuning_mode == "CENTRAL" and not self.updating_view:
            new_center_mhz = (view_range[0] + view_range[1]) / 2.0
            
            # 1. 立即更新内部变量和 UI，实现视觉跟手
            # 此处应用 max/min 限制，确保频率不会被拖到硬件支持范围外导致 GNU Radio 报错
            target_hz = max(MIN_FREQ_HZ, min(MAX_FREQ_HZ, new_center_mhz * 1e6))
            new_clamped_mhz = target_hz / 1e6
            
            self.sdr_freq_hz = target_hz
            self.target_freq_hz = target_hz
            self.ui.center_line.setValue(new_clamped_mhz)
            self.update_filter_region(new_clamped_mhz)
            self.ui.freq_label.setText(f"当前频率: {new_clamped_mhz:.3f} MHz")
            
            # 同步移动瀑布图底层映射，防止错位
            self.updating_view = True
            self.ui.waterfall_widget.setXRange(view_range[0], view_range[1], padding=0)
            rect = QtCore.QRectF(view_range[0], 0, (view_range[1] - view_range[0]), WATERFALL_ROWS)
            self.ui.waterfall_image.setRect(rect)
            self.updating_view = False
            
            # 2. 发送防抖网络请求
            self.pending_sdr_freq_hz = target_hz
            self.drag_tune_timer.start(50) 

    def apply_dragged_freq(self):
        """防抖定时器：实际调谐底层"""
        if self.pending_sdr_freq_hz:
            self.backend.set_sdr_freq(self.pending_sdr_freq_hz)
            self.backend.set_target_freq(self.pending_sdr_freq_hz)

    def safe_set_sdr_and_target_freq(self, target_hz):
        """绝对调谐 (同时改变硬件和解调中心)"""
        clamped_hz = max(MIN_FREQ_HZ, min(MAX_FREQ_HZ, target_hz))
        mhz = clamped_hz / 1e6
        try:
            self.backend.set_sdr_freq(clamped_hz)
            self.backend.set_target_freq(clamped_hz)
            self.sdr_freq_hz = clamped_hz
            self.target_freq_hz = clamped_hz
            self.averaged_power_db = None  
            
            # 强制立即刷新 UI 坐标系
            self.updating_view = True
            min_f = self.base_freqs[0] + mhz
            max_f = self.base_freqs[-1] + mhz
            self.ui.plot_widget.setXRange(min_f, max_f, padding=0)
            self.ui.waterfall_widget.setXRange(min_f, max_f, padding=0)
            rect = QtCore.QRectF(min_f, 0, (max_f - min_f), WATERFALL_ROWS)
            self.ui.waterfall_image.setRect(rect)
            self.ui.center_line.setValue(mhz)
            self.update_filter_region(mhz)
            self.ui.freq_label.setText(f"当前频率: {mhz:.3f} MHz")
            self.updating_view = False
        except Exception: pass

    def safe_set_target_freq(self, target_hz):
        """自由调谐 (仅在采样带宽内移动解调红线)"""
        # 限制红线范围在当前 SDR 中心频率的 +/- 带宽内
        bw = SAMPLE_RATE / 2.0
        clamped_hz = max(self.sdr_freq_hz - bw, min(self.sdr_freq_hz + bw, target_hz))
        try:
            self.backend.set_target_freq(clamped_hz)
            self.target_freq_hz = clamped_hz
            tmhz = clamped_hz / 1e6
            self.ui.center_line.setValue(tmhz)
            self.update_filter_region(tmhz)
            self.ui.freq_label.setText(f"当前频率: {tmhz:.3f} MHz")
        except Exception: pass

    # ================= 其他事件 =================
    def on_dial_rotated(self, value):
        delta = value - self.last_dial_value
        if delta > 180: delta -= 360
        elif delta < -180: delta += 360
        self.last_dial_value = value
        if delta == 0: return

        step_hz = (delta * (10.0 / 30.0)) * 1e6 # 每格调谐步进
        if self.tuning_mode == "CENTRAL":
            self.safe_set_sdr_and_target_freq(self.sdr_freq_hz + step_hz)
        else:
            self.safe_set_target_freq(self.target_freq_hz + step_hz)

    def on_line_dropped(self):
        """自由调谐下：红线停止拖拽"""
        if self.tuning_mode == "FREE":
            target_hz = self.ui.center_line.value() * 1e6
            self.safe_set_target_freq(target_hz)

    def on_set_frequency_clicked(self):
        try:
            target_hz = float(self.ui.freq_input.text()) * 1e6 
            self.safe_set_sdr_and_target_freq(target_hz)
            self.ui.freq_input.clear()
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "错误", "请输入有效的数字 (如 97.4)")

    # ================= 状态同步与绘图 =================
    def sync_status(self):
        """1s 同步，不应影响 UI 跟手度"""
        try:
            # 仅在未操作时同步
            if not self.updating_view and self.drag_tune_timer.remainingTime() <= 0:
                sdr_f = self.backend.get_sdr_freq()
                tar_f = self.backend.get_target_freq()
                
                # 容错与同步
                self.sdr_freq_hz = max(MIN_FREQ_HZ, min(MAX_FREQ_HZ, sdr_f)) if sdr_f != 0 else self.sdr_freq_hz
                self.target_freq_hz = tar_f if tar_f != 0 else self.sdr_freq_hz

                # 只有当硬件状态发生重大跳变时（如后台被脚本改变），才拉回视图
                current_view_center = (self.ui.plot_widget.viewRange()[0][0] + self.ui.plot_widget.viewRange()[0][1]) / 2.0
                if abs(current_view_center - (self.sdr_freq_hz / 1e6)) > 0.1: # 偏移 100K 以上强制对齐
                    self.safe_set_sdr_and_target_freq(self.sdr_freq_hz)

                self.ui.freq_label.setText(f"当前频率: {(self.target_freq_hz / 1e6):.3f} MHz")
        except Exception: pass 

    def update_plot(self):
        """核心绘图循环 (频谱 X 轴始终跟随 SDR 硬件中心频率)"""
        latest_fft = self.backend.get_latest_fft() 
        if latest_fft is not None:
            power_db = 20 * np.log10(np.abs(latest_fft) / FFT_SIZE + 1e-12) + CALIBRATION_OFFSET
            
            # 平均处理
            if self.averaged_power_db is None: self.averaged_power_db = power_db
            else: self.averaged_power_db = (self.alpha * power_db) + ((1.0 - self.alpha) * self.averaged_power_db)
            
            # X 轴绝对频率映射：基准 FFT 轴 + 硬件中心频率 MHz
            current_x = self.base_freqs + (self.sdr_freq_hz / 1e6)
            self.ui.curve.setData(current_x, self.averaged_power_db)
            
            # 瀑布图处理
            self.waterfall_data = np.roll(self.waterfall_data, -1, axis=0)
            self.waterfall_data[-1, :] = self.averaged_power_db
            self.ui.waterfall_image.setImage(self.waterfall_data.T, autoLevels=False)

    def closeEvent(self, event):
        self.plot_timer.stop(); self.sync_timer.stop(); self.backend.close(); event.accept()

if __name__ == '__main__':
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    font = app.font(); font.setPointSize(12); app.setFont(font)
    main_window = SpectrumAnalyzer()
    main_window.show()
    sys.exit(app.exec_())