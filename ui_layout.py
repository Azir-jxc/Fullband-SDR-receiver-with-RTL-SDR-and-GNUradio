# ui_layout.py
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
from config import *

class Ui_MainWindow:
    def setup_ui(self, window):
        """将所有的 UI 控件组装到传入的 window (主窗口) 上"""
        window.setWindowTitle("SDR 触摸屏接收机 UI")
        window.resize(800, 480)

        main_widget = QtWidgets.QWidget()
        window.setCentralWidget(main_widget)
        layout = QtWidgets.QVBoxLayout(main_widget)

        # --- 第一行：绝对频率控制 ---
        freq_layout = QtWidgets.QHBoxLayout()
        freq_layout.setSpacing(15)
        
        # 统一使用 self.xxx，以便 main.py 中通过 self.ui.xxx 访问
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

        # --- 第二行：循环平均按键 + 模式选择 + 增益开关 + 调频旋钮 ---
        ctrl_layout = QtWidgets.QHBoxLayout()
        ctrl_layout.setSpacing(15)

        # 平均长度切换按钮
        self.avg_cycle_btn = QtWidgets.QPushButton() 
        self.avg_cycle_btn.setMinimumSize(120, 40)
        ctrl_layout.addWidget(self.avg_cycle_btn)

        # 解调模式选择下拉框
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(list(DEMOD_MODES.keys()))
        self.mode_combo.setMinimumSize(100, 40)
        ctrl_layout.addWidget(self.mode_combo)

        # ++ 新增：调谐模式切换按钮 ++
        self.tuning_mode_btn = QtWidgets.QPushButton("模式: 中央调谐")
        self.tuning_mode_btn.setMinimumSize(120, 40)
        ctrl_layout.addWidget(self.tuning_mode_btn)

      
        # 新增：增益控制展开按钮
        self.gain_toggle_btn = QtWidgets.QPushButton("增益设置 ▼")
        self.gain_toggle_btn.setMinimumSize(100, 40)
        self.gain_toggle_btn.setCheckable(True) # 设置为可按下的状态
        ctrl_layout.addWidget(self.gain_toggle_btn)

        ctrl_layout.addStretch() 

    

        # 调频旋钮
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

        # --- 新增：隐藏的增益控制面板 ---
        self.gain_panel = QtWidgets.QWidget()
        gain_layout = QtWidgets.QHBoxLayout(self.gain_panel)
        gain_layout.setContentsMargins(10, 0, 10, 10) # 紧凑的边距
        
        # 辅助函数：快速创建带标签的增益滑块
        def create_gain_slider(name):
            vbox = QtWidgets.QVBoxLayout()
            label = QtWidgets.QLabel(f"{name}: 20 dB")
            label.setAlignment(QtCore.Qt.AlignCenter)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 50)      # RTL-SDR 典型增益范围
            slider.setValue(20)         # 默认值
            slider.setMinimumHeight(40) # 增加高度方便触摸屏拖动
            
            vbox.addWidget(label)
            vbox.addWidget(slider)
            gain_layout.addLayout(vbox)
            return slider, label

        # 实例化三个增益滑块及标签
        self.rf_slider, self.rf_label = create_gain_slider("RF")
        self.if_slider, self.if_label = create_gain_slider("IF")
        self.bb_slider, self.bb_label = create_gain_slider("BB")
        
        self.gain_panel.setVisible(False) # 默认隐藏
        layout.addWidget(self.gain_panel) # 插入到控制栏和绘图区之间

        # --- 绘图区：使用 QSplitter 分割上下画面 ---
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        layout.addWidget(self.splitter)

        # 1. 频谱图 (上半部分)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setTitle("实时 FFT 功率谱", color='#333333', size='12pt')
        self.plot_widget.setLabel('left', 'Power', units='dB')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setYRange(-100, 10)
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.setMenuEnabled(False)

        # 滤波器通带的阴影指示区域 (先 add 到图层，使其在曲线下方)
        self.filter_region = pg.LinearRegionItem(values=[0, 0], movable=False, 
                                                 brush=pg.mkBrush(0, 120, 215, 40), 
                                                 pen=pg.mkPen(None))
        self.plot_widget.addItem(self.filter_region)

        # 频谱曲线
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='#0078D7', width=2))
        
        # 中心频率红线 (最后 add，使其在最上层，方便触摸拖动)
        self.center_line = pg.InfiniteLine(pos=0, movable=True, pen=pg.mkPen('#E81123', width=3))
        self.line_label = pg.InfLineLabel(self.center_line, text="Freq", position=0.85, color='#E81123', fill='#F5F5F5')
        self.plot_widget.addItem(self.center_line)
        
        self.splitter.addWidget(self.plot_widget)

        # 2. 瀑布图 (下半部分)
        self.waterfall_widget = pg.PlotWidget()
        self.waterfall_widget.setLabel('bottom', 'Absolute Frequency', units='MHz')
        self.waterfall_widget.setLabel('left', 'Time')
        self.waterfall_widget.setMouseEnabled(x=False, y=False)
        self.waterfall_widget.setMenuEnabled(False)
        
        self.waterfall_image = pg.ImageItem()
        self.waterfall_widget.addItem(self.waterfall_image)
        
        # 加载内置的伪彩映射 (Colormap)
        colormap = pg.colormap.get('viridis')
        self.waterfall_image.setLookupTable(colormap.getLookupTable())
        self.waterfall_image.setLevels([-100, 0]) 
        
        self.splitter.addWidget(self.waterfall_widget)
        
        # 初始高度比例 1:1
        self.splitter.setSizes([200, 200])