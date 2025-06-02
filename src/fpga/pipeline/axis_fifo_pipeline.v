module axis_fifo_pipeline #(
    parameter integer INPUT_WIDTH  = 32,
    parameter integer OUTPUT_WIDTH = 32,
    parameter integer FIFO_DEPTH   = 16
) (
    input wire aclk,
    input wire aresetn,

    input  wire [INPUT_WIDTH-1:0] s_axis_tdata,
    input  wire                   s_axis_tvalid,
    output wire                   s_axis_tready,
    input  wire                   s_axis_tlast,

    output wire [OUTPUT_WIDTH-1:0] m_axis_tdata,
    output wire                    m_axis_tvalid,
    input  wire                    m_axis_tready,
    output wire                    m_axis_tlast,

    output wire overflow
);

    // Handshake Signals
    wire s_handshake;
    wire m_handshake;

    assign s_handshake = s_axis_tvalid && s_axis_tready;
    assign m_handshake = m_axis_tvalid && m_axis_tready;

    // Counter
    localparam integer CounterWidth = $clog2(FIFO_DEPTH + 1);

    reg [CounterWidth-1 : 0] counter;

    always @(posedge aclk) begin
        if (!aresetn) begin
            counter <= 0;
        end else begin
            if (s_handshake && !m_handshake) begin
                counter <= counter + 1;
            end else if (!s_handshake && m_handshake) begin
                counter <= counter - 1;
            end else begin
                counter <= counter;
            end
        end
    end

    // Pipeline
    wire [ INPUT_WIDTH-1 : 0] data_i;
    wire [OUTPUT_WIDTH-1 : 0] data_o;

    assign data_i = s_axis_tdata;

    wire valid_i;
    wire last_i;
    wire valid_o;
    wire last_o;

    assign valid_i = s_handshake;
    assign last_i  = s_axis_tlast;

    // FIFO
    localparam integer TOTAL_WIDTH = OUTPUT_WIDTH + 1;  // 1 bit for last

    // FIFO Data Signals
    wire [TOTAL_WIDTH-1 : 0] fifo_din;
    wire [TOTAL_WIDTH-1 : 0] fifo_dout;

    assign fifo_din                     = {last_o, data_o};
    assign {m_axis_tlast, m_axis_tdata} = fifo_dout;

    // FIFO Control Signals
    wire fifo_wr_en;
    wire fifo_rd_en;
    wire fifo_wr_rst_busy;
    wire fifo_rd_rst_busy;
    wire fifo_empty;
    wire fifo_full;
    wire fifo_ready;

    assign fifo_ready    = !fifo_wr_rst_busy && !fifo_rd_rst_busy;

    assign fifo_wr_en    = valid_o;
    assign fifo_rd_en    = m_handshake;

    assign s_axis_tready = fifo_ready ? (counter < FIFO_DEPTH) : 1'b0;
    assign m_axis_tvalid = fifo_ready ? !fifo_empty : 1'b0;

    xpm_fifo_sync #(
        .DOUT_RESET_VALUE("0"),
        .ECC_MODE("no_ecc"),
        .FIFO_MEMORY_TYPE("auto"),
        .READ_MODE("fwft"),
        .FIFO_READ_LATENCY(1),
        .FIFO_WRITE_DEPTH(FIFO_DEPTH),
        .PROG_EMPTY_THRESH(10),
        .PROG_FULL_THRESH(10),
        .RD_DATA_COUNT_WIDTH(CounterWidth),
        .READ_DATA_WIDTH(TOTAL_WIDTH),
        .WRITE_DATA_WIDTH(TOTAL_WIDTH),
        .WR_DATA_COUNT_WIDTH(CounterWidth)
    ) xpm_fifo_sync_inst (
        .wr_clk(aclk),
        .rst(~aresetn),

        .din(fifo_din),
        .wr_en(fifo_wr_en),
        .full(fifo_full),
        .prog_full(),
        .wr_data_count(),

        .dout(fifo_dout),
        .rd_en(fifo_rd_en),
        .empty(fifo_empty),
        .prog_empty(),
        .rd_data_count(),

        .injectdbiterr(1'b0),
        .injectsbiterr(1'b0),
        .dbiterr(),
        .sbiterr(),

        .wr_rst_busy(fifo_wr_rst_busy),
        .rd_rst_busy(fifo_rd_rst_busy)
    );

    // Interrupt Signals
    assign overflow = fifo_full && valid_o;

    // Internal Pipeline
    pipeline #(
        .INPUT_WIDTH(INPUT_WIDTH),
        .OUTPUT_WIDTH(OUTPUT_WIDTH)
    ) pipeline_inst (
        .aclk(aclk),
        .aresetn(aresetn),

        .s_axis_tdata (data_i),
        .s_axis_tvalid(valid_i),
        .s_axis_tlast (last_i),

        .m_axis_tdata (data_o),
        .m_axis_tvalid(valid_o),
        .m_axis_tlast (last_o)
    );


endmodule
