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
//auto  free

//manual    free
be u16 pump_rpm_manual @ 0x06;

//temp target     pay
u8 pump_temp_source @ 0x4D;
//0=watertemp_intern    1=extern   2=soft1  3=soft2   4=watertemp
be u16 pump_temp_target @ 0x94;
pid pump_pid @ 0x96;

//pump curve    pay
be u16 pump_curve_start_line @ 0x52;
be u16 pump_curve_y[16] @ 0x54;
be u16 pump_curve_x[16] @ 0x74;
u8 pump_curve_temp_source @ 0x4C;

//flow target   pay
u8 pump_flow_source @ 0x0D;
//5=extern   6=virtual
be u16 pump_flow_target @ 0x0A;


//FANS ################################

//fan mode
u8 fan_mode @0x49;
//0=manual  1=target_temp   4=aquabus
//i guess: 2=curve  3=2point

//manual    free
be u16 fan_max_rpm @ 0x47;
u8 voltage_or_pwm @ 0x41;
//0 = voltage // 1 = pwm
be u16 fan_output_percent  @ 0x4A;


//temp target   free
be u16 fan_target_temp @ 0xEA;
u8 fan_target_temp_source @ 0xA3;
//0=watertemp_intern    1=extern   2=soft1  3=soft2   4=watertemp
pid fan_pid @ 0xEC;


//fan curve     pay
be u16 fan_curve_y[16] @ 0xAA;
be u16 fan_curve_x[16] @ 0xCA;
be u16 fan_curve_start_line @ 0xAB;

//2 point   pay


//Alarms

u8 rpm_out @ 0xF8;
//rpm out inactive on alarm + acoustic = 0x05  				//0 0 0 0 | 0 A P R
//rpm out inactive on alarm + acoustic off = 0x01 			//  		8 4 2 1
//rpm_out_always active + acoustic = 0x04     				//Acoustic on A=1  // Acoustic off A=0
//rpm out always active + acoustic off = 0x00				//always active R=0
//acoustic off powerbutton mode = 0x02						//inactive on alarm R=1
//acoustic on powerbutton mode = 0x06						//powerbutton mode on P=1 // off P=0

u8 alarm_source @ 0xFA;
//0x01 flowextern
//0x02 flowvirtual
//0x04 fans
//0x08 temp ext
//0x10 temp_int

be u16 flow_extern_linit @ 0xFB;
be u16 flow_virtual @ 0xFD;
be u16 temp_int @ 0xFF;
be u16 temp_ext @ 0x101;
be u16 soft_1 @ 0x103;
be u16 soft_2 @ 0x105;


//two byte CRC-16/USB checksum in the last two places
//The checksum is calculated from the data between the starting `0x03` report ID at the very
//beginning and the (existing) checksum at the end.
be u16 checksum @ 0x108;    //

//sensor offsets

be u16 flow_extern_correction @ 0x10; //in %
be u16 flow_virtual_correction @ 0x12;  //i guess
be u16 temp_int_offset @ 0x14;
be u16 temp_ext_offset @ 0x16;