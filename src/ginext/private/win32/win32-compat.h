/* Force-included on Windows builds (see src/meson.build) to supply POSIX types
   and definitions the ginext C sources expect but MSVC/clang-cl headers lack. */
#pragma once

#include <BaseTsd.h>
typedef SSIZE_T ssize_t;
