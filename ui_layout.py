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
/* 频率容器专门样式，严格限制只渲染外框，防止子控件(数字)继承边框 */
QWidget#FreqContainer {
    background-color: #000000; 
    border: 2px solid #333333; 
    border-radius: 8px; 
}
/* 触屏块状大按钮 */
QPushButton { 
    background-color: #2D2D2D; 
    border: 2px solid #404040; 
    border-radius: 8px; 
    color: #E0E0E0; 
    font-size: 16px; 
    font-weight: bold; 
    padding: 15px 5px; 
}
QPushButton:pressed { 
    background-color: #00FFCC; 
    color: #000000; 
}
/* S-Meter 信号条 */
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
/* 弹窗内部组件 */
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
    """独立的数字位，捕捉点击高亮和左右拖拽"""
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
        # 强制 border: none，切断继承，并保证数字连续性
        base_style = "font-size: 56px; font-weight: bold; font-family: 'Consolas', monospace; border: none;"
        if selected:
            # 选中时加上圆角，显得像光标卡在数字上
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
    """封装完整的交互式频率面板"""
    sig_step_requested = QtCore.pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.freq_hz = 0
        
        # 绑定 QSS 中的专用 ID，并开启背景渲染
        self.setObjectName("FreqContainer")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(0) # 将间距设为0，让数字紧贴，呈现整体感
        
        self.digits = []
        
        # 频率前面 4 位 (百兆、十兆、兆)
        self.add_digit(layout, 1000000000) # 1G
        self.add_digit(layout, 100000000)  # 100M
        self.add_digit(layout, 10000000)   # 10M
        self.add_digit(layout, 1000000)    # 1M
        
        # 小数点 (精准对齐底部并缩小宽度)
        dot = QtWidgets.QLabel(".")
        dot.setStyleSheet("color: #00FFCC; font-size: 56px; font-weight: bold; font-family: 'Consolas', monospace; border: none; background: transparent;")
        dot.setAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignCenter)
        dot.setFixedSize(20, 70) # 把小数点框压窄，防止隔开数字
        layout.addWidget(dot)
        
        # 频率后面 3 位 (百K、十K、单K)
        self.add_digit(layout, 100000)     # 100k
        self.add_digit(layout, 10000)      # 10k
        self.add_digit(layout, 1000)       # 1k
        
        # 单位 MHz (利用 padding-bottom 把它稍微垫高，和数字的基线平齐)
        unit = QtWidgets.QLabel(" MHz")
        unit.setStyleSheet("color: #00FFCC; font-size: 26px; font-weight: bold; border: none; background: transparent; padding-bottom: 12px;")
        unit.setAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft)
        unit.setFixedHeight(70)
        layout.addWidget(unit)
        
        # 默认选中 100kHz 位
        self.on_digit_selected(100000)

    def add_digit(self, layout, step_hz):
        lbl = DigitLabel(step_hz)
        lbl.setFixedSize(38, 70) # 固定每个数字位的大小，保持等宽字体对齐
        lbl.sig_selected.connect(self.on_digit_selected)
        lbl.sig_stepped.connect(lambda direction, step=step_hz: self.sig_step_requested.emit(direction * step))
        self.digits.append(lbl)
        layout.addWidget(lbl)

    def on_digit_selected(self, step_hz):
        for d in self.digits:
            d.set_selected(d.step_hz == step_hz)

    def set_freq(self, hz):
        self.freq_hz = hz
        val = int(round(hz / 1000)) # 提取到 kHz
        s = f"{val:07d}" 
        if len(s) > 7: s = s[-7:] 
        
        for i, char in enumerate(s):
            if i < len(self.digits):
                self.digits[i].setText(char)

# ================= 此行以下的代码（包括弹窗和 Ui_MainWindow）完全保持原样 =================
# ... (保留你之前的 DemodConfigDialog, ConfigDialog 和 Ui_MainWindow 代码)
# ==========================================================

class DemodConfigDialog(QtWidgets.QDialog):
    # (此弹窗代码与上个版本完全一致，为了节省篇幅保持原样)
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
    # (此弹窗代码与上个版本完全一致)
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
    def setup_ui(self, window):
        window.setWindowTitle("Malachite-Style SDR")
        window.resize(1024, 600)
        window.setStyleSheet(DARK_STYLE) 

        main_widget = QtWidgets.QWidget()
        window.setCentralWidget(main_widget)
        
        main_layout = QtWidgets.QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # ================= 左侧：数据可视化区 =================
        left_panel = QtWidgets.QVBoxLayout()
        
        # 1. 交互式数字荧光屏
        top_dash_layout = QtWidgets.QHBoxLayout()
        self.freq_display = InteractiveFreqDisplay()
        top_dash_layout.addWidget(self.freq_display)
        top_dash_layout.addStretch() # 把频率条往左推
        left_panel.addLayout(top_dash_layout)

        # 2. S-Meter (信号强度指示条)
        self.s_meter = QtWidgets.QProgressBar()
        self.s_meter.setRange(-100, 0)
        self.s_meter.setValue(-100)
        self.s_meter.setFormat(" S-Meter: %v dBm ")
        self.s_meter.setFixedHeight(20)
        left_panel.addWidget(self.s_meter)

        # 3. 无边框绘图区
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
        self.splitter.setSizes([250, 250])
        left_panel.addWidget(self.splitter)
        
        # ================= 右侧：大块状控制台 (移除旋钮) =================
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.setSpacing(15)
        
        panel_label = QtWidgets.QLabel("CONTROL DESK")
        panel_label.setAlignment(QtCore.Qt.AlignCenter)
        panel_label.setStyleSheet("color: #666; font-weight: bold; letter-spacing: 2px;")
        right_panel.addWidget(panel_label)

        self.demod_config_btn = QtWidgets.QPushButton("DEMOD / AUDIO\n解调与音量")
        self.demod_config_btn.setStyleSheet("background-color: #005A9E;") 
        right_panel.addWidget(self.demod_config_btn)
        
        self.config_btn = QtWidgets.QPushButton("RF FRONTEND\n射频前端")
        right_panel.addWidget(self.config_btn)

        self.tuning_mode_btn = QtWidgets.QPushButton("TUNE MODE\n中央调谐")
        right_panel.addWidget(self.tuning_mode_btn)

        self.avg_cycle_btn = QtWidgets.QPushButton("FFT AVG\n平滑: 1")
        right_panel.addWidget(self.avg_cycle_btn)

        right_panel.addStretch() # 自动填补下方空白区域

        main_layout.addLayout(left_panel, stretch=7)
        main_layout.addLayout(right_panel, stretch=2)