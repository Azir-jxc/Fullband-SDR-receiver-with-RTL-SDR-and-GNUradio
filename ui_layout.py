# ui_layout.py
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import numpy as np
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
    background-color: #FFFF00; 
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

# ================= 悬浮音量滑块组件 =================
class VolumePopup(QtWidgets.QWidget):
    sig_vol_changed = QtCore.pyqtSignal(float)

    def __init__(self, parent=None, init_val=0.4):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(50, 160)
        
        self.container = QtWidgets.QFrame(self)
        self.container.setGeometry(0, 0, 50, 160)
        self.container.setStyleSheet("QFrame { background-color: rgba(20,20,20,230); border: 1px solid #555; border-radius: 8px; }")
        
        layout = QtWidgets.QVBoxLayout(self.container)
        layout.setContentsMargins(5, 15, 5, 15)
        
        self.slider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        self.slider.setRange(0, 8)
        self.slider.setValue(int(init_val * 10))
        
        self.slider.setStyleSheet("""
            QSlider::groove:vertical { background: #444; width: 6px; border-radius: 3px; }
            QSlider::handle:vertical { background: #FFFF00; height: 16px; margin: 0 -6px; border-radius: 8px; }
            QSlider::add-page:vertical { background: #FFFF00; width: 6px; border-radius: 3px; } 
            QSlider::sub-page:vertical { background: #444; width: 6px; border-radius: 3px; }    
        """)
        self.slider.valueChanged.connect(self.on_slide)
        layout.addWidget(self.slider, alignment=QtCore.Qt.AlignHCenter)

    def on_slide(self, val):
        real_val = 0.0 if val == 0 else val / 10.0
        self.sig_vol_changed.emit(real_val)

# ================= 自定义交互式频率管组件 =================
class DigitLabel(QtWidgets.QLabel):
    sig_stepped = QtCore.pyqtSignal(int)
    sig_selected = QtCore.pyqtSignal(int)
    sig_double_clicked = QtCore.pyqtSignal()

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
            self.setStyleSheet(f"{base_style} color: #000000; background-color: #FFFF00; border-radius: 6px;")
        else:
            self.setStyleSheet(f"{base_style} color: #FFFF00; background-color: transparent;")

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
            
    def mouseDoubleClickEvent(self, event):
        self.sig_double_clicked.emit()
        super().mouseDoubleClickEvent(event)

class InteractiveFreqDisplay(QtWidgets.QWidget):
    sig_step_requested = QtCore.pyqtSignal(float)
    sig_double_clicked = QtCore.pyqtSignal()

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
        dot.setStyleSheet("color: #FFFF00; font-size: 56px; font-weight: bold; font-family: 'Consolas', monospace; border: none; background: transparent;")
        dot.setAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignCenter)
        dot.setFixedSize(20, 70) 
        layout.addWidget(dot)
        
        self.add_digit(layout, 100000)     
        self.add_digit(layout, 10000)      
        self.add_digit(layout, 1000)       
        
        unit = QtWidgets.QLabel(" MHz")
        unit.setStyleSheet("color: #FFFF00; font-size: 26px; font-weight: bold; border: none; background: transparent; padding-bottom: 12px;")
        unit.setAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft)
        unit.setFixedHeight(70)
        layout.addWidget(unit)
        self.on_digit_selected(100000)

    def add_digit(self, layout, step_hz):
        lbl = DigitLabel(step_hz)
        lbl.setFixedSize(38, 70) 
        lbl.sig_selected.connect(self.on_digit_selected)
        lbl.sig_stepped.connect(lambda direction, step=step_hz: self.sig_step_requested.emit(direction * step))
        lbl.sig_double_clicked.connect(self.sig_double_clicked.emit)
        self.digits.append(lbl)
        layout.addWidget(lbl)

    def mouseDoubleClickEvent(self, event):
        self.sig_double_clicked.emit()
        super().mouseDoubleClickEvent(event)

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

class SpectrumConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, cur_tune="CENTRAL", cur_avg="1", grid_on=True):
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

        grid_layout = QtWidgets.QHBoxLayout()
        grid_layout.addWidget(QtWidgets.QLabel("背景网格:"))
        self.grid_combo = QtWidgets.QComboBox()
        self.grid_combo.addItems(["开启 (ON)", "关闭 (OFF)"])
        self.grid_combo.setCurrentIndex(0 if grid_on else 1)
        self.grid_combo.setMinimumHeight(35)
        grid_layout.addWidget(self.grid_combo)
        layout.addLayout(grid_layout)

        btn_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用")
        self.apply_btn.setStyleSheet("background-color: #0078D7; color: white;")
        self.close_btn = QtWidgets.QPushButton("关闭")
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

class DemodConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, cur_mode="WFM", cur_low=-75000, cur_high=75000, cur_squelch=-70):
        super().__init__(parent)
        self.setWindowTitle("解调与接收配置")
        self.setMinimumWidth(350)
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
        
        agc_box = QtWidgets.QGroupBox("静噪门限")
        agc_layout = QtWidgets.QGridLayout(agc_box)
        agc_layout.addWidget(QtWidgets.QLabel("静噪 (dB):"), 0, 0)
        self.squelch_spin = QtWidgets.QSpinBox()
        self.squelch_spin.setRange(-150, 0)
        self.squelch_spin.setValue(int(cur_squelch))
        agc_layout.addWidget(self.squelch_spin, 0, 1)
        layout.addWidget(agc_box)
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用配置")
        self.apply_btn.setStyleSheet("background-color: #0078D7; color: white;")
        self.close_btn = QtWidgets.QPushButton("关闭")
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        self.mode_combo.currentIndexChanged.connect(self.auto_update_filter_bounds)

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

class NumpadDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, current_mhz=""):
        super().__init__(parent)
        self.setWindowTitle("输入频率 (MHz)")
        self.setFixedSize(300, 380)
        self.setStyleSheet(DARK_STYLE)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)

        layout = QtWidgets.QVBoxLayout(self)

        self.display = QtWidgets.QLineEdit(str(current_mhz))
        self.display.setReadOnly(True)
        self.display.setAlignment(QtCore.Qt.AlignRight)
        self.display.setStyleSheet("font-size: 28px; font-weight: bold; padding: 10px; background: #111; border: 1px solid #555; color: #00FFCC; font-family: 'Consolas';")
        layout.addWidget(self.display)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        
        buttons = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('.', 3, 0), ('0', 3, 1), ('删除', 3, 2),
            ('取消', 4, 0), ('确认', 4, 1, 1, 2)
        ]

        for btn_info in buttons:
            text = btn_info[0]
            row = btn_info[1]
            col = btn_info[2]
            
            btn = QtWidgets.QPushButton(text)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            btn.setStyleSheet("font-size: 20px; font-weight: bold;")
            btn.clicked.connect(lambda checked, t=text: self.on_button_clicked(t))
            
            if len(btn_info) == 5:
                grid.addWidget(btn, row, col, btn_info[3], btn_info[4])
            else:
                grid.addWidget(btn, row, col)

        layout.addLayout(grid)
        layout.setStretchFactor(grid, 1)

    def on_button_clicked(self, text):
        current = self.display.text()
        if text == '取消':
            self.reject()
        elif text == '确认':
            if current:
                self.accept()
        elif text == '删除':
            self.display.setText(current[:-1])
        elif text == '.':
            if '.' not in current:
                self.display.setText(current + '.')
        else:
            self.display.setText(current + text)

    def get_value(self):
        try:
            return float(self.display.text())
        except ValueError:
            return 0.0

