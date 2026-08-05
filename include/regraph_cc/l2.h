#ifndef GRASU_REGRAPH_CC_L2_H
#define GRASU_REGRAPH_CC_L2_H

#include <ap_int.h>

typedef ap_uint<32> prop_t;

static constexpr unsigned REGRAPH_CC_ACTIVE_MASK = 0x80000000U;
static constexpr unsigned REGRAPH_CC_LABEL_MASK = 0x7fffffffU;

inline bool regraph_cc_is_active(prop_t value)
{
#pragma HLS INLINE
    return (value & REGRAPH_CC_ACTIVE_MASK) != 0;
}

inline prop_t regraph_cc_label(prop_t value)
{
#pragma HLS INLINE
    return value & REGRAPH_CC_LABEL_MASK;
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
    return regraph_cc_is_active(source) ? source : prop_t(0);
}

inline prop_t gatherFunc(prop_t original, prop_t update)
{
#pragma HLS INLINE
    if (!regraph_cc_is_active(update)) return original;
    if (!regraph_cc_is_active(original)) return update;
    return regraph_cc_label(update) < regraph_cc_label(original)
               ? update
               : original;
}

inline prop_t applyFunc(prop_t temporary,
                        prop_t source,
                        prop_t out_degree,
                        unsigned int arg)
{
#pragma HLS INLINE
    (void)out_degree;
    (void)arg;
    const prop_t old_label = regraph_cc_label(source);
    if (regraph_cc_is_active(temporary) &&
        regraph_cc_label(temporary) < old_label) {
        return temporary;
    }
    return old_label;
}

#endif
