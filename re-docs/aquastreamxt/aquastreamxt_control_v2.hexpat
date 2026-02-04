bitfield AlarmConfiguration {
external_temp: 1;   #LSB
water_temp: 1;
pump: 1;
fan_speed: 1;
flow_rate: 1;
output_overload: 1;
amp_temp80: 1;
amp_temp100: 1;		#MSB
};

bitfield SpeedSignalOutput {
fan_speed: 1;
flow_sensor: 1;
pump_speed: 1;
static_speed: 1;
switch_off_on_alarm: 1;
};

bitfield FanMode {
manual: 1;
automatic: 1;
hold_min: 1;
};

bitfield PumpMode {   
padding: 1;
automatic: 1;
padding: 3;
hold_min: 1;
};

##############################

u8 aqaubus_adress_offset = 0x01  #aquabus adress
u8 aquabus_or_flow_offset = 0x02  #0=flow  /  1=aquabus
?  aquabus_sensors_select_offset = 0x05  

BF PumpMode @ 0x3;

le u16 pump_speed @ 0x8;

BF AlarmConfiguration @ 0xe;
BF SpeedSignalOutput @ 0xf;

le u32 alarm_flow_speed @ 0x12;
le u16 alarm_external_temp @ 0x16;
le u16 alarm_water_temp @ 0x18;

BF FanMode @ 0x1a;

u8 fan_pwm @ 0x1b;
le u16 fan_hysteresis @ 0x1c;
u8 fan_temp_src @ 0x1e;
le u16 fan_target_temp @ 0x1f;
le u16 fan_p @ 0x21;
le u16 fan_i @ 0x23;
le u16 fan_d @ 0x25;
le u16 fan_min_temp @ 0x27;
le u16 fan_max_temp @ 0x29;
u8 fan_min_pwm @ 0x2b;
u8 fan_max_pwm @ 0x2c;
le u16 pump_min_speed @ 0x2f;
le u16 pump_max_speed @ 0x31;
