module axis_skid_buffer #(
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

    // Handshake Signals
    wire s_handshake;
    wire m_handshake;

    assign s_handshake = s_axis_tvalid && s_axis_tready;
    assign m_handshake = m_axis_tvalid && m_axis_tready;

    // State Machine
    localparam integer EMPTY = 2'b00;
    localparam integer ACTIVE = 2'b01;
    localparam integer FULL = 2'b11;

    reg [1:0] state;

    always @(posedge aclk) begin
        if (!aresetn) begin
            state <= EMPTY;
        end else begin
            case (state)
                EMPTY: begin
                    if (s_handshake) begin
                        state <= ACTIVE;
                    end
                end
                ACTIVE: begin
                    if (s_handshake && !m_handshake) begin
                        state <= FULL;
                    end else if (!s_handshake && m_handshake) begin
                        state <= EMPTY;
                    end
                end
                FULL: begin
                    if (m_handshake) begin
                        state <= ACTIVE;
                    end
                end
                default: begin
                    state <= EMPTY;
                end
            endcase
        end
    end

    // Process Control Signals
    assign s_axis_tready = aresetn ? (state == EMPTY || state == ACTIVE) : 1'b0;

    assign m_axis_tvalid = state == ACTIVE || state == FULL;

    // Process Data
    localparam integer TOTAL_WIDTH = DATA_WIDTH + 1;  // 1 bit for tlast

    wire [TOTAL_WIDTH-1 : 0] data_i;
    reg  [  TOTAL_WIDTH-1:0] buffer;
    reg  [  TOTAL_WIDTH-1:0] data_o;

    assign data_i = {s_axis_tlast, s_axis_tdata};

    always @(posedge aclk) begin
        case (state)
            EMPTY: begin
                if (s_handshake) begin
                    data_o <= data_i;
                end
            end
            ACTIVE: begin
                if (s_handshake) begin
                    if (m_handshake) begin
                        data_o <= data_i;
                    end else begin
                        buffer <= data_i;
                    end
                end
            end
            FULL: begin
                if (m_handshake) begin
                    data_o <= buffer;
                end
            end
            default: begin
                data_o <= data_o;
                buffer <= buffer;
            end
        endcase
    end

    assign {m_axis_tlast, m_axis_tdata} = data_o;

endmodule
