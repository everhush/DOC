cmake_minimum_required(VERSION 3.20)
project(doc_active_set_runtime VERSION 2.16.0 LANGUAGES CXX)

option(DOC_ENABLE_ASAN "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)
option(DOC_ENABLE_TSAN "Enable ThreadSanitizer" OFF)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)
find_package(Python3 COMPONENTS Interpreter REQUIRED)

if(DOC_ENABLE_ASAN AND DOC_ENABLE_TSAN)
  message(FATAL_ERROR "ASan/UBSan and TSan cannot be enabled together")
endif()

add_library(doc_runtime
  src/runtime.cpp
  src/placement.cpp
  src/recurrence.cpp
  src/graph_versions.cpp
  src/transport.cpp
  src/network_runtime.cpp
  src/recovery.cpp
  src/typed_value.cpp
  src/effect.cpp
)
target_include_directories(doc_runtime PUBLIC include)
target_link_libraries(doc_runtime PUBLIC Threads::Threads)
target_compile_options(doc_runtime PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)

if(DOC_ENABLE_ASAN)
  target_compile_options(doc_runtime PUBLIC -fsanitize=address,undefined -fno-omit-frame-pointer)
  target_link_options(doc_runtime PUBLIC -fsanitize=address,undefined)
endif()
if(DOC_ENABLE_TSAN)
  target_compile_options(doc_runtime PUBLIC -fsanitize=thread -fno-omit-frame-pointer)
  target_link_options(doc_runtime PUBLIC -fsanitize=thread)
endif()

add_executable(doc_example examples/canonical.cpp)
target_link_libraries(doc_example PRIVATE doc_runtime)

add_executable(doc_tests tests/runtime_tests.cpp)
target_link_libraries(doc_tests PRIVATE doc_runtime)

add_library(doc_benchmark_support benchmarks/workload_generator.cpp)
target_include_directories(doc_benchmark_support PUBLIC benchmarks)
target_link_libraries(doc_benchmark_support PUBLIC doc_runtime)
target_compile_options(doc_benchmark_support PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)

add_executable(doc_benchmark benchmarks/benchmark.cpp)
target_link_libraries(doc_benchmark PRIVATE doc_benchmark_support)

add_executable(doc_benchmark_tests tests/benchmark_generator_tests.cpp)
target_link_libraries(doc_benchmark_tests PRIVATE doc_benchmark_support)

enable_testing()
add_test(NAME doc_tests COMMAND doc_tests)
add_test(NAME doc_benchmark_generator COMMAND doc_benchmark_tests)
add_test(NAME doc_bounded_model_check COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/formal/model_check.py)
add_test(NAME doc_repair_model_check COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/formal/repair_model_check.py)
add_test(NAME doc_graph_version_model_check COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/formal/graph_version_model_check.py)
add_test(NAME doc_duplicate_premise_model_check COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/formal/duplicate_premise_model_check.py)
add_test(NAME doc_demand_recurrence_model_check COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/formal/demand_recurrence_model_check.py)
set_tests_properties(doc_tests PROPERTIES TIMEOUT 180)
set_tests_properties(doc_benchmark_generator PROPERTIES TIMEOUT 120)
set_tests_properties(doc_bounded_model_check PROPERTIES TIMEOUT 120)
set_tests_properties(doc_repair_model_check PROPERTIES TIMEOUT 180)
set_tests_properties(doc_graph_version_model_check PROPERTIES TIMEOUT 120)
set_tests_properties(doc_duplicate_premise_model_check PROPERTIES TIMEOUT 120)
set_tests_properties(doc_demand_recurrence_model_check PROPERTIES TIMEOUT 180)
