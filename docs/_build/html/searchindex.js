Search.setIndex({envversion:46,filenames:["index","mobly","mobly.controllers","mobly.controllers.android_device_lib","mobly.controllers.attenuator_lib","mobly.controllers.sniffer_lib","mobly.controllers.sniffer_lib.local"],objects:{"":{mobly:[1,0,0,"-"]},"mobly.asserts":{abort_all:[1,1,1,""],abort_all_if:[1,1,1,""],abort_class:[1,1,1,""],abort_class_if:[1,1,1,""],assert_equal:[1,1,1,""],assert_false:[1,1,1,""],assert_raises:[1,1,1,""],assert_raises_regex:[1,1,1,""],assert_true:[1,1,1,""],explicit_pass:[1,1,1,""],fail:[1,1,1,""],skip:[1,1,1,""],skip_if:[1,1,1,""]},"mobly.base_test":{BaseTestClass:[1,2,1,""],Error:[1,5,1,""]},"mobly.base_test.BaseTestClass":{TAG:[1,3,1,""],clean_up:[1,4,1,""],controller_configs:[1,3,1,""],current_test_name:[1,3,1,""],exec_one_test:[1,4,1,""],generate_tests:[1,4,1,""],get_existing_test_names:[1,4,1,""],log_path:[1,3,1,""],on_fail:[1,4,1,""],on_pass:[1,4,1,""],on_skip:[1,4,1,""],register_controller:[1,3,1,""],results:[1,3,1,""],run:[1,4,1,""],setup_class:[1,4,1,""],setup_generated_tests:[1,4,1,""],setup_test:[1,4,1,""],teardown_class:[1,4,1,""],teardown_test:[1,4,1,""],test_bed_name:[1,3,1,""],tests:[1,3,1,""],unpack_userparams:[1,4,1,""],user_params:[1,3,1,""]},"mobly.config_parser":{MoblyConfigError:[1,5,1,""],TestRunConfig:[1,2,1,""],load_test_config_file:[1,1,1,""]},"mobly.config_parser.TestRunConfig":{controller_configs:[1,3,1,""],copy:[1,4,1,""],log_path:[1,3,1,""],register_controller:[1,3,1,""],summary_writer:[1,3,1,""],test_bed_name:[1,3,1,""],user_params:[1,3,1,""]},"mobly.controllers":{android_device:[2,0,0,"-"],android_device_lib:[3,0,0,"-"],attenuator:[2,0,0,"-"],attenuator_lib:[4,0,0,"-"],iperf_server:[2,0,0,"-"],monsoon:[2,0,0,"-"],sniffer:[2,0,0,"-"],sniffer_lib:[5,0,0,"-"]},"mobly.controllers.android_device":{AndroidDevice:[2,2,1,""],AndroidDeviceLoggerAdapter:[2,2,1,""],DeviceError:[2,5,1,""],Error:[2,5,1,""],SnippetError:[2,5,1,""],create:[2,1,1,""],destroy:[2,1,1,""],filter_devices:[2,1,1,""],get_all_instances:[2,1,1,""],get_device:[2,1,1,""],get_info:[2,1,1,""],get_instances:[2,1,1,""],get_instances_with_configs:[2,1,1,""],list_adb_devices:[2,1,1,""],list_adb_devices_by_usb_id:[2,1,1,""],list_fastboot_devices:[2,1,1,""],take_bug_reports:[2,1,1,""]},"mobly.controllers.android_device.AndroidDevice":{adb:[2,3,1,""],adb_logcat_file_path:[2,3,1,""],build_info:[2,3,1,""],cat_adb_log:[2,4,1,""],debug_tag:[2,3,1,""],fastboot:[2,3,1,""],handle_reboot:[2,4,1,""],handle_usb_disconnect:[2,4,1,""],is_adb_detectable:[2,4,1,""],is_adb_root:[2,3,1,""],is_boot_completed:[2,4,1,""],is_bootloader:[2,3,1,""],is_rootable:[2,3,1,""],load_config:[2,4,1,""],load_sl4a:[2,4,1,""],load_snippet:[2,4,1,""],log:[2,3,1,""],log_path:[2,3,1,""],model:[2,3,1,""],reboot:[2,4,1,""],root_adb:[2,4,1,""],run_iperf_client:[2,4,1,""],serial:[2,3,1,""],start_adb_logcat:[2,4,1,""],start_services:[2,4,1,""],stop_adb_logcat:[2,4,1,""],stop_services:[2,4,1,""],take_bug_report:[2,4,1,""],wait_for_boot_completion:[2,4,1,""]},"mobly.controllers.android_device.AndroidDeviceLoggerAdapter":{process:[2,4,1,""]},"mobly.controllers.android_device_lib":{adb:[3,0,0,"-"],event_dispatcher:[3,0,0,"-"],fastboot:[3,0,0,"-"],jsonrpc_client_base:[3,0,0,"-"],jsonrpc_shell_base:[3,0,0,"-"],sl4a_client:[3,0,0,"-"],snippet_client:[3,0,0,"-"]},"mobly.controllers.android_device_lib.adb":{AdbError:[3,5,1,""],AdbProxy:[3,2,1,""],AdbTimeoutError:[3,5,1,""],list_occupied_adb_ports:[3,1,1,""]},"mobly.controllers.android_device_lib.adb.AdbProxy":{forward:[3,4,1,""],getprop:[3,4,1,""]},"mobly.controllers.android_device_lib.event_dispatcher":{DuplicateError:[3,5,1,""],EventDispatcher:[3,2,1,""],EventDispatcherError:[3,5,1,""],IllegalStateError:[3,5,1,""]},"mobly.controllers.android_device_lib.event_dispatcher.EventDispatcher":{DEFAULT_TIMEOUT:[3,3,1,""],clean_up:[3,4,1,""],clear_all_events:[3,4,1,""],clear_events:[3,4,1,""],get_event_q:[3,4,1,""],handle_event:[3,4,1,""],handle_subscribed_event:[3,4,1,""],poll_events:[3,4,1,""],pop_all:[3,4,1,""],pop_event:[3,4,1,""],pop_events:[3,4,1,""],register_handler:[3,4,1,""],start:[3,4,1,""],wait_for_event:[3,4,1,""]},"mobly.controllers.android_device_lib.fastboot":{FastbootProxy:[3,2,1,""],exe_cmd:[3,1,1,""]},"mobly.controllers.android_device_lib.fastboot.FastbootProxy":{args:[3,4,1,""]},"mobly.controllers.android_device_lib.jsonrpc_client_base":{ApiError:[3,5,1,""],AppRestoreConnectionError:[3,5,1,""],AppStartError:[3,5,1,""],Error:[3,5,1,""],JsonRpcClientBase:[3,2,1,""],JsonRpcCommand:[3,2,1,""],ProtocolError:[3,5,1,""]},"mobly.controllers.android_device_lib.jsonrpc_client_base.JsonRpcClientBase":{"__getattr__":[3,4,1,""],app_name:[3,3,1,""],connect:[3,4,1,""],device_port:[3,3,1,""],disconnect:[3,4,1,""],host_port:[3,3,1,""],restore_app_connection:[3,4,1,""],start_app_and_connect:[3,4,1,""],stop_app:[3,4,1,""],uid:[3,3,1,""]},"mobly.controllers.android_device_lib.jsonrpc_client_base.JsonRpcCommand":{CONTINUE:[3,3,1,""],INIT:[3,3,1,""]},"mobly.controllers.android_device_lib.jsonrpc_client_base.ProtocolError":{MISMATCHED_API_ID:[3,3,1,""],NO_RESPONSE_FROM_HANDSHAKE:[3,3,1,""],NO_RESPONSE_FROM_SERVER:[3,3,1,""]},"mobly.controllers.android_device_lib.jsonrpc_shell_base":{Error:[3,5,1,""],JsonRpcShellBase:[3,2,1,""]},"mobly.controllers.android_device_lib.jsonrpc_shell_base.JsonRpcShellBase":{load_device:[3,4,1,""],main:[3,4,1,""],start_console:[3,4,1,""]},"mobly.controllers.android_device_lib.sl4a_client":{Sl4aClient:[3,2,1,""]},"mobly.controllers.android_device_lib.sl4a_client.Sl4aClient":{restore_app_connection:[3,4,1,""],start_app_and_connect:[3,4,1,""],stop_app:[3,4,1,""],stop_event_dispatcher:[3,4,1,""]},"mobly.controllers.android_device_lib.snippet_client":{Error:[3,5,1,""],ProtocolVersionError:[3,5,1,""],SnippetClient:[3,2,1,""]},"mobly.controllers.android_device_lib.snippet_client.SnippetClient":{restore_app_connection:[3,4,1,""],start_app_and_connect:[3,4,1,""],stop_app:[3,4,1,""]},"mobly.controllers.attenuator":{AttenuatorPath:[2,2,1,""],Error:[2,5,1,""],create:[2,1,1,""],destroy:[2,1,1,""]},"mobly.controllers.attenuator.AttenuatorPath":{get_atten:[2,4,1,""],get_max_atten:[2,4,1,""],set_atten:[2,4,1,""]},"mobly.controllers.attenuator_lib":{minicircuits:[4,0,0,"-"],telnet_scpi_client:[4,0,0,"-"]},"mobly.controllers.attenuator_lib.minicircuits":{AttenuatorDevice:[4,2,1,""]},"mobly.controllers.attenuator_lib.minicircuits.AttenuatorDevice":{close:[4,4,1,""],get_atten:[4,4,1,""],is_open:[4,3,1,""],open:[4,4,1,""],path_count:[4,3,1,""],set_atten:[4,4,1,""]},"mobly.controllers.attenuator_lib.telnet_scpi_client":{TelnetScpiClient:[4,2,1,""]},"mobly.controllers.attenuator_lib.telnet_scpi_client.TelnetScpiClient":{close:[4,4,1,""],cmd:[4,4,1,""],is_open:[4,3,1,""],open:[4,4,1,""]},"mobly.controllers.iperf_server":{IPerfResult:[2,2,1,""],IPerfServer:[2,2,1,""],create:[2,1,1,""],destroy:[2,1,1,""]},"mobly.controllers.iperf_server.IPerfResult":{avg_rate:[2,3,1,""],avg_receive_rate:[2,3,1,""],avg_send_rate:[2,3,1,""],error:[2,3,1,""],get_json:[2,4,1,""]},"mobly.controllers.iperf_server.IPerfServer":{start:[2,4,1,""],stop:[2,4,1,""]},"mobly.controllers.monsoon":{Monsoon:[2,2,1,""],MonsoonData:[2,2,1,""],MonsoonError:[2,5,1,""],MonsoonProxy:[2,2,1,""],create:[2,1,1,""],destroy:[2,1,1,""]},"mobly.controllers.monsoon.Monsoon":{attach_device:[2,4,1,""],measure_power:[2,4,1,""],set_max_current:[2,4,1,""],set_max_init_current:[2,4,1,""],set_voltage:[2,4,1,""],status:[2,3,1,""],take_samples:[2,4,1,""],usb:[2,3,1,""]},"mobly.controllers.monsoon.MonsoonData":{average_current:[2,3,1,""],delimiter:[2,3,1,""],from_string:[2,6,1,""],from_text_file:[2,6,1,""],get_average_record:[2,4,1,""],get_data_with_timestamps:[2,4,1,""],lr:[2,3,1,""],save_to_text_file:[2,6,1,""],sr:[2,3,1,""],total_charge:[2,3,1,""],total_power:[2,3,1,""],update_offset:[2,4,1,""]},"mobly.controllers.monsoon.MonsoonProxy":{CollectData:[2,4,1,""],GetStatus:[2,4,1,""],GetUsbPassthrough:[2,4,1,""],GetVoltage:[2,4,1,""],RampVoltage:[2,4,1,""],SetMaxCurrent:[2,4,1,""],SetMaxPowerUpCurrent:[2,4,1,""],SetUsbPassthrough:[2,4,1,""],SetVoltage:[2,4,1,""],StartDataCollection:[2,4,1,""],StopDataCollection:[2,4,1,""]},"mobly.controllers.sniffer":{ActiveCaptureContext:[2,2,1,""],ExecutionError:[2,5,1,""],InvalidDataError:[2,5,1,""],InvalidOperationError:[2,5,1,""],Sniffer:[2,2,1,""],SnifferError:[2,5,1,""],create:[2,1,1,""],destroy:[2,1,1,""]},"mobly.controllers.sniffer.Sniffer":{CONFIG_KEY_CHANNEL:[2,3,1,""],get_capture_file:[2,4,1,""],get_descriptor:[2,4,1,""],get_interface:[2,4,1,""],get_subtype:[2,4,1,""],get_type:[2,4,1,""],start_capture:[2,4,1,""],stop_capture:[2,4,1,""],wait_for_capture:[2,4,1,""]},"mobly.controllers.sniffer_lib":{local:[6,0,0,"-"]},"mobly.controllers.sniffer_lib.local":{local_base:[6,0,0,"-"],tcpdump:[6,0,0,"-"],tshark:[6,0,0,"-"]},"mobly.controllers.sniffer_lib.local.local_base":{SnifferLocalBase:[6,2,1,""]},"mobly.controllers.sniffer_lib.local.local_base.SnifferLocalBase":{get_capture_file:[6,4,1,""],get_interface:[6,4,1,""],get_type:[6,4,1,""],start_capture:[6,4,1,""],stop_capture:[6,4,1,""],wait_for_capture:[6,4,1,""]},"mobly.controllers.sniffer_lib.local.tcpdump":{Sniffer:[6,2,1,""]},"mobly.controllers.sniffer_lib.local.tcpdump.Sniffer":{get_descriptor:[6,4,1,""],get_subtype:[6,4,1,""]},"mobly.controllers.sniffer_lib.local.tshark":{Sniffer:[6,2,1,""]},"mobly.controllers.sniffer_lib.local.tshark.Sniffer":{get_descriptor:[6,4,1,""],get_subtype:[6,4,1,""]},"mobly.keys":{Config:[1,2,1,""]},"mobly.keys.Config":{key_log_path:[1,3,1,""],key_mobly_params:[1,3,1,""],key_testbed:[1,3,1,""],key_testbed_controllers:[1,3,1,""],key_testbed_name:[1,3,1,""],key_testbed_test_params:[1,3,1,""]},"mobly.logger":{create_latest_log_alias:[1,1,1,""],epoch_to_log_line_timestamp:[1,1,1,""],get_log_file_timestamp:[1,1,1,""],get_log_line_timestamp:[1,1,1,""],is_valid_logline_timestamp:[1,1,1,""],kill_test_logger:[1,1,1,""],logline_timestamp_comparator:[1,1,1,""],normalize_log_line_timestamp:[1,1,1,""],setup_test_logger:[1,1,1,""]},"mobly.records":{Error:[1,5,1,""],ExceptionRecord:[1,2,1,""],TestResult:[1,2,1,""],TestResultEnums:[1,2,1,""],TestResultRecord:[1,2,1,""],TestSummaryEntryType:[1,2,1,""],TestSummaryWriter:[1,2,1,""]},"mobly.records.ExceptionRecord":{"__deepcopy__":[1,4,1,""],exception:[1,3,1,""],extras:[1,3,1,""],position:[1,3,1,""],stacktrace:[1,3,1,""],to_dict:[1,4,1,""]},"mobly.records.TestResult":{"__add__":[1,4,1,""],add_class_error:[1,4,1,""],add_controller_info:[1,4,1,""],add_record:[1,4,1,""],is_all_pass:[1,3,1,""],is_test_executed:[1,4,1,""],json_str:[1,4,1,""],requested_test_names_dict:[1,4,1,""],summary_dict:[1,4,1,""],summary_str:[1,4,1,""]},"mobly.records.TestResult.self":{error:[1,3,1,""],executed:[1,3,1,""],failed:[1,3,1,""],passed:[1,3,1,""],requested:[1,3,1,""],skipped:[1,3,1,""]},"mobly.records.TestResultEnums":{RECORD_BEGIN_TIME:[1,3,1,""],RECORD_CLASS:[1,3,1,""],RECORD_DETAILS:[1,3,1,""],RECORD_END_TIME:[1,3,1,""],RECORD_EXTRAS:[1,3,1,""],RECORD_EXTRA_ERRORS:[1,3,1,""],RECORD_NAME:[1,3,1,""],RECORD_POSITION:[1,3,1,""],RECORD_RESULT:[1,3,1,""],RECORD_STACKTRACE:[1,3,1,""],RECORD_UID:[1,3,1,""],TEST_RESULT_ERROR:[1,3,1,""],TEST_RESULT_FAIL:[1,3,1,""],TEST_RESULT_PASS:[1,3,1,""],TEST_RESULT_SKIP:[1,3,1,""]},"mobly.records.TestResultRecord":{"__repr__":[1,4,1,""],add_error:[1,4,1,""],begin_time:[1,3,1,""],details:[1,3,1,""],end_time:[1,3,1,""],extra_errors:[1,3,1,""],extras:[1,3,1,""],json_str:[1,4,1,""],result:[1,3,1,""],stacktrace:[1,3,1,""],termination_signal:[1,3,1,""],test_begin:[1,4,1,""],test_error:[1,4,1,""],test_fail:[1,4,1,""],test_name:[1,3,1,""],test_pass:[1,4,1,""],test_skip:[1,4,1,""],to_dict:[1,4,1,""],uid:[1,3,1,""],update_record:[1,4,1,""]},"mobly.records.TestSummaryEntryType":{CONTROLLER_INFO:[1,3,1,""],RECORD:[1,3,1,""],SUMMARY:[1,3,1,""],TEST_NAME_LIST:[1,3,1,""]},"mobly.records.TestSummaryWriter":{dump:[1,4,1,""]},"mobly.signals":{ControllerError:[1,5,1,""],TestAbortAll:[1,5,1,""],TestAbortClass:[1,5,1,""],TestAbortSignal:[1,5,1,""],TestError:[1,5,1,""],TestFailure:[1,5,1,""],TestPass:[1,5,1,""],TestSignal:[1,5,1,""],TestSignalError:[1,5,1,""],TestSkip:[1,5,1,""]},"mobly.signals.TestSignal":{details:[1,3,1,""],extras:[1,3,1,""]},"mobly.test_runner":{Error:[1,5,1,""],TestRunner:[1,2,1,""],main:[1,1,1,""],verify_controller_module:[1,1,1,""]},"mobly.test_runner.TestRunner":{add_test_class:[1,4,1,""],run:[1,4,1,""]},"mobly.test_runner.TestRunner.self":{results:[1,3,1,""]},"mobly.utils":{Error:[1,5,1,""],abs_path:[1,1,1,""],concurrent_exec:[1,1,1,""],create_alias:[1,1,1,""],create_dir:[1,1,1,""],epoch_to_human_time:[1,1,1,""],find_field:[1,1,1,""],find_files:[1,1,1,""],get_available_host_port:[1,1,1,""],get_current_epoch_time:[1,1,1,""],get_current_human_time:[1,1,1,""],get_timezone_olson_id:[1,1,1,""],grep:[1,1,1,""],load_file_to_base64_str:[1,1,1,""],rand_ascii_str:[1,1,1,""],start_standing_subprocess:[1,1,1,""],stop_standing_subprocess:[1,1,1,""],wait_for_standing_subprocess:[1,1,1,""]},mobly:{asserts:[1,0,0,"-"],base_test:[1,0,0,"-"],config_parser:[1,0,0,"-"],controllers:[2,0,0,"-"],keys:[1,0,0,"-"],logger:[1,0,0,"-"],records:[1,0,0,"-"],signals:[1,0,0,"-"],test_runner:[1,0,0,"-"],utils:[1,0,0,"-"]}},objnames:{"0":["py","module","Python module"],"1":["py","function","Python function"],"2":["py","class","Python class"],"3":["py","attribute","Python attribute"],"4":["py","method","Python method"],"5":["py","exception","Python exception"],"6":["py","staticmethod","Python static method"]},objtypes:{"0":"py:module","1":"py:function","2":"py:class","3":"py:attribute","4":"py:method","5":"py:exception","6":"py:staticmethod"},terms:{"5min":2,"__add__":1,"__deepcopy__":1,"__getattr__":3,"__main__":1,"__name__":1,"__repr__":1,"__str__":2,"_socket_connection_timeout":3,"_socket_read_timeout":3,"_timeout":2,"byte":1,"case":[1,2,3],"catch":1,"char":2,"class":[1,2,3,4,6],"default":[1,2,3,4],"enum":1,"final":[1,2,6],"float":[2,4],"function":[1,2,3,4],"import":1,"int":[1,2,3,4],"long":[1,2,3],"new":[1,2,3],"null":[1,3],"public":3,"return":[1,2,3,4],"short":1,"static":2,"switch":2,"throw":[1,2,3],"true":[1,2,3,4],"try":[2,3],"void":3,"while":2,abl:3,abort:1,abort_al:1,abort_all_if:1,abort_class:1,abort_class_if:1,about:1,abs_path:1,absolut:1,access:[1,2,4],accord:1,action:2,action_boot_complet:2,action_that_reconnects_usb:2,activ:2,activatezoom:2,activecapturecontext:2,actual:[1,2,6],actual_path:1,adapt:2,adb:[1,2],adb_logcat_file_path:2,adb_proxi:3,adberror:3,adbproxi:[2,3],adbtimeouterror:3,add:[1,2],add_class_error:1,add_controller_info:1,add_error:1,add_record:1,add_test_class:1,addit:[1,2],additional_arg:[2,6],address:[2,4],affect:1,after:[1,2,3],afterward:[1,2],again:[1,3],against:3,aggreg:1,alia:1,alias_path:1,aliv:[1,2],all:[1,2,3],alloc:1,allow:[1,2],alreadi:[1,2,3],also:[1,2],alwai:[1,2,3],amp:2,androi:2,android:[2,3],android_devic:[0,1],android_device_lib:[1,2],androiddevic:[2,3],androiddeviceloggeradapt:2,androidmanifest:2,angler:2,ani:[1,2,3,4],anoth:1,anyth:1,ap1:2,ap2:2,api:3,apierror:3,apk:[2,3],app:3,app_nam:3,appear:[1,3],append:2,apprestoreconnectionerror:3,appropir:1,appstarterror:3,arbitrari:3,arg:[1,2,3],arg_a:1,arg_set:1,argument:[1,2,3],argv:1,arrai:3,ascend:3,ascii:1,assert:0,assert_equ:1,assert_fals:1,assert_rais:1,assert_raises_regex:1,assert_tru:1,assertionerror:1,associ:[1,3],async:2,attach:2,attach_devic:2,attempt:[2,3],attenu:[0,1],attenuation_devic:2,attenuation_path:2,attenuator_lib:[1,2],attenuatordevic:4,attenuatorpath:2,attribut:[1,2,3],auto:2,automat:2,avail:[1,2,3],averag:2,average_curr:2,avg_rat:2,avg_receive_r:2,avg_send_r:2,avoid:3,back:6,base64:1,base:[1,2,3,4,6],base_config:[2,6],base_test:0,baseconfig:2,baselin:2,basetestclass:1,basic:[1,4],batteri:2,becaus:[1,2,3],bed:[1,2],been:[1,2,3],befor:[1,2,3],begin:[1,2],begin_tim:[1,2],behavior:[2,6],benefit:2,between:[1,3],binari:1,bind:3,block:[1,2,3],bool:1,boot:2,bootload:2,both:[1,2],bound:1,box:2,broadcast:2,broken:3,bug:2,bugreport:2,build:2,build_info:2,cach:[2,3],cacul:2,calcul:2,call:[1,2,3,4],callback:[2,3],callbackhandl:3,caller:2,calm:2,can:[1,2,3],cannot:2,capabl:4,captur:[2,6],cat:3,cat_adb_log:2,categor:1,categori:1,caus:[1,2],cautious:2,certain:[1,2],chang:[1,2],channel:[2,4],charact:1,charg:2,check:[1,2,3],check_cal:1,circuit:4,claus:2,clean:[1,2,3],clean_up:[1,3],clear:[2,3],clear_all_ev:3,clear_ev:3,clear_log:2,cli:1,client:[2,3],close:[3,4],cmd:[1,3,4],cmd_str:4,code:[1,2,4],collect:[1,2],collectdata:2,com:[2,4],combin:2,come:3,command:[1,2,3,4],common:[1,4,6],commun:[3,4],compar:1,compat:[1,3],compens:2,complet:[1,2],compos:1,comput:2,concaten:1,concurr:[1,2,3],concurrent_exec:1,cond:[1,3],cond_timeout:3,condit:[1,2,3],config:[1,2],config_key_:2,config_key_channel:2,config_pars:0,config_path:6,configur:[1,2,6],connect:[2,3,4],consid:1,consist:1,consol:[2,3],constant:1,constructor:1,consum:1,consumpt:[1,2],contain:[1,2,3],content:0,context:[1,2],continu:3,control:[0,1],controller_config:1,controller_info:1,controllererror:[1,2],controllerinfo:1,convei:1,conveni:[2,3],convent:1,convert:1,copi:1,correct:2,correspond:[1,2,3],could:[1,2,3],count:1,creat:[1,2,3],create_alia:1,create_dir:1,create_latest_log_alia:1,cross:1,cur:2,current:[1,2,4],current_test_nam:1,custom:[1,2],cut:2,cycl:2,dai:1,dat:4,data:[1,2,3],data_point:2,data_str:2,databas:1,date:2,deal:3,debug:[1,2],debug_tag:2,declar:1,decoupl:2,deep:1,deepcopi:1,def:1,default_timeout:3,defin:[1,2,6],delimit:2,delta:1,depend:[1,2],deprec:1,deriv:2,describ:[1,2],descript:[1,3],desir:[1,3,4],destin:1,destroi:[1,2],detail:1,detect:2,determin:2,devic:[1,2,3,4],device_port:3,deviceerror:2,dict:[1,2],dictionari:[1,2],did:[1,2],differ:[1,2,3],difficult:1,digit:1,direct:3,directli:[1,2,3,4],directori:[1,2],disabl:2,discard:2,disconnect:[2,3],discoveri:3,disk:1,dispatch:3,displai:1,do_someth:2,doc:1,doe:[1,2,3],doesn:3,don:3,done:[1,3],down:[1,2,3],dst:1,due:[1,2],dump:1,duplic:[1,3],duplicateerror:3,durat:[2,6],dure:[1,2,3],dut:2,each:[1,2,3],easi:1,easier:1,echo:3,effect:2,effici:1,either:[1,2],element:1,emit:2,empti:[2,3],emul:2,enabl:2,encod:1,encount:2,end:[1,2,6],end_tim:1,eng:2,engin:3,entir:[1,2],entri:[1,3],entry_typ:1,environ:3,epoch:1,epoch_tim:1,epoch_to_human_tim:1,epoch_to_log_line_timestamp:1,equip:1,equival:1,error:[1,2,3,4],essenti:1,etc:1,evalu:1,even:2,event:[2,3],event_dispatch:[1,2],event_handl:3,event_nam:3,event_obj:3,event_timeout:3,eventdispatch:[2,3],eventdispatchererror:3,everi:[1,2],exampl:2,except:[1,2,3],exceptionrecord:1,excerpt:2,exchang:3,exe_cmd:3,exec_one_test:1,execut:[1,2,3],execute_one_test_class:1,executionerror:2,executor:3,exedcut:1,exist:[1,2,3],exit:[2,3],expand:1,expect:[1,2,3],expected_except:1,expected_regex:1,expir:2,explain:1,explan:1,explicit:[1,2],explicit_pass:1,explicitli:[1,2],expr:1,express:[1,3],extend:2,extens:1,extra:[1,2,3],extra_arg:2,extra_error:1,extract:1,f_path:1,fail:[1,3],failur:1,fall:1,fals:[1,2,3],fastboot:[1,2],fastbootproxi:[2,3],field:1,file:[1,2,3],file_path:2,file_pred:1,filen:1,filenam:1,filter:2,filter_devic:2,find:[1,2,3],find_field:1,find_fil:1,finish:1,first:[1,2],flag:[1,2,3],flow:2,folder:1,follow:[1,2,3],foo:[2,3],forc:2,format:[1,2],former:2,forward:[1,3],found:[1,3],four:2,framework:2,from:[1,2,3,4],from_str:2,from_text_fil:2,frontend:3,fulfil:2,full:[1,2],func:[1,2],futur:3,gener:[1,2],generate_test:1,get:[1,2,3],get_all_inst:2,get_atten:[2,4],get_available_host_port:1,get_average_record:2,get_capture_fil:[2,6],get_current_epoch_tim:1,get_current_human_tim:1,get_data_with_timestamp:2,get_descriptor:[2,6],get_devic:2,get_event_q:3,get_existing_test_nam:1,get_info:[1,2],get_inst:2,get_instances_with_config:2,get_interfac:[2,6],get_json:2,get_log_file_timestamp:1,get_log_line_timestamp:1,get_max_atten:2,get_subtyp:[2,6],get_timezone_olson_id:1,get_typ:[2,6],getlogg:2,getprop:3,getstatu:2,getusbpassthrough:2,getvoltag:2,gil:1,given:[1,2,3,4],goe:2,googl:2,got:[2,3],gradual:2,greater:4,grep:1,group:2,guarante:[1,2],guard:1,handl:[2,3],handle_:2,handle_ev:3,handle_reboot:2,handle_subscribed_ev:3,handle_usb_disconnect:2,handler:[1,3],handshak:3,happen:[1,3],have:[1,2,3],held:1,hello:1,helper:4,here:1,hold:[1,3],host:[1,3,4],host_port:3,hostnam:4,hour:1,how:[1,2],http:[2,4],human:1,idea:1,identifi:[1,2,3,4],idx:[2,4],ignor:[1,4],illeg:[2,3],illegalstateerror:3,immedi:3,implement:[1,2,3,4,6],implicit:2,implicitli:[1,2],importlib:1,improv:1,includ:[1,2],include_fastboot:2,increas:[2,3],index:[0,2,4],indexerror:4,individu:1,info:[1,2,3],inform:[1,2,4],inherit:1,init:[2,3],initi:[1,2,3],inject:3,input:1,insid:1,instanc:[1,2,3],instanti:1,instead:[1,2,3],instrument:4,integ:[1,2,3],intend:1,intention:1,interact:[2,3],interfac:[1,2,3,6],intern:4,interpret:2,interrupt:2,invalid:[1,2],invaliddataerror:2,invalidoperationerror:2,invok:[1,2,3],ioerror:3,iperf3:2,iperf:2,iperf_serv:[0,1],iperfresult:2,iperfserv:2,irrespect:2,is_adb_detect:2,is_adb_root:2,is_all_pass:1,is_boot_complet:2,is_bootload:2,is_open:4,is_root:2,is_test_execut:1,is_valid_logline_timestamp:1,item:1,item_list:1,iter:[1,3],itself:1,java:3,join:3,json:[1,2,3],json_str:1,jsonrpc:3,jsonrpc_client_bas:[1,2],jsonrpc_shell_bas:[1,2],jsonrpcclientbas:3,jsonrpccommand:3,jsonrpcshellbas:3,just:2,keep:1,kei:0,kept:[1,2],key_log_path:1,key_mobly_param:1,key_testb:1,key_testbed_control:1,key_testbed_nam:1,key_testbed_test_param:1,keyword:[2,3],keywordss:1,kill:[1,3],kill_sign:1,kill_test_logg:1,kwarg:[1,2,3],kwd:2,label:[1,2],labequip:2,last:2,latest:[1,3],latter:2,launch:[2,3],layer:3,least:3,leav:[4,6],len:2,length:1,let:1,letter:1,level:2,lib:[1,2,3],librari:[3,4],life:2,lifecycl:1,like:[1,2],limit:1,line:[1,2],linux:1,list:[1,2,3],list_adb_devic:2,list_adb_devices_by_usb_id:2,list_fastboot_devic:2,list_occupied_adb_port:3,live:[1,2],load:[1,2],load_config:2,load_devic:3,load_file_to_base64_str:1,load_sl4a:2,load_snippet:2,load_test_config_fil:1,local:[1,2,3,5],local_bas:[1,2,5],locat:[1,2],log:[1,2,3],log_dir:1,log_line_timestamp:1,log_path:[1,2],logcat:2,logger:0,loggeradapt:2,logic:1,loglin:[1,2],logline_timestamp_compar:1,logpath:1,longer:3,loop:3,lose:2,mac:1,machin:[2,6],made:[1,3],magic:3,mah:2,mai:[2,3],main:[1,3],make:[1,2],manag:[1,2,3],mani:[1,2],map:[1,2,3],mark:1,match:[1,2,3],max:2,max_filename_len:1,max_port_allocation_retri:1,maximum:4,mean:2,measur:2,measure_pow:2,mechan:6,member:1,memo:1,memori:1,merg:1,messag:[1,2,3],meter:2,method:[1,2,3],metric:1,millisecond:1,min:1,mini:4,minicircuit:[1,2],minut:2,mismatch:3,mismatched_api_id:3,miss:3,moblyconfigerror:1,moblyparam:1,mode:2,model:2,modul:0,mon:2,monoton:3,monsoon:[0,1],monsoon_data:2,monsoondata:2,monsoonerror:2,monsoonproxi:2,month:1,more:[1,2,3],most:[1,2],move:2,msg:[1,2],msoon:2,multipl:[1,2,3],must:[1,2,3],my_log:2,mydata:2,name:[1,2,3,4],name_func:1,natur:1,necessari:2,need:[1,2,3,4],neg:1,never:3,new_offset:2,newli:1,no_response_from_handshak:3,no_response_from_serv:3,nomin:2,non:[1,2,3],none:[1,2,3,6],nopermissionerror:2,normal:1,normalize_log_line_timestamp:1,note:[1,3],number:[1,2,3,4],obj:2,object:[1,2,3,4],obtain:[1,2,3],occupi:3,occur:[1,2,3],occurr:1,ocur:1,off:2,offset:[1,2],old:1,oldest:3,olson:1,on_fail:[1,2],on_pass:1,on_skip:1,onc:[1,3],ongo:2,onli:[1,2,3,4],open:[3,4],oper:[1,2,3],oppos:2,opt_list:1,opt_param_nam:1,option:[1,2,3,4],order:[1,3],ordereddict:1,origin:1,other:2,otherwis:[1,2,3],out:[1,2,3],output:[1,2,3],over:[1,2,3,4,6],overrid:[1,3],overridden:2,override_config:[2,6],overvoltag:2,overwrit:2,own:[1,2,3],packag:0,packet:[2,6],packet_count:[2,6],page:0,pair:2,param:[1,2,3],param_list:1,paramet:[1,2,3,4],parform:1,pars:1,parser:1,part:[2,4],partial:2,particular:[3,4],pass:[1,2,3],passthrough:2,path:[1,2,4],path_count:4,pattern:[1,3],pdf:4,peculiar:3,per:2,perform:2,period:2,permiss:2,permissionerror:1,phase:1,phone_numb:2,physic:2,pipe:3,place:[1,2],plan:[1,2],platform:1,point:[1,2],poll:3,poll_ev:3,pollut:2,pop:3,pop_al:3,pop_ev:3,popen:3,port:[1,2,3,4],posit:[1,3],possibl:[2,3],potenti:2,power:2,powermonitor:2,pre:1,predic:[1,3],prefix:[1,2],preprocess:1,present:3,preserv:1,prevent:2,previou:2,previous:[1,2],print:[1,2],prior:4,prioriti:1,probabl:2,problem:1,proc:1,procedur:4,process:[1,2,3],product:2,prog_manu:4,programmable_attenu:4,prompt:4,prop_nam:3,propag:1,properli:[1,2],properti:[2,3],protocol:3,protocolerror:3,protocolversionerror:3,provi:1,provid:[1,2,3,4,6],proxi:3,pseudo:1,pull:1,put:[1,3],python:[1,3],pytz:1,queri:4,queue:3,quot:3,rais:[1,2,3,4],ramp:2,rampvoltag:2,rand_ascii_str:1,random:1,rate:2,rather:1,raw:[1,2],rcdat:4,read:3,readabl:1,readi:2,readibl:1,real:2,realli:3,reason:[1,3],reboot:2,receiv:2,recent:2,recommend:3,reconnect:[2,3],recor:1,record:0,record_begin_tim:1,record_class:1,record_detail:1,record_end_tim:1,record_extra:1,record_extra_error:1,record_nam:1,record_posit:1,record_result:1,record_stacktrac:1,record_uid:1,reduc:1,refer:1,regex:[1,3],regex_pattern:3,regist:[1,3],register_control:1,register_handl:3,regular:3,rel:2,relat:[1,2],releas:[1,3],reli:1,remot:[2,3],remov:[1,3],repetit:1,replac:[1,3],report:[1,2,3],repres:[1,2,3],represent:[1,2],req_param_nam:1,request:[1,2,3,4],requested_test_names_dict:1,requir:[1,2],required_list:1,requrest:1,reserv:1,resolv:[1,4],resourc:[1,3],respons:3,restart:2,restor:[2,3],restore_app_connect:3,restrict:2,result:[1,2,3],result_path:2,ret_cod:3,retriev:[2,3],right:2,root:[1,2],root_adb:2,rootabl:2,rootlogg:3,rpc:[2,3],run:[1,2,3,6],run_iperf_cli:2,runner:1,runtim:1,rx_cmd_separ:4,same:[1,3],sampl:2,sample_hz:2,sample_num:2,sample_offset:2,satisfi:[1,2,3],save:2,save_to_text_fil:2,scalabl:1,scope:4,scpi:4,script:[1,2,3],search:0,sec:1,second:[1,2,3],section:1,secur:2,see:[1,2,3,4,6],seen:2,select:[1,3],self:[1,2,3],send:2,sensit:1,separ:[1,2,3],sequenc:3,seri:4,serial:[1,2,3],serializ:1,serialno:2,server:[2,3],server_host:2,servic:[1,2],session:[2,3],set:[1,2,3,4],set_atten:[2,4],set_max_curr:2,set_max_init_curr:2,set_voltag:2,setmaxcurr:2,setmaxpowerupcurr:2,setup:[1,3],setup_class:1,setup_generated_test:1,setup_test:1,setup_test_logg:1,setusbpassthrough:2,setvoltag:2,sever:1,shall:1,share:[1,3],shell:[1,3],shortcut:1,shorter:1,should:[1,2,3,4],shouldn:[3,4],shown:1,shut:3,signal:0,silent:3,similar:1,simpl:2,singl:[1,2],skip:[1,2],skip_if:1,sl4a:[2,3],sl4a_client:[1,2],sl4aclient:3,sleep:2,sniff:6,sniffer:[0,1],sniffer_lib:[1,2],sniffererror:2,snifferlocalbas:6,snippet:[2,3],snippet_cli:[1,2],snippetcli:3,snippeterror:2,snippetrunn:3,socket:[1,3],softwaredownload:4,some:[2,3],some_timeout:2,someth:3,sort:3,sourc:[1,2,3,4,6],special:1,specif:[1,2,4,6],specifi:[1,2,3],spin:2,stacktrac:1,stamp:1,stand:2,start:[1,2,3],start_adb_logcat:2,start_app_and_connect:3,start_captur:[2,6],start_consol:3,start_serv:3,start_servic:2,start_standing_subprocess:1,startdatacollect:2,startup:2,stat:1,state:[2,3,4],statement:1,statu:2,stderr:3,stdout:[2,3],step:2,still:[1,2],stop:[1,2,3],stop_adb_logcat:2,stop_app:3,stop_captur:[2,6],stop_event_dispatch:3,stop_servic:2,stop_standing_subprocess:1,stopdatacollect:2,store:[2,3],str:[2,3],stream:1,string:[1,2,3],structur:2,sub:[2,6],subclass:3,submodul:0,subpackag:0,subprocess:[1,2,3],subsequ:[1,3],subset:1,subtyp:2,success:2,successfulli:[2,4],sudo:2,sugar:2,suit:1,sum:1,summar:1,summari:1,summary_dict:1,summary_str:1,summary_writ:1,superclass:3,suppli:[1,2,3],support:2,sure:2,surviv:2,symlink:1,syntact:[2,3],system:[1,2,3],t_class:1,t_name:1,tag:[1,2],take:[1,2,3],take_bug_report:2,take_sampl:2,taken:2,talk:2,talli:1,target:[1,2],target_field:1,target_path:1,task:1,tb_filter:1,tcpdump:[1,2,5],teardown:[1,4],teardown_class:1,teardown_test:1,teat_result_:1,tell:2,telnet:4,telnet_scpi_cli:[1,2],telnetscpicli:4,temporarili:2,termin:[1,2],termination_sign:1,test:[1,2],test_bed_nam:1,test_begin:1,test_class:1,test_config:1,test_config_path:1,test_error:1,test_fail:1,test_identifi:1,test_log:1,test_method:1,test_nam:[1,2],test_name_list:1,test_pass:1,test_record:1,test_result_error:1,test_result_fail:1,test_result_pass:1,test_result_skip:1,test_runn:0,test_skip:1,test_someth:1,test_summari:1,testabortal:1,testabortclass:1,testabortsign:1,testb:1,testerror:1,testfailur:1,testnamelist:1,testparam:1,testpass:1,testresult:1,testresultenum:1,testresultrecord:1,testrunconfig:1,testrunn:1,testsign:1,testsignalerror:1,testskip:1,testsummaryentrytyp:1,testsummarywrit:1,text:2,than:[1,2,3,4],thei:2,therefor:2,thi:[1,2,3,4,6],thing:3,those:4,thread:3,threw:1,through:[1,3],thrown:[2,3],tier:1,time:[1,2,3],time_zon:1,timeout:[1,2,3,6],timeout_decor:2,timeoutexpir:1,timestamp:[1,2,3],timetout:2,timezon:1,tmp:3,to_dict:1,todo:1,togeth:1,token:1,torn:2,total:[1,2],total_charg:2,total_pow:2,treat:1,tri:3,trigger:[2,3],trip:2,truncat:1,tshark:[1,2,5],tupl:[1,2],turn:3,two:[1,2],tx_cmd_separ:4,type:[1,2,3],tzinfo:1,uid:[1,3],unblock:3,uncaught:1,under:[1,2],underli:[2,4],unexpect:1,uniqu:[1,2],unit:2,unix:1,unknown:[1,3],unknown_uid:3,unless:1,unpack:1,unpack_userparam:1,unplug:2,unsuccess:2,until:[2,3],updat:[1,2],update_offset:2,update_record:1,upon:[1,2,3],usag:[1,2],usb:[2,3],user:[1,2,3,4],user_arg:3,user_param:1,userdebug:2,usual:1,usuali:2,utf:1,util:0,val:2,valid:[1,2,4],valu:[1,2,3,4],valueerror:4,variabl:1,variou:2,verifi:[1,2],verify_controller_modul:1,version:1,via:[1,2],visibl:3,volt:2,voltag:2,vulner:3,wai:[1,2,3],wait:[1,2,3],wait_for_boot_complet:2,wait_for_captur:[2,6],wait_for_devic:2,wait_for_ev:3,wait_for_standing_subprocess:1,wait_ret:4,want:[1,2,3],warn:1,well:[1,3],were:1,what:3,when:[1,2,3],where:[1,2],wherea:2,whether:2,which:[1,2,3,4,6],whose:[1,3],why:1,wifi:2,window:1,within:[1,2],without:[1,2,3],wlan0:2,wlan:[2,6],won:[1,3],work:1,worker:3,would:[1,2],wrapper:[1,2,3],write:[1,2,3],writer:1,written:1,www:4,xml:2,xxx:[1,3],yaml:1,year:1,you:[1,2,3],your:1,zero:4,zone:1},titles:["Welcome to Mobly&#8217;s documentation!","mobly package","mobly.controllers package","mobly.controllers.android_device_lib package","mobly.controllers.attenuator_lib package","mobly.controllers.sniffer_lib package","mobly.controllers.sniffer_lib.local package"],titleterms:{adb:3,android_devic:2,android_device_lib:3,assert:1,attenu:2,attenuator_lib:4,base_test:1,config_pars:1,content:[1,2,3,4,5,6],control:[2,3,4,5,6],document:0,event_dispatch:3,fastboot:3,indic:0,iperf_serv:2,jsonrpc_client_bas:3,jsonrpc_shell_bas:3,kei:1,local:6,local_bas:6,logger:1,minicircuit:4,mobli:[0,1,2,3,4,5,6],modul:[1,2,3,4,5,6],monsoon:2,packag:[1,2,3,4,5,6],record:1,signal:1,sl4a_client:3,sniffer:2,sniffer_lib:[5,6],snippet_cli:3,submodul:[1,2,3,4,6],subpackag:[1,2,5],tabl:0,tcpdump:6,telnet_scpi_cli:4,test_runn:1,tshark:6,util:1,welcom:0}})