#!/usr/bin/env python3

    # OpenStreamControl
    # A simple Programm to Control the Aquastream XT Pump from Aquacomputer
    # Copyright (C) 2026  Cat Sniffer catpawsniffer@proton.me

    # This program is free software: you can redistribute it and/or modify
    # it under the terms of the GNU General Public License as published by
    # the Free Software Foundation, either version 3 of the License, or
    # (at your option) any later version.

    # This program is distributed in the hope that it will be useful,
    # but WITHOUT ANY WARRANTY; without even the implied warranty of
    # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    # GNU General Public License for more details.

    # You should have received a copy of the GNU General Public License
    # along with this program.  If not, see <https://www.gnu.org/licenses/>.

    
    # Uses Qt-6 library https://www.qt.io/development/qt-framework/qt6
    
    # Based on infos from https://github.com/aleksamagicka/aquacomputer_d5next-hwmon
    
    
############################################################################
############################################################################

import hid
import time
import sys 
import os
import threading
import xml.etree.ElementTree as ET 


from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon
from PySide6.QtCore import Signal

#UI Load
from ui_gui  import Ui_MainWindow

############
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg


#############################################################
#############################################################

hid_counter=0

tree = ET.parse("settings.xml") 
root = tree.getroot() 


#vid 0x0c70    pid 0xf0b6
vid = 0x0c70	# 
pid = 0xf0b6	# Aquastream XT


try:
    h = hid.Device(vid, pid) 
except:
    print("Aquastream XT not found")
    print("or /dev/hidraw* not accessible as current user") 
    print("Check how to gain access as normal user")
    exit()

#h.nonblocking=1  

print("")

print("Pump found:")

print("Manufacturer: %s" % h.manufacturer)
print("Product: %s" % h.product)
#print("Serial No: %s" % h.serial)

#manufacturer_string = h.manufacturer()
product_string = h.product


AQUASTREAMXT_SENSOR_FEATURE_REPORT_ID = 0x04   #feature report nr 4
AQUASTREAMXT_CTRL_FEATURE_REPORT_ID	= 0x06

#define AQUASTREAMXT_SENSOR_REPORT_SIZE		0x42
#define AQUASTREAMXT_CTRL_REPORT_SIZE		0x34
AQUASTREAMXT_SENSOR_REPORT_SIZE	= 0x43   #0x42 = 66dec // 0x43 = 67dec   report is 66 bytes
AQUASTREAMXT_CTRL_REPORT_SIZE =	0x34     #0x34 52d // ox33 = 51dec  report is 51 bytes

#The HID report that the official software always sends after writing value
#/* Secondary HID report values for Aquastream XT */
AQUASTREAMXT_SECONDARY_CTRL_REPORT_ID	= 0x02
AQUASTREAMXT_SECONDARY_CTRL_REPORT_SIZE	= 0x04

#sec_ctrl_report=[0x02, 0x05, 0x00, 0x00] #works
sec_ctrl_report=[0x02, 0x05, 0x00, 0x00]


#ausgabefile = open("meine_ctrl_feature_123.bin", "bw")
#reportdaten= h.get_feature_report(AQUASTREAMXT_CTRL_FEATURE_REPORT_ID, AQUASTREAMXT_CTRL_REPORT_SIZE)    
#ausgabefile.write(bytes(reportdaten))
#ausgabefile.close()

#ausgabefile = open("meine_sensor_feature_123.bin", "bw")
#reportdaten = h.get_feature_report(AQUASTREAMXT_SENSOR_FEATURE_REPORT_ID, AQUASTREAMXT_SENSOR_REPORT_SIZE)    
#ausgabefile.write(bytes(reportdaten))
#ausgabefile.close()


def write_int16_le(int16val, report, offset):
    ausgabe_h = (( int(int16val) & 0xff00 ) >> 8)
    ausgabe_l = ( int(int16val) & 0x00ff)
    report[offset] = ausgabe_l
    report[offset +1] = ausgabe_h
    
def write_int32_le(int32val, report, offset):
    int32val = int(int32val)
    byte1 = int32val & 0xff
    byte2 = (int32val & 0xff00) >> 8
    byte3 = (int32val & 0xff0000) >> 16
    byte4 = (int32val & 0xff000000) >> 24
    report[offset] = byte1
    report[offset+1] = byte2
    report[offset+2] = byte3
    report[offset+3] = byte4
    
# def write_int24_le(int24val, report, offset):
    # int24val = int(int24val)
    # byte1 = int24val & 0xff
    # byte2 = (int24val & 0xff00) >> 8
    # byte3 = (int24val & 0xff0000) >> 16
    # report[offset] = byte1
    # report[offset+1] = byte2
    # report[offset+2] = byte3
    
# def read_int24_le(report, offset):
    # return(report[offset] + report[offset +1] * 0x100 + report[offset + 2] * 0x10000 )
    
def read_int16_le(report, offset):
    return (report[offset] + report[offset +1] * 0x100)
    
def read_int32_le(report, offset):
    return(report[offset] + report[offset +1] * 0x100 + report[offset + 2] * 0x10000 + report[offset +3] * 0x1000000)
    
    
def conv_rpm_to_raw_pump(rpmval):
    return int(45000000 / rpmval)
    
def conv_raw_to_rpm_fan(rpmval):
    return int(5646000 / rpmval)
    
def conv_raw_to_rpm_pump(raw):
    return int(45000000 / raw)
    
def get_bit(val, pos):
    return (val >> pos) & 1

def set_bit(val, pos):   # 0 to 7
    return (val | (1 << pos))
    
def delete_bit(val, pos):
    return (val & ~( 1 << pos))

def update_bit(byte, pos, bit):
    if (bit == 0):
        return delete_bit(byte, pos)
    if (bit == 1):
        return set_bit(byte, pos)     
        
###############################################

#Check for Aquabus
    
aqaubus_adress_offset = 0x01  #aquabus adress
aquabus_or_flow_offset = 0x02  #0=flow  /  1=aquabus
aquabus_sensors_select_offset = 0x05  #Sensors on aquabus  0=electronicstemp / 1=externalsensor / 2=watertemp / 0xff=no_sensor

reportdata= h.get_feature_report(AQUASTREAMXT_CTRL_FEATURE_REPORT_ID, AQUASTREAMXT_CTRL_REPORT_SIZE)

if (reportdata[aquabus_or_flow_offset] == 1):
    print("")
    print("Your Pump seems to be configured to use Aquabus")
    print("Aquabus not supported. wrong settings can damage your hardware!!")
    print("Use original software to change")
    print("Only flow sensor setup is supported")
    print("I dont want to be reliable for any hardware damage")
    print("Good bye")
    exit()

if (reportdata[aquabus_or_flow_offset] == 0):  #just a double check
    print("Aquabus disabled. good")
else:
    exit()
    
#################################################

