// Dense FC layer with the 2x2 sum-pool folded in. 81% of the network's
// weights live here.
//
// The golden model computes pooled = sum_pool_2x2(c3_spikes) then
// i = pooled @ W. Folded:  W[n,j] * pooled[j]  =  W[n,j] added once per
// spike in pool window j. So this engine never materialises the pool -- it
// walks the raw c3 spike map with 4 spike positions sharing each weight,
// and stays multiplier-free like everything else in the datapath.
//
//   for n in 0..N_OUT-1:                     one output neuron
//       acc = 0
//       for j in 0..N_POOL-1:                pool window (c, py, px)
//           for p in 0..3:                   position in the 2x2 window
//               y = 2*py + (p>>1);  x = 2*px + (p&1)
//               if spike[c, y, x]: acc += W[n, j]
//       (V, spike) = lif_update(vmem[n], acc)     THRESHOLD = 256 (D0004:
//                                                 the pool's /4 lives in
//                                                 the threshold's 2^(k+2))
//
// Input rows/cols 4 of the 5x5 map are never addressed (y,x <= 3), exactly
// like the golden model's floor-cropped pool.
//
// Interface and read discipline identical to conv_layer (D0012: registered
// reads everywhere). Address formulas match sim/export_fc_vectors.py.
//
// UNVERIFIED until sim/run_fc_tb.sh passes. Never synthesised.

`default_nettype none

module fc_layer #(
    parameter C_IN = 64, H_IN = 5, W_IN = 5,   // c3 spike map geometry
    parameter N_OUT = 128,
    parameter WIDTH = 16, LEAK_SHIFT = 3,
    parameter signed [15:0] THRESHOLD = 256,
    parameter WEIGHT_FILE = "sim/vectors/fc_w.hex",
    parameter IN_BITS = C_IN * H_IN * W_IN,
    parameter N_POOL  = C_IN * 4               // pool windows = j index
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        clear,
    input  wire        start,
    output reg         busy,
    output reg         done,

    input  wire                       in_we,
    input  wire [$clog2(IN_BITS)-1:0] in_addr,
    input  wire                       in_data,

    input  wire [$clog2(N_OUT)-1:0]   out_addr,
    output wire                       out_data,
    input  wire [$clog2(N_OUT)-1:0]   v_addr,
    output wire signed [WIDTH-1:0]    v_data
);

    reg signed [7:0]       wrom [0:N_OUT*N_POOL-1];
    reg                    in_mem [0:IN_BITS-1];
    reg                    out_mem [0:N_OUT-1];
    reg signed [WIDTH-1:0] vmem [0:N_OUT-1];

    initial $readmemh(WEIGHT_FILE, wrom);

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

    // Pipelined MAC loop, same shape as conv_layer: each S_MAC cycle issues
    // the read for position (j,p) while consuming the one before; S_TAIL
    // consumes the last. `prime` marks the no-consume first cycle.
    localparam S_IDLE = 0, S_CLEAR = 1, S_MAC = 2, S_TAIL = 3,
               S_VRD = 4, S_UPDATE = 5;
    reg [2:0] state;
    reg prime;

    integer n, j, p, clr;
    reg signed [WIDTH-1:0] acc;
    reg                    in_bit_r;
    reg signed [7:0]       w_r;
    reg signed [WIDTH-1:0] v_r;

    // pool window j = (c*2 + py)*2 + px; position p = (dy, dx)
    wire [31:0] c  = j >> 2;
    wire [31:0] py = (j >> 1) & 1;
    wire [31:0] px = j & 1;
    wire [31:0] y  = 2*py + (p >> 1);
    wire [31:0] x  = 2*px + (p & 1);

    wire signed [WIDTH-1:0] v_next;
    wire                    spike_next;
    lif_update #(
        .WIDTH(WIDTH), .LEAK_SHIFT(LEAK_SHIFT), .THRESHOLD(THRESHOLD)
    ) update (
        .v_in(v_r), .current_in(acc), .v_out(v_next), .spike(spike_next)
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
                n <= 0; j <= 0; p <= 0;
                acc <= 0; prime <= 1'b1;
                busy <= 1'b1; state <= S_MAC;
            end
        end

        S_CLEAR: begin
            vmem[clr] <= 0;
            out_mem[clr] <= 1'b0;
            if (clr == N_OUT-1) begin state <= S_IDLE; done <= 1'b1; end
            else clr <= clr + 1;
        end

        S_MAC: begin
            in_bit_r <= in_mem[(c*H_IN + y)*W_IN + x];
            w_r      <= wrom[n*N_POOL + j];
            if (!prime && in_bit_r) acc <= acc + {{(WIDTH-8){w_r[7]}}, w_r};  // explicit sign-extend
            prime <= 1'b0;
            if (p != 3) p <= p + 1;
            else begin p <= 0;
                if (j != N_POOL-1) j <= j + 1;
                else begin j <= 0; state <= S_TAIL; end
            end
        end

        S_TAIL: begin
            if (in_bit_r) acc <= acc + {{(WIDTH-8){w_r[7]}}, w_r};  // explicit sign-extend
            state <= S_VRD;
        end

        S_VRD: begin
            v_r   <= vmem[n];
            state <= S_UPDATE;
        end

        S_UPDATE: begin
            vmem[n]    <= v_next;
            out_mem[n] <= spike_next;
            acc <= 0;
            prime <= 1'b1;
            if (n != N_OUT-1) begin n <= n + 1; state <= S_MAC; end
            else begin state <= S_IDLE; done <= 1'b1; end
        end

        endcase
    end

endmodule

`default_nettype wire
