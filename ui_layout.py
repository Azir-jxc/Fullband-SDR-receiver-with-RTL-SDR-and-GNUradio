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
/* 巨型数字频率管 */
QLabel#FreqLabel { 
    color: #00FFCC; 
    font-size: 54px; 
    font-weight: bold; 
    font-family: "Consolas", monospace; 
    background-color: #000000; 
    border: 2px solid #333333; 
    border-radius: 8px; 
    padding: 0px 15px;
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
/* 频率输入框 */
QLineEdit { 
    background-color: #1E1E1E; 
    border: 2px solid #404040; 
    color: #00FFCC; 
    font-size: 20px; 
    font-weight: bold;
    border-radius: 6px; 
    padding: 5px;
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

class DemodConfigDialog(QtWidgets.QDialog):
    """解调、滤波器与音量配置弹窗"""
    def __init__(self, parent=None, cur_mode="WFM", cur_low=-75000, cur_high=75000, cur_squelch=-70, cur_audio_value=0.4):
        super().__init__(parent)
        self.setWindowTitle("解调与接收配置")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self.setStyleSheet(DARK_STYLE) # 弹窗也应用暗黑风格

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
    """前端硬件配置弹窗"""
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
        window.setStyleSheet(DARK_STYLE) # 注入全局灵魂暗黑样式

        main_widget = QtWidgets.QWidget()
        window.setCentralWidget(main_widget)
        
        # 整体采用左右分栏的水平布局
        main_layout = QtWidgets.QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # ================= 左侧：数据可视化区 (占大头) =================
        left_panel = QtWidgets.QVBoxLayout()
        
        # 1. 顶部频率与仪表盘
        top_dash_layout = QtWidgets.QHBoxLayout()
        
        # 巨型数字显示
        self.freq_label = QtWidgets.QLabel("---.--- MHz")
        self.freq_label.setObjectName("FreqLabel")
        self.freq_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        top_dash_layout.addWidget(self.freq_label, stretch=3)
        
        # 右侧的快捷输入区
        input_layout = QtWidgets.QVBoxLayout()
        self.freq_input = QtWidgets.QLineEdit()
        self.freq_input.setPlaceholderText("Direct Input (MHz)")
        self.set_freq_btn = QtWidgets.QPushButton("SET FREQ")
        self.set_freq_btn.setStyleSheet("padding: 5px;")
        input_layout.addWidget(self.freq_input)
        input_layout.addWidget(self.set_freq_btn)
        top_dash_layout.addLayout(input_layout, stretch=1)
        
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
        
        # 频谱图 (黑底黄线，去掉坐标轴留白)
        pg.setConfigOption('background', '#000000')
        pg.setConfigOption('foreground', '#666666')
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.hideAxis('left')   # 隐藏 Y 轴
        self.plot_widget.hideAxis('bottom') # 隐藏 X 轴
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setYRange(-100, 10)
        self.plot_widget.setMenuEnabled(False)

        # 红色瞄准线
        pen_red_line = pg.mkPen(color='#FF1744', width=2)
        self.center_line = pg.InfiniteLine(angle=90, movable=False, pen=pen_red_line)
        self.plot_widget.addItem(self.center_line)

        # 滤波器阴影
        pen_null = pg.mkPen(color=(0,0,0,0)) 
        brush_shadow = pg.mkBrush(color=(0, 255, 204, 50)) # 青色阴影
        self.filter_region = pg.LinearRegionItem([0, 0], pg.LinearRegionItem.Vertical, movable=False, pen=pen_null, brush=brush_shadow)
        self.plot_widget.addItem(self.filter_region)

        # 发光质感的黄/青色曲线
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='#FFD700', width=2.5))
        self.splitter.addWidget(self.plot_widget)

        # 瀑布图 (彻底贴边)
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
        
        # ================= 右侧：大块状控制台 =================
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.setSpacing(10)
        
        # 顶部状态标签
        panel_label = QtWidgets.QLabel("CONTROL DESK")
        panel_label.setAlignment(QtCore.Qt.AlignCenter)
        panel_label.setStyleSheet("color: #666; font-weight: bold; letter-spacing: 2px;")
        right_panel.addWidget(panel_label)

        # 块状功能大按钮
        self.demod_config_btn = QtWidgets.QPushButton("DEMOD / AUDIO\n解调与音量")
        self.demod_config_btn.setStyleSheet("background-color: #005A9E;") # 给点主色调
        right_panel.addWidget(self.demod_config_btn)
        
        self.config_btn = QtWidgets.QPushButton("RF FRONTEND\n射频前端")
        right_panel.addWidget(self.config_btn)

        self.tuning_mode_btn = QtWidgets.QPushButton("TUNE MODE\n中央调谐")
        right_panel.addWidget(self.tuning_mode_btn)

        self.avg_cycle_btn = QtWidgets.QPushButton("FFT AVG\n平滑: 1")
        right_panel.addWidget(self.avg_cycle_btn)

        right_panel.addStretch()

        # 双旋钮区
        dials_layout = QtWidgets.QHBoxLayout()
        
        coarse_layout = QtWidgets.QVBoxLayout()
        self.coarse_dial = QtWidgets.QDial()
        self.coarse_dial.setRange(0, 359)
        self.coarse_dial.setWrapping(True)
        self.coarse_dial.setNotchesVisible(True)
        self.coarse_dial.setFixedSize(80, 80)
        coarse_label = QtWidgets.QLabel("COARSE\n(100kHz)")
        coarse_label.setAlignment(QtCore.Qt.AlignCenter)
        coarse_label.setStyleSheet("font-size: 12px; color: #888;")
        coarse_layout.addWidget(self.coarse_dial, alignment=QtCore.Qt.AlignCenter)
        coarse_layout.addWidget(coarse_label)
        
        fine_layout = QtWidgets.QVBoxLayout()
        self.fine_dial = QtWidgets.QDial()
        self.fine_dial.setRange(0, 359)
        self.fine_dial.setWrapping(True)
        self.fine_dial.setNotchesVisible(True)
        self.fine_dial.setFixedSize(80, 80)
        fine_label = QtWidgets.QLabel("FINE\n(5kHz)")
        fine_label.setAlignment(QtCore.Qt.AlignCenter)
        fine_label.setStyleSheet("font-size: 12px; color: #888;")
        fine_layout.addWidget(self.fine_dial, alignment=QtCore.Qt.AlignCenter)
        fine_layout.addWidget(fine_label)

        dials_layout.addLayout(coarse_layout)
        dials_layout.addLayout(fine_layout)
        right_panel.addLayout(dials_layout)

        # 将左右面板加入主布局，设定比例 7:3
        main_layout.addLayout(left_panel, stretch=7)
        main_layout.addLayout(right_panel, stretch=3)