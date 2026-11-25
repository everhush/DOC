static inline doc_value doc_word_bits(uint64_t bits){
    // Convert the exact two's-complement bit pattern without libc or an
    // implementation-defined out-of-range unsigned-to-signed conversion.
    int64_t signed_bits=bits<=INT64_MAX?(int64_t)bits:-1-(int64_t)(UINT64_MAX-bits);
    return (doc_value){.kind=DOC_INT,.scalar=signed_bits};
}
static inline int doc_word_quot(doc_value x,doc_value y,doc_value *out){
    if(!y.scalar||(x.scalar==INT64_MIN&&y.scalar==-1))return 0;
    *out=(doc_value){.kind=DOC_INT,.scalar=x.scalar/y.scalar};return 1;
}
static inline int doc_word_rem(doc_value x,doc_value y,doc_value *out){
    if(!y.scalar||(x.scalar==INT64_MIN&&y.scalar==-1))return 0;
    *out=(doc_value){.kind=DOC_INT,.scalar=x.scalar%y.scalar};return 1;
}
static inline int doc_word_bit_and(doc_value x,doc_value y,doc_value *out){
    *out=doc_word_bits((uint64_t)x.scalar&(uint64_t)y.scalar);return 1;
}
static inline int doc_word_bit_or(doc_value x,doc_value y,doc_value *out){
    *out=doc_word_bits((uint64_t)x.scalar|(uint64_t)y.scalar);return 1;
}
static inline int doc_word_bit_xor(doc_value x,doc_value y,doc_value *out){
    *out=doc_word_bits((uint64_t)x.scalar^(uint64_t)y.scalar);return 1;
}
static inline int doc_word_shift_left(doc_value x,doc_value y,doc_value *out){
    if(y.scalar<0||y.scalar>=64)return 0;
    *out=doc_word_bits((uint64_t)x.scalar<<(unsigned)y.scalar);return 1;
}
static inline int doc_word_shift_right(doc_value x,doc_value y,doc_value *out){
    if(y.scalar<0||y.scalar>=64)return 0;
    *out=doc_word_bits((uint64_t)x.scalar>>(unsigned)y.scalar);return 1;
}
