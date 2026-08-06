#include <ap_int.h>
#include <hls_stream.h>

#include <iostream>

#include "../kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp"

namespace {

constexpr unsigned kBlockBeats = SRC_BUFFER_SIZE >> 4;

void push_request(hls::stream<l_ppb_request_pkt> &stream,
                  unsigned block,
                  bool last)
{
    l_ppb_request_pkt request;
    request.data = block;
    request.last = last;
    stream.write(request);
}

bool check_response(hls::stream<l_ppb_response_pkt> &stream,
                    const ap_uint<512> *expected,
                    unsigned block)
{
    const unsigned base = block * kBlockBeats;
    for (unsigned offset = 0; offset < kBlockBeats; ++offset) {
        const l_ppb_response_pkt response = stream.read();
        if (response.last || response.dest != base + offset ||
            response.data != expected[base + offset]) {
            return false;
        }
    }
    return stream.read().last == 1;
}

}  // namespace

int main()
{
    static ap_uint<512> source_a[2 * kBlockBeats];
    static ap_uint<512> source_b[2 * kBlockBeats];
    for (unsigned index = 0; index < 2 * kBlockBeats; ++index) {
        source_a[index] = 0x100000 + index;
        source_b[index] = 0x200000 + index;
    }

    hls::stream<l_ppb_request_pkt> request_a;
    hls::stream<l_ppb_request_pkt> request_b;
    hls::stream<l_ppb_response_pkt> response_a;
    hls::stream<l_ppb_response_pkt> response_b;
    push_request(request_a, 1, false);
    push_request(request_a, 0, true);
    push_request(request_b, 0, false);
    push_request(request_b, 0, true);

    sharedLittleKernelReadMemory<0>(
        source_a, source_b, 1, 1,
        request_a, request_b, response_a, response_b);

    if (!check_response(response_a, source_a, 1) ||
        !check_response(response_b, source_b, 0) ||
        !response_a.empty() || !response_b.empty()) {
        std::cerr << "shared K4 HBM reader response mismatch\n";
        return 1;
    }
    std::cout << "regraph_k4_shared_hbm_wrapper_tb PASS\n";
    return 0;
}
