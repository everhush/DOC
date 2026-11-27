#include <random>
#include <iostream>
int main(){std::mt19937_64 r(2026U);for(int i=0;i<512;i++)std::cout<<r()%1000000U<<'\n';}
