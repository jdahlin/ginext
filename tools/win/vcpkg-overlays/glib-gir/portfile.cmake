# Builds the matching glib sources a second time with -Dintrospection=enabled and
# installs ONLY the generated typelibs/girs. Depending here on glib (for the
# headers/libs to scan) and gobject-introspection (for the host g-ir-scanner) is
# safe because glib-gir is a leaf -- nothing depends back on it -- so unlike an
# introspection feature on glib itself, no glib<->gobject-introspection cycle
# forms. See tools/win/BOOTSTRAP.md.
set(VERSION 2.88.1)
string(REGEX MATCH "^([0-9]*[.][0-9]*)" VERSION_MAJOR_MINOR "${VERSION}")

# Data-only port: it ships typelibs/girs, no libs or headers.
set(VCPKG_POLICY_EMPTY_INCLUDE_FOLDER enabled)
set(VCPKG_POLICY_MISMATCHED_NUMBER_OF_BINARIES enabled)

vcpkg_download_distfile(GLIB_ARCHIVE
    URLS
        "https://download.gnome.org/sources/glib/${VERSION_MAJOR_MINOR}/glib-${VERSION}.tar.xz"
        "https://www.mirrorservice.org/sites/ftp.gnome.org/pub/GNOME/sources/glib/${VERSION_MAJOR_MINOR}/glib-${VERSION}.tar.xz"
    FILENAME "glib-${VERSION}.tar.xz"
    SHA512 74e6d6086081e5dfb5b7fd3b74f59171033be0c340ff2dd798fea9cb42e5f680e13b2ac3dde8dd423bceb9c6556103005f9542aeda166e9a3b89da8bacecca23
)

vcpkg_extract_source_archive(SOURCE_PATH
    ARCHIVE "${GLIB_ARCHIVE}"
    PATCHES
        use-libiconv-on-windows.patch
        libintl.patch
)

set(LANGUAGES C CXX)
if(VCPKG_TARGET_IS_OSX OR VCPKG_TARGET_IS_IOS)
    list(APPEND LANGUAGES OBJC OBJCXX)
endif()

# Host gobject-introspection supplies the scanner. Reuse its own port-config to
# get a Python venv that has setuptools/distutils (the installed g-ir-scanner
# imports distutils.cygwinccompiler, which a bare vcpkg python3 lacks), plus the
# resolved g-ir-scanner / g-ir-compiler paths.
set(gi_host_tools "${CURRENT_HOST_INSTALLED_DIR}/tools/gobject-introspection")
include("${CURRENT_HOST_INSTALLED_DIR}/share/gobject-introspection/vcpkg-port-config.cmake")
vcpkg_get_gobject_introspection_programs(PYTHON3 GIR_COMPILER GIR_SCANNER)

vcpkg_list(SET ADDITIONAL_BINARIES)
if(VCPKG_HOST_IS_WINDOWS)
    vcpkg_list(APPEND ADDITIONAL_BINARIES "bash = ['${CMAKE_COMMAND}', '-E', 'false']")
    vcpkg_list(APPEND ADDITIONAL_BINARIES "sh = ['${CMAKE_COMMAND}', '-E', 'false']")
endif()
vcpkg_find_acquire_program(FLEX)
vcpkg_find_acquire_program(BISON)
vcpkg_list(APPEND ADDITIONAL_BINARIES
    "g-ir-scanner = ['${PYTHON3}', '${GIR_SCANNER}']"
    "g-ir-compiler = ['${GIR_COMPILER}']"
    "flex = '${FLEX}'"
    "bison = '${BISON}'"
)

