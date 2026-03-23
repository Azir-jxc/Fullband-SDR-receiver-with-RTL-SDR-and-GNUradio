# ui_layout.py
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
from config import *

class DemodConfigDialog(QtWidgets.QDialog):
    """解调、滤波器与音量 (audio_value) 配置弹窗"""
    def __init__(self, parent=None, cur_mode="WFM", cur_low=-75000, cur_high=75000, cur_squelch=-70, cur_audio_value=0.4):
        super().__init__(parent)
        self.setWindowTitle("解调与接收配置")
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)

        # --- 1. 解调模式 ---
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("解调模式:"))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(list(DEMOD_MODES.keys()))
        self.mode_combo.setCurrentText(cur_mode)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)

        # --- 2. 滤波器带宽配置 ---
        filter_box = QtWidgets.QGroupBox("滤波器带宽 (Hz)")
        filter_layout = QtWidgets.QGridLayout(filter_box)
        
        filter_layout.addWidget(QtWidgets.QLabel("下限频率:"), 0, 0)
        self.low_spin = QtWidgets.QSpinBox()
        self.low_spin.setRange(-500000, 500000)
        self.low_spin.setSingleStep(100)
        self.low_spin.setValue(int(cur_low))
        filter_layout.addWidget(self.low_spin, 0, 1)

        filter_layout.addWidget(QtWidgets.QLabel("上限频率:"), 1, 0)
        self.high_spin = QtWidgets.QSpinBox()
        self.high_spin.setRange(-500000, 500000)
        self.high_spin.setSingleStep(100)
        self.high_spin.setValue(int(cur_high))
        filter_layout.addWidget(self.high_spin, 1, 1)
        layout.addWidget(filter_box)

        # --- 3. 后置 AGC 与 静噪配置 ---
        agc_box = QtWidgets.QGroupBox("音频与静噪")
        agc_layout = QtWidgets.QGridLayout(agc_box)
        
        agc_layout.addWidget(QtWidgets.QLabel("静噪门限 (dB):"), 0, 0)
        self.squelch_spin = QtWidgets.QSpinBox()
        self.squelch_spin.setRange(-150, 0)
        self.squelch_spin.setValue(int(cur_squelch))
        agc_layout.addWidget(self.squelch_spin, 0, 1)

        # 音量/AGC 滑块 (0 = 0.0, 1-8 = 0.1-0.8)
        agc_layout.addWidget(QtWidgets.QLabel("音量 (audio_value):"), 1, 0)
        self.audio_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.audio_slider.setRange(0, 8)
        
        # 初始化滑块位置
        init_val = 0 if cur_audio_value == 0 else int(cur_audio_value * 10)
        self.audio_slider.setValue(init_val)
        
        self.audio_label = QtWidgets.QLabel(f"{cur_audio_value:.1f}")
        self.audio_label.setMinimumWidth(30)
        self.audio_slider.valueChanged.connect(self.on_audio_slide)
        
        agc_layout.addWidget(self.audio_slider, 1, 1)
        agc_layout.addWidget(self.audio_label, 1, 2)
        layout.addWidget(agc_box)

        # --- 4. 底部按钮 ---
        btn_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用配置")
        self.apply_btn.setStyleSheet("background-color: #0078D7; color: white; font-weight: bold; padding: 5px;")
        self.close_btn = QtWidgets.QPushButton("关闭")
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        # 联动：切换模式时，自动填入 config.py 中的默认带宽
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
    """独立的弹窗配置窗口"""
    def __init__(self, parent=None, cur_rf=20, cur_if=20, cur_bb=20, cur_sr="2.4", cur_mode="正交采样 (Quadrature)"):
        super().__init__(parent)
        self.setWindowTitle("前端参数配置")
        self.setMinimumWidth(350)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool) 
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)

        sr_layout = QtWidgets.QHBoxLayout()
        sr_layout.addWidget(QtWidgets.QLabel("采样率 (MHz):"))
        self.sr_combo = QtWidgets.QComboBox()
        self.sr_combo.addItems(["1.024", "1.28", "2.048", "2.4", "2.56", "2.8", "3.2"])
        self.sr_combo.setCurrentText(cur_sr)
        sr_layout.addWidget(self.sr_combo)
        layout.addLayout(sr_layout)

        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("采样模式:"))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["正交采样 (Quadrature)", "I 通道直采 (Direct I)", "Q 通道直采 (Direct Q)"])
        self.mode_combo.setCurrentText(cur_mode)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)

        self.rf_slider, self.rf_label = self.create_slider("RF 增益", cur_rf, layout)
        self.if_slider, self.if_label = self.create_slider("IF 增益", cur_if, layout)
        self.bb_slider, self.bb_label = self.create_slider("BB 增益", cur_bb, layout)

        btn_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用重启")
        self.apply_btn.setStyleSheet("background-color: #0078D7; color: white; font-weight: bold; padding: 5px;")
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
        window.setWindowTitle("SDR 触摸屏接收机 UI")
        window.resize(800, 480)

        main_widget = QtWidgets.QWidget()
        window.setCentralWidget(main_widget)
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

        freq_layout.addWidget(self.freq_label)
        freq_layout.addWidget(self.freq_input)
        freq_layout.addWidget(self.set_freq_btn)
        freq_layout.addStretch()

        # --- 第二行：控制按键 ---
        ctrl_layout = QtWidgets.QHBoxLayout()
        ctrl_layout.setSpacing(15)

        self.avg_cycle_btn = QtWidgets.QPushButton() 
        self.avg_cycle_btn.setMinimumSize(120, 40)
        ctrl_layout.addWidget(self.avg_cycle_btn)

        self.tuning_mode_btn = QtWidgets.QPushButton("模式: 中央调谐")
        self.tuning_mode_btn.setMinimumSize(120, 40)
        ctrl_layout.addWidget(self.tuning_mode_btn)

        self.config_btn = QtWidgets.QPushButton("前端 ⚙️")
        self.config_btn.setMinimumSize(80, 40)
        ctrl_layout.addWidget(self.config_btn)
        
        self.demod_config_btn = QtWidgets.QPushButton("解调 🎛️")
        self.demod_config_btn.setMinimumSize(80, 40)
        ctrl_layout.addWidget(self.demod_config_btn)

        ctrl_layout.addStretch() 

        dial_label = QtWidgets.QLabel("Freq")
        dial_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        ctrl_layout.addWidget(dial_label)

        self.freq_dial = QtWidgets.QDial()
        self.freq_dial.setRange(0, 359) 
        self.freq_dial.setWrapping(True) 
        self.freq_dial.setNotchesVisible(True) 
        self.freq_dial.setFixedSize(60, 60) 
        ctrl_layout.addWidget(self.freq_dial)

        layout.addLayout(freq_layout)
        layout.addLayout(ctrl_layout)

        # --- 绘图区 ---
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        layout.addWidget(self.splitter)

        # 1. 频谱图
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setTitle("实时 FFT 功率谱", color='#333333', size='12pt')
        self.plot_widget.setLabel('left', 'Power', units='dB')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setYRange(-100, 10)
        self.plot_widget.setMenuEnabled(False)

        pen_red_line = pg.mkPen(color='#FF1744', width=1.5)
        self.center_line = pg.InfiniteLine(angle=90, movable=False, pen=pen_red_line)
        self.plot_widget.addItem(self.center_line)

        pen_null = pg.mkPen(color=(0,0,0,0)) 
        brush_shadow = pg.mkBrush(color=(255, 23, 68, 40)) 
        self.filter_region = pg.LinearRegionItem([0, 0], pg.LinearRegionItem.Vertical, movable=False, pen=pen_null, brush=brush_shadow)
        self.plot_widget.addItem(self.filter_region)

        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='#0078D7', width=2))
        self.splitter.addWidget(self.plot_widget)

        # 2. 瀑布图
        self.waterfall_widget = pg.PlotWidget()
        self.waterfall_widget.setLabel('bottom', 'Absolute Frequency', units='MHz')
        self.waterfall_widget.setLabel('left', 'Time')
        self.waterfall_widget.setMouseEnabled(x=False, y=False)
        self.waterfall_widget.setMenuEnabled(False)
        
        self.waterfall_image = pg.ImageItem()
        self.waterfall_widget.addItem(self.waterfall_image)
        
        colormap = pg.colormap.get('viridis')
        self.waterfall_image.setLookupTable(colormap.getLookupTable())
        self.waterfall_image.setLevels([-100, 0]) 
        
        self.splitter.addWidget(self.waterfall_widget)
        self.splitter.setSizes([200, 200])