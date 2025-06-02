module axis_prefetch #(
    parameter integer DATA_WIDTH = 32
) (
    input wire aclk,
    input wire aresetn,

    input  wire [DATA_WIDTH-1:0] s_axis_tdata,
    input  wire                  s_axis_tvalid,
    output wire                  s_axis_tready,
    input  wire                  s_axis_tlast,

    output wire [DATA_WIDTH-1:0] m_axis_tdata,
    output wire                  m_axis_tvalid,
    input  wire                  m_axis_tready,
    output wire                  m_axis_tlast
);

    // Process Control Signals
    reg valid_o;

    assign s_axis_tready = aresetn ? !m_axis_tvalid || m_axis_tready : 1'b0;

    assign m_axis_tvalid = valid_o;

    always @(posedge aclk) begin
        if (!aresetn) begin
            valid_o <= 1'b0;
        end else if (s_axis_tvalid && s_axis_tready) begin
            valid_o <= 1'b1;
        end else if (m_axis_tvalid && m_axis_tready) begin
            valid_o <= 0;
        end
    end

    // Process Data
    localparam integer TOTAL_WIDTH = DATA_WIDTH + 1;

    wire [TOTAL_WIDTH-1 : 0] data_i;
    reg [TOTAL_WIDTH-1 : 0] data_o;

    assign data_i = {s_axis_tlast, s_axis_tdata};

    always @(posedge aclk) begin
        if (s_axis_tvalid && s_axis_tready) begin
            data_o <= data_i;
        end
    end

    assign {m_axis_tlast, m_axis_tdata} = data_o;

endmodule