class MainWindow(QMainWindow):


    # bitfield AlarmConfiguration {
    # external_temp: 1;
    # water_temp: 1;
    # pump: 1;
    # fan_speed: 1;
    # flow_rate: 1;
    # output_overload: 1;
    # amp_temp80: 1;
    # amp_temp100: 1;
    # };
    
    bitfield_alarm_configuration_external_temp_offset = 0
    bitfield_alarm_configuration_int_temp_offset = 1
    bitfield_alarm_configuration_pump_offset = 2
    bitfield_alarm_configuration_fan_speed_offset = 3
    bitfield_alarm_configuration_flow_rate_offset = 4
    bitfield_alarm_configuration_output_overload_offset = 5
    bitfield_alarm_configuration_amp_temp80_offset = 6
    bitfield_alarm_configuration_amp_temp100_offset = 7
    
    bitfield_alarm_configuration_external_temp = 0
    bitfield_alarm_configuration_int_temp = 0
    bitfield_alarm_configuration_pump = 0
    bitfield_alarm_configuration_fan_speed = 0
    bitfield_alarm_configuration_flow_rate = 0
    bitfield_alarm_configuration_output_overload = 0
    bitfield_alarm_configuration_amp_temp80 = 0
    bitfield_alarm_configuration_amp_temp100 = 0
    
    # bitfield SpeedSignalOutput {
    # fan_speed: 1;
    # flow_sensor: 1;
    # pump_speed: 1;
    # static_speed: 1;
    # switch_off_on_alarm: 1;
    # };
    bitfield_speed_signal_output_fan_speed_offset = 0
    bitfield_speed_signal_output_flow_sensor_offset = 1
    bitfield_speed_signal_output_pump_speed_offset = 2
    bitfield_speed_signal_output_static_speed_offset = 3
    bitfield_speed_signal_output_switch_off_on_alarm_offset = 4

    bitfield_speed_signal_output_fan_speed = 0
    bitfield_speed_signal_output_flow_sensor = 0
    bitfield_speed_signal_output_pump_speed = 0
    bitfield_speed_signal_output_static_speed = 0
    bitfield_speed_signal_output_switch_off_on_alarm = 0    
    
    # bitfield FanMode 
    # manual: 1;
    # automatic: 1;
    # hold_min: 1;

    
    bitfield_fan_mode_manual_offset = 0
    bitfield_fan_mode_automatic_offset = 1
    bitfield_fan_mode_hold_min_offset = 2

    bitfield_fan_mode_manual = 0
    bitfield_fan_mode_automatic = 0
    bitfield_fan_mode_hold_min = 0
    
    # bitfield PumpMode  
    # padding: 1;    LSB
    # automatic/manual: 1;   (auto = 1 / manual = 0)
    # unknown_value: 1;  (always 1)
    # padding: 1;
    # aquabus/flow switch: 1   (flow = 0 / aquabus = 1)
    # hold_min: 1;
    # 0, 0, hold_min, aquabus/flow, 0,  1, auto/man, 0
    
    bitfield_pump_mode_hold_min_offset = 5
    bitfield_pump_mode_aquabus_flow_offset = 4
    bitfield_pump_mode_auto_man_offset = 1
    
    bitfield_pump_mode_hold_min = 0
    bitfield_pump_mode_aquabus_flow = 0
    bitfield_pump_mode_auto_man = 0
    
    
    ################################
    #Aquabus
    
    aqaubus_adress_offset = 0x01  #aquabus adress
    aquabus_or_flow_offset = 0x02  #0=flow  /  1=aquabus
    aquabus_sensors_select_offset = 0x05  #Sensors on aquabus  0=electronicstemp / 1=externalsensor / 2=watertemp / 0xff=no_sensor

    # ##############################

    # BF   PumpMode pump_mode @ 0x3;
    pump_mode_bf_offset_8 = 0x3
    # le u16 pump_speed @ 0x8;
    pump_speed_offset_16 = 0x08
    # BF   AlarmConfiguration alarm_config @ 0xe;
    alarm_config_bf_offset_8 = 0xe
    # BF   SpeedSignalOutput speed_signal_out_mode @ 0xf;
    speed_signal_out_mode_bf_offset_8 = 0xf
    # le u24 alarm_flow_speed @ 0x12; 
    alarm_flow_speed_offset_32 = 0x12
    # le u16 alarm_external_temp @ 0x16;
    alarm_external_temp_offset_16 = 0x16
    # le u16 alarm_int_temp @ 0x18;
    alarm_int_temp_offset_16 = 0x18
    # BF   FanMode fan_mode @ 0x1a;
    fan_mode_bf_offset_8 = 0x1a
    # u8 fan_pwm @ 0x1b;
    fan_pwm_offset_8 = 0x1b
    # le u16 fan_hysteresis @ 0x1c;
    fan_hysteresis_offset_16 = 0x1c
    # u8 fan_temp_src @ 0x1e;
    fan_temp_src_offset_8 = 0x1e
    # le u16 fan_target_temp @ 0x1f;
    fan_target_temp_offset_16 = 0x1f
    # le u16 fan_p @ 0x21;
    fan_p_offset_16 = 0x21
    # le u16 fan_i @ 0x23;
    fan_i_offset_16 = 0x23
    # le u16 fan_d @ 0x25;
    fan_d_offset_16 = 0x25
    # le u16 fan_min_temp @ 0x27;
    fan_min_temp_offset_16 = 0x27
    # le u16 fan_max_temp @ 0x29;
    fan_max_temp_offset_16 = 0x29
    # u8 fan_min_pwm @ 0x2b;
    fan_min_pwm_offset_8 = 0x2b
    # u8 fan_max_pwm @ 0x2c;
    fan_max_pwm_offset_8 = 0x2c
    # le u16 pump_min_speed @ 0x2f;
    pump_min_speed_offset_16 = 0x2f
    # le u16 pump_max_speed @ 0x31;
    pump_max_speed_offset_16 = 0x31

    ######################
    
    pump_mode_bf = 0
    alarm_config_bf = 0
    speed_signal_out_mode_bf = 0
    fan_mode_bf = 0

    alarm_flow_speed = 0
    alarm_external_temp = 0
    alarm_int_temp = 0
    
    ###PID
    fan_hysteresis = 0
    fan_p = 0
    fan_i = 0
    fan_d = 0
    fan_min_temp = 0
    fan_max_temp = 0
    ###
    
    fan_pwm = 0
    fan_temp_src = 0
    fan_min_pwm = 0
    fan_max_pwm = 0
    fan_target_temp = 0
    
    pump_speed = 0
    pump_min_speed = 0
    pump_max_speed = 0

    #########################

    int_temp_offset = 0
    ext_temp_offset = 0
    #high flow has 169
    cal_imp_per_liter = 0 #169
    ###

    ctrl_report = 0
    
    pump_max_limit=6000
    pump_min_limit=3000
    pump_max_hz_limit = int(pump_max_limit / 60)
    pump_min_hz_limit = int(pump_min_limit / 60)
    
    fan_max_limit_hz = 100
    fan_min_limit_hz = 0
    
    fan_limit = 2000  #max rpm
    
    sensor_update_signal = Signal(float, float, float, float, float, float, int, int, int, int, float, int)
    sensor_pump_infos_signal = Signal(int, int, list)
    #################### von sensor report
    sensor_fan_voltage = 0
    sensor_pump_voltage = 0
    sensor_pump_curr = 0
    sensor_temp_sensor_fan_amp = 0
    sensor_temp_sensor_ext = 0
    sensor_temp_sensor_int = 0
    sensor_pump_speed = 0
    sensor_fan_speed = 0   # auch wenn sie ned laufen nicht 0
    sensor_fan_status = 0  #?????   0-> läuft   4-> steht ?
    sensor_fan_pwm = 0     #?????  % auslastung   100% = 255 raw
    sensor_pump_watts = 0
    sensor_flow_sensor_raw = 0
    ######################
    
    sensor_firmware = 0
    sensor_serial_number = 0
    sensor_device_key = [0, 0, 0, 0, 0, 0]  ###6 bytes
    ######################
    
    flow_sensor_l_p_h = 0
    
    
    def __init__(self):
        #super(self.__class__, self).__init__()
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        #self.ctrl_report = list(h.get_feature_report(AQUASTREAMXT_CTRL_FEATURE_REPORT_ID, AQUASTREAMXT_CTRL_REPORT_SIZE))
        
        self.get_report_and_update_local_vars()
        
        self.ui.stackedWidget_1.setCurrentWidget(self.ui.page_1)
        self.ui.pushButton_1.clicked.connect(self.button_1)
        self.ui.pushButton_2.clicked.connect(self.button_2)
        self.ui.pushButton_3.clicked.connect(self.button_3)
        self.ui.pushButton_4.clicked.connect(self.button_4)
        self.ui.pushButton_ctrl_report.clicked.connect(self.print_ctrl_report)
        self.ui.pushButton_sensor_report.clicked.connect(self.print_sensor_report)
        #self.ui.pushButton_send_ctrl_report.clicked.connect(self.send_ctrl_report)
        
        #self.get_report_and_update_local_vars()
        
        self.ui.checkBox_extempenable.stateChanged.connect(self.extempenable_changed)
        self.ui.checkBox_flowenable.stateChanged.connect(self.flowenable_changed)
        
        self.stdfont = self.ui.pushButton_1.font()
        self.boldfont = self.ui.pushButton_1.font()
        self.boldfont.setBold(1)
        self.ui.pushButton_1.setFont(self.boldfont)
        
        self.ui.lineEdit_model.setText(product_string)
        
        self.ui.radioButton_pump_auto.pressed.connect(self.hit_radio_pump_auto)
        self.ui.radioButton_pump_manual.pressed.connect(self.hit_radio_pump_manual)
        self.ui.radioButton_fans_auto.toggled.connect(self.hit_radio_fans_auto)
        self.ui.radioButton_fans_man.toggled.connect(self.hit_radio_fans_manual)

        #self.ui.checkBox_pump_man_no_below.stateChanged.connect(self.sync_dont_go_below_pump_checkstate_man)
        #self.ui.checkBox_pump_auto_no_below.stateChanged.connect(self.sync_dont_go_below_pump_checkstate_auto)
        
        # pump limits setzen
        #self.ui.horizontalSlider_pump_man_min.setMinimum(self.pump_min_limit)
        self.ui.horizontalSlider_pump_man_pump_rpm.setMinimum(self.pump_min_limit)
        #self.ui.spinBox_pump_man_min.setMinimum(self.pump_min_limit)
        #self.ui.spinBox_pump_man_min_hz.setMinimum(self.pump_min_hz_limit)
        self.ui.spinBox_pump_man_pump_rpm.setMinimum(self.pump_min_limit)
        self.ui.spinBox_pump_man_pump_rpm_hz.setMinimum(self.pump_min_hz_limit)
        self.ui.horizontalSlider_pump_auto_max.setMinimum(self.pump_min_limit)
        self.ui.horizontalSlider_pump_auto_min.setMinimum(self.pump_min_limit)
        self.ui.spinBox_pump_auto_max.setMinimum(self.pump_min_limit)
        self.ui.spinBox_pump_auto_max_hz.setMinimum(self.pump_min_hz_limit)
        self.ui.spinBox_pump_auto_min.setMinimum(self.pump_min_limit)
        self.ui.spinBox_pump_auto_min_hz.setMinimum(self.pump_min_hz_limit)
        
        #self.ui.horizontalSlider_pump_man_min.setMaximum(self.pump_max_limit)
        self.ui.horizontalSlider_pump_man_pump_rpm.setMaximum(self.pump_max_limit)
        #self.ui.spinBox_pump_man_min.setMaximum(self.pump_max_limit)
        #self.ui.spinBox_pump_man_min_hz.setMaximum(self.pump_max_hz_limit)
        self.ui.spinBox_pump_man_pump_rpm.setMaximum(self.pump_max_limit)
        self.ui.spinBox_pump_man_pump_rpm_hz.setMaximum(self.pump_max_hz_limit)
        self.ui.horizontalSlider_pump_auto_max.setMaximum(self.pump_max_limit)
        self.ui.horizontalSlider_pump_auto_min.setMaximum(self.pump_max_limit)
        self.ui.spinBox_pump_auto_max.setMaximum(self.pump_max_limit)
        self.ui.spinBox_pump_auto_max_hz.setMaximum(self.pump_max_hz_limit)
        self.ui.spinBox_pump_auto_min.setMaximum(self.pump_max_limit)
        self.ui.spinBox_pump_auto_min_hz.setMaximum(self.pump_max_hz_limit)
        
        #fan limits setzen
        self.ui.horizontalSlider_fans_auto_max.setMinimum(self.fan_min_limit_hz)
        self.ui.horizontalSlider_fans_auto_min.setMinimum(self.fan_min_limit_hz)
        self.ui.spinBox_fans_auto_fans_max_hz.setMinimum(self.fan_min_limit_hz)
        self.ui.spinBox_fans_auto_fans_min_hz.setMinimum(self.fan_min_limit_hz)
        self.ui.horizontalSlider_fans_man.setMinimum(self.fan_min_limit_hz)
        self.ui.spinBox_fans_man.setMinimum(self.fan_min_limit_hz)
        
        self.ui.horizontalSlider_fans_auto_max.setMaximum(self.fan_max_limit_hz)
        self.ui.horizontalSlider_fans_auto_min.setMaximum(self.fan_max_limit_hz)
        self.ui.spinBox_fans_auto_fans_max_hz.setMaximum(self.fan_max_limit_hz)
        self.ui.spinBox_fans_auto_fans_min_hz.setMaximum(self.fan_max_limit_hz)
        self.ui.horizontalSlider_fans_man.setMaximum(self.fan_max_limit_hz)
        self.ui.spinBox_fans_man.setMaximum(self.fan_max_limit_hz)
        
        #synchronise
        #pump auto
        #min
        self.ui.spinBox_pump_auto_min.valueChanged.connect(self.sync_pump_auto_min_value)
        self.ui.spinBox_pump_auto_min_hz.valueChanged.connect(self.sync_pump_auto_min_hz)
        self.ui.horizontalSlider_pump_auto_min.valueChanged.connect(self.sync_pump_auto_min_slider)
        #max
        self.ui.spinBox_pump_auto_max.valueChanged.connect(self.sync_pump_auto_max_value)
        self.ui.spinBox_pump_auto_max_hz.valueChanged.connect(self.sync_pump_auto_max_hz)
        self.ui.horizontalSlider_pump_auto_max.valueChanged.connect(self.sync_pump_auto_max_slider)
        
        #pump man
        #man pump rpm
        self.ui.spinBox_pump_man_pump_rpm.valueChanged.connect(self.sync_pump_man_pump_value)
        self.ui.spinBox_pump_man_pump_rpm_hz.valueChanged.connect(self.sync_pump_man_pump_hz)
        self.ui.horizontalSlider_pump_man_pump_rpm.valueChanged.connect(self.sync_man_pump_slider)
        #man min
        #self.ui.spinBox_pump_man_min.valueChanged.connect(self.sync_pump_man_min_value)
        #self.ui.spinBox_pump_man_min_hz.valueChanged.connect(self.sync_pump_man_min_hz)
        #self.ui.horizontalSlider_pump_man_min.valueChanged.connect(self.sync_pump_man_min_slider)
        
        #sync Fans auto
        #fans auto min
        self.ui.spinBox_fans_auto_fans_min_hz.valueChanged.connect(self.sync_fans_auto_min_hz)
        self.ui.horizontalSlider_fans_auto_min.valueChanged.connect(self.sync_fans_auto_min_slider)
        #fans auto max
        self.ui.spinBox_fans_auto_fans_max_hz.valueChanged.connect(self.sync_fans_auto_max_hz)
        self.ui.horizontalSlider_fans_auto_max.valueChanged.connect(self.sync_fans_auto_max_slider)
        
        #fans man
        self.ui.spinBox_fans_man.valueChanged.connect(self.sync_fans_man_hz)
        self.ui.horizontalSlider_fans_man.valueChanged.connect(self.sync_fans_man_slider)
        
        self.ui.spinBox_settings_flow_calib.valueChanged.connect(self.spinBox_settings_flow_calib_valueChanged)
        
        #temp offsets
        self.ui.spinBox_settings_ext_offset.valueChanged.connect(self.spinBox_settings_ext_offset_valueChanged)
        self.ui.spinBox_settings_int_offset.valueChanged.connect(self.spinBox_settings_int_offset_valueChanged)
        
        self.ui.pushButton_pump_save_to_pump.clicked.connect(self.save_to_pump)
        self.ui.pushButton_fans_save_to_pump.clicked.connect(self.save_to_pump)
        self.ui.pushButton_settings_save_to_pump.clicked.connect(self.save_to_pump)
        
        
        #self.ui.pushButton_get_new_ctrl_data.clicked.connect(self.get_new_ctrl_data_and_update_gui)
        
        self.ui.pushButton_save_reports_to_disk.clicked.connect(self.get_and_save_reports_to_disk)
        
        ### signals
        self.sensor_pump_infos_signal.connect(self.recieve_pump_infos)
        self.sensor_update_signal.connect(self.recieve_new_sensor_values)
        
        ##################################################
        
        self.setup_plots()

        #####################################

        self.load_settings()

        self.update_gui_from_local_vars()
        
        
    #######################################################
    
    def recieve_pump_infos(self, sensor_firmware, sensor_serial_number, sensor_device_key):
    
        self.sensor_firmware = sensor_firmware
        self.sensor_serial_number = sensor_serial_number
        self.sensor_device_key = sensor_device_key
        #firmware 
        #self.ui.lineEdit_settings_firmware.setText(str(self.sensor_firmware))
        #serial_number 
        #self.ui.lineEdit_settings_serial.setText(str(self.sensor_serial_number))
        #device_key = [0, 0, 0, 0, 0, 0]  ###6 bytes
        #self.ui.lineEdit_settings_device_key.setText(str([hex(x) for x in self.sensor_device_key]))
        
    
    def recieve_new_sensor_values(self, sensor_fan_voltage, sensor_pump_voltage, sensor_pump_curr, sensor_temp_sensor_fan_amp, sensor_temp_sensor_ext, sensor_temp_sensor_int, sensor_pump_speed, sensor_fan_speed, sensor_fan_status, sensor_fan_pwm, sensor_pump_watts, sensor_flow_sensor_raw):
        
        #################### von sensor report
        self.sensor_fan_voltage = sensor_fan_voltage
        self.sensor_pump_voltage = sensor_pump_voltage
        self.sensor_pump_curr = sensor_pump_curr
        self.sensor_temp_sensor_fan_amp = sensor_temp_sensor_fan_amp
        self.sensor_temp_sensor_ext = sensor_temp_sensor_ext
        self.sensor_temp_sensor_int = sensor_temp_sensor_int
        self.sensor_pump_speed = sensor_pump_speed
        self.sensor_fan_speed = sensor_fan_speed # auch wenn sie ned laufen nicht 0
        #nix self.sensor_fan_status = 0  #?????   0-> läuft   4-> steht ?
        self.sensor_fan_pwm = sensor_fan_pwm     #?????  % auslastung   100% = 255 raw
        self.sensor_pump_watts = sensor_pump_watts
        self.sensor_flow_sensor_raw = sensor_flow_sensor_raw

        
        
        if (self.ui.checkBox_extempenable.isChecked() == True ):
            self.ui.lineEdit_ext_temp.setText(str(self.sensor_temp_sensor_ext + self.ext_temp_offset))
        else:
            self.ui.lineEdit_ext_temp.setText("")
            
        self.ui.lineEdit_fan_amp_temp.setText(str(self.sensor_temp_sensor_fan_amp))
        self.ui.lineEdit_fan_pwm.setText(str(self.sensor_fan_pwm))
        self.ui.lineEdit_fan_speed.setText(str(self.sensor_fan_speed))
        self.ui.lineEdit_fan_volt.setText(str(self.sensor_fan_voltage))
        
        ## flow raw -> l_p_h
        if (self.sensor_flow_sensor_raw < 2343):
            self.flow_sensor_l_p_h = round((2644850 / self.sensor_flow_sensor_raw)/ self.cal_imp_per_liter, 1)
        else:
            self.flow_sensor_l_p_h = 0
        ##        
        
        if (self.ui.checkBox_flowenable.isChecked() == True ):
            self.ui.lineEdit_flow.setText(str(self.flow_sensor_l_p_h))
            self.ui.lineEdit_settings_flow.setText(str(self.flow_sensor_l_p_h))
        else:
            self.ui.lineEdit_flow.setText("")      
            self.ui.lineEdit_settings_flow.setText("")
            
        self.ui.lineEdit_pump_curr.setText(str(self.sensor_pump_curr))
        self.ui.lineEdit_pump_speed.setText(str(self.sensor_pump_speed))
        self.ui.lineEdit_pump_volt.setText(str(self.sensor_pump_voltage))
        self.ui.lineEdit_pump_watts.setText(str(self.sensor_pump_watts))
        self.ui.lineEdit_temp_int.setText(str(self.sensor_temp_sensor_int + self.int_temp_offset))
        
        self.ui.lineEdit_pump_actual_rpm.setText(str(self.sensor_pump_speed)) #Pump dialogue
        self.ui.lineEdit_fans_fan_speed.setText(str(self.sensor_fan_speed)) #Fans dialogue
        self.ui.lineEdit_fans_auto_temp_ext.setText(str(self.sensor_temp_sensor_ext + self.ext_temp_offset ))
        self.ui.lineEdit_fans_auto_temp_int.setText(str(self.sensor_temp_sensor_int + self.int_temp_offset ))


        self.ui.lineEdit_fans_pwm_graph.setText(str(self.sensor_fan_pwm))
        self.ui.lineEdit_pump_current_graph.setText(str(self.sensor_pump_curr))
        
    
    def setup_plots(self):
        
        self.xrange = 500
        
        
        self.ui.plotWidget_pump.setBackground("w") 
        #window.ui.plotWidget.setBackground('#393939')
        self.pw = self.ui.plotWidget_pump
        self.p1 = self.pw.plotItem
        styles = {"color": "red", "font-size": "15px"}

        self.p1.setLabel('left', "Current (mA)", **styles)

        self.p2 = pg.ViewBox()
        self.p1.showAxis('right')
        self.p1.scene().addItem(self.p2)
        self.p1.getAxis('right').linkToView(self.p2)
        self.p2.setXLink(self.p1)
        styles = {"color": "blue", "font-size": "15px"}
        self.p1.getAxis('right').setLabel('Rpm', **styles)

        self.time = list(range(self.xrange))
        self.pumprpm_1 = [0 for _ in range(self.xrange)]
        self.pumpcurr_2 = [0 for _ in range(self.xrange)]
        
        self.p3 = pg.ViewBox()
        self.p1.scene().addItem(self.p3)
        self.p3.setXLink(self.p1)

        self.line2 = pg.PlotCurveItem(self.time, self.pumprpm_1, pen='b')
        self.p2.addItem(self.line2)
        self.p2.setGeometry(self.p1.vb.sceneBoundingRect())
        
        self.line3 = pg.PlotCurveItem(self.time, self.pumpcurr_2, pen='r')
        self.p3.addItem(self.line3)
        self.p3.setGeometry(self.p1.vb.sceneBoundingRect())
        
        self.p1.setXRange(0, self.xrange)    
        self.p1.setYRange(0, 1000)  #wichtig für axe 1
        self.p2.setYRange(0, 6000)  #axe 2 
        self.p3.setYRange(0, 1000)  #scaling kurve 3
        #self.ui.plotWidget_pump.showGrid(x=True, y=True)
        
        self.line2.setData(self.time, self.pumprpm_1)        
        self.line3.setData(self.time, self.pumpcurr_2)
        
        #######################################################
        
        
        self.ui.plotWidget_fans.setBackground("w") 
        #window.ui.plotWidget.setBackground('#393939')
        self.pw2 = self.ui.plotWidget_fans
        self.p1_2 = self.pw2.plotItem
        styles = {"color": "red", "font-size": "15px"}

        self.p1_2.setLabel('left', "Pwm (%)", **styles)

        self.p2_2 = pg.ViewBox()
        self.p1_2.showAxis('right')
        self.p1_2.scene().addItem(self.p2_2)
        self.p1_2.getAxis('right').linkToView(self.p2_2)
        self.p2_2.setXLink(self.p1_2)
        styles = {"color": "blue", "font-size": "15px"}
        self.p1_2.getAxis('right').setLabel('Rpm', **styles)

        #self.time = list(range(self.xrange))
        self.fanrpm = [0 for _ in range(self.xrange)]
        self.fanpwm = [0 for _ in range(self.xrange)]
        
        self.p3_2 = pg.ViewBox()
        self.p1_2.scene().addItem(self.p3_2)
        self.p3_2.setXLink(self.p1_2)

        self.line2_2 = pg.PlotCurveItem(self.time, self.fanrpm, pen='b')
        self.p2_2.addItem(self.line2_2)
        self.p2_2.setGeometry(self.p1_2.vb.sceneBoundingRect())
        
        self.line3_2 = pg.PlotCurveItem(self.time, self.fanpwm, pen='r')
        self.p3_2.addItem(self.line3_2)
        self.p3_2.setGeometry(self.p1_2.vb.sceneBoundingRect())
        
        self.p1_2.setXRange(0, self.xrange)    
        self.p1_2.setYRange(0, 100)  #wichtig für axe 1
        self.p2_2.setYRange(0, self.fan_limit)  #axe 2 
        self.p3_2.setYRange(0, 100)  #scaling kurve 3
        #self.ui.plotWidget_pump.showGrid(x=True, y=True)
        
        self.line2_2.setData(self.time, self.fanrpm)        
        self.line3_2.setData(self.time, self.fanpwm)
        
        #############################################################
        self.timer = QtCore.QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()
    
        #self.p1.plot(self.time, self.pumprpm_1)
    
    def update_plot(self):
        #global time, line2, line3
        self.time = self.time[1:]
        self.time.append(self.time[-1] + 1)
        self.pumprpm_1 = self.pumprpm_1[1:]
        self.pumpcurr_2 = self.pumpcurr_2[1:]
        
        self.fanrpm = self.fanrpm[1:]
        self.fanpwm = self.fanpwm[1:]
        

        self.pumprpm_1.append(self.sensor_pump_speed)
        self.pumpcurr_2.append(self.sensor_pump_curr * 1000)
        
        self.fanrpm.append(self.sensor_fan_speed)
        self.fanpwm.append(self.sensor_fan_pwm)
        
        
        self.p1.setXRange(self.time[0], self.time[self.xrange -1])
        self.line2.setData(self.time, self.pumprpm_1)        
        self.line3.setData(self.time, self.pumpcurr_2)
        self.p3.setGeometry(self.p1.vb.sceneBoundingRect())
        self.p2.setGeometry(self.p1.vb.sceneBoundingRect())
        
        self.p1_2.setXRange(self.time[0], self.time[self.xrange -1])
        self.line2_2.setData(self.time, self.fanrpm)        
        self.line3_2.setData(self.time, self.fanpwm)
        self.p3_2.setGeometry(self.p1_2.vb.sceneBoundingRect())
        self.p2_2.setGeometry(self.p1_2.vb.sceneBoundingRect())
