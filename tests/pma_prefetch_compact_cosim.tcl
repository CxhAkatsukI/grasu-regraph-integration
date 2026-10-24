set root [file normalize [file join [file dirname [info script]] ..]]
set out [file normalize $::env(PMA_COSIM_OUT)]
set mode $::env(PMA_COSIM_MODE)
set include $::env(HLS_INCLUDE)
if {[file exists [file join $out project]]} { error "refuse overwriting RTL evidence" }
set flags "-pthread -D_GTHREAD_USE_COND_INIT_FUNC -I$include/etc"
if {[info exists ::env(PMA_COSIM_SHARED)] && $::env(PMA_COSIM_SHARED) eq "1"} {
    append flags " -DGRI_HMSS_SHARED_INGRESS=1"
}
if {$mode eq "weighted"} {
    append flags " -DGRASU_REGRAPH_WEIGHTED_PMA=1"
} elseif {$mode eq "destination"} {
    append flags " -DGRASU_REGRAPH_DESTINATION_ONLY=1"
} elseif {$mode ne "unit"} {
    error "unsupported PMA_COSIM_MODE"
}
open_project [file join $out project]
set_top pma_to_regraph_adapter
add_files [file join $root kernels pma_prefetch_compact top.cpp] -cflags $flags
add_files -tb [file join $root tests pma_prefetch_compact_cosim_tb.cpp] -cflags $flags
open_solution -flow_target vitis solution
set_part xcu55c-fsvh2892-2L-e
create_clock -period 150MHz -name default
config_dataflow -strict_mode warning
config_rtl -deadlock_detection sim
config_interface -m_axi_conservative_mode=1
config_interface -m_axi_addr64
config_interface -m_axi_auto_max_ports=0
# Manual-burst AXI depths are declared on the source interfaces. A depth-only
# Tcl directive on the pointer argument does not configure the generated bundle.
csim_design -ldflags "-pthread -Wl,--threads=2"
csynth_design
# Keep declared FIFO capacities: automatic FIFO enlargement would hide deadlocks.
cosim_design -setup -rtl verilog -tool xsim -random_stall \
    -enable_dataflow_profiling -ldflags "-pthread -Wl,--threads=2"
source [file join $root tests repair_cosim_axi_ids.tcl]
set simulation [file join $out project solution sim verilog]
repair_cosim_axi_ids $simulation pma_to_regraph_adapter
cd $simulation
exec sh sim.sh >@ stdout 2>@ stderr
set channel [open [file join $simulation xsim.log] r]
set transcript [read $channel]
close $channel
foreach line [split $transcript "\n"] {
    if {[regexp {^UVM_(ERROR|FATAL)\s*:\s*([0-9]+)} [string trim $line] -> kind count] && $count != 0} {
        error "RTL $kind count is $count; retain the failed evidence"
    }
}
set channel [open [file join $out project solution sim wrapc_pc temp0.log] r]
set comparison [read $channel]
close $channel
if {[regexp -all {PMA_RTL_CASE_PASS} $comparison] != 8} {
    error "all eight RTL output comparisons are required"
}
puts "PMA_RANDOM_STALL_RTL_OUTPUT_CHECK_PASS"
close_project
exit
