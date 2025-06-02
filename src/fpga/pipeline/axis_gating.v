module axis_gating #(
    parameter integer DATA_WIDTH = 32
) (
    input wire aclk,
    input wire aresetn,

    input wire enable,

    input  wire [DATA_WIDTH-1 : 0] s_axis_tdata,
    input  wire                    s_axis_tvalid,
    output wire                    s_axis_tready,
    input  wire                    s_axis_tlast,

    output wire [DATA_WIDTH-1 : 0] m_axis_tdata,
    output wire                    m_axis_tvalid,
    input  wire                    m_axis_tready,
    output wire                    m_axis_tlast
);

    // Handshake Signals
    wire s_handshake;
    wire m_handshake;

    assign s_handshake = s_axis_tvalid && s_axis_tready;
    assign m_handshake = m_axis_tvalid && m_axis_tready;

    // Write and Read Indexes
    reg [1:0] w_idx;
    reg [1:0] r_idx;

    always @(posedge aclk) begin
        if (!aresetn) begin
            w_idx <= 2'b00;
        end else if (s_handshake) begin
            w_idx <= w_idx + 1;
        end
    end

    always @(posedge aclk) begin
        if (!aresetn) begin
            r_idx <= 2'b00;
        end else if (m_handshake) begin
            r_idx <= r_idx + 1;
        end
    end

    // State Machine
    localparam integer EMPTY = 2'b00;
    localparam integer ACTIVE = 2'b01;
    localparam integer FULL = 2'b11;

    reg [1:0] state;

    always @(*) begin
        if (w_idx == r_idx) begin
            state = EMPTY;
        end else if (w_idx[0] != r_idx[0]) begin
            state = ACTIVE;
        end else begin
            state = FULL;
        end
    end

    // Pipeline Stall
    reg stall;

    always @(posedge aclk) begin
        if (!aresetn) begin
            stall <= 1'b1;
        end else if (m_handshake) begin
            stall <= !enable || (state == ACTIVE && !s_handshake);
        end else if (stall && enable && (s_handshake || state != EMPTY)) begin
            stall <= 1'b0;
        end
    end

    assign s_axis_tready = aresetn ? (state == EMPTY || state == ACTIVE) : 1'b0;
    assign m_axis_tvalid = (!stall) ? (state == ACTIVE || state == FULL) : 1'b0;

    // Process Data
    localparam integer TOTAL_WIDTH = DATA_WIDTH + 1;

    reg  [TOTAL_WIDTH-1 : 0] data_o [0:1];

    always @(posedge aclk) begin
        if (s_axis_tvalid && s_axis_tready) begin
            data_o[w_idx[0]] <= {s_axis_tlast, s_axis_tdata};
        end
    end

    assign {m_axis_tlast, m_axis_tdata} = data_o[r_idx[0]];

endmodule
