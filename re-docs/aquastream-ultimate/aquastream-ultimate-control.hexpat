struct pid {
    be u16 P;
    be u16 I;
    be u16 D;
    be u16 reset_time;
    be u16 hysteresis;
};

//PUMP #############################

u8 pumpmode @ 0x05;
/*  pump_auto = 0
    pump_man = 1
    pump_temp_target =2
    pump_curve = 3
    pump_flow = 4
    de_air = software?
    pump_aquabus = 5
*/
//auto 	free

//manual	free
be u16 pump_rpm_manual @ 0x06;

//temp target     pay
u8 pump_temp_source @ 0x4D;
//0=watertemp_intern    1=extern   2=soft1  3=soft2   4=watertemp
be u16 pump_temp_target @ 0x94;
pid pump_pid @ 0x96;

//pump curve	pay
be u16 pump_curve_start_line @ 0x52;
be u16 pump_curve_y[16] @ 0x54;
be u16 pump_curve_x[16] @ 0x74;
u8 pump_curve_temp_source @ 0x4C;

//flow target	pay
u8 pump_flow_source @ 0x0D;
//5=extern   6=virtual
be u16 pump_flow_target @ 0x0A;


//FANS ################################

//fan mode
u8 fan_mode @0x49;
//0=manual  1=target_temp   4=aquabus
//i guess: 2=curve  3=2point

//manual	free
be u16 fan_max_rpm @ 0x47;
u8 voltage_or_pwm @ 0x41;
//0 = voltage // 1 = pwm
be u16 fan_output_percent  @ 0x4A;


//temp target	free
be u16 fan_target_temp @ 0xEA;
u8 fan_target_temp_source @ 0xA3;
//0=watertemp_intern    1=extern   2=soft1  3=soft2   4=watertemp
pid fan_pid @ 0xEC;


//fan curve		pay
be u16 fan_curve_y[16] @ 0xAA;
be u16 fan_curve_x[16] @ 0xCA;
be u16 fan_curve_start_line @ 0xAB;

//2 point   pay