# ui_layout.py
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
from config import *

# ================= 全局暗黑专业仪器 QSS 样式 =================
DARK_STYLE = """
QMainWindow, QDialog, QWidget { 
    background-color: #121212; 
    color: #E0E0E0; 
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}
QWidget#FreqContainer {
    background-color: #000000; 
    border: 2px solid #333333; 
    border-radius: 8px; 
}
QPushButton { 
    background-color: #2D2D2D; 
    border: 1px solid #555555; 
    border-radius: 6px; 
    color: #E0E0E0; 
    font-size: 14px; 
    font-weight: bold; 
    padding: 8px 15px; 
}
QPushButton:pressed { 
    background-color: #00FFCC; 
    color: #000000; 
}
QProgressBar { 
    border: 1px solid #333; 
    border-radius: 4px; 
    background-color: #000000; 
    text-align: right; 
    color: #FFFFFF;
    font-weight: bold;
    font-size: 12px;
}
QProgressBar::chunk { 
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
        stop:0 #00FF00, stop:0.7 #FFFF00, stop:1 #FF1744); 
}
QGroupBox { 
    color: #00FFCC; 
    font-weight: bold; 
    border: 1px solid #404040; 
    margin-top: 15px; 
}
QGroupBox::title { 
    subcontrol-origin: margin; 
    left: 10px; 
    padding: 0 5px; 
}
QSpinBox, QDoubleSpinBox, QComboBox { 
    background-color: #1E1E1E; 
    color: #E0E0E0; 
    border: 1px solid #404040; 
    padding: 5px; 
    border-radius: 4px;
}
"""

# ================= 自定义交互式频率管组件 =================
class DigitLabel(QtWidgets.QLabel):
    sig_stepped = QtCore.pyqtSignal(int)
    sig_selected = QtCore.pyqtSignal(int)

    def __init__(self, step_hz, parent=None):
        super().__init__(parent)
        self.step_hz = step_hz
        self.drag_start_x = 0
        self.drag_accum = 0
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setCursor(QtCore.Qt.SizeHorCursor) 
        self.set_selected(False)

    def set_selected(self, selected):
        base_style = "font-size: 56px; font-weight: bold; font-family: 'Consolas', monospace; border: none;"
        if selected:
            self.setStyleSheet(f"{base_style} color: #000000; background-color: #00FFCC; border-radius: 6px;")
        else:
            self.setStyleSheet(f"{base_style} color: #00FFCC; background-color: transparent;")

    def mousePressEvent(self, event):
        self.drag_start_x = event.x()
        self.drag_accum = 0
        self.sig_selected.emit(self.step_hz)

    def mouseMoveEvent(self, event):
        dx = event.x() - self.drag_start_x
        self.drag_accum += dx
        self.drag_start_x = event.x()
        
        threshold = 15 
        while self.drag_accum > threshold:
            self.sig_stepped.emit(1)
            self.drag_accum -= threshold
        while self.drag_accum < -threshold:
            self.sig_stepped.emit(-1)
            self.drag_accum += threshold

class InteractiveFreqDisplay(QtWidgets.QWidget):
    sig_step_requested = QtCore.pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.freq_hz = 0
        self.setObjectName("FreqContainer")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(0) 
        
        self.digits = []
        
        self.add_digit(layout, 1000000000) 
        self.add_digit(layout, 100000000)  
        self.add_digit(layout, 10000000)   
        self.add_digit(layout, 1000000)    
        
        dot = QtWidgets.QLabel(".")
        dot.setStyleSheet("color: #00FFCC; font-size: 56px; font-weight: bold; font-family: 'Consolas', monospace; border: none; background: transparent;")
        dot.setAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignCenter)
        dot.setFixedSize(20, 70) 
        layout.addWidget(dot)
        
        self.add_digit(layout, 100000)     
        self.add_digit(layout, 10000)      
        self.add_digit(layout, 1000)       
        
        unit = QtWidgets.QLabel(" MHz")
        unit.setStyleSheet("color: #00FFCC; font-size: 26px; font-weight: bold; border: none; background: transparent; padding-bottom: 12px;")
        unit.setAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft)
        unit.setFixedHeight(70)
        layout.addWidget(unit)
        
        self.on_digit_selected(100000)

    def add_digit(self, layout, step_hz):
        lbl = DigitLabel(step_hz)
        lbl.setFixedSize(38, 70) 
        lbl.sig_selected.connect(self.on_digit_selected)
        lbl.sig_stepped.connect(lambda direction, step=step_hz: self.sig_step_requested.emit(direction * step))
        self.digits.append(lbl)
        layout.addWidget(lbl)

    def on_digit_selected(self, step_hz):
        for d in self.digits:
            d.set_selected(d.step_hz == step_hz)

    def set_freq(self, hz):
        self.freq_hz = hz
        val = int(round(hz / 1000)) 
        s = f"{val:07d}" 
        if len(s) > 7: s = s[-7:] 
        
        for i, char in enumerate(s):
            if i < len(self.digits):
                self.digits[i].setText(char)

