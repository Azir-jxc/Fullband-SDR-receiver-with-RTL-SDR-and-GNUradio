# ui_layout.py
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
from config import *

class ConfigDialog(QtWidgets.QDialog):
    """独立的弹窗配置窗口"""
    def __init__(self, parent=None, cur_rf=20, cur_if=20, cur_bb=20, cur_sr="2.4", cur_mode="正交采样 (Quadrature)"):
        super().__init__(parent)
        self.setWindowTitle("前端参数配置")
        self.setMinimumWidth(350)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool) # 设为工具窗口，浮动在上方
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)

        # --- 1. 采样率配置 ---
        sr_layout = QtWidgets.QHBoxLayout()
        sr_layout.addWidget(QtWidgets.QLabel("采样率 (MHz):"))
        self.sr_combo = QtWidgets.QComboBox()
        self.sr_combo.addItems(["1.024", "1.28", "2.048", "2.4", "2.56", "2.8", "3.2"])
        self.sr_combo.setCurrentText(cur_sr)
        sr_layout.addWidget(self.sr_combo)
        layout.addLayout(sr_layout)

        # --- 2. 采样模式配置 ---
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("采样模式:"))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["正交采样 (Quadrature)", "I 通道直采 (Direct I)", "Q 通道直采 (Direct Q)"])
        self.mode_combo.setCurrentText(cur_mode)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)

        # 分割线
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)

        # --- 3. 增益配置 ---
        self.rf_slider, self.rf_label = self.create_slider("RF 增益", cur_rf, layout)
        self.if_slider, self.if_label = self.create_slider("IF 增益", cur_if, layout)
        self.bb_slider, self.bb_label = self.create_slider("BB 增益", cur_bb, layout)

        # --- 4. 底部按钮 ---
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

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(list(DEMOD_MODES.keys()))
        self.mode_combo.setMinimumSize(100, 40)
        ctrl_layout.addWidget(self.mode_combo)

        self.tuning_mode_btn = QtWidgets.QPushButton("模式: 中央调谐")
        self.tuning_mode_btn.setMinimumSize(120, 40)
        ctrl_layout.addWidget(self.tuning_mode_btn)

        # 前端配置弹窗按钮
        self.config_btn = QtWidgets.QPushButton("前端配置 ⚙️")
        self.config_btn.setMinimumSize(100, 40)
        ctrl_layout.addWidget(self.config_btn)

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