#include <array>
#include <cassert>

#include "../kernels/pma_frontend_mux/pma_frontend_mux.cpp"

int main()
{
    for (unsigned selected = 0; selected < 4; ++selected) {
        std::array<hls::stream<edge_burst_pkt_t>, 4> inputs;
        for (unsigned input = 0; input < 4; ++input) {
            for (unsigned packet = 0; packet < 2; ++packet) {
                edge_burst_pkt_t value;
                value.data = input * 16 + packet;
                value.keep = -1;
                value.strb = -1;
                value.last = packet == 0;
                inputs[input].write(value);
            }
        }
        hls::stream<edge_burst_pkt_t> output;
        pma_frontend_mux(inputs[0], inputs[1], inputs[2], inputs[3],
                         selected, 2, output);
        assert(output.size() == 2);
        const edge_burst_pkt_t first = output.read();
        const edge_burst_pkt_t second = output.read();
        assert(first.data == selected * 16);
        assert(second.data == selected * 16 + 1);
        assert(!first.last);
        assert(second.last);
        for (unsigned input = 0; input < 4; ++input) {
            assert(inputs[input].size() == (input == selected ? 0 : 2));
        }
    }
    return 0;
}
