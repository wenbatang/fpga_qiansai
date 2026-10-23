// Reflected CRC-32/ISO-HDLC: init FFFFFFFF, xorout FFFFFFFF.
function automatic [31:0] crc32_byte(input [31:0] crc, input [7:0] value);
    reg [31:0] c;
    integer bit_index;
    begin
        c = crc ^ {24'd0, value};
        for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1)
            c = c[0] ? (c >> 1) ^ 32'hEDB88320 : c >> 1;
        crc32_byte = c;
    end
endfunction
