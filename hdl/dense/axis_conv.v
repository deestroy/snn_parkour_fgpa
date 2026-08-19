// AXI-Stream wrapper around the dense conv engine.
//
// Translates between the DMA's dialect (32-bit words, tvalid/tready
// handshake, tlast framing) and the engine's (1-bit spike writes, clear/
// start pulses, done). Per sample:
//
//   clear membranes
//   for t in 0..T-1:
//       receive WORDS_IN words, unpack LSB-first into the spike buffer
//       run the engine for one timestep
//       read NEURONS spike bits, pack LSB-first, send WORDS_OUT words
//   (tlast on the final word of the final timestep)
//
// Word <-> bit mapping, both directions: flat index = word*32 + bit, i.e.
// bit 0 of the first word is flat address 0. The host packs with
// numpy packbits(bitorder='little') -- host/conv_test.py and the testbench
// exporter must agree with this line, and the testbench checks they do.
//
// Streaming the spike map after EVERY timestep is deliberate: hardware
// verification keeps the same per-timestep granularity as the golden model.
//
// UNVERIFIED until sim/run_axis_tb.sh passes. Never synthesised.

`default_nettype none

module axis_conv #(
    parameter C_IN  = 2,  H_IN  = 34, W_IN  = 34,
    parameter C_OUT = 16, H_OUT = 17, W_OUT = 17,
    parameter T = 4,
    parameter signed [15:0] THRESHOLD = 64,
    parameter WEIGHT_FILE = "sim/vectors/conv_c1_w.hex",
    parameter BAKED_WEIGHTS = 0,
    // ENGINE: 0 = dense conv_layer (M3/M4);  1 = event-driven ed_conv_layer
    // (M6). Same framing, same words in and out -- the two designs are
    // interchangeable behind this wrapper, which is what makes M7's
    // comparison honest. ED_K = banks for the event-driven engine.
    parameter ENGINE = 0,
    parameter ED_K = 1,
    parameter WT_FILE = "sim/vectors/ed_c1_wt.hex",
    parameter IN_BITS    = C_IN * H_IN * W_IN,
    parameter NEURONS    = C_OUT * H_OUT * W_OUT,
    parameter WORDS_IN   = (IN_BITS + 31) / 32,
    parameter WORDS_OUT  = (NEURONS + 31) / 32
) (
    input  wire        clk,
    input  wire        rst,

    // slave stream: packed input spikes from the DMA (MM2S)
    input  wire [31:0] s_axis_tdata,
    input  wire        s_axis_tvalid,
    output wire        s_axis_tready,
    input  wire        s_axis_tlast,   // accepted but not required

    // master stream: packed output spikes to the DMA (S2MM)
    output reg  [31:0] m_axis_tdata,
    output reg         m_axis_tvalid,
    input  wire        m_axis_tready,
    output reg         m_axis_tlast
);

    // --- the verified engine ---------------------------------------------
    reg                          eng_clear, eng_start;
    wire                         eng_busy, eng_done;
    reg                          in_we;
    reg  [$clog2(IN_BITS)-1:0]   in_addr;
    reg                          in_bit;
    wire [$clog2(NEURONS)-1:0]   out_addr;
    wire                         out_bit;
    wire signed [15:0]           v_unused;
    // Vivado's block-design RTL importer dislikes {$clog2(N){1'b0}} in a
    // port connection; a plainly-typed zero wire is the same thing.
    wire [$clog2(NEURONS)-1:0]   v_addr_zero = 0;

    // event-driven engine takes spike ADDRESS pushes, not bit writes -- and
    // the address is FIELDS {ic, iy, ix} (D0020 rev 2), which the unpacker
    // keeps as three counters walking in lockstep with the flat bit index.
    localparam IC_W = (C_IN > 1) ? $clog2(C_IN) : 1;
    localparam IY_W = $clog2(H_IN), IX_W = $clog2(W_IN);
    reg                          spk_we;
    reg  [IC_W-1:0]              u_ic;
    reg  [IY_W-1:0]              u_iy;
    reg  [IX_W-1:0]              u_ix;
    reg  [IC_W+IY_W+IX_W-1:0]    spk_addr_f;

    generate if (ENGINE == 1) begin : g_ed
        ed_conv_layer #(
            .C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN),
            .C_OUT(C_OUT), .H_OUT(H_OUT), .W_OUT(W_OUT),
            .K(ED_K), .THRESHOLD(THRESHOLD), .WT_FILE(WT_FILE),
            .BAKED_WEIGHTS(BAKED_WEIGHTS)
        ) engine (
            .clk(clk), .rst(rst),
            .clear(eng_clear), .spk_we(spk_we), .spk_addr(spk_addr_f),
            .start(eng_start), .busy(eng_busy), .done(eng_done),
            .out_addr(out_addr), .out_data(out_bit),
            .v_addr(v_addr_zero), .v_data(v_unused)
        );
    end else
    // BAKED_WEIGHTS=1 (synthesis): conv_layer_c1, the generated variant with
    // the conv1 table inlined -- no include, no $readmemh, nothing for Vivado
    // to lose. BAKED_WEIGHTS=0 (simulation of any layer): conv_layer + hex.
    if (BAKED_WEIGHTS) begin : g_baked
        conv_layer_c1 #(
            .C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN),
            .C_OUT(C_OUT), .H_OUT(H_OUT), .W_OUT(W_OUT),
            .THRESHOLD(THRESHOLD)
        ) engine (
            .clk(clk), .rst(rst),
            .clear(eng_clear), .start(eng_start),
            .busy(eng_busy), .done(eng_done),
            .in_we(in_we), .in_addr(in_addr), .in_data(in_bit),
            .out_addr(out_addr), .out_data(out_bit),
            .v_addr(v_addr_zero), .v_data(v_unused)
        );
    end else begin : g_file
        conv_layer #(
            .C_IN(C_IN), .H_IN(H_IN), .W_IN(W_IN),
            .C_OUT(C_OUT), .H_OUT(H_OUT), .W_OUT(W_OUT),
            .THRESHOLD(THRESHOLD), .WEIGHT_FILE(WEIGHT_FILE), .BAKED_WEIGHTS(0)
        ) engine (
            .clk(clk), .rst(rst),
            .clear(eng_clear), .start(eng_start),
            .busy(eng_busy), .done(eng_done),
            .in_we(in_we), .in_addr(in_addr), .in_data(in_bit),
            .out_addr(out_addr), .out_data(out_bit),
            .v_addr(v_addr_zero), .v_data(v_unused)
        );
    end endgenerate

    // --- wrapper FSM ------------------------------------------------------
    localparam S_CLR = 0, S_CLRW = 1, S_RX = 2, S_UNPACK = 3,
               S_GO = 4, S_RUNW = 5, S_TXRD = 6, S_TXCAP = 7, S_TXSEND = 8;
    reg [3:0] state;

    reg [31:0] shift;                       // rx unpack register
    reg [31:0] word_acc;                    // tx pack register
    reg [5:0]  bit_cnt;                     // 0..32 within a word
    reg [$clog2(IN_BITS+1)-1:0]  rx_bits;   // flat input bit index
    reg [$clog2(NEURONS+1)-1:0]  tx_bits;   // flat output bit index
    reg [$clog2(WORDS_OUT+1)-1:0] tx_words;
    reg [$clog2(T+1)-1:0] t_step;

    assign s_axis_tready = (state == S_RX);

    // Address the engine's registered read port combinationally from the
    // bit counter: the engine captures out_mem[tx_bits] during S_TXRD and
    // out_bit is valid in S_TXCAP -- exactly one cycle of latency. (A
    // registered address here would make it two and skew every bit.)
    assign out_addr = tx_bits[$clog2(NEURONS)-1:0];

    always @(posedge clk) begin
        eng_clear <= 1'b0;
        eng_start <= 1'b0;
        in_we     <= 1'b0;
        spk_we    <= 1'b0;

        if (rst) begin
            state <= S_CLR;
            m_axis_tvalid <= 1'b0;
            m_axis_tlast  <= 1'b0;
        end else case (state)

        S_CLR: begin                       // new sample: zero the membranes
            eng_clear <= 1'b1;
            t_step <= 0;
            rx_bits <= 0; u_ic <= 0; u_iy <= 0; u_ix <= 0;
            state <= S_CLRW;
        end

        S_CLRW: if (eng_done) state <= S_RX;

        S_RX: if (s_axis_tvalid) begin     // one word accepted this cycle
            shift <= s_axis_tdata;
            bit_cnt <= 0;
            state <= S_UNPACK;
        end

        S_UNPACK: begin                    // 1 bit -> spike buffer per cycle
            if (rx_bits < IN_BITS) begin
                in_we   <= 1'b1;                    // dense: write every bit
                spk_we  <= shift[0];                // event-driven: push only the 1s
                in_addr <= rx_bits[$clog2(IN_BITS)-1:0];
                spk_addr_f <= {u_ic, u_iy, u_ix};   // same bit, as fields
                in_bit  <= shift[0];
                rx_bits <= rx_bits + 1;
                if (u_ix == W_IN-1) begin
                    u_ix <= 0;
                    if (u_iy == H_IN-1) begin u_iy <= 0; u_ic <= u_ic + 1; end
                    else u_iy <= u_iy + 1;
                end else u_ix <= u_ix + 1;
            end
            shift <= {1'b0, shift[31:1]};
            bit_cnt <= bit_cnt + 1;
            if (bit_cnt == 31 || rx_bits >= IN_BITS - 1) begin
                if (rx_bits >= IN_BITS - 1 && !(rx_bits < IN_BITS))
                    state <= S_GO;                    // padding word done
                else if (rx_bits == IN_BITS - 1)
                    state <= S_GO;                    // last real bit now
                else
                    state <= S_RX;                    // next word please
            end
        end

        S_GO: begin
            eng_start <= 1'b1;
            state <= S_RUNW;
        end

        S_RUNW: if (eng_done) begin
            tx_bits <= 0;
            tx_words <= 0;
            word_acc <= 32'b0;
            bit_cnt <= 0;
            state <= S_TXRD;
        end

        S_TXRD: begin                      // engine captures out_mem[out_addr]
            state <= S_TXCAP;
        end

        S_TXCAP: begin                     // consume the bit read last cycle
            if (tx_bits < NEURONS)
                word_acc[bit_cnt[4:0]] <= out_bit;
            tx_bits <= tx_bits + 1;
            bit_cnt <= bit_cnt + 1;
            if (bit_cnt == 31)
                state <= S_TXSEND;
            else
                state <= S_TXRD;
        end

        S_TXSEND: begin
            if (!m_axis_tvalid) begin
                m_axis_tdata  <= word_acc;
                m_axis_tvalid <= 1'b1;
                m_axis_tlast  <= (tx_words == WORDS_OUT-1) &&
                                 (t_step == T-1);
            end else if (m_axis_tready) begin
                m_axis_tvalid <= 1'b0;
                m_axis_tlast  <= 1'b0;
                word_acc <= 32'b0;
                bit_cnt <= 0;
                if (tx_words == WORDS_OUT-1) begin
                    if (t_step == T-1)
                        state <= S_CLR;    // sample finished
                    else begin
                        t_step <= t_step + 1;
                        rx_bits <= 0; u_ic <= 0; u_iy <= 0; u_ix <= 0;
                        state <= S_RX;     // next timestep's input
                    end
                end else begin
                    tx_words <= tx_words + 1;
                    state <= S_TXRD;
                end
            end
        end

        endcase
    end

endmodule

`default_nettype wire
