module axis_circular_buffer #(
    parameter integer DATA_WIDTH  = 32,
    parameter integer TID_WIDTH   = 8,
    parameter integer BUFFER_SIZE = 16
) (
    input wire aclk,
    input wire aresetn,

    input  wire [DATA_WIDTH-1:0] s_axis_tdata,
    input  wire                  s_axis_tvalid,
    output wire                  s_axis_tready,
    input  wire                  s_axis_tlast,
    input  wire [ TID_WIDTH-1:0] s_axis_tid,

    output wire [DATA_WIDTH-1:0] m_axis_tdata,
    output wire                  m_axis_tvalid,
    input  wire                  m_axis_tready,
    output wire                  m_axis_tlast,
    output wire [ TID_WIDTH-1:0] m_axis_tid
);

    // Handshake signals
    wire s_handshake;
    wire m_handshake;

    assign s_handshake = s_axis_tvalid && s_axis_tready;
    assign m_handshake = m_axis_tvalid && m_axis_tready;

    // Buffer Selection
    reg w_buf_sel;
    reg r_buf_sel;

    // Index
    localparam integer INDEX_WIDTH = $clog2(BUFFER_SIZE);
    reg [INDEX_WIDTH-1:0] w_idx;
    reg [INDEX_WIDTH-1:0] r_idx;

    always @(posedge aclk) begin
        if (!aresetn) begin
            w_buf_sel <= 1'b0;
            w_idx     <= 0;
        end else if (s_handshake) begin
            if (s_axis_tlast) begin
                w_buf_sel <= ~r_buf_sel;  // Switch to the unused buffer
                w_idx     <= 0;
            end else if (w_idx < BUFFER_SIZE - 1) begin
                w_idx <= w_idx + 1;
            end
        end
    end

    always @(posedge aclk) begin
        if (!aresetn) begin
            r_buf_sel <= 1'b0;
            r_idx     <= 0;
        end else if (m_handshake) begin
            if (m_axis_tlast) begin
                r_buf_sel <= ~r_buf_sel;  // Switch to the other buffer
                r_idx     <= 0;
            end else if (r_idx < BUFFER_SIZE - 1) begin
                r_idx <= r_idx + 1;
            end
        end
    end

    assign s_axis_tready = aresetn ? 1'b1 : 1'b0;
    assign m_axis_tvalid = w_buf_sel != r_buf_sel || w_idx != r_idx;

    // Double Buffer
    localparam integer TOTAL_WIDTH = DATA_WIDTH + TID_WIDTH + 1;

    reg [TOTAL_WIDTH-1:0] buffer[0:1][0:BUFFER_SIZE-1];

    always @(posedge aclk) begin
        if (s_handshake) begin
            buffer[w_buf_sel][w_idx] <= {s_axis_tlast, s_axis_tid, s_axis_tdata};
        end
    end

    assign {m_axis_tlast, m_axis_tid, m_axis_tdata} = buffer[r_buf_sel][r_idx];

endmodule
