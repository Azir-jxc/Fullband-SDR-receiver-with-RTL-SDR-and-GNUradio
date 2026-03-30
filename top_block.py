#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Top Block
# GNU Radio version: v3.8.2.0-57-gd71cd177

from distutils.version import StrictVersion

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio.filter import firdes
import sip
from gnuradio import analog
from gnuradio import audio
from gnuradio import blocks
from gnuradio import fft
from gnuradio.fft import window
from gnuradio import filter
from gnuradio import gr
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import zeromq
from gnuradio.qtgui import Range, RangeWidget
import osmosdr
import time
try:
    from xmlrpc.server import SimpleXMLRPCServer
except ImportError:
    from SimpleXMLRPCServer import SimpleXMLRPCServer
import threading

from gnuradio import qtgui

class top_block(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Top Block")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Top Block")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "top_block")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Variables
        ##################################################
        self.target_freq = target_freq = 94.5e6
        self.sdr_freq = sdr_freq = 94.5e6
        self.wfm_co_freq = wfm_co_freq = 7.5e4
        self.usb_co_freq_low = usb_co_freq_low = 0.2e3
        self.usb_co_freq_high = usb_co_freq_high = 2.8e3
        self.syn_mode = syn_mode = 0
        self.squelch = squelch = -70
        self.sdr_samp_rate = sdr_samp_rate = 2.4e6
        self.samp_rate = samp_rate = 48000
        self.receive_width = receive_width = 100e3
        self.offset_freq = offset_freq = target_freq-sdr_freq
        self.nfm_co_freq = nfm_co_freq = 7.5e3
        self.lsb_co_freq_low = lsb_co_freq_low = -2.8e3
        self.lsb_co_freq_high = lsb_co_freq_high = -0.2e3
        self.gain_rf = gain_rf = 20
        self.gain_if = gain_if = 20
        self.gain_bb = gain_bb = 20
        self.dev_args = dev_args = 'rtl=0,direct_samp=0'
        self.demod_mode = demod_mode = 2
        self.audio_value = audio_value = 0.4
        self.am_co_freq = am_co_freq = 5e3

        ##################################################
        # Blocks
        ##################################################
        self._sdr_freq_range = Range(28e6, 1.7e9, 100e3, 94.5e6, 200)
        self._sdr_freq_win = RangeWidget(self._sdr_freq_range, self.set_sdr_freq, 'sdr_freq', "counter_slider", float)
        self.top_grid_layout.addWidget(self._sdr_freq_win, 4, 3, 1, 1)
        for r in range(4, 5):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(3, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.zeromq_pub_sink_0_0 = zeromq.pub_sink(gr.sizeof_gr_complex, 1024, 'tcp://127.0.0.1:5556', 100, False, -1)
        self.zeromq_pub_sink_0 = zeromq.pub_sink(gr.sizeof_gr_complex, 1024, 'tcp://127.0.0.1:5555', 100, False, -1)
        self.xmlrpc_server_0 = SimpleXMLRPCServer(('localhost', 8080), allow_none=True)
        self.xmlrpc_server_0.register_instance(self)
        self.xmlrpc_server_0_thread = threading.Thread(target=self.xmlrpc_server_0.serve_forever)
        self.xmlrpc_server_0_thread.daemon = True
        self.xmlrpc_server_0_thread.start()
        self.rtlsdr_source_0 = osmosdr.source(
            args="numchan=" + str(1) + " " + dev_args
        )
        self.rtlsdr_source_0.set_time_unknown_pps(osmosdr.time_spec_t())
        self.rtlsdr_source_0.set_sample_rate(sdr_samp_rate)
        self.rtlsdr_source_0.set_center_freq(sdr_freq, 0)
        self.rtlsdr_source_0.set_freq_corr(0, 0)
        self.rtlsdr_source_0.set_dc_offset_mode(0, 0)
        self.rtlsdr_source_0.set_iq_balance_mode(0, 0)
        self.rtlsdr_source_0.set_gain_mode(False, 0)
        self.rtlsdr_source_0.set_gain(gain_rf, 0)
        self.rtlsdr_source_0.set_if_gain(gain_if, 0)
        self.rtlsdr_source_0.set_bb_gain(gain_bb, 0)
        self.rtlsdr_source_0.set_antenna('', 0)
        self.rtlsdr_source_0.set_bandwidth(0, 0)
        self.qtgui_freq_sink_x_0 = qtgui.freq_sink_c(
            1024, #size
            firdes.WIN_BLACKMAN_hARRIS, #wintype
            sdr_freq, #fc
            sdr_samp_rate, #bw
            "", #name
            1
        )
        self.qtgui_freq_sink_x_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0.set_y_axis(-140, 10)
        self.qtgui_freq_sink_x_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0.enable_grid(True)
        self.qtgui_freq_sink_x_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0.enable_control_panel(False)



        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_win)
        self.low_pass_filter_0_1 = filter.fir_filter_ccf(
            1,
            firdes.low_pass(
                1,
                sdr_samp_rate/10,
                wfm_co_freq,
                25000,
                firdes.WIN_HAMMING,
                6.76))
        self.low_pass_filter_0_0_0 = filter.fir_filter_ccf(
            10,
            firdes.low_pass(
                1,
                sdr_samp_rate,
                receive_width,
                5000,
                firdes.WIN_HAMMING,
                6.76))
        self.low_pass_filter_0_0 = filter.fir_filter_ccf(
            5,
            firdes.low_pass(
                1,
                sdr_samp_rate/10,
                am_co_freq,
                5000,
                firdes.WIN_HAMMING,
                6.76))
        self.low_pass_filter_0 = filter.fir_filter_ccf(
            5,
            firdes.low_pass(
                1,
                sdr_samp_rate/10,
                nfm_co_freq,
                5000,
                firdes.WIN_HAMMING,
                6.76))
        self.fft_vxx_0 = fft.fft_vcc(1024, True, window.blackmanharris(1024), True, 1)
        self.blocks_stream_to_vector_0_0 = blocks.stream_to_vector(gr.sizeof_gr_complex*1, 1024)
        self.blocks_stream_to_vector_0 = blocks.stream_to_vector(gr.sizeof_gr_complex*1, 1024)
        self.blocks_selector_0_0 = blocks.selector(gr.sizeof_float*1,demod_mode,0)
        self.blocks_selector_0_0.set_enabled(True)
        self.blocks_selector_0 = blocks.selector(gr.sizeof_gr_complex*1,0,demod_mode)
        self.blocks_selector_0.set_enabled(True)
        self.blocks_multiply_xx_1_0 = blocks.multiply_vff(1)
        self.blocks_multiply_xx_1 = blocks.multiply_vcc(1)
        self.blocks_complex_to_real_0_0 = blocks.complex_to_real(1)
        self.blocks_complex_to_real_0 = blocks.complex_to_real(1)
        self.band_pass_filter_0_0 = filter.fir_filter_ccc(
            5,
            firdes.complex_band_pass(
                1,
                sdr_samp_rate/10,
                lsb_co_freq_low,
                lsb_co_freq_high,
                1000,
                firdes.WIN_HAMMING,
                6.76))
        self.band_pass_filter_0 = filter.fir_filter_ccc(
            5,
            firdes.complex_band_pass(
                1,
                sdr_samp_rate/10,
                usb_co_freq_low,
                usb_co_freq_high,
                1000,
                firdes.WIN_HAMMING,
                6.76))
        self.audio_sink_0 = audio.sink(48000, '', False)
        self.analog_wfm_rcv_0 = analog.wfm_rcv(
        	quad_rate=sdr_samp_rate / 10,
        	audio_decimation=5,
        )
        self.analog_simple_squelch_cc_4 = analog.simple_squelch_cc(squelch, 1)
        self.analog_simple_squelch_cc_3 = analog.simple_squelch_cc(squelch, 1)
        self.analog_simple_squelch_cc_2 = analog.simple_squelch_cc(squelch, 1)
        self.analog_simple_squelch_cc_1 = analog.simple_squelch_cc(squelch, 1)
        self.analog_sig_source_x_1 = analog.sig_source_c(sdr_samp_rate, analog.GR_COS_WAVE, -offset_freq, 1, 0, 0)
        self.analog_nbfm_rx_0 = analog.nbfm_rx(
        	audio_rate=48000,
        	quad_rate=int(sdr_samp_rate/50),
        	tau=75e-6,
        	max_dev=5.0e3,
          )
        self.analog_const_source_x_0 = analog.sig_source_f(0, analog.GR_CONST_WAVE, 0, 0, audio_value)
        self.analog_am_demod_cf_0 = analog.am_demod_cf(
        	channel_rate=sdr_samp_rate/50,
        	audio_decim=1,
        	audio_pass=5000,
        	audio_stop=5500,
        )



        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_am_demod_cf_0, 0), (self.blocks_selector_0_0, 0))
        self.connect((self.analog_const_source_x_0, 0), (self.blocks_multiply_xx_1_0, 1))
        self.connect((self.analog_nbfm_rx_0, 0), (self.blocks_selector_0_0, 1))
        self.connect((self.analog_sig_source_x_1, 0), (self.blocks_multiply_xx_1, 1))
        self.connect((self.analog_simple_squelch_cc_1, 0), (self.analog_nbfm_rx_0, 0))
        self.connect((self.analog_simple_squelch_cc_2, 0), (self.analog_wfm_rcv_0, 0))
        self.connect((self.analog_simple_squelch_cc_3, 0), (self.blocks_complex_to_real_0, 0))
        self.connect((self.analog_simple_squelch_cc_4, 0), (self.blocks_complex_to_real_0_0, 0))
        self.connect((self.analog_wfm_rcv_0, 0), (self.blocks_selector_0_0, 2))
        self.connect((self.band_pass_filter_0, 0), (self.analog_simple_squelch_cc_3, 0))
        self.connect((self.band_pass_filter_0_0, 0), (self.analog_simple_squelch_cc_4, 0))
        self.connect((self.blocks_complex_to_real_0, 0), (self.blocks_selector_0_0, 3))
        self.connect((self.blocks_complex_to_real_0_0, 0), (self.blocks_selector_0_0, 4))
        self.connect((self.blocks_multiply_xx_1, 0), (self.low_pass_filter_0_0_0, 0))
        self.connect((self.blocks_multiply_xx_1_0, 0), (self.audio_sink_0, 0))
        self.connect((self.blocks_selector_0, 3), (self.band_pass_filter_0, 0))
        self.connect((self.blocks_selector_0, 4), (self.band_pass_filter_0_0, 0))
        self.connect((self.blocks_selector_0, 1), (self.low_pass_filter_0, 0))
        self.connect((self.blocks_selector_0, 0), (self.low_pass_filter_0_0, 0))
        self.connect((self.blocks_selector_0, 2), (self.low_pass_filter_0_1, 0))
        self.connect((self.blocks_selector_0_0, 0), (self.blocks_multiply_xx_1_0, 0))
        self.connect((self.blocks_stream_to_vector_0, 0), (self.fft_vxx_0, 0))
        self.connect((self.blocks_stream_to_vector_0_0, 0), (self.zeromq_pub_sink_0_0, 0))
        self.connect((self.fft_vxx_0, 0), (self.zeromq_pub_sink_0, 0))
        self.connect((self.low_pass_filter_0, 0), (self.analog_simple_squelch_cc_1, 0))
        self.connect((self.low_pass_filter_0_0, 0), (self.analog_am_demod_cf_0, 0))
        self.connect((self.low_pass_filter_0_0_0, 0), (self.blocks_selector_0, 0))
        self.connect((self.low_pass_filter_0_1, 0), (self.analog_simple_squelch_cc_2, 0))
        self.connect((self.rtlsdr_source_0, 0), (self.blocks_multiply_xx_1, 0))
        self.connect((self.rtlsdr_source_0, 0), (self.blocks_stream_to_vector_0, 0))
        self.connect((self.rtlsdr_source_0, 0), (self.blocks_stream_to_vector_0_0, 0))
        self.connect((self.rtlsdr_source_0, 0), (self.qtgui_freq_sink_x_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "top_block")
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()

    def get_target_freq(self):
        return self.target_freq

    def set_target_freq(self, target_freq):
        self.target_freq = target_freq
        self.set_offset_freq(self.target_freq-self.sdr_freq)

    def get_sdr_freq(self):
        return self.sdr_freq

    def set_sdr_freq(self, sdr_freq):
        self.sdr_freq = sdr_freq
        self.set_offset_freq(self.target_freq-self.sdr_freq)
        self.qtgui_freq_sink_x_0.set_frequency_range(self.sdr_freq, self.sdr_samp_rate)
        self.rtlsdr_source_0.set_center_freq(self.sdr_freq, 0)

    def get_wfm_co_freq(self):
        return self.wfm_co_freq

    def set_wfm_co_freq(self, wfm_co_freq):
        self.wfm_co_freq = wfm_co_freq
        self.low_pass_filter_0_1.set_taps(firdes.low_pass(1, self.sdr_samp_rate/10, self.wfm_co_freq, 25000, firdes.WIN_HAMMING, 6.76))

    def get_usb_co_freq_low(self):
        return self.usb_co_freq_low

    def set_usb_co_freq_low(self, usb_co_freq_low):
        self.usb_co_freq_low = usb_co_freq_low
        self.band_pass_filter_0.set_taps(firdes.complex_band_pass(1, self.sdr_samp_rate/10, self.usb_co_freq_low, self.usb_co_freq_high, 1000, firdes.WIN_HAMMING, 6.76))

    def get_usb_co_freq_high(self):
        return self.usb_co_freq_high

    def set_usb_co_freq_high(self, usb_co_freq_high):
        self.usb_co_freq_high = usb_co_freq_high
        self.band_pass_filter_0.set_taps(firdes.complex_band_pass(1, self.sdr_samp_rate/10, self.usb_co_freq_low, self.usb_co_freq_high, 1000, firdes.WIN_HAMMING, 6.76))

    def get_syn_mode(self):
        return self.syn_mode

    def set_syn_mode(self, syn_mode):
        self.syn_mode = syn_mode

    def get_squelch(self):
        return self.squelch

    def set_squelch(self, squelch):
        self.squelch = squelch
        self.analog_simple_squelch_cc_1.set_threshold(self.squelch)
        self.analog_simple_squelch_cc_2.set_threshold(self.squelch)
        self.analog_simple_squelch_cc_3.set_threshold(self.squelch)
        self.analog_simple_squelch_cc_4.set_threshold(self.squelch)

    def get_sdr_samp_rate(self):
        return self.sdr_samp_rate

    def set_sdr_samp_rate(self, sdr_samp_rate):
        self.sdr_samp_rate = sdr_samp_rate
        self.analog_sig_source_x_1.set_sampling_freq(self.sdr_samp_rate)
        self.band_pass_filter_0.set_taps(firdes.complex_band_pass(1, self.sdr_samp_rate/10, self.usb_co_freq_low, self.usb_co_freq_high, 1000, firdes.WIN_HAMMING, 6.76))
        self.band_pass_filter_0_0.set_taps(firdes.complex_band_pass(1, self.sdr_samp_rate/10, self.lsb_co_freq_low, self.lsb_co_freq_high, 1000, firdes.WIN_HAMMING, 6.76))
        self.low_pass_filter_0.set_taps(firdes.low_pass(1, self.sdr_samp_rate/10, self.nfm_co_freq, 5000, firdes.WIN_HAMMING, 6.76))
        self.low_pass_filter_0_0.set_taps(firdes.low_pass(1, self.sdr_samp_rate/10, self.am_co_freq, 5000, firdes.WIN_HAMMING, 6.76))
        self.low_pass_filter_0_0_0.set_taps(firdes.low_pass(1, self.sdr_samp_rate, self.receive_width, 5000, firdes.WIN_HAMMING, 6.76))
        self.low_pass_filter_0_1.set_taps(firdes.low_pass(1, self.sdr_samp_rate/10, self.wfm_co_freq, 25000, firdes.WIN_HAMMING, 6.76))
        self.qtgui_freq_sink_x_0.set_frequency_range(self.sdr_freq, self.sdr_samp_rate)
        self.rtlsdr_source_0.set_sample_rate(self.sdr_samp_rate)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate

    def get_receive_width(self):
        return self.receive_width

    def set_receive_width(self, receive_width):
        self.receive_width = receive_width
        self.low_pass_filter_0_0_0.set_taps(firdes.low_pass(1, self.sdr_samp_rate, self.receive_width, 5000, firdes.WIN_HAMMING, 6.76))

    def get_offset_freq(self):
        return self.offset_freq

    def set_offset_freq(self, offset_freq):
        self.offset_freq = offset_freq
        self.analog_sig_source_x_1.set_frequency(-self.offset_freq)

    def get_nfm_co_freq(self):
        return self.nfm_co_freq

    def set_nfm_co_freq(self, nfm_co_freq):
        self.nfm_co_freq = nfm_co_freq
        self.low_pass_filter_0.set_taps(firdes.low_pass(1, self.sdr_samp_rate/10, self.nfm_co_freq, 5000, firdes.WIN_HAMMING, 6.76))

    def get_lsb_co_freq_low(self):
        return self.lsb_co_freq_low

    def set_lsb_co_freq_low(self, lsb_co_freq_low):
        self.lsb_co_freq_low = lsb_co_freq_low
        self.band_pass_filter_0_0.set_taps(firdes.complex_band_pass(1, self.sdr_samp_rate/10, self.lsb_co_freq_low, self.lsb_co_freq_high, 1000, firdes.WIN_HAMMING, 6.76))

    def get_lsb_co_freq_high(self):
        return self.lsb_co_freq_high

    def set_lsb_co_freq_high(self, lsb_co_freq_high):
        self.lsb_co_freq_high = lsb_co_freq_high
        self.band_pass_filter_0_0.set_taps(firdes.complex_band_pass(1, self.sdr_samp_rate/10, self.lsb_co_freq_low, self.lsb_co_freq_high, 1000, firdes.WIN_HAMMING, 6.76))

    def get_gain_rf(self):
        return self.gain_rf

    def set_gain_rf(self, gain_rf):
        self.gain_rf = gain_rf
        self.rtlsdr_source_0.set_gain(self.gain_rf, 0)

    def get_gain_if(self):
        return self.gain_if

    def set_gain_if(self, gain_if):
        self.gain_if = gain_if
        self.rtlsdr_source_0.set_if_gain(self.gain_if, 0)

    def get_gain_bb(self):
        return self.gain_bb

    def set_gain_bb(self, gain_bb):
        self.gain_bb = gain_bb
        self.rtlsdr_source_0.set_bb_gain(self.gain_bb, 0)

    def get_dev_args(self):
        return self.dev_args

    def set_dev_args(self, dev_args):
        self.dev_args = dev_args

    def get_demod_mode(self):
        return self.demod_mode

    def set_demod_mode(self, demod_mode):
        self.demod_mode = demod_mode
        self.blocks_selector_0.set_output_index(self.demod_mode)
        self.blocks_selector_0_0.set_input_index(self.demod_mode)

    def get_audio_value(self):
        return self.audio_value

    def set_audio_value(self, audio_value):
        self.audio_value = audio_value
        self.analog_const_source_x_0.set_offset(self.audio_value)

    def get_am_co_freq(self):
        return self.am_co_freq

    def set_am_co_freq(self, am_co_freq):
        self.am_co_freq = am_co_freq
        self.low_pass_filter_0_0.set_taps(firdes.low_pass(1, self.sdr_samp_rate/10, self.am_co_freq, 5000, firdes.WIN_HAMMING, 6.76))





def main(top_block_cls=top_block, options=None):

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    def quitting():
        tb.stop()
        tb.wait()

    qapp.aboutToQuit.connect(quitting)
    qapp.exec_()

if __name__ == '__main__':
    main()