# Scanner runtime: its tools, the host Python, and the host DLLs it loads on
# PATH; pkg-config (giscanner shells out to it for each scanned namespace, even
# for --version) with PKG_CONFIG_PATH pointing at the installed .pc files; plus
# the VCPKG_GI_* shims the vcpkg gobject-introspection scanner reads.
vcpkg_find_acquire_program(PKGCONFIG)
set(ENV{PKG_CONFIG} "${PKGCONFIG}")
get_filename_component(_pkgconfig_dir "${PKGCONFIG}" DIRECTORY)
vcpkg_add_to_path(PREPEND "${_pkgconfig_dir}")
vcpkg_host_path_list(PREPEND ENV{PKG_CONFIG_PATH} "${CURRENT_INSTALLED_DIR}/lib/pkgconfig")
vcpkg_host_path_list(PREPEND ENV{PKG_CONFIG_PATH} "${CURRENT_INSTALLED_DIR}/share/pkgconfig")
vcpkg_add_to_path(PREPEND "${gi_host_tools}")
vcpkg_add_to_path(PREPEND "${CURRENT_HOST_INSTALLED_DIR}/tools/python3")
vcpkg_add_to_path(PREPEND "${CURRENT_HOST_INSTALLED_DIR}/bin")
set(ENV{VCPKG_GI_LIBDIR} "${CURRENT_INSTALLED_DIR}/lib")
# Point the scanner's data dir at the INSTALLED share: it must contain both
# gir-1.0 (asserted to exist at scanner startup) and the gobject-introspection
# helper sources it compiles (share/gobject-introspection-1.0/gdump.c). The
# packages share is empty at this point, so it cannot be used here.
set(ENV{VCPKG_GI_DATADIR} "${CURRENT_INSTALLED_DIR}/share")
if(VCPKG_TARGET_IS_WINDOWS)
    set(ENV{VCPKG_GI_LIBDIR_VAR} "LIB")
elseif(VCPKG_TARGET_IS_OSX OR VCPKG_TARGET_IS_IOS)
    set(ENV{VCPKG_GI_LIBDIR_VAR} "DYLD_LIBRARY_PATH")
else()
    set(ENV{VCPKG_GI_LIBDIR_VAR} "LD_LIBRARY_PATH")
endif()

vcpkg_configure_meson(
    SOURCE_PATH "${SOURCE_PATH}"
    LANGUAGES ${LANGUAGES}
    ADDITIONAL_BINARIES
        ${ADDITIONAL_BINARIES}
    OPTIONS
        -Ddocumentation=false
        -Ddtrace=disabled
        -Dinstalled_tests=false
        -Dlibelf=disabled
        -Dlibmount=disabled
        -Dman-pages=disabled
        -Dselinux=disabled
        -Dsysprof=disabled
        -Dtests=false
        -Dxattr=false
    OPTIONS_RELEASE
        -Dintrospection=enabled
    OPTIONS_DEBUG
        -Dintrospection=disabled
)
vcpkg_install_meson(ADD_BIN_TO_PATH)

# Ship ONLY the typelibs/girs that the glib and gobject-introspection ports do
# NOT already provide: GIRepository-3.0 (glib's self-introspection of the bundled
# girepository-2.0) plus, on Windows, the GLibWin32/GioWin32 platform typelibs.
# The GLib/GObject/Gio/GModule-2.0 ones glib-gir also generates would conflict
# with gobject-introspection, so they are dropped.
set(KEEP_NAMESPACES GIRepository-3.0)
if(VCPKG_TARGET_IS_WINDOWS)
    list(APPEND KEEP_NAMESPACES GLibWin32-2.0 GioWin32-2.0)
endif()

set(_stage "${CURRENT_BUILDTREES_DIR}/glib-gir-keep")
file(REMOVE_RECURSE "${_stage}")
file(MAKE_DIRECTORY "${_stage}/lib" "${_stage}/share")
foreach(_ns IN LISTS KEEP_NAMESPACES)
    set(_tl "${CURRENT_PACKAGES_DIR}/lib/girepository-1.0/${_ns}.typelib")
    set(_gir "${CURRENT_PACKAGES_DIR}/share/gir-1.0/${_ns}.gir")
    if(NOT EXISTS "${_tl}")
        message(FATAL_ERROR "glib-gir: expected typelib not generated: ${_ns}.typelib")
    endif()
    file(COPY "${_tl}" DESTINATION "${_stage}/lib")
    if(EXISTS "${_gir}")
        file(COPY "${_gir}" DESTINATION "${_stage}/share")
    endif()
endforeach()

# Wipe everything the build installed, then restore only the kept artifacts.
file(GLOB _top "${CURRENT_PACKAGES_DIR}/*")
file(REMOVE_RECURSE ${_top})
file(MAKE_DIRECTORY "${CURRENT_PACKAGES_DIR}/lib/girepository-1.0" "${CURRENT_PACKAGES_DIR}/share/gir-1.0")
file(GLOB _kt "${_stage}/lib/*.typelib")
file(GLOB _kg "${_stage}/share/*.gir")
file(COPY ${_kt} DESTINATION "${CURRENT_PACKAGES_DIR}/lib/girepository-1.0")
file(COPY ${_kg} DESTINATION "${CURRENT_PACKAGES_DIR}/share/gir-1.0")

vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSES/LGPL-2.1-or-later.txt")
