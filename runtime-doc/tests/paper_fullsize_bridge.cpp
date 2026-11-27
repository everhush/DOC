#include <cstddef>
#include <cstdint>
#include <random>
namespace doc::bench {
std::uint64_t count_primes(std::uint64_t, std::uint64_t);
std::int64_t financial_unit_value(std::int64_t,std::int64_t,std::int64_t,std::int64_t,std::size_t);
}
extern "C" std::int64_t prime_leaf(std::int64_t x, std::uint64_t start, std::uint64_t len) {
 return doc::bench::count_primes(start+(x<0?-x:x),len);
}
extern "C" std::int64_t financial_leaf(std::int64_t a,std::int64_t b,std::int64_t c,std::int64_t d){return doc::bench::financial_unit_value(a,b,c,d,360);}
extern "C" void seed_sort(std::int64_t *out,std::size_t n){std::mt19937_64 random(2026U);for(std::size_t i=0;i<n;i++)out[i]=static_cast<std::int64_t>(random()%1000000U);}
