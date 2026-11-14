# ==============================================================================
# scripts/run_opensta.tcl
# OpenSTA Static Timing Analysis (STA) Script for CNN Accelerators
# Usage:
#   sta scripts/run_opensta.tcl
# Parameters configured via environment variables:
#   DESIGN_NAME: "cnn_accel" or "cnn_accel_parallel" (default: "cnn_accel")
#   LIB_FILE: Path to target .lib (e.g. sky130_fd_sc_hd__tt_025C_1v80.lib)
#   SDC_FILE: Path to constraints (default: constraints/cnn_accel.sdc)
# ==============================================================================

set design_name [expr {[info exists env(DESIGN_NAME)] ? $env(DESIGN_NAME) : "cnn_accel"}]
set lib_file    [expr {[info exists env(LIB_FILE)] ? $env(LIB_FILE) : ""}]
set sdc_file    [expr {[info exists env(SDC_FILE)] ? $env(SDC_FILE) : "constraints/cnn_accel.sdc"}]
set netlist     "src/${design_name}_synth.v"

puts "=============================================================="
puts "  OpenSTA Static Timing Analysis: $design_name"
puts "=============================================================="

if {$lib_file eq "" || ![file exists $lib_file]} {
    puts "NOTE: Target Liberty library file not specified or not found."
    puts "      To run physical STA, provide a valid PDK .lib file via LIB_FILE environment variable."
    puts "      Example:"
    puts "        export LIB_FILE=/path/to/sky130_fd_sc_hd__tt_025C_1v80.lib"
    puts "        sta scripts/run_opensta.tcl"
    exit 0
}

puts "Reading Liberty library: $lib_file"
read_liberty $lib_file

puts "Reading synthesized netlist: $netlist"
read_verilog $netlist

puts "Linking design top module: $design_name"
link_design $design_name

puts "Reading SDC timing constraints: $sdc_file"
read_sdc $sdc_file

puts "\n--- Timing Check: Setup Timing & Worst Slack ---"
report_checks -path_delay max -fields {slew cap input nets fanout} -digits 3

puts "\n--- Timing Check: Hold Timing ---"
report_checks -path_delay min -fields {slew cap input nets fanout} -digits 3

puts "\n--- Summary Metrics ---"
report_worst_slack -max
report_worst_slack -min
report_tns

puts "=============================================================="
puts "  OpenSTA Timing Analysis Complete"
puts "=============================================================="
