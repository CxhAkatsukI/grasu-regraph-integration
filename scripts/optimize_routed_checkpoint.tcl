# Produce a separate candidate; final timing and bus-skew signoff remain mandatory.
if {$argc != 2} {
    error "usage: routed-checkpoint.dcp existing-output-directory"
}
set checkpoint [file normalize [lindex $argv 0]]
set output [file normalize [lindex $argv 1]]
if {![file isfile $checkpoint] || ![file isdirectory $output]} {
    error "checkpoint and existing isolated output directory required"
}
if {[version -short] ne "2024.1"} {
    error "this repair harness is validated only for Vivado 2024.1"
}
foreach name {timing_before.rpt route_before.rpt clocks_before.rpt timing_after.rpt
              route_after.rpt clocks_after.rpt bus_skew_after.rpt optimized_routed.dcp} {
    if {[file exists [file join $output $name]]} {
        error "refusing to overwrite repair evidence: $name"
    }
}
set_param general.maxThreads 4
open_checkpoint $checkpoint
if {![report_route_status -boolean_check ROUTED_FULLY]} {
    error "repair requires a fully routed input checkpoint"
}
report_route_status -file [file join $output route_before.rpt]
report_clocks -file [file join $output clocks_before.rpt]
report_timing_summary -max_paths 20 -file [file join $output timing_before.rpt] -warn_on_violation

phys_opt_design -directive ExploreWithHoldFix

if {![report_route_status -boolean_check ROUTED_FULLY]} {
    error "optimized candidate is not fully routed"
}
report_route_status -file [file join $output route_after.rpt]
report_clocks -file [file join $output clocks_after.rpt]
report_timing_summary -max_paths 20 -file [file join $output timing_after.rpt] -warn_on_violation
report_bus_skew -file [file join $output bus_skew_after.rpt] -warn_on_violation
write_checkpoint [file join $output optimized_routed.dcp]
puts "POST_ROUTE_CANDIDATE_WRITTEN_NOT_SIGNED_OFF"
close_design
exit
