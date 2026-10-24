#pragma once
#include <hls_stream.h>
#include "acc_config.h"
#include "acc_data_types.h"
#include "fpga_application.h"

namespace framed_regraph {
using EdgePacket = ap_axiu<512, 0, 0, 0>;
struct Updates { update_set_dt values; bool last; };
}