class Ui_MainWindow:
    def create_status_badge(self, text, color="#00FFCC"):
        lbl = QtWidgets.QLabel(text)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setStyleSheet(f"background-color: #111111; color: {color}; border: 1px solid {color}; border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: bold; font-family: 'Consolas', monospace;")
        return lbl

    def setup_ui(self, window):
        window.setWindowTitle("Malachite-Style SDR")
        window.resize(1024, 600) # 调回标准窗口高度
        window.setStyleSheet(DARK_STYLE) 

        main_widget = QtWidgets.QWidget()
        window.setCentralWidget(main_widget)
        
        root_layout = QtWidgets.QVBoxLayout(main_widget)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # ================= 1. 顶栏 =================
        top_bar_layout = QtWidgets.QHBoxLayout()
        top_bar_layout.setSpacing(15)
        
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
        top_bar_layout.addStretch() 
        
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

        # ================= 2. 频率管、音频频谱与音量 =================
        main_content_layout = QtWidgets.QVBoxLayout()
        
        freq_layout = QtWidgets.QHBoxLayout()
        self.freq_display = InteractiveFreqDisplay()
        freq_layout.addWidget(self.freq_display)
        
        # --- 新增：将音频频谱放在这里（替代原本的 stretch 空白区） ---
        self.audio_container = QtWidgets.QWidget()
        self.audio_container.setFixedHeight(95) # 设定合适高度匹配左侧频率管
        audio_layout = QtWidgets.QVBoxLayout(self.audio_container)
        audio_layout.setContentsMargins(15, 0, 15, 0) # 左右稍微留出边距
        audio_layout.setSpacing(2)
        
        lbl_audio_title = QtWidgets.QLabel(" 音频频谱 ")
        lbl_audio_title.setStyleSheet("color: #8BC34A; background: transparent; font-weight: bold; font-family: 'Consolas'; font-size: 10px; padding: 0px;")
        audio_layout.addWidget(lbl_audio_title)

        self.audio_plot_widget = pg.PlotWidget()
        self.audio_plot_widget.setMenuEnabled(False)
        self.audio_plot_widget.setMouseEnabled(x=False, y=False)
        self.audio_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        small_font = QtGui.QFont('Consolas', 8)
        audio_axis_bottom = self.audio_plot_widget.getAxis('bottom')
        audio_axis_bottom.setTickFont(small_font)
        audio_axis_bottom.setTextPen('#888888')
        audio_axis_bottom.setPen('#555555')
        audio_axis_bottom.setHeight(18) # 减少底部坐标轴占用的高度
        
        audio_axis_left = self.audio_plot_widget.getAxis('left')
        audio_axis_left.setTickFont(small_font)
        audio_axis_left.setTextPen('#888888')
        audio_axis_left.setPen('#555555')
        audio_axis_left.setWidth(25)

        self.audio_plot_widget.setYRange(-100, 0, padding=0)
        self.audio_plot_widget.setXRange(0, 5, padding=0) 
        
        self.audio_curve = self.audio_plot_widget.plot(pen=pg.mkPen(color='#8BC34A', width=1.5))
        audio_layout.addWidget(self.audio_plot_widget)
        
        # 将音频频谱区域添加到顶栏，并让其自动填满剩余空间
        freq_layout.addWidget(self.audio_container, stretch=1) 

        self.vol_btn = QtWidgets.QPushButton("音量")
        self.vol_btn.setFixedSize(65, 36) 
        self.vol_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.vol_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #555;
                border-radius: 6px;
                font-family: 'Microsoft YaHei', sans-serif;
                font-size: 15px;
                font-weight: bold;
                margin-right: 10px;
            }
            QPushButton:hover { color: #FFFF00; border: 1px solid #FFFF00; }
            QPushButton:pressed { background-color: #FFFF00; color: #000000; }
        """)
        freq_layout.addWidget(self.vol_btn, alignment=QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
        
        main_content_layout.addLayout(freq_layout)

        self.s_meter = QtWidgets.QProgressBar()
        self.s_meter.setRange(-100, 0)
        self.s_meter.setValue(-100)
        self.s_meter.setFormat(" S-Meter: %v dBm ")
        self.s_meter.setFixedHeight(20)
        main_content_layout.addWidget(self.s_meter)

        # ================= 3. 数据视图区 =================
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        pg.setConfigOption('background', '#000000')
        pg.setConfigOption('foreground', '#666666')
        
        # --- A. 频谱图区 ---
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.hideAxis('left')
        self.plot_widget.hideAxis('bottom')
        self.plot_widget.showAxis('right')
        
        spec_right_axis = self.plot_widget.getAxis('right')
        spec_right_axis.setTickSpacing(20, 10) 
        spec_right_axis.setWidth(28) 
        spec_right_axis.setStyle(tickTextOffset=1)
        spec_right_axis.setTickFont(small_font)
        spec_right_axis.setTextPen('#888888')
        spec_right_axis.setPen('#555555')
        
        self.plot_widget.setYRange(-100, -30, padding=0)
        self.plot_widget.setMenuEnabled(False)

        pen_red_line = pg.mkPen(color='#FF1744', width=2)
        self.center_line = pg.InfiniteLine(angle=90, movable=False, pen=pen_red_line)
        self.plot_widget.addItem(self.center_line)

        pen_null = pg.mkPen(color=(0,0,0,0)) 
        brush_shadow = pg.mkBrush(color=(0, 255, 204, 50)) 
        self.filter_region = pg.LinearRegionItem([0, 0], pg.LinearRegionItem.Vertical, movable=False, pen=pen_null, brush=brush_shadow)
        self.plot_widget.addItem(self.filter_region)

        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='#FFD700', width=2.5))
        
        self.plot_container = QtWidgets.QWidget()
        overlay_layout = QtWidgets.QGridLayout(self.plot_container)
        overlay_layout.setContentsMargins(0, 0, 0, 0) 
        overlay_layout.addWidget(self.plot_widget, 0, 0, 3, 3) 
        
        osd_style_left = "color: rgba(255, 255, 255, 140); font-family: 'Consolas', monospace; font-size: 13px; font-weight: bold; background: transparent; padding: 5px;"
        osd_style_right = "color: rgba(255, 255, 255, 140); font-family: 'Consolas', monospace; font-size: 13px; font-weight: bold; background: transparent; padding: 5px; padding-right: 35px;"
        
        self.lbl_scale = QtWidgets.QLabel("0.5 MHz / Div")
        self.lbl_scale.setStyleSheet(osd_style_right)
        self.lbl_left_freq = QtWidgets.QLabel("---.--- MHz")
        self.lbl_left_freq.setStyleSheet(osd_style_left)
        self.lbl_right_freq = QtWidgets.QLabel("---.--- MHz")
        self.lbl_right_freq.setStyleSheet(osd_style_right)

        overlay_layout.addWidget(self.lbl_scale, 0, 2, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)
        overlay_layout.addWidget(self.lbl_left_freq, 2, 0, QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft)
        overlay_layout.addWidget(self.lbl_right_freq, 2, 2, QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight)
        
        overlay_layout.setRowStretch(1, 1)
        overlay_layout.setColumnStretch(1, 1)
        self.splitter.addWidget(self.plot_container)

        # --- B. 瀑布图与独立色卡区 ---
        self.waterfall_container = QtWidgets.QWidget()
        wf_layout = QtWidgets.QHBoxLayout(self.waterfall_container)
        wf_layout.setContentsMargins(0, 0, 0, 0)
        wf_layout.setSpacing(0)
        
        self.waterfall_widget = pg.PlotWidget()
        self.waterfall_widget.hideAxis('left')
        self.waterfall_widget.hideAxis('bottom')
        self.waterfall_widget.setMouseEnabled(x=False, y=False)
        self.waterfall_widget.setMenuEnabled(False)
        self.waterfall_widget.setXLink(self.plot_widget) 
        
        pos = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
        colors = np.array([
            [0, 0, 20, 255],       
            [0, 0, 220, 255],      
            [0, 200, 200, 255],    
            [0, 210, 0, 255],      
            [255, 220, 0, 255],    
            [180, 0, 0, 255]       
        ], dtype=np.ubyte)
        sdr_cmap = pg.ColorMap(pos, colors)
        
        self.waterfall_image = pg.ImageItem()
        self.waterfall_widget.addItem(self.waterfall_image)
        self.waterfall_image.setLookupTable(sdr_cmap.getLookupTable())
        self.waterfall_image.setLevels([-100, -30]) 
        
        self.colorbar_widget = pg.PlotWidget()
        self.colorbar_widget.setFixedWidth(28) 
        self.colorbar_widget.hideAxis('left')
        self.colorbar_widget.hideAxis('bottom')
        self.colorbar_widget.showAxis('right')
        self.colorbar_widget.setMouseEnabled(x=False, y=False)
        self.colorbar_widget.setMenuEnabled(False)
        self.colorbar_widget.setYRange(-100, -30, padding=0)
        self.colorbar_widget.setXRange(0, 1, padding=0)
        
        cb_axis = self.colorbar_widget.getAxis('right')
        cb_axis.setTickSpacing(20, 10)
        cb_axis.setWidth(18) 
        cb_axis.setStyle(tickTextOffset=1)
        cb_axis.setTickFont(small_font)
        cb_axis.setTextPen('#888888')
        cb_axis.setPen('#555555')
        
        lut = sdr_cmap.getLookupTable()
        channels = lut.shape[1] 
        cb_data = np.zeros((1, lut.shape[0], channels), dtype=np.uint8)
        cb_data[0, :, :] = lut
        cb_image = pg.ImageItem()
        cb_image.setImage(cb_data)
        cb_image.setRect(QtCore.QRectF(0, -100, 1, 70))
        self.colorbar_widget.addItem(cb_image)
        
        wf_layout.addWidget(self.waterfall_widget)
        wf_layout.addWidget(self.colorbar_widget)
        self.splitter.addWidget(self.waterfall_container)

        # 恢复正常的二等分比例
        self.splitter.setSizes([150, 450]) 
        main_content_layout.addWidget(self.splitter)
        root_layout.addLayout(main_content_layout)