cmake_minimum_required(VERSION 3.22)
project(crispr_native_cpp LANGUAGES CXX)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(CRISPR_NATIVE_ENABLE_OPENMP "Enable OpenMP support" ON)
option(CRISPR_NATIVE_USE_NATIVE_ARCH "Enable -march=native (if supported)" OFF)

find_package(pybind11 CONFIG REQUIRED)

if(CRISPR_NATIVE_ENABLE_OPENMP)
  find_package(OpenMP)
endif()

pybind11_add_module(crispr_native src/module.cpp)

if(MSVC)
  target_compile_options(crispr_native PRIVATE /O2 /EHsc)
else()
  target_compile_options(crispr_native PRIVATE -O3 -fvisibility=hidden)
  if(CRISPR_NATIVE_USE_NATIVE_ARCH)
    target_compile_options(crispr_native PRIVATE -march=native)
  endif()
endif()

if(OpenMP_CXX_FOUND)
  target_compile_definitions(crispr_native PRIVATE CRISPR_NATIVE_HAS_OPENMP=1)
  target_link_libraries(crispr_native PRIVATE OpenMP::OpenMP_CXX)
endif()

if(DEFINED ENV{CRISPR_NATIVE_SANITIZER} AND NOT MSVC)
  string(REPLACE "," ";" _sanitizers "$ENV{CRISPR_NATIVE_SANITIZER}")
  foreach(_san ${_sanitizers})
    target_compile_options(crispr_native PRIVATE "-fsanitize=${_san}")
    target_link_options(crispr_native PRIVATE "-fsanitize=${_san}")
  endforeach()
endif()

target_include_directories(crispr_native PRIVATE ${PROJECT_SOURCE_DIR}/include)