# ================= 弹窗组件类 =================

class SpectrumConfigDialog(QtWidgets.QDialog):
    """新增：频谱与调谐设置弹窗"""
    def __init__(self, parent=None, cur_tune="CENTRAL", cur_avg="1"):
        super().__init__(parent)
        self.setWindowTitle("频谱与调谐设置")
        self.setMinimumWidth(300)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self.setStyleSheet(DARK_STYLE)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)

        tune_layout = QtWidgets.QHBoxLayout()
        tune_layout.addWidget(QtWidgets.QLabel("调谐模式:"))
        self.tune_combo = QtWidgets.QComboBox()
        self.tune_combo.addItems(["CENTRAL (中央调谐)", "FREE (自由调谐)"])
        self.tune_combo.setCurrentText("CENTRAL (中央调谐)" if cur_tune == "CENTRAL" else "FREE (自由调谐)")
        self.tune_combo.setMinimumHeight(35)
        tune_layout.addWidget(self.tune_combo)
        layout.addLayout(tune_layout)

        avg_layout = QtWidgets.QHBoxLayout()
        avg_layout.addWidget(QtWidgets.QLabel("FFT 平滑 (AVG):"))
        self.avg_combo = QtWidgets.QComboBox()
        self.avg_combo.addItems(["1", "5", "10", "25"])
        self.avg_combo.setCurrentText(str(cur_avg))
        self.avg_combo.setMinimumHeight(35)
        avg_layout.addWidget(self.avg_combo)
        layout.addLayout(avg_layout)

        btn_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用")
        self.apply_btn.setStyleSheet("background-color: #0078D7; color: white;")
        self.close_btn = QtWidgets.QPushButton("关闭")
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

class DemodConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, cur_mode="WFM", cur_low=-75000, cur_high=75000, cur_squelch=-70, cur_audio_value=0.4):
        super().__init__(parent)
        self.setWindowTitle("解调与接收配置")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self.setStyleSheet(DARK_STYLE) 
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("解调模式:"))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(list(DEMOD_MODES.keys()))
        self.mode_combo.setCurrentText(cur_mode)
        self.mode_combo.setMinimumHeight(35)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)
        filter_box = QtWidgets.QGroupBox("滤波器带宽 (Hz)")
        filter_layout = QtWidgets.QGridLayout(filter_box)
        filter_layout.addWidget(QtWidgets.QLabel("下限:"), 0, 0)
        self.low_spin = QtWidgets.QSpinBox()
        self.low_spin.setRange(-500000, 500000)
        self.low_spin.setSingleStep(100)
        self.low_spin.setValue(int(cur_low))
        filter_layout.addWidget(self.low_spin, 0, 1)
        filter_layout.addWidget(QtWidgets.QLabel("上限:"), 1, 0)
        self.high_spin = QtWidgets.QSpinBox()
        self.high_spin.setRange(-500000, 500000)
        self.high_spin.setSingleStep(100)
        self.high_spin.setValue(int(cur_high))
        filter_layout.addWidget(self.high_spin, 1, 1)
        layout.addWidget(filter_box)
        agc_box = QtWidgets.QGroupBox("音频与静噪")
        agc_layout = QtWidgets.QGridLayout(agc_box)
        agc_layout.addWidget(QtWidgets.QLabel("静噪门限 (dB):"), 0, 0)
        self.squelch_spin = QtWidgets.QSpinBox()
        self.squelch_spin.setRange(-150, 0)
        self.squelch_spin.setValue(int(cur_squelch))
        agc_layout.addWidget(self.squelch_spin, 0, 1)
        agc_layout.addWidget(QtWidgets.QLabel("音量 (VOL):"), 1, 0)
        self.audio_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.audio_slider.setRange(0, 8)
        init_val = 0 if cur_audio_value == 0 else int(cur_audio_value * 10)
        self.audio_slider.setValue(init_val)
        self.audio_label = QtWidgets.QLabel(f"{cur_audio_value:.1f}")
        self.audio_label.setMinimumWidth(30)
        self.audio_slider.valueChanged.connect(self.on_audio_slide)
        agc_layout.addWidget(self.audio_slider, 1, 1)
        agc_layout.addWidget(self.audio_label, 1, 2)
        layout.addWidget(agc_box)
        btn_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用配置")
        self.apply_btn.setStyleSheet("background-color: #0078D7; color: white;")
        self.close_btn = QtWidgets.QPushButton("关闭")
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        self.mode_combo.currentIndexChanged.connect(self.auto_update_filter_bounds)

    def on_audio_slide(self, val):
        real_val = 0.0 if val == 0 else val / 10.0
        self.audio_label.setText(f"{real_val:.1f}")
    def auto_update_filter_bounds(self):
        mode = self.mode_combo.currentText()
        if mode in DEMOD_MODES:
            _, low, high = DEMOD_MODES[mode]
            self.low_spin.setValue(int(low))
            self.high_spin.setValue(int(high))

class ConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, cur_rf=20, cur_if=20, cur_bb=20, cur_sr="2.4", cur_mode="正交采样 (Quadrature)"):
        super().__init__(parent)
        self.setWindowTitle("硬件射频前端")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool) 
        self.setStyleSheet(DARK_STYLE)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        sr_layout = QtWidgets.QHBoxLayout()
        sr_layout.addWidget(QtWidgets.QLabel("采样率 (MHz):"))
        self.sr_combo = QtWidgets.QComboBox()
        self.sr_combo.addItems(["1.024", "1.28", "2.048", "2.4", "2.56", "2.8", "3.2"])
        self.sr_combo.setCurrentText(cur_sr)
        self.sr_combo.setMinimumHeight(35)
        sr_layout.addWidget(self.sr_combo)
        layout.addLayout(sr_layout)
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("采样模式:"))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["正交采样 (Quadrature)", "I 通道直采 (Direct I)", "Q 通道直采 (Direct Q)"])
        self.mode_combo.setCurrentText(cur_mode)
        self.mode_combo.setMinimumHeight(35)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)
        self.rf_slider, self.rf_label = self.create_slider("RF 增益", cur_rf, layout)
        self.if_slider, self.if_label = self.create_slider("IF 增益", cur_if, layout)
        self.bb_slider, self.bb_label = self.create_slider("BB 增益", cur_bb, layout)
        btn_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用重启")
        self.apply_btn.setStyleSheet("background-color: #0078D7; color: white;")
        self.close_btn = QtWidgets.QPushButton("关闭")
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def create_slider(self, name, default_val, parent_layout):
        vbox = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel(f"{name}: {default_val} dB")
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 50)
        slider.setValue(default_val)
        slider.valueChanged.connect(lambda v, l=label, n=name: l.setText(f"{n}: {v} dB"))
        vbox.addWidget(label)
        vbox.addWidget(slider)
        parent_layout.addLayout(vbox)
        return slider, label


