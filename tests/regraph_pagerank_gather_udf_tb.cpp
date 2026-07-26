#include <ap_int.h>

#include <cassert>
#include <cmath>
#include <cstdint>

#include "regraph_pagerank/l2.h"

int main()
{
    const prop_t left = regraph_float_to_word(0.1F);
    const prop_t right = regraph_float_to_word(-0.025F);
    const prop_t sum = gatherFunc(left, right);
    assert(std::fabs(regraph_word_to_float(sum) - 0.075F) <= 1.0e-7F);
    assert(preprocessProperty(left) == left);
    assert(scatterFunc(left, 99) == left);
    return 0;
}
