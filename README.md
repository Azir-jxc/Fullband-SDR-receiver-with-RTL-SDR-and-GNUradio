# Fullband-SDR-receiver-with-RTL-SDR-and-GNUradio
A full-band (0.5~2000MHz) SDR receiver built with RTL-SDR and GNU Radio, featuring multi-mode demodulation, waterfall display, and FT8 decoding.
🌟 核心特性 (Features)

跨平台图形界面：基于 PyQt5 和 pyqtgraph 构建，支持高帧率实时频谱（Spectrum）与瀑布图（Waterfall）显示，针对触摸屏（如树莓派）做了全屏无边框优化。

软硬结合：底层基于 GNU Radio 流图控制，支持实时调节 RF/IF/BB 增益、采样率，并支持 RTL-SDR 的直采模式（Q通道/I通道）切换。

多模式解调与监听：支持 WFM、USB 等多种解调模式，支持灵活拖拽调节目标频率、自定义滤波器带宽（Filter BW）及静噪阈值（Squelch）。

内置 FT8 解码器：集成 FT8 通信协议解码线程，支持自动/手动时间同步，实时捕获并解析信噪比（SNR）、频偏与电文。

高可用性设计：内置硬件热插拔检测机制（基于 lsusb），断开后自动挂起，重新插入后自动恢复底层 SDR 进程。