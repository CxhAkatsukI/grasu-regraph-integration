# Read-only signoff of a final checkpoint; do not route or change constraints.
if {$argc != 2} {
    error "usage: checkpoint.dcp output-directory"
}
set checkpoint [file normalize [lindex $argv 0]]
set output [file normalize [lindex $argv 1]]
if {![file isfile $checkpoint] || ![file isdirectory $output]} {
    error "checkpoint and existing isolated output directory required"
}
if {[version -short] ne "2024.1"} {
    error "this signoff harness is validated only for Vivado 2024.1"
}
set_param general.maxThreads 4
open_checkpoint $checkpoint
report_bus_skew -file [file join $output bus_skew.rpt] -warn_on_violation
close_design
exit
