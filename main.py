# main.py
import sys
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

from config import *
from radio_backend import RadioBackend
from ui_layout import Ui_MainWindow

class SpectrumAnalyzer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.ui = Ui_MainWindow()
        self.ui.setup_ui(self)
        self.backend = RadioBackend()
        
        # --- 核心状态变量 ---
        self.tuning_mode = "CENTRAL" 
        self.sdr_freq_hz = 0.0       
        self.target_freq_hz = 0.0    
        
        # --- 渲染控制锁 ---
        self.updating_view = False       
        self.pause_plot_update = False   
        
        # --- 前端配置状态缓存 ---
        self.cur_rf_gain = 20
        self.cur_if_gain = 20
        self.cur_bb_gain = 20
        self.cur_sr_mhz = SAMPLE_RATE / 1e6
        self.cur_samp_mode = "正交采样 (Quadrature)"
        self.config_dialog = None 

        # --- 解调与AGC状态缓存 ---
        self.demod_dialog = None
        self.cur_demod_mode = "WFM"  
        self.cur_squelch = -70
        self.cur_audio_value = 0.4   

        # --- 数据与内存初始化 ---
        self.base_freqs = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1/SAMPLE_RATE)) / 1e6
        self.waterfall_data = np.full((WATERFALL_ROWS, FFT_SIZE), -100.0)
        self.ui.waterfall_image.setImage(np.ascontiguousarray(self.waterfall_data.T), autoLevels=False)
        self.ui.waterfall_widget.setYRange(0, WATERFALL_ROWS, padding=0)

        self.initialize_hardware_state()

        self.drag_tune_timer = QtCore.QTimer()
        self.drag_tune_timer.setSingleShot(True)
        self.drag_tune_timer.timeout.connect(self.apply_dragged_freq)
        self.pending_sdr_freq_hz = None

        self.avg_lengths = [1, 5, 10, 25]
        self.avg_index = 1
        self.alpha = 2.0 / (self.avg_lengths[self.avg_index] + 1.0)
        self.averaged_power_db = None
        self.ui.avg_cycle_btn.setText(f"FFT AVG\n平滑: {self.avg_lengths[self.avg_index]}")
        
        self.bind_events()
        
        self.ui.plot_widget.setMouseEnabled(x=True, y=False)
        self.ui.center_line.setMovable(False)

        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start(100) 

        self.sync_timer = QtCore.QTimer()
        self.sync_timer.timeout.connect(self.sync_status)
        self.sync_timer.start(1000) 

    def update_waterfall_rect(self):
        mhz = self.sdr_freq_hz / 1e6
        sr_mhz = self.cur_sr_mhz
        min_f = mhz - (sr_mhz / 2.0)
        rect = QtCore.QRectF(min_f, 0, sr_mhz, WATERFALL_ROWS)
        self.ui.waterfall_image.setRect(rect)

    def initialize_hardware_state(self):
        try:
            self.sdr_freq_hz = self.backend.get_sdr_freq()
            self.target_freq_hz = self.backend.get_target_freq()
            
            if self.sdr_freq_hz == 0: self.sdr_freq_hz = 100e6 
            if self.target_freq_hz == 0: self.target_freq_hz = self.sdr_freq_hz
            
            mhz = self.sdr_freq_hz / 1e6
            tmhz = self.target_freq_hz / 1e6
            
            self.updating_view = True 
            min_f = self.base_freqs[0] + mhz
            max_f = self.base_freqs[-1] + mhz
            self.ui.plot_widget.setXRange(min_f, max_f, padding=0)
            self.ui.waterfall_widget.setXRange(min_f, max_f, padding=0)
            
            self.update_waterfall_rect()
            self.ui.center_line.setValue(tmhz)
            self.update_filter_region(tmhz)
            
            # 将硬件频率同步到数字面板
            self.ui.freq_display.set_freq(self.target_freq_hz)
            
            self.updating_view = False 
        except Exception as e: pass

    def bind_events(self):
        # 绑定全新的交互式频率拖拽信号
        self.ui.freq_display.sig_step_requested.connect(self.on_freq_step_requested)
        
        self.ui.avg_cycle_btn.clicked.connect(self.cycle_averaging)
        self.ui.center_line.sigDragged.connect(self.on_line_dragged)
        self.ui.center_line.sigPositionChangeFinished.connect(self.on_line_dropped)
        self.ui.tuning_mode_btn.clicked.connect(self.toggle_tuning_mode)
        self.ui.config_btn.clicked.connect(self.open_config_dialog)
        self.ui.demod_config_btn.clicked.connect(self.open_demod_config_dialog)
        self.ui.plot_widget.getViewBox().sigXRangeChanged.connect(self.on_xrange_changed)
        self.ui.plot_widget.scene().sigMouseClicked.connect(self.on_plot_clicked)

    # ================= 交互式面板核心逻辑 =================
    def on_freq_step_requested(self, delta_hz):
        """处理面板上数字被左右拖拽时发出的步进请求"""
        if self.tuning_mode == "CENTRAL":
            # 中央调谐：平移整个频谱底图
            self.safe_set_sdr_and_target_freq(self.sdr_freq_hz + delta_hz)
        else:
            # 自由调谐：仅在画面内移动目标红线
            self.safe_set_target_freq(self.target_freq_hz + delta_hz)

    # ================= 前端与解调弹窗配置 =================
    def open_demod_config_dialog(self):
        if self.demod_dialog is None:
            from ui_layout import DemodConfigDialog
            _, cur_low, cur_high = DEMOD_MODES[self.cur_demod_mode]

            self.demod_dialog = DemodConfigDialog(
                self, self.cur_demod_mode, cur_low, cur_high, self.cur_squelch, self.cur_audio_value
            )
            self.demod_dialog.apply_btn.clicked.connect(self.apply_demod_config)
            self.demod_dialog.close_btn.clicked.connect(self.demod_dialog.hide)
            
        self.demod_dialog.mode_combo.setCurrentText(self.cur_demod_mode)
        self.demod_dialog.show()
        self.demod_dialog.raise_()

    def apply_demod_config(self):
        if not self.demod_dialog: return
        
        new_mode = self.demod_dialog.mode_combo.currentText()
        new_low = self.demod_dialog.low_spin.value()
        new_high = self.demod_dialog.high_spin.value()
        self.cur_squelch = self.demod_dialog.squelch_spin.value()
        
        slider_val = self.demod_dialog.audio_slider.value()
        self.cur_audio_value = 0.0 if slider_val == 0 else slider_val / 10.0
        
        idx = DEMOD_MODES[new_mode][0]
        DEMOD_MODES[new_mode] = (idx, new_low, new_high)
        
        if self.cur_demod_mode != new_mode:
            self.cur_demod_mode = new_mode
            self.backend.set_demod_mode(idx)
            
        self.update_filter_region()
        self.backend.set_squelch(self.cur_squelch)
        self.backend.set_audio_value(self.cur_audio_value)
        self.backend.set_filter_bw(new_mode, new_low, new_high)
        self.demod_dialog.hide()

    def open_config_dialog(self):
        if self.config_dialog is None:
            from ui_layout import ConfigDialog
            self.config_dialog = ConfigDialog(
                self, self.cur_rf_gain, self.cur_if_gain, self.cur_bb_gain,
                str(self.cur_sr_mhz), self.cur_samp_mode
            )
            self.config_dialog.rf_slider.valueChanged.connect(self.on_rf_changed)
            self.config_dialog.if_slider.valueChanged.connect(self.on_if_changed)
            self.config_dialog.bb_slider.valueChanged.connect(self.on_bb_changed)
            self.config_dialog.apply_btn.clicked.connect(self.apply_hardware_config)
            self.config_dialog.close_btn.clicked.connect(self.config_dialog.hide)
            
        self.config_dialog.show()
        self.config_dialog.raise_()

    def on_rf_changed(self, val):
        self.cur_rf_gain = val; self.backend.set_gain_rf(val)
    def on_if_changed(self, val):
        self.cur_if_gain = val; self.backend.set_gain_if(val)
    def on_bb_changed(self, val):
        self.cur_bb_gain = val; self.backend.set_gain_bb(val)

    def apply_hardware_config(self):
        if not self.config_dialog: return
        new_sr_str = self.config_dialog.sr_combo.currentText()
        new_mode_str = self.config_dialog.mode_combo.currentText()
        new_sr_mhz = float(new_sr_str)
        
        if new_mode_str != self.cur_samp_mode:
            self.cur_samp_mode = new_mode_str
            mode_idx = 0 if "正交" in new_mode_str else (1 if "I 通道" in new_mode_str else 2)
            self.backend.set_direct_samp_mode(mode_idx)
            
        if new_sr_mhz != self.cur_sr_mhz:
            self.cur_sr_mhz = new_sr_mhz
            new_sr_hz = new_sr_mhz * 1e6
            self.backend.set_sdr_samp_rate(new_sr_hz)
            self.base_freqs = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1/new_sr_hz)) / 1e6
            self.safe_set_sdr_and_target_freq(self.sdr_freq_hz)

        self.config_dialog.hide()

    # ================= 业务逻辑与交互 =================
    def update_filter_region(self, center_freq_mhz=None):
        if center_freq_mhz is None: center_freq_mhz = self.ui.center_line.value()
        _, low_hz, high_hz = DEMOD_MODES[self.cur_demod_mode]
        self.ui.filter_region.setRegion([center_freq_mhz + (low_hz / 1e6), center_freq_mhz + (high_hz / 1e6)])

    def cycle_averaging(self):
        self.avg_index = (self.avg_index + 1) % len(self.avg_lengths)
        length = self.avg_lengths[self.avg_index]
        self.ui.avg_cycle_btn.setText(f"FFT AVG\n平滑: {length}")
        self.alpha = 1.0 if length == 1 else 2.0 / (length + 1.0)
        self.averaged_power_db = None 

    def toggle_tuning_mode(self):
        if self.tuning_mode == "CENTRAL":
            self.tuning_mode = "FREE"
            self.ui.tuning_mode_btn.setText("TUNE MODE\n自由调谐")
            self.ui.plot_widget.setMouseEnabled(x=False, y=False) 
            self.ui.center_line.setMovable(True)                  
        else:
            self.tuning_mode = "CENTRAL"
            self.ui.tuning_mode_btn.setText("TUNE MODE\n中央调谐")
            self.ui.plot_widget.setMouseEnabled(x=True, y=False)  
            self.ui.center_line.setMovable(False)                 
            self.safe_set_sdr_and_target_freq(self.target_freq_hz)

    def on_plot_clicked(self, event):
        if self.tuning_mode == "FREE" and event.button() == QtCore.Qt.LeftButton:
            pos = event.scenePos()
            if self.ui.plot_widget.sceneBoundingRect().contains(pos):
                mouse_point = self.ui.plot_widget.plotItem.vb.mapSceneToView(pos)
                clicked_freq_hz = mouse_point.x() * 1e6
                self.safe_set_target_freq(clicked_freq_hz)

    def on_xrange_changed(self, view_box, view_range):
        if self.tuning_mode == "CENTRAL" and not self.updating_view:
            self.pause_plot_update = True 
            
            new_center_mhz = (view_range[0] + view_range[1]) / 2.0
            target_hz = max(MIN_FREQ_HZ, min(MAX_FREQ_HZ, new_center_mhz * 1e6))
            new_clamped_mhz = target_hz / 1e6
            
            self.sdr_freq_hz = target_hz
            self.target_freq_hz = target_hz
            self.ui.center_line.setValue(new_clamped_mhz)
            self.update_filter_region(new_clamped_mhz)
            
            self.ui.freq_display.set_freq(target_hz)
            
            self.updating_view = True
            self.ui.waterfall_widget.setXRange(view_range[0], view_range[1], padding=0)
            self.update_waterfall_rect() 
            self.updating_view = False
            
            self.pending_sdr_freq_hz = target_hz
            self.drag_tune_timer.start(50) 

    def apply_dragged_freq(self):
        if self.pending_sdr_freq_hz:
            self.backend.set_sdr_freq(self.pending_sdr_freq_hz)
            self.backend.set_target_freq(self.pending_sdr_freq_hz)
        QtCore.QTimer.singleShot(200, self.resume_plot)

    def resume_plot(self):
        self.pause_plot_update = False
        self.averaged_power_db = None  

    def safe_set_sdr_and_target_freq(self, target_hz):
        clamped_hz = max(MIN_FREQ_HZ, min(MAX_FREQ_HZ, target_hz))
        mhz = clamped_hz / 1e6
        try:
            self.backend.set_sdr_freq(clamped_hz)
            self.backend.set_target_freq(clamped_hz)
            self.sdr_freq_hz = clamped_hz
            self.target_freq_hz = clamped_hz
            self.averaged_power_db = None  
            
            self.updating_view = True
            min_f = self.base_freqs[0] + mhz
            max_f = self.base_freqs[-1] + mhz
            self.ui.plot_widget.setXRange(min_f, max_f, padding=0)
            self.ui.waterfall_widget.setXRange(min_f, max_f, padding=0)
            self.update_waterfall_rect()
            self.ui.center_line.setValue(mhz)
            self.update_filter_region(mhz)
            
            self.ui.freq_display.set_freq(clamped_hz)
            self.updating_view = False
        except Exception: pass

    def safe_set_target_freq(self, target_hz):
        bw = self.cur_sr_mhz * 1e6 / 2.0
        clamped_hz = max(self.sdr_freq_hz - bw, min(self.sdr_freq_hz + bw, target_hz))
        try:
            self.backend.set_target_freq(clamped_hz)
            self.target_freq_hz = clamped_hz
            tmhz = clamped_hz / 1e6
            self.ui.center_line.setValue(tmhz)
            self.update_filter_region(tmhz)
            self.ui.freq_display.set_freq(clamped_hz)
        except Exception: pass

    def on_line_dragged(self):
        if self.tuning_mode == "FREE":
            self.is_dragging = True
            target_freq_mhz = self.ui.center_line.value()
            self.update_filter_region(target_freq_mhz)
            self.ui.freq_display.set_freq(target_freq_mhz * 1e6)

    def on_line_dropped(self):
        if self.tuning_mode == "FREE":
            self.is_dragging = False
            target_hz = self.ui.center_line.value() * 1e6
            self.safe_set_target_freq(target_hz)

    def sync_status(self):
        try:
            if not self.updating_view and self.drag_tune_timer.remainingTime() <= 0 and not getattr(self, 'is_dragging', False):
                sdr_f = self.backend.get_sdr_freq()
                tar_f = self.backend.get_target_freq()
                
                self.sdr_freq_hz = max(MIN_FREQ_HZ, min(MAX_FREQ_HZ, sdr_f)) if sdr_f != 0 else self.sdr_freq_hz
                self.target_freq_hz = tar_f if tar_f != 0 else self.sdr_freq_hz

                current_view_center = (self.ui.plot_widget.viewRange()[0][0] + self.ui.plot_widget.viewRange()[0][1]) / 2.0
                if abs(current_view_center - (self.sdr_freq_hz / 1e6)) > 0.1: 
                    self.safe_set_sdr_and_target_freq(self.sdr_freq_hz)

                self.ui.freq_display.set_freq(self.target_freq_hz)
        except Exception: pass 

    def update_plot(self):
        latest_fft = self.backend.get_latest_fft() 
        if self.pause_plot_update: return

        if latest_fft is not None:
            power_db = 20 * np.log10(np.abs(latest_fft) / FFT_SIZE + 1e-12) + CALIBRATION_OFFSET
            
            if self.averaged_power_db is None: self.averaged_power_db = power_db
            else: self.averaged_power_db = (self.alpha * power_db) + ((1.0 - self.alpha) * self.averaged_power_db)
            
            current_x = self.base_freqs + (self.sdr_freq_hz / 1e6)
            self.ui.curve.setData(current_x, self.averaged_power_db)
            
            self.waterfall_data = np.roll(self.waterfall_data, -1, axis=0)
            self.waterfall_data[-1, :] = self.averaged_power_db
            
            render_data = np.ascontiguousarray(self.waterfall_data.T)
            self.ui.waterfall_image.setImage(render_data, autoLevels=False)

            target_mhz = self.target_freq_hz / 1e6
            idx = (np.abs(current_x - target_mhz)).argmin()
            s_meter_val = self.averaged_power_db[idx]
            self.ui.s_meter.setValue(int(s_meter_val))

    def closeEvent(self, event):
        self.plot_timer.stop(); self.sync_timer.stop(); self.backend.close(); event.accept()

if __name__ == '__main__':
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    
    main_window = SpectrumAnalyzer()
    main_window.show()
    sys.exit(app.exec_())