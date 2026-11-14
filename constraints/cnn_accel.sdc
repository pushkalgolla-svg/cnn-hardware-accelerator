# ==============================================================================
# constraints/cnn_accel.sdc
# Synopsys Design Constraints (SDC) for CNN Hardware Accelerators
# Target: 100.0 MHz Nominal Reference Clock (10.0 ns Period)
# ==============================================================================

# Current unit definitions
set_time_unit -nanoseconds
set_capacitance_unit -picofarads

# 1. Primary Clock Definition
# 100.0 MHz clock frequency -> 10.0 ns period
create_clock -name clk -period 10.0 [get_ports clk]

# 2. Clock Uncertainty (Jitter & Skew Margin: 200 ps)
set_clock_uncertainty 0.200 [get_clocks clk]

# 3. Input Delays (assumes external driving register with 2.0 ns budget)
set_input_delay -clock clk -max 2.000 [all_inputs -no_clocks]
set_input_delay -clock clk -min 0.200 [all_inputs -no_clocks]

# 4. Output Delays (assumes external receiving register with 2.0 ns budget)
set_output_delay -clock clk -max 2.000 [all_outputs]
set_output_delay -clock clk -min 0.200 [all_outputs]

# 5. False Paths / Reset
# Synchronous reset does not require false path, but asynchronous would
# set_false_path -from [get_ports rst]
