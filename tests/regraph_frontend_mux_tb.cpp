#include <array>
#include <cassert>

#include "../kernels/regraph_frontend_mux/regraph_frontend_mux.cpp"

int main()
{
    for (unsigned selected = 0; selected < 4; ++selected) {
        std::array<hls::stream<l_tmp_prop_pkt>, 4> inputs;
        for (unsigned input = 0; input < 4; ++input) {
            for (unsigned packet = 0; packet < 3; ++packet) {
                l_tmp_prop_pkt value;
                value.data = input * 16 + packet;
                inputs[input].write(value);
            }
        }
        hls::stream<l_tmp_prop_pkt> output;
        regraph_frontend_mux(inputs[0], inputs[1], inputs[2], inputs[3],
                             selected, 3, output);
        assert(output.size() == 3);
        for (unsigned packet = 0; packet < 3; ++packet) {
            assert(output.read().data == selected * 16 + packet);
        }
        for (unsigned input = 0; input < 4; ++input) {
            assert(inputs[input].size() == (input == selected ? 0 : 3));
            while (!inputs[input].empty()) {
                (void)inputs[input].read();
            }
        }
    }
    return 0;
}