class Ui_MainWindow:
    def create_status_badge(self, text, color="#00FFCC"):
        """边框颜色和字体颜色同步的指示灯"""
        lbl = QtWidgets.QLabel(text)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setStyleSheet(f"background-color: #111111; color: {color}; border: 1px solid {color}; border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: bold; font-family: 'Consolas', monospace;")
        return lbl

    def setup_ui(self, window):
        window.setWindowTitle("Malachite-Style SDR")
        window.resize(1024, 600)
        window.setStyleSheet(DARK_STYLE) 

        main_widget = QtWidgets.QWidget()
        window.setCentralWidget(main_widget)
        
        # 整体采用上下垂直布局
        root_layout = QtWidgets.QVBoxLayout(main_widget)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # ================= 1. 顶栏：左侧状态灯矩阵 + 右侧控制按钮 =================
        top_bar_layout = QtWidgets.QHBoxLayout()
        top_bar_layout.setSpacing(15)
        
        # 状态灯布局
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.setSpacing(8)
        self.lbl_mod = self.create_status_badge("MOD: WFM", "#00FFCC")
        self.lbl_tune = self.create_status_badge("TUNE: CENT", "#FF9800")
        self.lbl_samp = self.create_status_badge("SMP: QUAD", "#8BC34A")
        self.lbl_sr = self.create_status_badge("SR: 2.4M", "#8BC34A")
        self.lbl_sql = self.create_status_badge("SQL: -70", "#FF5252")
        self.lbl_avg = self.create_status_badge("AVG: 1", "#E040FB") 
        self.lbl_agc = self.create_status_badge("AGC: OFF", "#666666") 
        
        status_layout.addWidget(self.lbl_mod)
        status_layout.addWidget(self.lbl_tune)
        status_layout.addWidget(self.lbl_samp)
        status_layout.addWidget(self.lbl_sr)
        status_layout.addWidget(self.lbl_sql)
        status_layout.addWidget(self.lbl_avg)
        status_layout.addWidget(self.lbl_agc)
        
        top_bar_layout.addLayout(status_layout)
        top_bar_layout.addStretch() # 把两拨人往左右两侧推开
        
        # 右侧按钮组 (三个弹窗入口)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(8)
        self.demod_config_btn = QtWidgets.QPushButton("解调设置")
        self.config_btn = QtWidgets.QPushButton("射频前端")
        self.spectrum_config_btn = QtWidgets.QPushButton("频谱设置")
        
        btn_layout.addWidget(self.demod_config_btn)
        btn_layout.addWidget(self.config_btn)
        btn_layout.addWidget(self.spectrum_config_btn)
        
        top_bar_layout.addLayout(btn_layout)
        root_layout.addLayout(top_bar_layout)

        # ================= 2. 下方主内容：独占全宽的图形区 =================
        main_content_layout = QtWidgets.QVBoxLayout()
        
        # 交互式数字荧光屏 
        freq_layout = QtWidgets.QHBoxLayout()
        self.freq_display = InteractiveFreqDisplay()
        freq_layout.addWidget(self.freq_display)
        freq_layout.addStretch() # 保证频率屏居左不拉伸
        main_content_layout.addLayout(freq_layout)

        # S-Meter (信号强度指示条)
        self.s_meter = QtWidgets.QProgressBar()
        self.s_meter.setRange(-100, 0)
        self.s_meter.setValue(-100)
        self.s_meter.setFormat(" S-Meter: %v dBm ")
        self.s_meter.setFixedHeight(20)
        main_content_layout.addWidget(self.s_meter)

        # 无边框绘图区
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        pg.setConfigOption('background', '#000000')
        pg.setConfigOption('foreground', '#666666')
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.hideAxis('left')
        self.plot_widget.hideAxis('bottom')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setYRange(-100, 10)
        self.plot_widget.setMenuEnabled(False)

        pen_red_line = pg.mkPen(color='#FF1744', width=2)
        self.center_line = pg.InfiniteLine(angle=90, movable=False, pen=pen_red_line)
        self.plot_widget.addItem(self.center_line)

        pen_null = pg.mkPen(color=(0,0,0,0)) 
        brush_shadow = pg.mkBrush(color=(0, 255, 204, 50)) 
        self.filter_region = pg.LinearRegionItem([0, 0], pg.LinearRegionItem.Vertical, movable=False, pen=pen_null, brush=brush_shadow)
        self.plot_widget.addItem(self.filter_region)

        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='#FFD700', width=2.5))
        self.splitter.addWidget(self.plot_widget)

        self.waterfall_widget = pg.PlotWidget()
        self.waterfall_widget.hideAxis('left')
        self.waterfall_widget.hideAxis('bottom')
        self.waterfall_widget.setMouseEnabled(x=False, y=False)
        self.waterfall_widget.setMenuEnabled(False)
        
        self.waterfall_image = pg.ImageItem()
        self.waterfall_widget.addItem(self.waterfall_image)
        
        colormap = pg.colormap.get('viridis')
        self.waterfall_image.setLookupTable(colormap.getLookupTable())
        self.waterfall_image.setLevels([-100, 0]) 
        
        self.splitter.addWidget(self.waterfall_widget)
        self.splitter.setSizes([300, 300]) # 因为全宽了，图表可以更大
        
        main_content_layout.addWidget(self.splitter)
        root_layout.addLayout(main_content_layout)