set root [file normalize [file join [file dirname [info script]] ..]]
set out [file normalize $::env(PMA_COSIM_OUT)]
set mode $::env(PMA_COSIM_MODE)
set prefetch $::env(PMA_COSIM_PREFETCH)
set stop $::env(PMA_COSIM_STOP)
set skip_empty 0
if {[info exists ::env(PMA_COSIM_SKIP_EMPTY)]} {
    set skip_empty $::env(PMA_COSIM_SKIP_EMPTY)
}
set flags "-D_GTHREAD_USE_COND_INIT_FUNC -DGRASU_REGRAPH_COSIM_DEPTH=1 -DGRASU_REGRAPH_SHARDED_PMA=1 -DGRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS=1 -DGRASU_REGRAPH_ROW_PREFETCH=$prefetch -DGRASU_REGRAPH_STOP_AFTER_LAST=$stop -I/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include/etc"
append flags " -DGRASU_REGRAPH_SKIP_EMPTY_SEGMENT=$skip_empty"
if {$mode eq "weighted"} {
    append flags " -DGRASU_REGRAPH_WEIGHTED_PMA=1"
} elseif {$mode eq "destination"} {
    append flags " -DGRASU_REGRAPH_DESTINATION_ONLY=1"
} elseif {$mode ne "unit"} {
    error "unsupported PMA_COSIM_MODE"
}
open_project [file join $out project]
set_top pma_to_regraph_adapter
add_files [file join $root kernels pma_to_regraph_adapter pma_to_regraph_adapter.cpp] -cflags $flags
add_files -tb [file join $root tests pma_adapter_cosim_tb.cpp] -cflags $flags
open_solution -flow_target vitis solution
set_part xcu55c-fsvh2892-2L-e
create_clock -period 150MHz -name default
config_dataflow -strict_mode warning
config_rtl -deadlock_detection sim
config_interface -m_axi_conservative_mode=1
config_interface -m_axi_addr64
config_interface -m_axi_auto_max_ports=0
csim_design -ldflags "-Wl,--threads=2"
csynth_design
cosim_design -rtl verilog -tool xsim -ldflags "-Wl,--threads=2"
close_project
exit