# ###################################################################

   
    
    def get_and_save_reports_to_disk(self):
        ausgabefile = open(self.ui.lineEdit_ctrl_report_file_name.text() + "_control.bin", "bw")
        reportdaten = list(h.get_feature_report(AQUASTREAMXT_CTRL_FEATURE_REPORT_ID, AQUASTREAMXT_CTRL_REPORT_SIZE))    
        ausgabefile.write(bytes(reportdaten))
        ausgabefile.close()
        print("saved", self.ui.lineEdit_ctrl_report_file_name.text() + "_control.bin")
    
        ausgabefile = open(self.ui.lineEdit_ctrl_report_file_name.text() + "_sensor.bin", "bw")
        reportdaten = list(h.get_feature_report(AQUASTREAMXT_SENSOR_FEATURE_REPORT_ID, AQUASTREAMXT_SENSOR_REPORT_SIZE))  
        ausgabefile.write(bytes(reportdaten))
        ausgabefile.close()
        print("saved", self.ui.lineEdit_ctrl_report_file_name.text() + "_sensor.bin")
        
        
    def update_local_ctrl_report(self):
    
        # # BF   PumpMode pump_mode @ 0x3;
        # pump_mode_bf_offset_8 = 0x3
        # # le u16 pump_speed @ 0x8;
        # pump_speed_offset_16 = 0x08
        # # BF   AlarmConfiguration alarm_config @ 0xe;
        # alarm_config_bf_offset_8 = 0xe
        # # BF   SpeedSignalOutput speed_signal_out_mode @ 0xf;
        # speed_signal_out_mode_bf_offset_8 = 0xf
        # # le u24 alarm_flow_speed @ 0x12; 
        # alarm_flow_speed_offset_32 = 0x12
        # # le u16 alarm_external_temp @ 0x16;
        # alarm_external_temp_offset_16 = 0x16
        # # le u16 alarm_int_temp @ 0x18;
        # alarm_int_temp_offset_16 = 0x18
        # # BF   FanMode fan_mode @ 0x1a;
        # fan_mode_bf_offset_8 = 0x1a
        # # u8 fan_pwm @ 0x1b;
        # fan_pwm_offset_8 = 0x1b
        # # le u16 fan_hysteresis @ 0x1c;
        # fan_hysteresis_offset_16 = 0x1c
        # # u8 fan_temp_src @ 0x1e;
        # fan_temp_src_offset_8 = 0x1e
        # # le u16 fan_target_temp @ 0x1f;
        # fan_target_temp_offset_16 = 0x1f
        # # le u16 fan_p @ 0x21;
        # fan_p_offset_16 = 0x21
        # # le u16 fan_i @ 0x23;
        # fan_i_offset_16 = 0x23
        # # le u16 fan_d @ 0x25;
        # fan_d_offset_16 = 0x25
        # # le u16 fan_min_temp @ 0x27;
        # fan_min_temp_offset_16 = 0x27
        # # le u16 fan_max_temp @ 0x29;
        # fan_max_temp_offset_16 = 0x29
        # # u8 fan_min_pwm @ 0x2b;
        # fan_min_pwm_offset_8 = 0x2b
        # # u8 fan_max_pwm @ 0x2c;
        # fan_max_pwm_offset_8 = 0x2c
        # # le u16 pump_min_speed @ 0x2f;
        # pump_min_speed_offset_16 = 0x2f
        # # le u16 pump_max_speed @ 0x31;
        # pump_max_speed_offset_16 = 0x31
        
        # pump_mode_bf = b'0x00'
        self.ctrl_report[self.pump_mode_bf_offset_8] = self.pump_mode_bf
        # alarm_config_bf = 0
        self.ctrl_report[self.alarm_config_bf_offset_8] = self.alarm_config_bf
        # speed_signal_out_mode_bf = 0
        self.ctrl_report[self.speed_signal_out_mode_bf_offset_8] = self.speed_signal_out_mode_bf
        # fan_mode_bf = 0
        self.ctrl_report[self.fan_mode_bf_offset_8] = self.fan_mode_bf

        #write_int24_le(int24val, report, offset):
        # alarm_flow_speed = 0
        #write_int24_le(self.alarm_flow_speed, self.ctrl_report, self.alarm_flow_speed_offset_32)
        write_int32_le(self.alarm_flow_speed, self.ctrl_report, self.alarm_flow_speed_offset_32)
        # alarm_external_temp = 0
        write_int16_le(self.alarm_external_temp, self.ctrl_report, self.alarm_external_temp_offset_16)
        # alarm_int_temp = 0
        write_int16_le(self.alarm_int_temp, self.ctrl_report, self.alarm_int_temp_offset_16)
        
        
        #fan_hysteresis_offset_16 = 0x1c
        #fan_p_offset_16 = 0x21
        #fan_i_offset_16 = 0x23
        #fan_d_offset_16 = 0x25
        #fan_min_temp_offset_16 = 0x27
        #fan_max_temp_offset_16 = 0x29
        
        #PID
        # fan_hysteresis = 0
        write_int16_le(self.fan_hysteresis , self.ctrl_report, self.fan_hysteresis_offset_16)
        # fan_p = 0
        write_int16_le(self.fan_p , self.ctrl_report, self.fan_p_offset_16)
        # fan_i = 0
        write_int16_le(self.fan_i , self.ctrl_report, self.fan_i_offset_16)
        # fan_d = 0
        write_int16_le(self.fan_d , self.ctrl_report, self.fan_d_offset_16)
        # fan_min_temp = 0
        write_int16_le(self.fan_min_temp , self.ctrl_report, self.fan_min_temp_offset_16)
        # fan_max_temp = 0
        write_int16_le(self.fan_max_temp , self.ctrl_report, self.fan_max_temp_offset_16)
        
        #FANS
        #write_int16_le(self., self.ctrl_report, self.)
        # fan_target_temp = 0
        write_int16_le(self.fan_target_temp, self.ctrl_report, self.fan_target_temp_offset_16)
        # fan_pwm = 0
        self.ctrl_report[self.fan_pwm_offset_8] = int(self.fan_pwm * 2.55)
        # fan_temp_src = 0
        self.ctrl_report[self.fan_temp_src_offset_8] = self.fan_temp_src
        # fan_min_pwm = 0
        self.ctrl_report[self.fan_min_pwm_offset_8] = int(self.fan_min_pwm * 2.55)
        # fan_max_pwm = 0
        self.ctrl_report[self.fan_max_pwm_offset_8] = int(self.fan_max_pwm * 2.55)
        
        #PUMP
        # pump_speed = 0     
        write_int16_le(conv_rpm_to_raw_pump(self.pump_speed), self.ctrl_report, self.pump_speed_offset_16)
        # pump_min_speed = 0
        write_int16_le(conv_rpm_to_raw_pump(self.pump_min_speed), self.ctrl_report, self.pump_min_speed_offset_16)
        # pump_max_speed = 0
        write_int16_le(conv_rpm_to_raw_pump(self.pump_max_speed), self.ctrl_report, self.pump_max_speed_offset_16)
    
    
    
    def save_gui_values_into_local_vars(self):
        ###########    
        #PUMP           when setting pump speed manually its limited by max_speed value
        
        # self.pump_speed = conv_raw_to_rpm_pump(read_int16_le(self.ctrl_report, self.pump_speed_offset_16))
        self.pump_speed = self.ui.spinBox_pump_man_pump_rpm.value()  
        # self.pump_min_speed = conv_raw_to_rpm_pump(read_int16_le(self.ctrl_report, self.pump_min_speed_offset_16))
        self.pump_min_speed =  self.ui.spinBox_pump_auto_min.value()
        # self.pump_max_speed = conv_raw_to_rpm_pump(read_int16_le(self.ctrl_report, self.pump_max_speed_offset_16))
        
        #if (self.ui.radioButton_pump_manual.isChecked() == 1):
        #    self.pump_max_speed=6000
        #else:
            
        self.pump_max_speed = self.ui.spinBox_pump_auto_max.value()
        ###########    
        
        # self.bitfield_pump_mode_hold_min = get_bit(self.ctrl_report[self.pump_mode_bf_offset_8],self.bitfield_pump_mode_hold_min_offset)
        self.bitfield_pump_mode_hold_min = int(self.ui.checkBox_pump_auto_no_below.isChecked())
        # self.bitfield_pump_mode_auto_man = get_bit(self.ctrl_report[self.pump_mode_bf_offset_8],self.bitfield_pump_mode_auto_man_offset) 
        #auto = 1 / manual = 0)
        if (self.ui.radioButton_pump_auto.isChecked() == True):
            self.bitfield_pump_mode_auto_man = 1
        if (self.ui.radioButton_pump_manual.isChecked() == True):
            self.bitfield_pump_mode_auto_man = 0
        

        self.alarm_flow_speed = 3994070 / self.ui.spinBox_alarm_flow_min.value()   #3994128.7777    #3994070 fast
        #self.alarm_flow_speed = 3994070 / 0.01   #3994128.7777    #3994070 fast
        
        # self.alarm_external_temp = read_int16_le(self.ctrl_report, self.alarm_external_temp_offset_16)
        self.alarm_external_temp = self.ui.spinBox_alarm_ext_temp_max.value() * 100
        # self.alarm_int_temp = read_int16_le(self.ctrl_report, self.alarm_int_temp_offset_16)
        self.alarm_int_temp = self.ui.spinBox_alarm_int_temp_max.value() * 100

        #FANS
        # self.fan_pwm = int(self.ctrl_report[self.fan_pwm_offset_8] / 2.55)
        #0 - 100
        self.fan_pwm = self.ui.spinBox_fans_man.value() 
        # self.fan_temp_src = self.ctrl_report[self.fan_temp_src_offset_8]
        #self.fan_temp_src    #1 = ext  /   2 = int
        #if (self.fan_temp_src == 1):
        #    self.ui.radioButton_fans_auto_ext_temp.setChecked(True)
        #if (self.fan_temp_src == 2):
        #    self.ui.radioButton_fans_auto_int_temp.setChecked(True)    
        if (self.ui.radioButton_fans_auto_ext_temp.isChecked() == True):
            self.fan_temp_src = 1
        if (self.ui.radioButton_fans_auto_int_temp.isChecked() == True):
            self.fan_temp_src = 2
        # self.fan_target_temp = read_int16_le(self.ctrl_report, self.fan_target_temp_offset_16)
        self.fan_target_temp = self.ui.spinBox_fans_auto_target_temp.value() * 100
        # 0 - 100
        # self.fan_min_pwm = int(self.ctrl_report[self.fan_min_pwm_offset_8] / 2.55)
        self.fan_min_pwm = self.ui.spinBox_fans_auto_fans_min_hz.value() 
        # self.fan_max_pwm = int(self.ctrl_report[self.fan_max_pwm_offset_8] / 2.55)
        self.fan_max_pwm = self.ui.spinBox_fans_auto_fans_max_hz.value() 
        
        #PID
        # self.fan_hysteresis = aus gui auslesen
        # self.fan_p = 
        # self.fan_i = 
        # self.fan_d = 
        # self.fan_min_temp = 
        # self.fan_max_temp = 
        
        #-2
        if (self.ui.comboBox_fans_pid.currentIndex() == 0):
            self.fan_hysteresis = 200
            self.fan_p = 100
            self.fan_i = 25
            self.fan_d = 50
            self.fan_min_temp = 1800
            self.fan_max_temp = 3700
            print("Save PID -2")
        
        #-1
        if (self.ui.comboBox_fans_pid.currentIndex() == 1):
            self.fan_hysteresis = 200
            self.fan_p = 100    
            self.fan_i = 50
            self.fan_d = 50
            self.fan_min_temp = 1800
            self.fan_max_temp = 3700  
            print("Save PID -1")
        
        #normal
        if (self.ui.comboBox_fans_pid.currentIndex() == 2):
            self.fan_hysteresis = 100
            self.fan_p = 100
            self.fan_i = 100
            self.fan_d = 100
            self.fan_min_temp = 1900
            self.fan_max_temp = 3600
            print("Save PID +-0")
        #+1
        if (self.ui.comboBox_fans_pid.currentIndex() == 3):
            self.fan_hysteresis = 100
            self.fan_p = 2000
            self.fan_i = 200
            self.fan_d = 1000
            self.fan_min_temp = 1900
            self.fan_max_temp = 3600
            print("Save PID +1")
        #+2
        if (self.ui.comboBox_fans_pid.currentIndex() == 4):
            self.fan_hysteresis = 50
            self.fan_p = 4000
            self.fan_i = 500
            self.fan_d = 1000
            self.fan_min_temp = 1950
            self.fan_max_temp = 3550
            print("Save PID +2")
        
        # #bitfields
        # self.bitfield_alarm_configuration_external_temp = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_external_temp_offset)
        self.bitfield_alarm_configuration_external_temp = int(self.ui.checkBox_alarm_ext_temp.isChecked())
        # self.bitfield_alarm_configuration_int_temp = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_int_temp_offset)
        self.bitfield_alarm_configuration_int_temp = int(self.ui.checkBox_alarm_int_temp.isChecked())
        # self.bitfield_alarm_configuration_pump = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_pump_offset)
        self.bitfield_alarm_configuration_pump = int(self.ui.checkBox_alarm_pump.isChecked())
        # self.bitfield_alarm_configuration_fan_speed = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_fan_speed_offset)
        self.bitfield_alarm_configuration_fan_speed = int(self.ui.checkBox_alarm_fan_rpm.isChecked())
        # self.bitfield_alarm_configuration_flow_rate = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_flow_rate_offset)
        self.bitfield_alarm_configuration_flow_rate = int(self.ui.checkBox_alarm_flow.isChecked())
        # self.bitfield_alarm_configuration_output_overload = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_output_overload_offset)
        self.bitfield_alarm_configuration_output_overload = int(self.ui.checkBox_alarm_fan_overload.isChecked())
        # self.bitfield_alarm_configuration_amp_temp80 = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_amp_temp80_offset)
        self.bitfield_alarm_configuration_amp_temp80 = int(self.ui.checkBox_alarm_80.isChecked())
        # self.bitfield_alarm_configuration_amp_temp100 = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_amp_temp100_offset)
        self.bitfield_alarm_configuration_amp_temp100 = int(self.ui.checkBox_alarm_100.isChecked())
        
        # self.bitfield_speed_signal_output_fan_speed = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_fan_speed_offset)
        self.bitfield_speed_signal_output_fan_speed =  int(self.ui.radioButton_source_fan.isChecked())
        # self.bitfield_speed_signal_output_flow_sensor = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_flow_sensor_offset)
        self.bitfield_speed_signal_output_flow_sensor = int(self.ui.radioButton_source_flow.isChecked())
        # self.bitfield_speed_signal_output_pump_speed = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_pump_speed_offset)
        self.bitfield_speed_signal_output_pump_speed = int(self.ui.radioButton_source_pump.isChecked())
        # self.bitfield_speed_signal_output_static_speed = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_static_speed_offset)
        self.bitfield_speed_signal_output_static_speed = int(self.ui.radioButton_source_static.isChecked())
        # self.bitfield_speed_signal_output_switch_off_on_alarm = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_switch_off_on_alarm_offset)
        self.bitfield_speed_signal_output_switch_off_on_alarm = int(self.ui.checkBox_source_turn_off_when_alarm.isChecked())
    
        # self.bitfield_fan_mode_manual = get_bit(self.ctrl_report[self.fan_mode_bf_offset_8],self.bitfield_fan_mode_manual_offset)
        self.bitfield_fan_mode_manual = int(self.ui.radioButton_fans_man.isChecked())
        # self.bitfield_fan_mode_automatic = get_bit(self.ctrl_report[self.fan_mode_bf_offset_8],self.bitfield_fan_mode_automatic_offset)
        self.bitfield_fan_mode_automatic = int(self.ui.radioButton_fans_auto.isChecked())
        # self.bitfield_fan_mode_hold_min = get_bit(self.ctrl_report[self.fan_mode_bf_offset_8],self.bitfield_fan_mode_hold_min_offset)
        self.bitfield_fan_mode_hold_min = int(self.ui.checkBox_fans_auto_hold_min.isChecked())

        
        #dont touch it
        # self.bitfield_pump_mode_aquabus_flow = get_bit(self.ctrl_report[self.pump_mode_bf_offset_8],self.bitfield_pump_mode_aquabus_flow_offset)
        
        
        #self.alarm_config_bf
        # self.pump_mode_bf = self.ctrl_report[self.pump_mode_bf_offset_8]
        # self.alarm_config_bf = self.ctrl_report[self.alarm_config_bf_offset_8]
        # self.speed_signal_out_mode_bf = self.ctrl_report[self.speed_signal_out_mode_bf_offset_8]
        # self.fan_mode_bf = self.ctrl_report[self.fan_mode_bf_offset_8]
        
        # bitfield_alarm_configuration_external_temp_offset = 0
        # bitfield_alarm_configuration_int_temp_offset = 1
        # bitfield_alarm_configuration_pump_offset = 2
        # bitfield_alarm_configuration_fan_speed_offset = 3
        # bitfield_alarm_configuration_flow_rate_offset = 4
        # bitfield_alarm_configuration_output_overload_offset = 5
        # bitfield_alarm_configuration_amp_temp80_offset = 6
        # bitfield_alarm_configuration_amp_temp100_offset = 7
        
        # bitfield_alarm_configuration_external_temp = 0
        # bitfield_alarm_configuration_int_temp = 0
        # bitfield_alarm_configuration_pump = 0
        # bitfield_alarm_configuration_fan_speed = 0
        # bitfield_alarm_configuration_flow_rate = 0
        # bitfield_alarm_configuration_output_overload = 0
        # bitfield_alarm_configuration_amp_temp80 = 0
        # bitfield_alarm_configuration_amp_temp100 = 0
        
        self.alarm_config_bf = update_bit(self.alarm_config_bf, self.bitfield_alarm_configuration_external_temp_offset, self.bitfield_alarm_configuration_external_temp)
        self.alarm_config_bf = update_bit(self.alarm_config_bf, self.bitfield_alarm_configuration_int_temp_offset, self.bitfield_alarm_configuration_int_temp)
        self.alarm_config_bf = update_bit(self.alarm_config_bf, self.bitfield_alarm_configuration_pump_offset, self.bitfield_alarm_configuration_pump)
        self.alarm_config_bf = update_bit(self.alarm_config_bf, self.bitfield_alarm_configuration_fan_speed_offset, self.bitfield_alarm_configuration_fan_speed)
        self.alarm_config_bf = update_bit(self.alarm_config_bf, self.bitfield_alarm_configuration_flow_rate_offset, self.bitfield_alarm_configuration_flow_rate)
        self.alarm_config_bf = update_bit(self.alarm_config_bf, self.bitfield_alarm_configuration_output_overload_offset, self.bitfield_alarm_configuration_output_overload)
        self.alarm_config_bf = update_bit(self.alarm_config_bf, self.bitfield_alarm_configuration_amp_temp80_offset, self.bitfield_alarm_configuration_amp_temp80)
        self.alarm_config_bf = update_bit(self.alarm_config_bf, self.bitfield_alarm_configuration_amp_temp100_offset, self.bitfield_alarm_configuration_amp_temp100)
        
        
        #self.speed_signal_out_mode_bf
        # bitfield_speed_signal_output_fan_speed_offset = 0
        # bitfield_speed_signal_output_flow_sensor_offset = 1
        # bitfield_speed_signal_output_pump_speed_offset = 2
        # bitfield_speed_signal_output_static_speed_offset = 3
        # bitfield_speed_signal_output_switch_off_on_alarm_offset = 4

        # bitfield_speed_signal_output_fan_speed = 0
        # bitfield_speed_signal_output_flow_sensor = 0
        # bitfield_speed_signal_output_pump_speed = 0
        # bitfield_speed_signal_output_static_speed = 0
        # bitfield_speed_signal_output_switch_off_on_alarm = 0    
        
        self.speed_signal_out_mode_bf = update_bit(self.speed_signal_out_mode_bf, self.bitfield_speed_signal_output_fan_speed_offset, self.bitfield_speed_signal_output_fan_speed)
        
        #!! flowrate as RPM output does not work for me and doesnt even work with windows + official software
        self.speed_signal_out_mode_bf = update_bit(self.speed_signal_out_mode_bf, self.bitfield_speed_signal_output_flow_sensor_offset, self.bitfield_speed_signal_output_flow_sensor)
        
        self.speed_signal_out_mode_bf = update_bit(self.speed_signal_out_mode_bf, self.bitfield_speed_signal_output_pump_speed_offset, self.bitfield_speed_signal_output_pump_speed)
        self.speed_signal_out_mode_bf = update_bit(self.speed_signal_out_mode_bf, self.bitfield_speed_signal_output_static_speed_offset, self.bitfield_speed_signal_output_static_speed)
        self.speed_signal_out_mode_bf = update_bit(self.speed_signal_out_mode_bf, self.bitfield_speed_signal_output_switch_off_on_alarm_offset, self.bitfield_speed_signal_output_switch_off_on_alarm)

        
        #self.fan_mode_bf
        # bitfield_fan_mode_manual_offset = 0
        # bitfield_fan_mode_automatic_offset = 1
        # bitfield_fan_mode_hold_min_offset = 2

        # bitfield_fan_mode_manual = 0
        # bitfield_fan_mode_automatic = 0
        # bitfield_fan_mode_hold_min = 0
        
        self.fan_mode_bf = update_bit(self.fan_mode_bf, self.bitfield_fan_mode_manual_offset, self.bitfield_fan_mode_manual)
        self.fan_mode_bf = update_bit(self.fan_mode_bf, self.bitfield_fan_mode_automatic_offset, self.bitfield_fan_mode_automatic)
        self.fan_mode_bf = update_bit(self.fan_mode_bf, self.bitfield_fan_mode_hold_min_offset, self.bitfield_fan_mode_hold_min)
        
        # self.pump_mode_bf
        # bitfield_pump_mode_hold_min_offset = 5
        # bitfield_pump_mode_aquabus_flow_offset = 4
        # bitfield_pump_mode_auto_man_offset = 1
        
        # bitfield_pump_mode_hold_min = 0
        # bitfield_pump_mode_aquabus_flow = 0
        # bitfield_pump_mode_auto_man = 0
        
        self.pump_mode_bf = update_bit( self.pump_mode_bf, self.bitfield_pump_mode_hold_min_offset, self.bitfield_pump_mode_hold_min)
        self.pump_mode_bf = update_bit( self.pump_mode_bf, self.bitfield_pump_mode_aquabus_flow_offset, self.bitfield_pump_mode_aquabus_flow)
        self.pump_mode_bf = update_bit( self.pump_mode_bf, self.bitfield_pump_mode_auto_man_offset, self.bitfield_pump_mode_auto_man)
    
    
    def save_to_pump(self):
        
        print("save to pump")
        
        #reason for this is if you click multiple times on save to pump button it will start the process as often as you have clicked.
        #now these extra clicks go into nirvana (on the disabled buttons) 
        
        self.ui.pushButton_pump_save_to_pump.blockSignals(True)
        self.ui.pushButton_fans_save_to_pump.blockSignals(True)
        self.ui.pushButton_settings_save_to_pump.blockSignals(True)
        #self.ui.pushButton_pump_save_to_pump.disconnect(self.save_to_pump)
        #self.ui.pushButton_fans_save_to_pump.disconnect(self.save_to_pump)
        #self.ui.pushButton_settings_save_to_pump.disconnect(self.save_to_pump)
        
        self.ui.pushButton_pump_save_to_pump.setDisabled(True)
        self.ui.pushButton_fans_save_to_pump.setDisabled(True)
        self.ui.pushButton_settings_save_to_pump.setDisabled(True)
 
        self.ui.pushButton_pump_save_to_pump.repaint()
        self.ui.pushButton_fans_save_to_pump.repaint()
        self.ui.pushButton_settings_save_to_pump.repaint()
        
        app.processEvents()  
 
        self.save_gui_values_into_local_vars()   #gui -> local vars
        
        
        self.update_local_ctrl_report()   #new local vars -> local ctrl_report
        self.print_data()
        
        ##############################################  HID Transfer #  local ctrl_report -> via usb to pump
        #sensorthread.sensor_hid_active = 0
        #sensorthread.main_hid_active = 0
    
        sensorthread.main_hid_active = 1
 
        while (sensorthread.sensor_hid_active == 1):
            time.sleep(0.2)
            
        try:
            h.send_feature_report(bytes(self.ctrl_report))
        except:
            print("hid error send ctrl report")
            
        try:
            h.send_feature_report(bytes(sec_ctrl_report))
        except:
            print("hid error send sec ctrl report")
        
        print("report sended")
        
        #time.sleep(1)
        
        #########
        try:
            self.get_report_and_update_local_vars()
        except:
            print("hid error get ctrl report")
            
        self.update_gui_from_local_vars()
        print("report loaded")
 
        sensorthread.main_hid_active = 0
        ########################################## Hid transfer end
        
        
        self.timer2 = QtCore.QTimer()
        self.timer2.setInterval(10)
        self.timer2.timeout.connect(self.enable_pump_buttons)
        self.timer2.start()
        #self.enable_pump_buttons()
        
    def enable_pump_buttons(self):    ##reason for this is if you click multiple times on save to pump button it will start the process as often as you have clicked.
                                        ## now these extra clicks go into nirvana (on the disabled buttons) 
        self.ui.pushButton_pump_save_to_pump.setEnabled(True)
        self.ui.pushButton_fans_save_to_pump.setEnabled(True)
        self.ui.pushButton_settings_save_to_pump.setEnabled(True)
        
        self.ui.pushButton_pump_save_to_pump.blockSignals(False)
        self.ui.pushButton_fans_save_to_pump.blockSignals(False)
        self.ui.pushButton_settings_save_to_pump.blockSignals(False)
        
        self.ui.pushButton_pump_save_to_pump.repaint()
        self.ui.pushButton_fans_save_to_pump.repaint()
        self.ui.pushButton_settings_save_to_pump.repaint()
        
        #self.timer2.stop()
        
        
    def spinBox_settings_ext_offset_valueChanged(self):
        self.ext_temp_offset = self.ui.spinBox_settings_ext_offset.value()
        
        
    def spinBox_settings_int_offset_valueChanged(self):
        self.int_temp_offset = self.ui.spinBox_settings_int_offset.value()       
        
    
    def spinBox_settings_flow_calib_valueChanged(self):
        self.cal_imp_per_liter=self.ui.spinBox_settings_flow_calib.value()
        
    
    ###SYNC fans man
    def sync_fans_man_hz(self):
        self.ui.horizontalSlider_fans_man.setValue(self.ui.spinBox_fans_man.value())
    
    def sync_fans_man_slider(self):
        self.ui.spinBox_fans_man.setValue(self.ui.horizontalSlider_fans_man.value())
    
    ###SYNC Fans auto max
    def sync_fans_auto_max_hz(self):
        self.ui.horizontalSlider_fans_auto_max.setValue(self.ui.spinBox_fans_auto_fans_max_hz.value())
        self.ui.horizontalSlider_fans_auto_min.setMaximum(self.ui.spinBox_fans_auto_fans_max_hz.value())
    
    def sync_fans_auto_max_slider(self):
        self.ui.spinBox_fans_auto_fans_max_hz.setValue(self.ui.horizontalSlider_fans_auto_max.value())
        self.ui.horizontalSlider_fans_auto_min.setMaximum(self.ui.horizontalSlider_fans_auto_max.value())
        
    ###SYNC Fans auto min
    def sync_fans_auto_min_hz(self):
        self.ui.horizontalSlider_fans_auto_min.setValue(self.ui.spinBox_fans_auto_fans_min_hz.value() )
        self.ui.horizontalSlider_fans_auto_max.setMinimum(self.ui.spinBox_fans_auto_fans_min_hz.value())
    
    def sync_fans_auto_min_slider(self):
        self.ui.spinBox_fans_auto_fans_min_hz.setValue(self.ui.horizontalSlider_fans_auto_min.value() )
        self.ui.horizontalSlider_fans_auto_max.setMinimum(self.ui.horizontalSlider_fans_auto_min.value() )
    
    ####SYNC pump man min
    
    # def sync_pump_man_min_value(self):
        # #self.ui.spinBox_pump_man_min.setValue(
        # self.ui.spinBox_pump_man_min_hz.setValue(int(self.ui.spinBox_pump_man_min.value() / 60))
        # self.ui.horizontalSlider_pump_man_min.setValue(self.ui.spinBox_pump_man_min.value())
    
    # def sync_pump_man_min_hz(self):
        # self.ui.spinBox_pump_man_min.setValue(int(self.ui.spinBox_pump_man_min_hz.value()*60))
        # #self.ui.spinBox_pump_man_min_hz.setValue(
        # self.ui.horizontalSlider_pump_man_min.setValue(int(self.ui.spinBox_pump_man_min_hz.value()*60))
    
    # def sync_pump_man_min_slider(self):
        # self.ui.spinBox_pump_man_min.setValue(self.ui.horizontalSlider_pump_man_min.value())
        # self.ui.spinBox_pump_man_min_hz.setValue(int(self.ui.horizontalSlider_pump_man_min.value() / 60))
        # #self.ui.horizontalSlider_pump_man_min.setValue(    
    
    #####SYNC pump man value
    def sync_pump_man_pump_value(self):
        #self.ui.spinBox_pump_man_pump_rpm.setValue(
        self.ui.spinBox_pump_man_pump_rpm_hz.setValue(int(self.ui.spinBox_pump_man_pump_rpm.value() / 60))
        self.ui.horizontalSlider_pump_man_pump_rpm.setValue(self.ui.spinBox_pump_man_pump_rpm.value())
        #auto
        self.ui.horizontalSlider_pump_auto_max.setValue(self.ui.horizontalSlider_pump_man_pump_rpm.value())
    
    def sync_pump_man_pump_hz(self):
        self.ui.spinBox_pump_man_pump_rpm.setValue(self.ui.spinBox_pump_man_pump_rpm_hz.value() * 60)
        #self.ui.spinBox_pump_man_pump_rpm_hz.setValue(
        self.ui.horizontalSlider_pump_man_pump_rpm.setValue( self.ui.spinBox_pump_man_pump_rpm_hz.value()*60)   
        #auto
        self.ui.horizontalSlider_pump_auto_max.setValue(self.ui.horizontalSlider_pump_man_pump_rpm.value())
        
    def sync_man_pump_slider(self):
        self.ui.spinBox_pump_man_pump_rpm.setValue(self.ui.horizontalSlider_pump_man_pump_rpm.value())
        self.ui.spinBox_pump_man_pump_rpm_hz.setValue(int(self.ui.horizontalSlider_pump_man_pump_rpm.value() / 60))
        #self.ui.horizontalSlider_pump_man_pump_rpm.setValue(    
        #auto
        self.ui.horizontalSlider_pump_auto_max.setValue(self.ui.horizontalSlider_pump_man_pump_rpm.value())
    
    
     ##### SYNC pump auto max rpm
    def sync_pump_auto_max_value(self):
        self.ui.horizontalSlider_pump_auto_max.setValue(self.ui.spinBox_pump_auto_max.value())
        self.ui.spinBox_pump_auto_max_hz.setValue(int(self.ui.spinBox_pump_auto_max.value() / 60))
        #man
        self.ui.horizontalSlider_pump_man_pump_rpm.setValue(self.ui.horizontalSlider_pump_auto_max.value())
        
        
    def sync_pump_auto_max_hz(self):
        self.ui.horizontalSlider_pump_auto_max.setValue(self.ui.spinBox_pump_auto_max_hz.value() * 60)
        self.ui.spinBox_pump_auto_max.setValue(self.ui.spinBox_pump_auto_max_hz.value()*60 )
        #man
        self.ui.horizontalSlider_pump_man_pump_rpm.setValue(self.ui.horizontalSlider_pump_auto_max.value())
        
    def sync_pump_auto_max_slider(self):
        self.ui.spinBox_pump_auto_max_hz.setValue(int(self.ui.horizontalSlider_pump_auto_max.value() / 60))
        self.ui.spinBox_pump_auto_max.setValue(self.ui.horizontalSlider_pump_auto_max.value())  
        #man
        self.ui.horizontalSlider_pump_man_pump_rpm.setValue(self.ui.horizontalSlider_pump_auto_max.value())
        #max
        self.ui.horizontalSlider_pump_auto_min.setMaximum(self.ui.horizontalSlider_pump_auto_max.value())
    
    ##### SYNC pump auto min rpm
    def sync_pump_auto_min_value(self):
        self.ui.horizontalSlider_pump_auto_min.setValue(self.ui.spinBox_pump_auto_min.value())
        self.ui.spinBox_pump_auto_min_hz.setValue(int(self.ui.spinBox_pump_auto_min.value() / 60))
        
    def sync_pump_auto_min_hz(self):
        self.ui.horizontalSlider_pump_auto_min.setValue(self.ui.spinBox_pump_auto_min_hz.value() * 60)
        self.ui.spinBox_pump_auto_min.setValue(self.ui.spinBox_pump_auto_min_hz.value()*60 )
        
    def sync_pump_auto_min_slider(self):
        self.ui.spinBox_pump_auto_min_hz.setValue(int(self.ui.horizontalSlider_pump_auto_min.value() / 60))
        self.ui.spinBox_pump_auto_min.setValue(self.ui.horizontalSlider_pump_auto_min.value())
        #min
        self.ui.horizontalSlider_pump_auto_max.setMinimum(self.ui.horizontalSlider_pump_auto_min.value())
    
    #######################################
    
    # def sync_dont_go_below_pump_checkstate_man(self):
        # if (self.ui.checkBox_pump_man_no_below.isChecked() == True):
            # self.ui.checkBox_pump_man_no_below.setChecked(True)
            # self.ui.checkBox_pump_auto_no_below.setChecked(True)
        
        # if (self.ui.checkBox_pump_man_no_below.isChecked() == False):
            # self.ui.checkBox_pump_man_no_below.setChecked(False)
            # self.ui.checkBox_pump_auto_no_below.setChecked(False)
        
    # def sync_dont_go_below_pump_checkstate_auto(self): 
        # if (self.ui.checkBox_pump_auto_no_below.isChecked() == True):
            # self.ui.checkBox_pump_man_no_below.setChecked(True)
            # self.ui.checkBox_pump_auto_no_below.setChecked(True)
        
        # if (self.ui.checkBox_pump_auto_no_below.isChecked() == False):
            # self.ui.checkBox_pump_man_no_below.setChecked(False)
            # self.ui.checkBox_pump_auto_no_below.setChecked(False)
    
    
    def hit_radio_fans_auto(self):
        self.ui.stackedWidget_fans.setCurrentWidget(self.ui.page_fans_auto)
        
    def hit_radio_fans_manual(self):
        self.ui.stackedWidget_fans.setCurrentWidget(self.ui.page_fans_manual)        
    
    
    def hit_radio_pump_auto(self):
        #self.new = 1
        self.ui.stackedWidget_pump.setCurrentWidget(self.ui.page_pump_auto)
        
        #if (self.pump_max_speed_saved != 0):
        #    self.ui.spinBox_pump_auto_max.setValue(self.pump_max_speed_saved)
        #else:
        #    self.pump_max_speed_saved = self.ui.spinBox_pump_auto_max.value()
        
        #print("self.pump_max_speed auto " + str(self.ui.spinBox_pump_auto_max.value()))
        
    def hit_radio_pump_manual(self):
        self.ui.stackedWidget_pump.setCurrentWidget(self.ui.page_pump_manual)
        
        #if (self.new == 1):
        #    self.new = 0
        #    self.pump_max_speed_saved = self.ui.spinBox_pump_auto_max.value()
        
        #self.ui.spinBox_pump_auto_max.setValue(6000)  #even on manual mode it limits the speed setting
        
        #print("self.pump_max_speed man " + str(self.ui.spinBox_pump_auto_max.value()))

        
    def extempenable_changed(self):
        if (self.ui.checkBox_extempenable.isChecked() == True ):  
            self.ui.lineEdit_ext_temp.setEnabled(1)
            self.ui.lineEdit_ext_temp.setText(str(self.sensor_temp_sensor_ext))
            
        if (self.ui.checkBox_extempenable.isChecked() == False ):
            self.ui.lineEdit_ext_temp.setEnabled(0)
            self.ui.lineEdit_ext_temp.setText("")
            
    def flowenable_changed(self):
        if (self.ui.checkBox_flowenable.isChecked() == True ):  
            self.ui.lineEdit_flow.setEnabled(1)
            self.ui.lineEdit_flow.setText(str(self.flow_sensor_l_p_h))
            
        if (self.ui.checkBox_flowenable.isChecked() == False ):
            self.ui.lineEdit_flow.setEnabled(0)
            self.ui.lineEdit_flow.setText("")
        
    def button_1(self):     #Sensors
        #print("button1")
        self.ui.stackedWidget_1.setCurrentWidget(self.ui.page_1)
        self.ui.pushButton_1.setDefault(1)
        self.ui.pushButton_2.setDefault(0)
        self.ui.pushButton_3.setDefault(0)
        self.ui.pushButton_4.setDefault(0)
        self.ui.pushButton_1.setFont(self.boldfont)
        self.ui.pushButton_2.setFont(self.stdfont)
        self.ui.pushButton_3.setFont(self.stdfont)
        self.ui.pushButton_4.setFont(self.stdfont)
        
        
    def button_2(self):     #Pump
        #print("button2")
        self.ui.stackedWidget_1.setCurrentWidget(self.ui.page_2)
        self.ui.pushButton_1.setDefault(0)
        self.ui.pushButton_2.setDefault(1)
        self.ui.pushButton_3.setDefault(0)
        self.ui.pushButton_4.setDefault(0)
        self.ui.pushButton_1.setFont(self.stdfont)
        self.ui.pushButton_2.setFont(self.boldfont)
        self.ui.pushButton_3.setFont(self.stdfont)
        self.ui.pushButton_4.setFont(self.stdfont)
        
    def button_3(self):     #Fans
        #print("button3")
        self.ui.stackedWidget_1.setCurrentWidget(self.ui.page_3)
        self.ui.pushButton_1.setDefault(0)
        self.ui.pushButton_2.setDefault(0)
        self.ui.pushButton_3.setDefault(1)
        self.ui.pushButton_4.setDefault(0)
        self.ui.pushButton_1.setFont(self.stdfont)
        self.ui.pushButton_2.setFont(self.stdfont)
        self.ui.pushButton_3.setFont(self.boldfont)
        self.ui.pushButton_4.setFont(self.stdfont)        
        
    def button_4(self):     #Settings
        #print("button4")
        self.ui.stackedWidget_1.setCurrentWidget(self.ui.page_4)
        self.ui.pushButton_1.setDefault(0)
        self.ui.pushButton_2.setDefault(0)
        self.ui.pushButton_3.setDefault(0)
        self.ui.pushButton_4.setDefault(1)
        self.ui.pushButton_1.setFont(self.stdfont)
        self.ui.pushButton_2.setFont(self.stdfont)
        self.ui.pushButton_3.setFont(self.stdfont)
        self.ui.pushButton_4.setFont(self.boldfont)        
        
    def get_report_and_update_local_vars(self):
    
        self.ctrl_report = list(h.get_feature_report(AQUASTREAMXT_CTRL_FEATURE_REPORT_ID, AQUASTREAMXT_CTRL_REPORT_SIZE))   
        
        self.pump_mode_bf = self.ctrl_report[self.pump_mode_bf_offset_8]
        self.alarm_config_bf = self.ctrl_report[self.alarm_config_bf_offset_8]
        self.speed_signal_out_mode_bf = self.ctrl_report[self.speed_signal_out_mode_bf_offset_8]
        self.fan_mode_bf = self.ctrl_report[self.fan_mode_bf_offset_8]
        self.alarm_flow_speed = read_int32_le(self.ctrl_report, self.alarm_flow_speed_offset_32)
        #self.alarm_flow_speed = read_int24_le(self.ctrl_report, self.alarm_flow_speed_offset_32)
        self.alarm_external_temp = read_int16_le(self.ctrl_report, self.alarm_external_temp_offset_16)
        self.alarm_int_temp = read_int16_le(self.ctrl_report, self.alarm_int_temp_offset_16)
        self.fan_pwm = int(self.ctrl_report[self.fan_pwm_offset_8] / 2.54)
        self.fan_temp_src = self.ctrl_report[self.fan_temp_src_offset_8]
        self.fan_target_temp = read_int16_le(self.ctrl_report, self.fan_target_temp_offset_16)
        self.fan_hysteresis = read_int16_le(self.ctrl_report, self.fan_hysteresis_offset_16)
        self.fan_p = read_int16_le(self.ctrl_report, self.fan_p_offset_16)
        self.fan_i = read_int16_le(self.ctrl_report, self.fan_i_offset_16)
        self.fan_d = read_int16_le(self.ctrl_report, self.fan_d_offset_16)
        self.fan_min_temp = read_int16_le(self.ctrl_report, self.fan_min_temp_offset_16)
        self.fan_max_temp = read_int16_le(self.ctrl_report, self.fan_max_temp_offset_16)
        self.fan_min_pwm = int(self.ctrl_report[self.fan_min_pwm_offset_8] / 2.54)
        self.fan_max_pwm = int(self.ctrl_report[self.fan_max_pwm_offset_8] / 2.53)
        
        self.pump_min_speed = conv_raw_to_rpm_pump(read_int16_le(self.ctrl_report, self.pump_min_speed_offset_16))
        self.pump_max_speed = conv_raw_to_rpm_pump(read_int16_le(self.ctrl_report, self.pump_max_speed_offset_16))        
        self.pump_speed = conv_raw_to_rpm_pump(read_int16_le(self.ctrl_report, self.pump_speed_offset_16))        

        
        #bitfields
        self.bitfield_alarm_configuration_external_temp = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_external_temp_offset)
        self.bitfield_alarm_configuration_int_temp = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_int_temp_offset)
        self.bitfield_alarm_configuration_pump = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_pump_offset)
        self.bitfield_alarm_configuration_fan_speed = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_fan_speed_offset)
        self.bitfield_alarm_configuration_flow_rate = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_flow_rate_offset)
        self.bitfield_alarm_configuration_output_overload = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_output_overload_offset)
        self.bitfield_alarm_configuration_amp_temp80 = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_amp_temp80_offset)
        self.bitfield_alarm_configuration_amp_temp100 = get_bit(self.ctrl_report[self.alarm_config_bf_offset_8],self.bitfield_alarm_configuration_amp_temp100_offset)
        
        self.bitfield_speed_signal_output_fan_speed = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_fan_speed_offset)
        self.bitfield_speed_signal_output_flow_sensor = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_flow_sensor_offset)
        self.bitfield_speed_signal_output_pump_speed = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_pump_speed_offset)
        self.bitfield_speed_signal_output_static_speed = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_static_speed_offset)
        self.bitfield_speed_signal_output_switch_off_on_alarm = get_bit(self.ctrl_report[self.speed_signal_out_mode_bf_offset_8],self.bitfield_speed_signal_output_switch_off_on_alarm_offset)
    
        self.bitfield_fan_mode_manual = get_bit(self.ctrl_report[self.fan_mode_bf_offset_8],self.bitfield_fan_mode_manual_offset)
        self.bitfield_fan_mode_automatic = get_bit(self.ctrl_report[self.fan_mode_bf_offset_8],self.bitfield_fan_mode_automatic_offset)
        self.bitfield_fan_mode_hold_min = get_bit(self.ctrl_report[self.fan_mode_bf_offset_8],self.bitfield_fan_mode_hold_min_offset)
    
        self.bitfield_pump_mode_hold_min = get_bit(self.ctrl_report[self.pump_mode_bf_offset_8],self.bitfield_pump_mode_hold_min_offset)
        self.bitfield_pump_mode_aquabus_flow = get_bit(self.ctrl_report[self.pump_mode_bf_offset_8],self.bitfield_pump_mode_aquabus_flow_offset)
        self.bitfield_pump_mode_auto_man = get_bit(self.ctrl_report[self.pump_mode_bf_offset_8],self.bitfield_pump_mode_auto_man_offset)
    

    
    def print_data(self):
        
        print("##### CONTROL REPORT #####")
        print("pump_mode_bf", "{:08b}".format(self.pump_mode_bf))
        print("alarm_config_bf", "{:08b}".format(self.alarm_config_bf))
        print("speed_signal_out_mode_bf", "{:08b}".format(self.speed_signal_out_mode_bf))
        print("fan_mode_bf", "{:08b}".format(self.fan_mode_bf))
        print("alarm_flow_speed_le_32bit", int(self.alarm_flow_speed), hex(int(self.alarm_flow_speed)), "-- ",self.ui.spinBox_alarm_flow_min.value(),  str([hex(x) for x in self.ctrl_report[0x12:0x16]]))
        print("alarm_external_temp", self.alarm_external_temp)
        print("alarm_int_temp", self.alarm_int_temp)
        print("fan_hysteresis", self.fan_hysteresis)
        print("fan_p", self.fan_p)
        print("fan_i", self.fan_i)
        print("fan_d", self.fan_d)
        print("fan_min_temp", self.fan_min_temp)
        print("fan_max_temp", self.fan_max_temp)
        print("fan_pwm manual", self.fan_pwm)
        print("fan_temp_src", self.fan_temp_src)
        print("fan_target_temp", self.fan_target_temp)
        print("fan_min_pwm", self.fan_min_pwm)
        print("fan_max_pwm", self.fan_max_pwm)
        print("pump_speed", self.pump_speed)
        print("pump_min_speed", self.pump_min_speed)
        print("pump_max_speed", self.pump_max_speed)
        print("bitfield_alarm_configuration_external_temp", self.bitfield_alarm_configuration_external_temp)
        print("bitfield_alarm_configuration_int_temp", self.bitfield_alarm_configuration_int_temp)
        print("bitfield_alarm_configuration_pump", self.bitfield_alarm_configuration_pump)
        print("bitfield_alarm_configuration_fan_speed", self.bitfield_alarm_configuration_fan_speed)
        print("bitfield_alarm_configuration_flow_rate", self.bitfield_alarm_configuration_flow_rate)
        print("bitfield_alarm_configuration_output_overload", self.bitfield_alarm_configuration_output_overload)
        print("bitfield_alarm_configuration_amp_temp80", self.bitfield_alarm_configuration_amp_temp80)
        print("bitfield_alarm_configuration_amp_temp100", self.bitfield_alarm_configuration_amp_temp100)
        print("bitfield_speed_signal_output_fan_speed", self.bitfield_speed_signal_output_fan_speed)
        print("bitfield_speed_signal_output_flow_sensor", self.bitfield_speed_signal_output_flow_sensor)
        print("bitfield_speed_signal_output_pump_speed", self.bitfield_speed_signal_output_pump_speed)
        print("bitfield_speed_signal_output_static_speed", self.bitfield_speed_signal_output_static_speed)
        print("bitfield_speed_signal_output_switch_off_on_alarm", self.bitfield_speed_signal_output_switch_off_on_alarm)
        print("bitfield_fan_mode_manual", self.bitfield_fan_mode_manual)
        print("bitfield_fan_mode_automatic", self.bitfield_fan_mode_automatic)
        print("bitfield_fan_mode_hold_min", self.bitfield_fan_mode_hold_min)
        print("bitfield_pump_mode_hold_min", self.bitfield_pump_mode_hold_min)
        print("bitfield_pump_mode_aquabus_flow", self.bitfield_pump_mode_aquabus_flow, "flow = 0 / aquabus = 1")
        print("bitfield_pump_mode_auto_man", self.bitfield_pump_mode_auto_man, "auto = 1, man = 0")
        print("##########################################")
        
    def print_ctrl_report(self):
        self.get_report_and_update_local_vars()
        self.print_data()       #from local vars
            
    
    def print_sensor_report(self):
        sensorthread.get_new_sensor_data()
        sensorthread.print_data() #from local vars in sensorthread 

                
    def load_settings(self): 
        
        #Sensors 
        self.ui.checkBox_flowenable.setChecked( eval( root.find('sensors/checkBox_flowenable').get('val')))
        self.ui.checkBox_extempenable.setChecked( eval( root.find('sensors/checkBox_extempenable').get('val')))
        
        #Settings
        self.ui.spinBox_settings_flow_calib.setValue(int(  root.find('settings/flow_sensor_calib').get('val')))
        self.flow_sensor_calib = int(  root.find('settings/flow_sensor_calib').get('val'))
        
        self.ui.spinBox_settings_ext_offset.setValue(int(  root.find('settings/ext_temp_offset').get('val')))
        self.ext_temp_offset = int(  root.find('settings/ext_temp_offset').get('val'))
        
        self.ui.spinBox_settings_int_offset.setValue(int(  root.find('settings/int_temp_offset').get('val')))
        self.int_temp_offset = int(  root.find('settings/int_temp_offset').get('val'))
        
    def save_settings(self):
        #Sensors
        root.find('sensors/checkBox_flowenable').set('val', str(bool(self.ui.checkBox_flowenable.isChecked())))
        root.find('sensors/checkBox_extempenable').set('val', str(bool(self.ui.checkBox_extempenable.isChecked())))
        #Settings
        root.find('settings/flow_sensor_calib').set('val', str(self.ui.spinBox_settings_flow_calib.value()))
        root.find('settings/ext_temp_offset').set('val', str(self.ui.spinBox_settings_ext_offset.value()))
        root.find('settings/int_temp_offset').set('val', str(self.ui.spinBox_settings_int_offset.value()))
        
    def update_gui_from_local_vars(self):

        #PUMP
        ############################AUTOMATIC
        #auto self.pump_min_speed
        #box
        self.ui.spinBox_pump_auto_min.setValue(self.pump_min_speed)
        #hz
        self.ui.spinBox_pump_auto_min_hz.setValue(int(self.pump_min_speed / 60))
        #slider
        self.ui.horizontalSlider_pump_auto_min.setValue(self.pump_min_speed)

        ##auto self.pump_max_speed
        #box
        self.ui.spinBox_pump_auto_max.setValue(self.pump_max_speed)
        #hz
        self.ui.spinBox_pump_auto_max_hz.setValue(int(self.pump_max_speed / 60))
        #slider 
        self.ui.horizontalSlider_pump_auto_max.setValue(self.pump_max_speed)
        
        ##############################MANUAL
        #man self.pump_speed
        #box
        self.ui.spinBox_pump_man_pump_rpm.setValue(self.pump_speed)
        #hz
        self.ui.spinBox_pump_man_pump_rpm_hz.setValue(int(self.pump_speed / 60))
        #slider
        self.ui.horizontalSlider_pump_man_pump_rpm.setValue(self.pump_speed)
        
        #man self.pump_min_speed
        #box
        #self.ui.spinBox_pump_man_min.setValue(self.pump_min_speed)
        #hz
        #self.ui.spinBox_pump_man_min_hz.setValue(int(self.pump_min_speed / 60))
        #slider
        #self.ui.horizontalSlider_pump_man_min.setValue(self.pump_min_speed)
        ########################
           
        #self.bitfield_pump_mode_hold_min
        #self.ui.checkBox_pump_man_no_below.setChecked(self.bitfield_pump_mode_hold_min)
        self.ui.checkBox_pump_auto_no_below.setChecked(self.bitfield_pump_mode_hold_min)
        
        #self.bitfield_pump_mode_auto_man
        if (self.bitfield_pump_mode_auto_man == 1):
            self.ui.radioButton_pump_auto.setChecked(1)
            self.ui.radioButton_pump_manual.setChecked(0)
            self.ui.stackedWidget_pump.setCurrentWidget(self.ui.page_pump_auto)
        if (self.bitfield_pump_mode_auto_man == 0):
            self.ui.radioButton_pump_auto.setChecked(0)
            self.ui.radioButton_pump_manual.setChecked(1)
            self.ui.stackedWidget_pump.setCurrentWidget(self.ui.page_pump_manual)
        
        
                
        #FANS
        #self.fan_pwm 100  ?? manual?
        self.ui.spinBox_fans_man.setValue(self.fan_pwm)
        #self.fan_temp_src    #1 = ext  /   2 = int
        if (self.fan_temp_src == 1):
            self.ui.radioButton_fans_auto_ext_temp.setChecked(True)
        if (self.fan_temp_src == 2):
            self.ui.radioButton_fans_auto_int_temp.setChecked(True)
        #self.fan_target_temp
        self.ui.spinBox_fans_auto_target_temp.setValue(int(self.fan_target_temp/100))
        
        #PID 
        #self.fan_hysteresis 100
        #self.fan_p
        #self.fan_i
        #self.fan_d
        #self.fan_min_temp     
        #self.fan_max_temp 
        if ( (self.fan_hysteresis == 200) & (self.fan_p == 100) & (self.fan_i == 25) & (self.fan_d == 50) & (self.fan_min_temp == 1800) & (self.fan_max_temp == 3700)):
            self.ui.comboBox_fans_pid.setCurrentIndex(0)
            print("Detected PID Minimum -2")
        else:
            if ( (self.fan_hysteresis == 200) & (self.fan_p == 100) & (self.fan_i == 50) & (self.fan_d == 50) & (self.fan_min_temp == 1800) & (self.fan_max_temp == 3700)):
                self.ui.comboBox_fans_pid.setCurrentIndex(1)    
                print("Detected PID Slower -1")
            else:    
                if ( (self.fan_hysteresis == 100) & (self.fan_p == 100) & (self.fan_i == 100) & (self.fan_d == 100) & (self.fan_min_temp == 1900) & (self.fan_max_temp == 3600)):
                    self.ui.comboBox_fans_pid.setCurrentIndex(2)    
                    print("Detected PID Normal")
                else:
                    if ( (self.fan_hysteresis == 100) & (self.fan_p == 2000) & (self.fan_i == 200) & (self.fan_d == 1000) & (self.fan_min_temp == 1900) & (self.fan_max_temp == 3600)):
                        self.ui.comboBox_fans_pid.setCurrentIndex(3)
                        print("Detected PID Faster +1")
                    else:
                        if ( (self.fan_hysteresis == 50) & (self.fan_p == 4000) & (self.fan_i == 500) & (self.fan_d == 1000) & (self.fan_min_temp == 1950) & (self.fan_max_temp == 3550)):
                            self.ui.comboBox_fans_pid.setCurrentIndex(4)    
                            print("Detected PID Maximum +2")
                        else:
                            print("Detected Custom PID Values")
                            print("Setting to Normal Speed")
                            self.ui.comboBox_fans_pid.setCurrentIndex(2)
                            
            
        #self.fan_min_pwm
        self.ui.spinBox_fans_auto_fans_min_hz.setValue(self.fan_min_pwm)
        #self.fan_max_pwm
        self.ui.spinBox_fans_auto_fans_max_hz.setValue(self.fan_max_pwm)
        #self.bitfield_fan_mode_manual
        self.ui.radioButton_fans_man.setChecked(self.bitfield_fan_mode_manual)
        #self.bitfield_fan_mode_automatic
        self.ui.radioButton_fans_auto.setChecked(self.bitfield_fan_mode_automatic)
        #self.bitfield_fan_mode_hold_min
        self.ui.checkBox_fans_auto_hold_min.setChecked(self.bitfield_fan_mode_hold_min)
        
        
        #SETTINGS
        #self.bitfield_pump_mode_aquabus_flow
        #aquabus/flow switch: 1   (flow = 0 / aquabus = 1)
        if (self.bitfield_pump_mode_aquabus_flow == 0):
            self.ui.label_flow_active.setEnabled(True)
            self.ui.label_aquabus_active.setEnabled(False)
        if (self.bitfield_pump_mode_aquabus_flow == 1):
            self.ui.label_flow_active.setEnabled(False)
            self.ui.label_aquabus_active.setEnabled(True)
            
        #self.bitfield_alarm_configuration_external_temp
        self.ui.checkBox_alarm_ext_temp.setChecked(self.bitfield_alarm_configuration_external_temp)
        #self.bitfield_alarm_configuration_int_temp
        self.ui.checkBox_alarm_int_temp.setChecked(self.bitfield_alarm_configuration_int_temp)
        #self.bitfield_alarm_configuration_pump
        self.ui.checkBox_alarm_pump.setChecked(self.bitfield_alarm_configuration_pump)
        #self.bitfield_alarm_configuration_fan_speed
        self.ui.checkBox_alarm_fan_rpm.setChecked(self.bitfield_alarm_configuration_fan_speed)
        #self.bitfield_alarm_configuration_flow_rate
        self.ui.checkBox_alarm_flow.setChecked(self.bitfield_alarm_configuration_flow_rate)
        #self.bitfield_alarm_configuration_output_overload
        self.ui.checkBox_alarm_fan_overload.setChecked(self.bitfield_alarm_configuration_output_overload)
        #self.bitfield_alarm_configuration_amp_temp80
        self.ui.checkBox_alarm_80.setChecked(self.bitfield_alarm_configuration_amp_temp80)
        #self.bitfield_alarm_configuration_amp_temp100
        self.ui.checkBox_alarm_100.setChecked(self.bitfield_alarm_configuration_amp_temp100)
        
        #self.bitfield_speed_signal_output_fan_speed
        self.ui.radioButton_source_fan.setChecked(self.bitfield_speed_signal_output_fan_speed)
        #self.bitfield_speed_signal_output_flow_sensor
        self.ui.radioButton_source_flow.setChecked(self.bitfield_speed_signal_output_flow_sensor)
        #self.bitfield_speed_signal_output_pump_speed
        self.ui.radioButton_source_pump.setChecked(self.bitfield_speed_signal_output_pump_speed)
        #self.bitfield_speed_signal_output_static_speed
        self.ui.radioButton_source_static.setChecked(self.bitfield_speed_signal_output_static_speed)
        #self.bitfield_speed_signal_output_switch_off_on_alarm     ##only applys on static output
        self.ui.checkBox_source_turn_off_when_alarm.setChecked(self.bitfield_speed_signal_output_switch_off_on_alarm)
        
        #alarm_flow_speed
        #self.ui.spinBox_alarm_flow_min.setValue(int( 3994128 * pow(self.alarm_flow_speed, -1)))
        self.ui.spinBox_alarm_flow_min.setValue(int( 3994128.7777 / self.alarm_flow_speed))        # 3994068    3994128.7777
        
        #alarm_external_temp = 0
        self.ui.spinBox_alarm_ext_temp_max.setValue(int(self.alarm_external_temp/100))
        #alarm_int_temp = 0
        self.ui.spinBox_alarm_int_temp_max.setValue(int(self.alarm_int_temp/100))
        
        
