`define ALIGNED(width) ((width + 7) / 8 * 8)
`define SAFE_WIDTH(width) width > 0 ? width : 1

module q_format_converter #(
    parameter integer M_IN = 1,
    parameter integer N_IN = 1,
    parameter integer M_OUT = 1,
    parameter integer N_OUT = 1,
    parameter integer ALLOW_OVERFLOW = 1
) (
    input wire aclk,
    input wire aresetn,

    input  wire [`ALIGNED(M_IN+N_IN+1)-1 : 0] s_axis_tdata,
    output wire                               s_axis_tready,
    input  wire                               s_axis_tvalid,
    input  wire                               s_axis_tlast,

    output wire [`ALIGNED(M_OUT+N_OUT+1)-1 : 0] m_axis_tdata,
    input  wire                                 m_axis_tready,
    output wire                                 m_axis_tvalid,
    output wire                                 m_axis_tlast
);

    localparam integer S_M_IN = `SAFE_WIDTH(M_IN);
    localparam integer S_N_IN = `SAFE_WIDTH(N_IN);
    localparam integer S_M_OUT = `SAFE_WIDTH(M_OUT);
    localparam integer S_N_OUT = `SAFE_WIDTH(N_OUT);

    // Data
    wire [  M_IN+N_IN : 0] data_i;
    wire [M_OUT+N_OUT : 0] data_o;

    assign data_i = s_axis_tdata[M_IN+N_IN : 0];

    // Sign Bit
    wire sgn_i;
    wire sgn_o;

    assign sgn_i = data_i[M_IN+N_IN];
    assign sgn_o = sgn_i;

    // Fractional Part
    wire [ S_N_IN-1 : 0] frac_i;
    wire [S_N_OUT-1 : 0] frac_o;

    assign frac_i = data_i[S_N_IN-1 : 0];

    generate
        if (N_IN > N_OUT) begin : gen_n_fit
            // Fit Fractional Part
            assign frac_o = frac_i[N_IN-1 : N_IN-S_N_OUT];
        end else if (N_IN < N_OUT) begin : gen_n_expand
            // Expand Fractional Part
            if (N_IN > 0) begin : gen_n_expand_exist
                assign frac_o = {frac_i, {N_OUT - N_IN{1'b0}}};
            end else begin : gen_n_expand_zero
                assign frac_o = {N_OUT{1'b0}};
            end
        end else begin : gen_n_keep
            // Keep Fractional Part
            assign frac_o = frac_i;
        end
    endgenerate


    // Integer Part
    wire [ S_M_IN-1 : 0] int_i;
    wire [S_M_OUT-1 : 0] int_o;

    assign int_i = data_i[S_M_IN+N_IN-1 : N_IN];

    generate
        if (M_IN > M_OUT) begin : gen_m_fit
            // Fit Integer Part
            assign int_o = int_i[S_M_OUT-1 : 0];
        end else if (M_IN < M_OUT) begin : gen_m_expand
            // Expand Integer Part
            if (M_IN > 0) begin : gen_m_expand_exist
                assign int_o = {{M_OUT - M_IN{sgn_i}}, int_i};
            end else begin : gen_m_expand_zero
                assign int_o = {M_OUT{sgn_i}};
            end
        end else begin : gen_m_keep
            // Keep Integer Part
            assign int_o = int_i;
        end
    endgenerate

    wire [M_OUT+N_OUT : 0] sgn_int_frac_o;

    assign sgn_int_frac_o[M_OUT+N_OUT] = sgn_o;

    if (M_OUT > 0) begin : gen_int_exist
        assign sgn_int_frac_o[M_OUT+N_OUT-1 : N_OUT] = int_o;
    end

    if (N_OUT > 0) begin : gen_frac_exist
        assign sgn_int_frac_o[N_OUT-1 : 0] = frac_o;
    end

    generate
        if (M_IN > M_OUT && !ALLOW_OVERFLOW) begin : gen_saturation
            wire overflow;
            assign overflow = |({M_IN - M_OUT{sgn_i}} ^ int_i[M_IN-1 : M_OUT]);

            assign data_o = (overflow)  // Overflow Check
                ? {sgn_o, {M_OUT + N_OUT{~sgn_o}}}  // Saturation
                : sgn_int_frac_o;  // Normal Value
        end else begin : gen_overflow
            assign data_o = sgn_int_frac_o;  // Normal Value
        end
    endgenerate

    reg [`ALIGNED(M_OUT+N_OUT+1)-1 : 0] tdata;
    reg                                 tvalid;
    reg                                 tlast;

    assign s_axis_tready = aresetn ? (!m_axis_tvalid || m_axis_tready) : 1'b0;

    always @(posedge aclk) begin
        if (!aresetn) begin
            tvalid <= 1'b0;
        end else if (s_axis_tready && s_axis_tvalid) begin
            tvalid <= 1'b1;
        end else if (m_axis_tready && m_axis_tvalid) begin
            tvalid <= 1'b0;
        end
    end

    always @(posedge aclk) begin
        if (s_axis_tready && s_axis_tvalid) begin
            tdata <= data_o;
            tlast <= s_axis_tlast;
        end
    end

    assign m_axis_tdata  = tdata;
    assign m_axis_tvalid = tvalid;
    assign m_axis_tlast  = tlast;

endmodule

