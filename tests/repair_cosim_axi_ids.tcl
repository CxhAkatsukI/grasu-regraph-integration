# Vitis HLS 2024.1 can truncate shared-master IDs in its generated VIP types.
# Derive widths from DUT RTL; repair only run-local testbench files, not the DUT.
proc cosim_read {path} {
    set channel [open $path r]
    set value [read $channel]
    close $channel
    return $value
}

proc cosim_replace_once {variable pattern replacement} {
    upvar 1 $variable value
    if {[regsub -all -- $pattern $value $replacement updated] != 1} {
        error "unexpected generated AXI template: $pattern"
    }
    set value $updated
}

proc repair_cosim_axi_ids {simulation kernel} {
    set environment [file join $simulation ${kernel}_subsystem ${kernel}_env.sv]
    set interfaces [file join $simulation svtb sv_module_top.sv]
    set sequences [file join $simulation svtb ${kernel}_subsys_test_sequence_lib.sv]
    foreach path [list $environment $interfaces $sequences] {
        if {[file exists ${path}.before-id-fix]} {
            error "refuse repeated test-environment repair"
        }
    }
    set original [cosim_read $environment]
    set original_interfaces [cosim_read $interfaces]
    set original_sequences [cosim_read $sequences]
    set dut [cosim_read [file join $simulation ${kernel}.v]]
    if {![string match {*v2024.1*} $original]} {
        error "AXI ID workaround is restricted to the inspected 2024.1 template"
    }
    set bindings [regexp -all -inline {axi_master_([a-zA-Z0-9_]+) = axi_pkg::axi_env#\([0-9]+,[0-9]+,[0-9]+,[0-9]+,[0-9]+\)::type_id} $original]
    if {![llength $bindings]} { error "no generated AXI master bindings" }
    set updated $original
    set updated_interfaces $original_interfaces
    set updated_sequences $original_sequences
    foreach {binding bundle} $bindings {
        set parameter [format {parameter\s+C_M_AXI_%s_ID_WIDTH\s*=\s*([0-9]+)\s*;} [string toupper $bundle]]
        if {[regexp -all -- $parameter $dut] != 1 ||
            ![regexp -- $parameter $dut unused width]} {
            error "missing unambiguous DUT AXI ID width for $bundle"
        }
        if {$width < 1 || $width > 4} { error "unexpected AXI ID width: $width" }
        if {[string first "${kernel}_cfg.${bundle}_cfg.id_num" $original] >= 0} {
            error "unexpected existing VIP ID capacity for $bundle"
        }
        set types {[0-9]+,[0-9]+,[0-9]+,[0-9]+,}
        cosim_replace_once updated [format {(axi_pkg::axi_env#\(%s)[0-9]+(\)\s+axi_master_%s\s*;)} $types $bundle] [format {\1%d\2} $width]
        cosim_replace_once updated [format {(axi_master_%s = axi_pkg::axi_env#\(%s)[0-9]+(\)::type_id)} $bundle $types] [format {\1%d\2} $width]
        cosim_replace_once updated_interfaces [format {(axi_if\s+#\(%s)[0-9]+(\)\s+axi_%s_if\s*\()} $types $bundle] [format {\1%d\2} $width]
        cosim_replace_once updated_interfaces [format {(uvm_config_db\s+#\( virtual axi_if#\(%s)[0-9]+(\) \)::set\([^\n]+axi_master_%s\.\*[^\n]+axi_%s_if\);)} $types $bundle $bundle] [format {\1%d\2} $width]
        cosim_replace_once updated_sequences [format {(axi_pkg::axi_slave_sequence#\(%s)[0-9]+(\)\s+axi_slave_%s_seq\s*;)} $types $bundle] [format {\1%d\2} $width]
        set anchor "${kernel}_cfg.${bundle}_cfg.set_default();"
        if {[string first $anchor $updated] < 0 ||
            [string first $anchor $updated] != [string last $anchor $updated]} {
            error "unexpected VIP initialization for $bundle"
        }
        set replacement "$anchor\n        ${kernel}_cfg.${bundle}_cfg.id_num = [expr {1 << $width}];"
        set updated [string map [list $anchor $replacement] $updated]
    }
    # Validate every anchor before changing any generated file.
    foreach path [list $environment $interfaces $sequences] {
        file copy $path ${path}.before-id-fix
    }
    foreach path [list $environment $interfaces $sequences] value [list $updated $updated_interfaces $updated_sequences] {
        set channel [open $path w]
        puts -nonewline $channel $value
        close $channel
    }
    puts "COSIM_AXI_ID_TEMPLATE_REPAIR bundles=[expr {[llength $bindings] / 2}] source=DUT_RTL"
}