#################################################

class sensor_thread(threading.Thread):   

    #le u16 fan_voltage @ 0x7;
    fan_voltage_offset_16 = 0x07
    #le u16 pump_voltage @ 0x9;
    pump_voltage_offset_16 = 0x09
    #le u16 pump_curr @ 0xb;
    pump_curr_offset_16 = 0x0b
    #le u16 fan reg temp 0x0d
    temp_sensor_fan_amp_offset_16 = 0x0d
    #le u16 ext temp 0x0f
    temp_sensor_ext_offset_16 = 0x0f
    #le u16 int temp 0x10
    temp_sensor_int_offset_16 = 0x11
    #le u16 pump_speed @ 0x13;
    pump_speed_offset_16 = 0x13
    #le u16 fan_speed @ 0x1b;
    fan_speed_offset_16 = 0x1b
    #le u16 fan_status @ 0x1d;  
    fan_status_offset_16 = 0x1d
    #u8 fan_pwm @ 0x1f;        
    fan_pwm_offset_8 = 0x1f
    #le u16 firmware @ 0x32;
    firmware_offset_16 = 0x32
    #le u16 serial_number @ 0x3a;
    serial_number_offset_16 = 0x3a
    #u8 device_key[6] @ 0x3c;
    device_key_offset_8 = 0x3c   #6 Bytes
    #le u16 flow sensor = 0x18
    flow_sensor_offset_16 = 0x18
    
    ###
    fan_voltage = 0
    pump_voltage = 0
    pump_curr = 0
    temp_sensor_fan_amp = 0
    temp_sensor_ext = 0
    temp_sensor_int = 0
    pump_speed = 0
    fan_speed = 0   # auch wenn sie ned laufen nicht 0
    fan_status = 0  #?????   0-> läuft   4-> steht ?
    fan_pwm = 0     #?????  % auslastung   100% = 255 raw
    pump_watts = 0
    flow_sensor_raw = 0
    ###
    
    #fan_voltage, pump_voltage, pump_curr, temp_sensor_fan_amp, temp_sensor_ext, temp_sensor_int, pump_speed, fan_speed, fan_status, fan_pwm, pump_watts, flow_sensor_raw
    #float, float, float, float, float, float, int, int, int, int, float, int,
    
    #firmware, serial_number, device_key
    # int, int, list
    
    firmware = 0
    serial_number = 0
    device_key = [0, 0, 0, 0, 0, 0]  ###6 bytes
    ###
  
    sensor_report = 0
 
    loop=1
    sensor_hid_active = 0
    main_hid_active = 0
    #delay = 0.5 #seconds?
    
    print_report_signal = Signal()
 
    def __init__(self):
        threading.Thread.__init__(self)
        super(self.__class__, self).__init__()
        
        #self.print_report_signal.connect(self.print_data)
        #self.sensor_update_signal.connect(self.recieve_new_sensor_values)
        
    def run(self):
        
        self.get_pump_infos()
        prog.sensor_pump_infos_signal.emit(self.firmware, self.serial_number, self.device_key)
        hid_counter = 0
        
        while(self.loop==1): 
        
            #self.sensor_hid_active = 1
            
            while (self.main_hid_active == 1):  #warten bis main fertig
                time.sleep(0.1)
                if ((self.sensor_hid_active == 1) & (self.main_hid_active == 1)):  #wenn beides aktiv und wartend
                    self.sensor_hid_active = 0                            #main machen lassen  
                    while (self.main_hid_active == 1):                    #main aktiv, warten bis durch
                        time.sleep(0.01)
                    self.sensor_hid_active = 1                            #sensor dran
                    print("conflict solved")
            
            self.sensor_hid_active = 1
            
            try:
                self.get_new_sensor_data()
            except:
                hid_counter = hid_counter +1
                print("oops usb hid error counter = ", hid_counter)
            
            self.sensor_hid_active = 0    

            #signals
            prog.sensor_update_signal.emit(self.fan_voltage, self.pump_voltage, self.pump_curr, self.temp_sensor_fan_amp, self.temp_sensor_ext, self.temp_sensor_int, self.pump_speed, self.fan_speed, self.fan_status, self.fan_pwm, self.pump_watts, self.flow_sensor_raw)
            time.sleep(1)             
            
        print("thread ended")
     
    def print_data(self):

        print("##### SENSOR REPORT #####")
        print("pump_speed", self.pump_speed)
        print("pump_watts", self.pump_watts)
        print("pump_voltage", self.pump_voltage)
        print("pump_curr", self.pump_curr)
        print("flow_sensor_raw", self.flow_sensor_raw)
        print("temp_sensor_fan_amp", self.temp_sensor_fan_amp)
        print("temp_sensor_ext", self.temp_sensor_ext)
        print("temp_sensor_int", self.temp_sensor_int)
        print("fan_speed", self.fan_speed)
        print("fan_status", self.fan_status)   
        print("fan_pwm", self.fan_pwm)  
        print("fan_voltage", self.fan_voltage)
        #print("firmware", self.firmware)
        #print("serial_number", self.serial_number)
        #print("device_key", [hex(x) for x in self.device_key])
        print("##################")
     
    def get_new_sensor_data(self):
        
        self.sensor_report = h.get_feature_report(AQUASTREAMXT_SENSOR_FEATURE_REPORT_ID, AQUASTREAMXT_SENSOR_REPORT_SIZE)    #66 dez

        self.fan_voltage = round (((1* read_int16_le(self.sensor_report, self.fan_voltage_offset_16)) / 63), 1)
        self.pump_voltage = round (((1 * read_int16_le(self.sensor_report, self.pump_voltage_offset_16)) / 61), 1)
        self.pump_curr = round ((((176 * read_int16_le(self.sensor_report, self.pump_curr_offset_16)) / 100 ) -30) / 1000, 3)  #30 i estimated
        
        self.temp_sensor_fan_amp = round (read_int16_le(self.sensor_report, self.temp_sensor_fan_amp_offset_16) / 100, 1)
        self.temp_sensor_ext     = round (read_int16_le(self.sensor_report, self.temp_sensor_ext_offset_16) / 100, 1)
        self.temp_sensor_int     = round (read_int16_le(self.sensor_report, self.temp_sensor_int_offset_16) / 100, 1)
        
        self.pump_speed = conv_raw_to_rpm_pump(read_int16_le(self.sensor_report, self.pump_speed_offset_16))
        
        self.fan_status = read_int16_le(self.sensor_report, self.fan_status_offset_16)
        if (self.fan_status == 4):
            self.fan_speed = 0
        if (self.fan_status == 0):
            self.fan_speed = conv_raw_to_rpm_fan(read_int16_le(self.sensor_report, self.fan_speed_offset_16))
        
        self.fan_pwm = int ((self.sensor_report[self.fan_pwm_offset_8] / 2.55) )
 
        self.pump_watts = round (self.pump_voltage * self.pump_curr, 3)
        
        self.flow_sensor_raw = read_int16_le(self.sensor_report, self.flow_sensor_offset_16)  

        
    def get_pump_infos(self):
    
        self.sensor_report = h.get_feature_report(AQUASTREAMXT_SENSOR_FEATURE_REPORT_ID, AQUASTREAMXT_SENSOR_REPORT_SIZE)    

        self.firmware = read_int16_le(self.sensor_report, self.firmware_offset_16)
        self.serial_number = read_int16_le(self.sensor_report, self.serial_number_offset_16)
        for i in range (0, 6):
            self.device_key[i] = (self.sensor_report[self.device_key_offset_8+i])
        

        
        
#######################################



if __name__ == '__main__':

    print("Hello")
  
  
    app = QApplication(sys.argv)

    ###### tray icon
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Systray", "I couldn't detect any system tray on this system.")
        sys.exit(1)

    #print(QSystemTrayIcon.isSystemTrayAvailable())
    #QApplication.setQuitOnLastWindowClosed(False)
    #######


    prog = MainWindow()
    prog.show()

    
    ##############################

    sensorthread=sensor_thread()  #Thread starten
    sensorthread.daemon=True
    sensorthread.start()


    ##########################
    
    app.exec()      #prog start
        
    ###########################     #Thread stoppen
                                
    if(sensorthread.is_alive()==True): #wenn defined und aktiv
        sensorthread.loop=0
        print("sensor_thread getting closed")
        sensorthread.join()

    #########################

    h.close()
    
    prog.save_settings()
    
    tree.write("settings.xml", encoding="utf-8", xml_declaration=True)
    
    print("Settings Saved")
    
    print("exit")
    
    sys.exit() #neccessary ?