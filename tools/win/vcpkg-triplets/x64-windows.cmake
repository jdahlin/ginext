set(VCPKG_TARGET_ARCHITECTURE x64)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE dynamic)
# ginext only needs release native libs; skip the debug half of every port
# (roughly halves the whole build, locally and in CI).
set(VCPKG_BUILD_TYPE release)

# ginext uses libffi's ffi_type_* in static initializers (built with
# FFI_STATIC_BUILD), which the dynamic libffi exposes as dllimport data and
# cannot be used that way. Build just libffi as a static lib (dynamic CRT =
# "static-md") while everything else stays dynamic.
if(PORT STREQUAL "libffi")
    set(VCPKG_LIBRARY_LINKAGE static)
endif()
