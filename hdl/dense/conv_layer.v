// Dense (clock-driven) spiking conv layer: 3x3, stride 2, pad 1.
//
// This is the baseline datapath of the thesis: every timestep it visits every
// output neuron whether anything spiked or not. One shared arithmetic unit,
// membranes in RAM -- the opposite of one-module-per-neuron.
//
//   for oc, oy, ox:                          outer FSM counters
//       acc = 0
//       for ic, ky, kx:                      inner FSM counters
//           iy = 2*oy + ky - 1               (pad 1, stride 2)
//           ix = 2*ox + kx - 1
//           if in bounds and spike_in[ic,iy,ix]:
//               acc += W[oc,ic,ky,kx]        no multiplier: spikes are 0/1
//       (V, spike) = lif_update(vmem[oc,oy,ox], acc)   the M2-verified core
//
// Address formulas match sim/export_conv_vectors.py line for line; that
// agreement is verified by the testbench, not assumed.
//
// Interface: pulse `clear` once per sample (zeroes membranes), then per
// timestep fill the input buffer through the write port and pulse `start`;
// `done` pulses when the sweep finishes. Spike and membrane read ports exist
// for the testbench and, later, the next layer.
//
// All memory reads are REGISTERED (address on one edge, data the next) so
// synthesis can map wrom/in_mem/vmem onto block RAM -- the D0012 pass.
// External read ports carry the same one-cycle latency. Weight loading
// still uses $readmemh, which Vivado honours at synthesis if the hex file
// is added as a project source.
//
// UNVERIFIED until sim/run_conv_tb.sh passes. Never synthesised.

