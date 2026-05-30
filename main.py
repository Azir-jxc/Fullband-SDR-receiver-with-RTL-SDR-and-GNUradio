# main.py
import sys
import os
import time
import subprocess
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
        
        self.tuning_mode = "CENTRAL" 
        self.sdr_freq_hz = 0.0       
        self.target_freq_hz = 0.0    
        
        self.updating_view = False       
        self.pause_plot_update = False   
        
        self.cur_rf_gain = 20
        self.cur_if_gain = 20
        self.cur_bb_gain = 20
        self.cur_sr_mhz = SAMPLE_RATE / 1e6
        self.cur_samp_mode = "正交采样 (Quadrature)"
        self.config_dialog = None 

        self.demod_dialog = None
        self.spectrum_dialog = None 
        self.vol_popup = None            
        self.cur_demod_mode = "WFM"  
        self.cur_squelch = -70
        self.cur_audio_value = 0.4   

        self.grid_enabled = True 

        # 初始化进程控制状态
        self.gr_process = None
        self.backend = None
        
        # 首次拉起底层进程 (默认模式 0)
        self.restart_sdr_process(0)

        self.base_freqs = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1/SAMPLE_RATE)) / 1e6
        self.waterfall_data = np.full((WATERFALL_ROWS, FFT_SIZE), -100.0)
        self.ui.waterfall_image.setImage(np.ascontiguousarray(self.waterfall_data.T), autoLevels=False)
        self.ui.waterfall_widget.setYRange(0, WATERFALL_ROWS, padding=0)

        self._init_custom_grid() 
        self.initialize_hardware_state()

        self.drag_tune_timer = QtCore.QTimer()
        self.drag_tune_timer.setSingleShot(True)
        self.drag_tune_timer.timeout.connect(self.apply_dragged_freq)
        self.pending_sdr_freq_hz = None

        self.avg_lengths = [1, 5, 10, 25]
        self.avg_index = 1
        self.alpha = 2.0 / (self.avg_lengths[self.avg_index] + 1.0)
        self.averaged_power_db = None
        
        # 音频频谱轴 (0 到 24 kHz，对应数组后半段)
        self.audio_freqs_x = np.linspace(0, 24, FFT_SIZE // 2)

        self.update_status_badges() 
        self.bind_events()
        
        self.ui.plot_widget.setMouseEnabled(x=True, y=False)
        self.ui.center_line.setMovable(False)

        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start(100) 

        self.sync_timer = QtCore.QTimer()
        self.sync_timer.timeout.connect(self.sync_status)
        self.sync_timer.start(1000) 

    def restart_sdr_process(self, mode_idx):
        """杀掉旧进程并根据新的直采模式拉起新进程"""
        print(f"[前端管控] 正在重启底层无线电进程，直采模式切换为: {mode_idx} ...")
        
        if self.backend:
            try: self.backend.close()
            except: pass
            
        if self.gr_process:
            self.gr_process.terminate()
            self.gr_process.wait()
            
        cmd = [sys.executable, "top_block.py", "--direct-samp-mode", str(mode_idx)]
        self.gr_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.STDOUT
        )
        
        self.backend = RadioBackend()
        
        ready = False
        for _ in range(20): 
            time.sleep(0.5)
            if self.backend.get_sdr_freq() > 0:
                ready = True
                break
                
        if not ready:
            print("[前端管控] 警告：底层进程初始化超时，状态可能无法同步！")
            return

        if self.cur_sr_mhz > 0:
            self.backend.set_sdr_samp_rate(self.cur_sr_mhz * 1e6)
            
        if self.sdr_freq_hz > 0:
            self.backend.set_sdr_freq(self.sdr_freq_hz)
        if self.target_freq_hz > 0:
            self.backend.set_target_freq(self.target_freq_hz)
            
        self.backend.set_gain_rf(self.cur_rf_gain)
        self.backend.set_gain_if(self.cur_if_gain)
        self.backend.set_gain_bb(self.cur_bb_gain)
        
        try:
            idx, low_hz, high_hz = DEMOD_MODES[self.cur_demod_mode]
            self.backend.set_demod_mode(idx)
            self.backend.set_filter_bw(self.cur_demod_mode, low_hz, high_hz)
        except Exception as e:
            print(f"[前端管控] 解调模式恢复异常: {e}")
            
        self.backend.set_squelch(self.cur_squelch)
        self.backend.set_audio_value(self.cur_audio_value)
        
        print("[前端管控] 底层流图重启并重连完毕，所有状态已对齐！")

    def _init_custom_grid(self):
        self.grid_lines_x = []
        self.grid_lines_y = []
        pen_grid = pg.mkPen(color=(255, 255, 255, 40), width=1, style=QtCore.Qt.DashLine)
        
        for y in range(-100, -20, 20):
            line = pg.InfiniteLine(angle=0, movable=False, pen=pen_grid)
            line.setPos(y)
            self.ui.plot_widget.addItem(line)
            self.grid_lines_y.append(line)
            
        for _ in range(30):
            line = pg.InfiniteLine(angle=90, movable=False, pen=pen_grid)
            self.ui.plot_widget.addItem(line)
            self.grid_lines_x.append(line)

    def update_grid_overlay(self):
        if self.cur_sr_mhz >= 2.4: spacing = 0.5
        elif self.cur_sr_mhz >= 2.0: spacing = 0.4
        else: spacing = 0.2

        self.ui.lbl_scale.setText(f"{spacing} MHz / Div")
        
        view_range = self.ui.plot_widget.viewRange()[0]
        left_f = view_range[0]
        right_f = view_range[1]
        
        self.ui.lbl_left_freq.setText(f"{left_f:.3f} MHz")
        self.ui.lbl_right_freq.setText(f"{right_f:.3f} MHz")

        for line in self.grid_lines_y:
            line.setVisible(self.grid_enabled)
            
        if not self.grid_enabled:
            for line in self.grid_lines_x:
                line.setVisible(False)
            return

        start_x = np.ceil(left_f / spacing) * spacing
        x_pos = start_x
        
        for line in self.grid_lines_x:
            if x_pos <= right_f:
                line.setPos(x_pos)
                line.setVisible(True)
                x_pos += spacing
            else:
                line.setVisible(False)

    def update_status_badges(self):
        self.ui.lbl_mod.setText(f"MOD: {self.cur_demod_mode}")
        self.ui.lbl_tune.setText("TUNE: FREE" if self.tuning_mode == "FREE" else "TUNE: CENT")
        
        samp_abbr = "QUAD"
        if "I 通道" in self.cur_samp_mode: samp_abbr = "DIR-I"
        elif "Q 通道" in self.cur_samp_mode: samp_abbr = "DIR-Q"
        self.ui.lbl_samp.setText(f"SMP: {samp_abbr}")
        
        self.ui.lbl_sr.setText(f"SR: {self.cur_sr_mhz}M")
        self.ui.lbl_sql.setText(f"SQL: {self.cur_squelch}")
        self.ui.lbl_avg.setText(f"AVG: {self.avg_lengths[self.avg_index]}")

    def update_waterfall_rect(self):
        mhz = self.sdr_freq_hz / 1e6
        min_f = self.base_freqs[0] + mhz
        max_f = self.base_freqs[-1] + mhz
        width = max_f - min_f
        rect = QtCore.QRectF(min_f, 0, width, WATERFALL_ROWS)
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
            
            self.update_waterfall_rect()
            self.ui.center_line.setValue(tmhz)
            self.update_filter_region(tmhz)
            self.ui.freq_display.set_freq(self.target_freq_hz)
            
            self.update_grid_overlay() 
            self.updating_view = False 
        except Exception as e: pass

    def bind_events(self):
        self.ui.freq_display.sig_step_requested.connect(self.on_freq_step_requested)
        self.ui.freq_display.sig_double_clicked.connect(self.open_numpad_dialog)
        
        self.ui.center_line.sigDragged.connect(self.on_line_dragged)
        self.ui.center_line.sigPositionChangeFinished.connect(self.on_line_dropped)
        
        self.ui.demod_config_btn.clicked.connect(self.open_demod_config_dialog)
        self.ui.config_btn.clicked.connect(self.open_config_dialog)
        self.ui.spectrum_config_btn.clicked.connect(self.open_spectrum_config_dialog)
        
        self.ui.vol_btn.clicked.connect(self.show_vol_popup)
        
        self.ui.plot_widget.getViewBox().sigXRangeChanged.connect(self.on_xrange_changed)
        self.ui.plot_widget.scene().sigMouseClicked.connect(self.on_plot_clicked)

    def open_numpad_dialog(self):
        from ui_layout import NumpadDialog
        dialog = NumpadDialog(self, "")
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_mhz = dialog.get_value()
            if new_mhz > 0:
                new_hz = new_mhz * 1e6
                if self.tuning_mode == "CENTRAL":
                    self.safe_set_sdr_and_target_freq(new_hz)
                else:
                    self.safe_set_target_freq(new_hz)

    def on_freq_step_requested(self, delta_hz):
        if self.tuning_mode == "CENTRAL":
            self.safe_set_sdr_and_target_freq(self.sdr_freq_hz + delta_hz)
        else:
            self.safe_set_target_freq(self.target_freq_hz + delta_hz)

    def show_vol_popup(self):
        if self.vol_popup is None:
            from ui_layout import VolumePopup
            self.vol_popup = VolumePopup(self, self.cur_audio_value)
            self.vol_popup.sig_vol_changed.connect(self.on_volume_changed)
        
        btn_pos = self.ui.vol_btn.mapToGlobal(QtCore.QPoint(0, self.ui.vol_btn.height() + 8))
        btn_pos.setX(btn_pos.x() - (self.vol_popup.width() - self.ui.vol_btn.width()) // 2)
        
        self.vol_popup.move(btn_pos)
        self.vol_popup.show()

    def on_volume_changed(self, val):
        self.cur_audio_value = val
        self.backend.set_audio_value(val)

    def open_spectrum_config_dialog(self):
        if self.spectrum_dialog is None:
            from ui_layout import SpectrumConfigDialog
            cur_avg_str = str(self.avg_lengths[self.avg_index])
            self.spectrum_dialog = SpectrumConfigDialog(self, self.tuning_mode, cur_avg_str, self.grid_enabled)
            self.spectrum_dialog.apply_btn.clicked.connect(self.apply_spectrum_config)
            self.spectrum_dialog.close_btn.clicked.connect(self.spectrum_dialog.hide)
            
        self.spectrum_dialog.tune_combo.setCurrentIndex(0 if self.tuning_mode == "CENTRAL" else 1)
        self.spectrum_dialog.avg_combo.setCurrentText(str(self.avg_lengths[self.avg_index]))
        self.spectrum_dialog.grid_combo.setCurrentIndex(0 if self.grid_enabled else 1)
        self.spectrum_dialog.show()
        self.spectrum_dialog.raise_()

    def apply_spectrum_config(self):
        if not self.spectrum_dialog: return
        
        new_tune_idx = self.spectrum_dialog.tune_combo.currentIndex()
        new_tune = "CENTRAL" if new_tune_idx == 0 else "FREE"
        
        new_avg_str = self.spectrum_dialog.avg_combo.currentText()
        self.avg_index = self.avg_lengths.index(int(new_avg_str))
        length = self.avg_lengths[self.avg_index]
        self.alpha = 1.0 if length == 1 else 2.0 / (length + 1.0)
        self.averaged_power_db = None 

        grid_idx = self.spectrum_dialog.grid_combo.currentIndex()
        self.grid_enabled = (grid_idx == 0)

        if self.tuning_mode != new_tune:
            self.tuning_mode = new_tune
            if self.tuning_mode == "FREE":
                self.ui.plot_widget.setMouseEnabled(x=False, y=False) 
                self.ui.center_line.setMovable(True)                  
            else:
                self.ui.plot_widget.setMouseEnabled(x=True, y=False)  
                self.ui.center_line.setMovable(False)                 
                self.safe_set_sdr_and_target_freq(self.target_freq_hz)
                
        self.update_status_badges()
        self.update_grid_overlay() 
        self.spectrum_dialog.hide()

    def open_demod_config_dialog(self):
        if self.demod_dialog is None:
            from ui_layout import DemodConfigDialog
            _, cur_low, cur_high = DEMOD_MODES[self.cur_demod_mode]

            self.demod_dialog = DemodConfigDialog(
                self, self.cur_demod_mode, cur_low, cur_high, self.cur_squelch
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
        
        idx = DEMOD_MODES[new_mode][0]
        DEMOD_MODES[new_mode] = (idx, new_low, new_high)
        
        if self.cur_demod_mode != new_mode:
            self.cur_demod_mode = new_mode
            self.backend.set_demod_mode(idx)
            
        self.update_filter_region()
        self.backend.set_squelch(self.cur_squelch)
        self.backend.set_filter_bw(new_mode, new_low, new_high)
        
        self.update_status_badges()
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
            self.restart_sdr_process(mode_idx) # 触发硬重启
            
        if new_sr_mhz != self.cur_sr_mhz:
            self.cur_sr_mhz = new_sr_mhz
            new_sr_hz = new_sr_mhz * 1e6
            self.backend.set_sdr_samp_rate(new_sr_hz)
            self.base_freqs = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1/new_sr_hz)) / 1e6
            self.safe_set_sdr_and_target_freq(self.sdr_freq_hz)

        self.update_status_badges()
        self.config_dialog.hide()

    def update_filter_region(self, center_freq_mhz=None):
        if center_freq_mhz is None: center_freq_mhz = self.ui.center_line.value()
        _, low_hz, high_hz = DEMOD_MODES[self.cur_demod_mode]
        self.ui.filter_region.setRegion([center_freq_mhz + (low_hz / 1e6), center_freq_mhz + (high_hz / 1e6)])

    def on_plot_clicked(self, event):
        if self.tuning_mode == "FREE" and event.button() == QtCore.Qt.LeftButton:
            pos = event.scenePos()
            if self.ui.plot_widget.sceneBoundingRect().contains(pos):
                mouse_point = self.ui.plot_widget.plotItem.vb.mapSceneToView(pos)
                clicked_freq_hz = mouse_point.x() * 1e6
                self.safe_set_target_freq(clicked_freq_hz)

    def on_xrange_changed(self, view_box, view_range):
        self.update_grid_overlay() 
        
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
            
            half_bw = self.cur_sr_mhz / 2.0
            min_f = mhz - half_bw
            max_f = mhz + half_bw
            
            self.ui.plot_widget.setXRange(min_f, max_f, padding=0)
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

        # === 修复：正确截取带有 shift 的音频 FFT 右半部分 (正频率) ===
        latest_audio_fft = self.backend.get_latest_audio_fft()
        if latest_audio_fft is not None:
            # FFT经过了shift，DC(0Hz)在正中央(index 512)，取右半部 [512:1024]
            audio_mag = np.abs(latest_audio_fft[FFT_SIZE // 2 :])
            
            # 由于切片正确包含了真实的低频能量，无需再加粗暴的补偿
            audio_power = 20 * np.log10(audio_mag / FFT_SIZE + 1e-12)
            self.ui.audio_curve.setData(self.audio_freqs_x, audio_power)

    def closeEvent(self, event):
        """窗口关闭时彻底清理资源和进程"""
        self.plot_timer.stop()
        self.sync_timer.stop()
        if self.backend:
            self.backend.close()
        if self.gr_process:
            self.gr_process.terminate()
            self.gr_process.wait()
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