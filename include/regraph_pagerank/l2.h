#ifndef GRASU_REGRAPH_PAGERANK_L2_H
#define GRASU_REGRAPH_PAGERANK_L2_H

#include <ap_int.h>
#include <cstdint>

typedef ap_uint<32> prop_t;

static float regraph_word_to_float(ap_uint<32> word)
{
#pragma HLS INLINE
    union {
        std::uint32_t word;
        float value;
    } bits = {word.to_uint()};
    return bits.value;
}

static ap_uint<32> regraph_float_to_word(float value)
{
#pragma HLS INLINE
    union {
        float value;
        std::uint32_t word;
    } bits = {value};
    return bits.word;
}

inline prop_t preprocessProperty(prop_t source)
{
#pragma HLS INLINE
    return source;
}

inline prop_t scatterFunc(prop_t source, prop_t edge_property)
{
#pragma HLS INLINE
    (void)edge_property;
    return source;
}

inline prop_t gatherFunc(prop_t original, prop_t update)
{
#pragma HLS INLINE
    return regraph_float_to_word(
        regraph_word_to_float(original) + regraph_word_to_float(update));
}

#endif