`default_nettype none

module conv_layer #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter WIDTH = 16, LEAK_SHIFT = 3,
    parameter signed [15:0] THRESHOLD = 64,
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex",
    // BAKED_WEIGHTS: 0 = load WEIGHT_FILE with $readmemh (simulation, any
    // layer); 1 = use the compiled-in conv1 table from
    // hdl/dense/weights/conv1_w.vh (synthesis: no file dependency, so a
    // silently-missing hex file can never yield a zero ROM on the board).
    parameter BAKED_WEIGHTS = 0,
    parameter IN_BITS  = C_IN * H_IN * W_IN,
    parameter NEURONS  = C_OUT * H_OUT * W_OUT
) (
    input  wire        clk,
    input  wire        rst,          // sync; aborts to IDLE
    input  wire        clear,        // pulse: zero membranes (new sample)
    input  wire        start,        // pulse: process one timestep
    output reg         busy,
    output reg         done,         // one-cycle pulse at timestep end

    input  wire                        in_we,    // input spike buffer write
    input  wire [$clog2(IN_BITS)-1:0]  in_addr,
    input  wire                        in_data,

    input  wire [$clog2(NEURONS)-1:0]  out_addr, // output spike read
    output wire                        out_data,
    input  wire [$clog2(NEURONS)-1:0]  v_addr,   // membrane read
    output wire signed [WIDTH-1:0]     v_data
);

    // --- memories ---------------------------------------------------------
    reg signed [7:0]        wrom [0:C_OUT*C_IN*9-1];
    reg                     in_mem [0:IN_BITS-1];
    reg                     out_mem [0:NEURONS-1];
    reg signed [WIDTH-1:0]  vmem [0:NEURONS-1];

    generate
        if (BAKED_WEIGHTS) begin : g_baked
            initial begin
                `include "weights/conv1_w.vh"
            end
        end else begin : g_file
            initial $readmemh(WEIGHT_FILE, wrom);
        end
    endgenerate

    // External read ports: REGISTERED (D0012). Present the address on one
    // clock edge; the data is valid after the next. This is the access
    // pattern block RAM physically provides.
    reg                    out_data_r;
    reg signed [WIDTH-1:0] v_data_r;
    always @(posedge clk) begin
        out_data_r <= out_mem[out_addr];
        v_data_r   <= vmem[v_addr];
    end
    assign out_data = out_data_r;
    assign v_data   = v_data_r;

    always @(posedge clk)
        if (in_we) in_mem[in_addr] <= in_data;

    // --- FSM --------------------------------------------------------------
    // Reads are registered (BRAM-style) AND pipelined: in S_MAC each cycle
    // issues the read for the current kernel position while accumulating the
    // one issued the cycle before. One prologue cycle per neuron (first
    // issue, nothing to consume yet, flagged by `prime`) and one epilogue
    // (S_TAIL consumes the final read). ~21 cycles/neuron vs 38 for the
    // unpipelined version; same bit-exact behaviour, same testbench.
    localparam S_IDLE = 0, S_CLEAR = 1, S_MAC = 2, S_TAIL = 3,
               S_VRD = 4, S_UPDATE = 5;
    reg [2:0] state;
    reg prime;  // first S_MAC cycle of a neuron: issue only, no consume

    // counters are 32-bit signed `integer`s for clarity; synthesis prunes
    integer oc, oy, ox;         // which output neuron
    integer ic, ky, kx;         // where in its kernel window
    integer clr;                // clear sweep address
    reg signed [WIDTH-1:0] acc;

    // registered memory outputs (the "one cycle later" data)
    reg                    in_bit_r;
    reg signed [7:0]       w_r;
    reg signed [WIDTH-1:0] v_r;

    // input coordinate for the CURRENT counter values (combinational
    // address math feeding the registered reads)
    wire signed [31:0] iy = 2*oy + ky - 1;
    wire signed [31:0] ix = 2*ox + kx - 1;
    wire in_bounds = (iy >= 0) && (iy < H_IN) && (ix >= 0) && (ix < W_IN);

    wire [31:0] neuron_addr = (oc*H_OUT + oy)*W_OUT + ox;

    // the one shared LIF update -- same module the M2 testbench verified
    wire signed [WIDTH-1:0] v_next;
    wire                    spike_next;
    lif_update #(
        .WIDTH(WIDTH), .LEAK_SHIFT(LEAK_SHIFT), .THRESHOLD(THRESHOLD)
    ) update (
        .v_in(v_r), .current_in(acc),
        .v_out(v_next), .spike(spike_next)
    );

    always @(posedge clk) begin
        done <= 1'b0;
        if (rst) begin
            state <= S_IDLE; busy <= 1'b0;
        end else case (state)

        S_IDLE: begin
            busy <= 1'b0;
            if (clear) begin
                clr <= 0; busy <= 1'b1; state <= S_CLEAR;
            end else if (start) begin
                oc <= 0; oy <= 0; ox <= 0;
                ic <= 0; ky <= 0; kx <= 0;
                acc <= 0; prime <= 1'b1;
                busy <= 1'b1; state <= S_MAC;
            end
        end

        S_CLEAR: begin
            vmem[clr] <= 0;
            out_mem[clr] <= 1'b0;
            if (clr == NEURONS-1) begin state <= S_IDLE; done <= 1'b1; end
            else clr <= clr + 1;
        end

        S_MAC: begin  // issue read for position k, consume position k-1
            in_bit_r <= in_bounds ? in_mem[(ic*H_IN + iy)*W_IN + ix] : 1'b0;
            w_r      <= wrom[((oc*C_IN + ic)*3 + ky)*3 + kx];
            if (!prime && in_bit_r) acc <= acc + {{(WIDTH-8){w_r[7]}}, w_r};  // explicit sign-extend
            prime <= 1'b0;
            if (kx != 2)      kx <= kx + 1;
            else begin kx <= 0;
                if (ky != 2)  ky <= ky + 1;
                else begin ky <= 0;
                    if (ic != C_IN-1) ic <= ic + 1;
                    else begin ic <= 0; state <= S_TAIL; end
                end
            end
        end

        S_TAIL: begin  // consume the final read of this neuron's window
            if (in_bit_r) acc <= acc + {{(WIDTH-8){w_r[7]}}, w_r};  // explicit sign-extend
            state <= S_VRD;
        end

        S_VRD: begin  // issue the membrane read for this neuron
            v_r   <= vmem[neuron_addr];
            state <= S_UPDATE;
        end

        S_UPDATE: begin
            vmem[neuron_addr]    <= v_next;
            out_mem[neuron_addr] <= spike_next;
            acc <= 0;
            prime <= 1'b1;
            if (ox != W_OUT-1) ox <= ox + 1;
            else begin ox <= 0;
                if (oy != H_OUT-1) oy <= oy + 1;
                else begin oy <= 0;
                    if (oc != C_OUT-1) oc <= oc + 1;
                    else begin state <= S_IDLE; done <= 1'b1; end
                end
            end
            if (!(ox == W_OUT-1 && oy == H_OUT-1 && oc == C_OUT-1))
                state <= S_MAC;
        end

        endcase
    end

endmodule

`default_nettype wire
