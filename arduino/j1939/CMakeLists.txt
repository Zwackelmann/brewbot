cmake_minimum_required(VERSION 3.16)
project(j1939_util_tests LANGUAGES C CXX)

# Standards
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# Warnings (tweak to taste)
if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Optional: sanitize in Debug
if (CMAKE_BUILD_TYPE STREQUAL "Debug" AND CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
  add_compile_options(-fsanitize=address,undefined)
  add_link_options(-fsanitize=address,undefined)
endif()

# Test executable
add_executable(run_tests
 tests/main_gtest.cpp
)
target_include_directories(run_tests PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# ---- GoogleTest via FetchContent ----
include(FetchContent)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
)
FetchContent_MakeAvailable(googletest)

target_link_libraries(run_tests PRIVATE GTest::gtest GTest::gtest_main)

# CTest
include(CTest)
add_test(NAME util_bitpack COMMAND run_tests)

