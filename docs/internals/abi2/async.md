# ABI2 Async Method Inventory

Generated from installed system `.gir` XML files. This inventory lists user-callable functions, constructors, and methods that either carry `glib:finish-func` metadata or use a legacy `*_async` name.

It intentionally does not list standalone `*_finish` callables unless they are the finish pair for an async entry below. Virtual methods, callback struct fields, and non-callable metadata are excluded from this user-facing ABI2 planning list.

## Summary

- Generated: `2026-05-16`
- Requested namespaces: `GLib`, `GObject`, `Gio`, `Gtk`, `Gst`
- Search directories: `/usr/share/gir-1.0`, `/usr/lib/x86_64-linux-gnu/gir-1.0`, `/usr/share/sushi/gir-1.0`
- Missing installed GIR namespaces: `Gst`

Installed namespace versions:
- `GLib-2.0`: `2` async entries from `/usr/lib/x86_64-linux-gnu/gir-1.0/GLib-2.0.gir`
- `GObject-2.0`: `0` async entries from `/usr/share/gir-1.0/GObject-2.0.gir`
- `Gio-2.0`: `136` async entries from `/usr/share/gir-1.0/Gio-2.0.gir`
- `Gtk-3.0`: `5` async entries from `/usr/share/gir-1.0/Gtk-3.0.gir`
- `Gtk-4.0`: `22` async entries from `/usr/share/gir-1.0/Gtk-4.0.gir`

## ABI2 Notes

- Entries with `finish:` are normal GIO-style async operations and are candidates for default-async ABI2 methods once cancellation, result shaping, and error-domain behavior are specified.
- When an ABI2 async plan promotes an operation, the natural method name is awaitable and the blocking operation is exposed as `_sync()`, for example `await file.load_contents()` and `file.load_contents_sync()`.
- Entries without a finish pair but with `*_async` are legacy fire-and-forget or callback APIs; they should not automatically become awaitable without a hand-written policy.
- GTK 4 includes async operations whose public method names are not suffixed with `_async`, for example dialog `choose`, `open`, and `save` methods. These are still listed because GIR declares `glib:finish-func`.
- Deprecated entries are marked, but retained because ABI2 may still need compatibility behavior or explicit non-promotion rules.

## Table Of Contents

- [[#GLib-2.0|GLib-2.0]]
- [[#GObject-2.0|GObject-2.0]]
- [[#Gio-2.0|Gio-2.0]]
- [[#Gtk-3.0|Gtk-3.0]]
- [[#Gtk-4.0|Gtk-4.0]]
- [[#Missing Namespaces|Missing Namespaces]]

## Namespaces

### GLib-2.0

Source: `/usr/lib/x86_64-linux-gnu/gir-1.0/GLib-2.0.gir`
Async entries: `2`

#### `GLib`

- `GLib.spawn_async` (function; finish: none; name: `*_async`; throws; C: `g_spawn_async`)
- `GLib.spawn_command_line_async` (function; finish: none; name: `*_async`; throws; C: `g_spawn_command_line_async`)

### GObject-2.0

Source: `/usr/share/gir-1.0/GObject-2.0.gir`
Async entries: `0`

No async entries found by the scan criteria.

### Gio-2.0

Source: `/usr/share/gir-1.0/Gio-2.0.gir`
Async entries: `136`

#### `Gio`

- `Gio.bus_get` (function; finish: `bus_get_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_bus_get`)
- `Gio.dbus_address_get_stream` (function; finish: `dbus_address_get_stream_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_address_get_stream`)

#### `Gio.AppInfo`

- `Gio.AppInfo.get_default_for_type_async` (function; finish: `get_default_for_type_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_app_info_get_default_for_type_async`)
- `Gio.AppInfo.get_default_for_uri_scheme_async` (function; finish: `get_default_for_uri_scheme_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_app_info_get_default_for_uri_scheme_async`)
- `Gio.AppInfo.launch_default_for_uri_async` (function; finish: `launch_default_for_uri_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_app_info_launch_default_for_uri_async`)
- `Gio.AppInfo.launch_uris_async` (method; finish: `launch_uris_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_app_info_launch_uris_async`)

#### `Gio.AsyncInitable`

- `Gio.AsyncInitable.init_async` (method; finish: `init_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_async_initable_init_async`)
- `Gio.AsyncInitable.new_async` (function; finish: none; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_async_initable_new_async`)
- `Gio.AsyncInitable.new_valist_async` (function; finish: none; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_async_initable_new_valist_async`)
- `Gio.AsyncInitable.newv_async` (function; finish: none; name: `*_async`; callback: `Gio.AsyncReadyCallback`; deprecated; C: `g_async_initable_newv_async`)

#### `Gio.BufferedInputStream`

- `Gio.BufferedInputStream.fill_async` (method; finish: `fill_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_buffered_input_stream_fill_async`)

#### `Gio.DBusConnection`

- `Gio.DBusConnection.call` (method; finish: `call_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_connection_call`)
- `Gio.DBusConnection.call_with_unix_fd_list` (method; finish: `call_with_unix_fd_list_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_connection_call_with_unix_fd_list`)
- `Gio.DBusConnection.close` (method; finish: `close_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_connection_close`)
- `Gio.DBusConnection.flush` (method; finish: `flush_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_connection_flush`)
- `Gio.DBusConnection.new` (function; finish: `new_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_connection_new`)
- `Gio.DBusConnection.new_for_address` (function; finish: `new_for_address_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_connection_new_for_address`)
- `Gio.DBusConnection.send_message_with_reply` (method; finish: `send_message_with_reply_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_connection_send_message_with_reply`)

#### `Gio.DBusObjectManagerClient`

- `Gio.DBusObjectManagerClient.new` (function; finish: `new_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_object_manager_client_new`)
- `Gio.DBusObjectManagerClient.new_for_bus` (function; finish: `new_for_bus_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_object_manager_client_new_for_bus`)

#### `Gio.DBusProxy`

- `Gio.DBusProxy.call` (method; finish: `call_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_proxy_call`)
- `Gio.DBusProxy.call_with_unix_fd_list` (method; finish: `call_with_unix_fd_list_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_proxy_call_with_unix_fd_list`)
- `Gio.DBusProxy.new` (function; finish: `new_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_proxy_new`)
- `Gio.DBusProxy.new_for_bus` (function; finish: `new_for_bus_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_dbus_proxy_new_for_bus`)

#### `Gio.DataInputStream`

- `Gio.DataInputStream.read_line_async` (method; finish: `read_line_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_data_input_stream_read_line_async`)
- `Gio.DataInputStream.read_until_async` (method; finish: `read_until_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; deprecated; C: `g_data_input_stream_read_until_async`)
- `Gio.DataInputStream.read_upto_async` (method; finish: `read_upto_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_data_input_stream_read_upto_async`)

#### `Gio.Drive`

- `Gio.Drive.eject` (method; finish: `eject_finish`; callback: `Gio.AsyncReadyCallback`; deprecated; C: `g_drive_eject`)
- `Gio.Drive.eject_with_operation` (method; finish: `eject_with_operation_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_drive_eject_with_operation`)
- `Gio.Drive.poll_for_media` (method; finish: `poll_for_media_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_drive_poll_for_media`)
- `Gio.Drive.start` (method; finish: `start_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_drive_start`)
- `Gio.Drive.stop` (method; finish: `stop_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_drive_stop`)

#### `Gio.DtlsConnection`

- `Gio.DtlsConnection.close_async` (method; finish: `close_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_dtls_connection_close_async`)
- `Gio.DtlsConnection.handshake_async` (method; finish: `handshake_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_dtls_connection_handshake_async`)
- `Gio.DtlsConnection.shutdown_async` (method; finish: `shutdown_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_dtls_connection_shutdown_async`)

#### `Gio.File`

- `Gio.File.append_to_async` (method; finish: `append_to_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_append_to_async`)
- `Gio.File.copy_async` (method; finish: `copy_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_copy_async`)
- `Gio.File.copy_async_with_closures` (method; finish: `copy_finish`; C: `g_file_copy_async_with_closures`)
- `Gio.File.create_async` (method; finish: `create_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_create_async`)
- `Gio.File.create_readwrite_async` (method; finish: `create_readwrite_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_create_readwrite_async`)
- `Gio.File.delete_async` (method; finish: `delete_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_delete_async`)
- `Gio.File.eject_mountable` (method; finish: `eject_mountable_finish`; callback: `Gio.AsyncReadyCallback`; deprecated; C: `g_file_eject_mountable`)
- `Gio.File.eject_mountable_with_operation` (method; finish: `eject_mountable_with_operation_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_file_eject_mountable_with_operation`)
- `Gio.File.enumerate_children_async` (method; finish: `enumerate_children_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_enumerate_children_async`)
- `Gio.File.find_enclosing_mount_async` (method; finish: `find_enclosing_mount_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_find_enclosing_mount_async`)
- `Gio.File.load_bytes_async` (method; finish: `load_bytes_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_load_bytes_async`)
- `Gio.File.load_contents_async` (method; finish: `load_contents_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_load_contents_async`)
- `Gio.File.load_partial_contents_async` (method; finish: `load_partial_contents_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_load_partial_contents_async`)
- `Gio.File.make_directory_async` (method; finish: `make_directory_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_make_directory_async`)
- `Gio.File.make_symbolic_link_async` (method; finish: `make_symbolic_link_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_make_symbolic_link_async`)
- `Gio.File.measure_disk_usage_async` (method; finish: `measure_disk_usage_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_measure_disk_usage_async`)
- `Gio.File.mount_enclosing_volume` (method; finish: `mount_enclosing_volume_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_file_mount_enclosing_volume`)
- `Gio.File.mount_mountable` (method; finish: `mount_mountable_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_file_mount_mountable`)
- `Gio.File.move_async` (method; finish: `move_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_move_async`)
- `Gio.File.move_async_with_closures` (method; finish: `move_finish`; C: `g_file_move_async_with_closures`)
- `Gio.File.new_tmp_async` (function; finish: `new_tmp_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_new_tmp_async`)
- `Gio.File.new_tmp_dir_async` (function; finish: `new_tmp_dir_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_new_tmp_dir_async`)
- `Gio.File.open_readwrite_async` (method; finish: `open_readwrite_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_open_readwrite_async`)
- `Gio.File.poll_mountable` (method; finish: `poll_mountable_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_file_poll_mountable`)
- `Gio.File.query_default_handler_async` (method; finish: `query_default_handler_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_query_default_handler_async`)
- `Gio.File.query_filesystem_info_async` (method; finish: `query_filesystem_info_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_query_filesystem_info_async`)
- `Gio.File.query_info_async` (method; finish: `query_info_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_query_info_async`)
- `Gio.File.read_async` (method; finish: `read_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_read_async`)
- `Gio.File.replace_async` (method; finish: `replace_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_replace_async`)
- `Gio.File.replace_contents_async` (method; finish: `replace_contents_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_replace_contents_async`)
- `Gio.File.replace_contents_bytes_async` (method; finish: none; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_replace_contents_bytes_async`)
- `Gio.File.replace_readwrite_async` (method; finish: `replace_readwrite_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_replace_readwrite_async`)
- `Gio.File.set_attributes_async` (method; finish: `set_attributes_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_set_attributes_async`)
- `Gio.File.set_display_name_async` (method; finish: `set_display_name_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_set_display_name_async`)
- `Gio.File.start_mountable` (method; finish: `start_mountable_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_file_start_mountable`)
- `Gio.File.stop_mountable` (method; finish: `stop_mountable_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_file_stop_mountable`)
- `Gio.File.trash_async` (method; finish: `trash_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_trash_async`)
- `Gio.File.unmount_mountable` (method; finish: `unmount_mountable_finish`; callback: `Gio.AsyncReadyCallback`; deprecated; C: `g_file_unmount_mountable`)
- `Gio.File.unmount_mountable_with_operation` (method; finish: `unmount_mountable_with_operation_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_file_unmount_mountable_with_operation`)

#### `Gio.FileEnumerator`

- `Gio.FileEnumerator.close_async` (method; finish: `close_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_enumerator_close_async`)
- `Gio.FileEnumerator.next_files_async` (method; finish: `next_files_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_enumerator_next_files_async`)

#### `Gio.FileIOStream`

- `Gio.FileIOStream.query_info_async` (method; finish: `query_info_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_io_stream_query_info_async`)

#### `Gio.FileInputStream`

- `Gio.FileInputStream.query_info_async` (method; finish: `query_info_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_input_stream_query_info_async`)

#### `Gio.FileOutputStream`

- `Gio.FileOutputStream.query_info_async` (method; finish: `query_info_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_file_output_stream_query_info_async`)

#### `Gio.IOSchedulerJob`

- `Gio.IOSchedulerJob.send_to_mainloop_async` (method; finish: none; name: `*_async`; deprecated; C: `g_io_scheduler_job_send_to_mainloop_async`)

#### `Gio.IOStream`

- `Gio.IOStream.close_async` (method; finish: `close_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_io_stream_close_async`)
- `Gio.IOStream.splice_async` (method; finish: none; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_io_stream_splice_async`)

#### `Gio.InputStream`

- `Gio.InputStream.close_async` (method; finish: `close_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_input_stream_close_async`)
- `Gio.InputStream.read_all_async` (method; finish: `read_all_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_input_stream_read_all_async`)
- `Gio.InputStream.read_async` (method; finish: `read_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_input_stream_read_async`)
- `Gio.InputStream.read_bytes_async` (method; finish: `read_bytes_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_input_stream_read_bytes_async`)
- `Gio.InputStream.skip_async` (method; finish: `skip_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_input_stream_skip_async`)

#### `Gio.LoadableIcon`

- `Gio.LoadableIcon.load_async` (method; finish: `load_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_loadable_icon_load_async`)

#### `Gio.Mount`

- `Gio.Mount.eject` (method; finish: `eject_finish`; callback: `Gio.AsyncReadyCallback`; deprecated; C: `g_mount_eject`)
- `Gio.Mount.eject_with_operation` (method; finish: `eject_with_operation_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_mount_eject_with_operation`)
- `Gio.Mount.guess_content_type` (method; finish: `guess_content_type_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_mount_guess_content_type`)
- `Gio.Mount.remount` (method; finish: `remount_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_mount_remount`)
- `Gio.Mount.unmount` (method; finish: `unmount_finish`; callback: `Gio.AsyncReadyCallback`; deprecated; C: `g_mount_unmount`)
- `Gio.Mount.unmount_with_operation` (method; finish: `unmount_with_operation_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_mount_unmount_with_operation`)

#### `Gio.NetworkMonitor`

- `Gio.NetworkMonitor.can_reach_async` (method; finish: `can_reach_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_network_monitor_can_reach_async`)

#### `Gio.OutputStream`

- `Gio.OutputStream.close_async` (method; finish: `close_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_output_stream_close_async`)
- `Gio.OutputStream.flush_async` (method; finish: `flush_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_output_stream_flush_async`)
- `Gio.OutputStream.splice_async` (method; finish: `splice_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_output_stream_splice_async`)
- `Gio.OutputStream.write_all_async` (method; finish: `write_all_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_output_stream_write_all_async`)
- `Gio.OutputStream.write_async` (method; finish: `write_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_output_stream_write_async`)
- `Gio.OutputStream.write_bytes_async` (method; finish: `write_bytes_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_output_stream_write_bytes_async`)
- `Gio.OutputStream.writev_all_async` (method; finish: `writev_all_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_output_stream_writev_all_async`)
- `Gio.OutputStream.writev_async` (method; finish: `writev_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_output_stream_writev_async`)

#### `Gio.Permission`

- `Gio.Permission.acquire_async` (method; finish: `acquire_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_permission_acquire_async`)
- `Gio.Permission.release_async` (method; finish: `release_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_permission_release_async`)

#### `Gio.Proxy`

- `Gio.Proxy.connect_async` (method; finish: `connect_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_proxy_connect_async`)

#### `Gio.ProxyResolver`

- `Gio.ProxyResolver.lookup_async` (method; finish: `lookup_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_proxy_resolver_lookup_async`)

#### `Gio.Resolver`

- `Gio.Resolver.lookup_by_address_async` (method; finish: `lookup_by_address_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_resolver_lookup_by_address_async`)
- `Gio.Resolver.lookup_by_name_async` (method; finish: `lookup_by_name_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_resolver_lookup_by_name_async`)
- `Gio.Resolver.lookup_by_name_with_flags_async` (method; finish: `lookup_by_name_with_flags_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_resolver_lookup_by_name_with_flags_async`)
- `Gio.Resolver.lookup_records_async` (method; finish: `lookup_records_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_resolver_lookup_records_async`)
- `Gio.Resolver.lookup_service_async` (method; finish: `lookup_service_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_resolver_lookup_service_async`)

#### `Gio.SocketAddressEnumerator`

- `Gio.SocketAddressEnumerator.next_async` (method; finish: `next_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_socket_address_enumerator_next_async`)

#### `Gio.SocketClient`

- `Gio.SocketClient.connect_async` (method; finish: `connect_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_socket_client_connect_async`)
- `Gio.SocketClient.connect_to_host_async` (method; finish: `connect_to_host_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_socket_client_connect_to_host_async`)
- `Gio.SocketClient.connect_to_service_async` (method; finish: `connect_to_service_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_socket_client_connect_to_service_async`)
- `Gio.SocketClient.connect_to_uri_async` (method; finish: `connect_to_uri_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_socket_client_connect_to_uri_async`)

#### `Gio.SocketConnection`

- `Gio.SocketConnection.connect_async` (method; finish: `connect_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_socket_connection_connect_async`)

#### `Gio.SocketListener`

- `Gio.SocketListener.accept_async` (method; finish: `accept_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_socket_listener_accept_async`)
- `Gio.SocketListener.accept_socket_async` (method; finish: `accept_socket_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_socket_listener_accept_socket_async`)

#### `Gio.Subprocess`

- `Gio.Subprocess.communicate_async` (method; finish: `communicate_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_subprocess_communicate_async`)
- `Gio.Subprocess.communicate_utf8_async` (method; finish: `communicate_utf8_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_subprocess_communicate_utf8_async`)
- `Gio.Subprocess.wait_async` (method; finish: `wait_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_subprocess_wait_async`)
- `Gio.Subprocess.wait_check_async` (method; finish: `wait_check_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_subprocess_wait_check_async`)

#### `Gio.TlsConnection`

- `Gio.TlsConnection.handshake_async` (method; finish: `handshake_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_tls_connection_handshake_async`)

#### `Gio.TlsDatabase`

- `Gio.TlsDatabase.lookup_certificate_for_handle_async` (method; finish: `lookup_certificate_for_handle_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_tls_database_lookup_certificate_for_handle_async`)
- `Gio.TlsDatabase.lookup_certificate_issuer_async` (method; finish: `lookup_certificate_issuer_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_tls_database_lookup_certificate_issuer_async`)
- `Gio.TlsDatabase.lookup_certificates_issued_by_async` (method; finish: `lookup_certificates_issued_by_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_tls_database_lookup_certificates_issued_by_async`)
- `Gio.TlsDatabase.verify_chain_async` (method; finish: `verify_chain_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_tls_database_verify_chain_async`)

#### `Gio.TlsInteraction`

- `Gio.TlsInteraction.ask_password_async` (method; finish: `ask_password_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_tls_interaction_ask_password_async`)
- `Gio.TlsInteraction.request_certificate_async` (method; finish: `request_certificate_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_tls_interaction_request_certificate_async`)

#### `Gio.UnixConnection`

- `Gio.UnixConnection.receive_credentials_async` (method; finish: `receive_credentials_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_unix_connection_receive_credentials_async`)
- `Gio.UnixConnection.send_credentials_async` (method; finish: `send_credentials_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `g_unix_connection_send_credentials_async`)

#### `Gio.Volume`

- `Gio.Volume.eject` (method; finish: `eject_finish`; callback: `Gio.AsyncReadyCallback`; deprecated; C: `g_volume_eject`)
- `Gio.Volume.eject_with_operation` (method; finish: `eject_with_operation_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_volume_eject_with_operation`)
- `Gio.Volume.mount` (method; finish: `mount_finish`; callback: `Gio.AsyncReadyCallback`; C: `g_volume_mount`)

### Gtk-3.0

Source: `/usr/share/gir-1.0/Gtk-3.0.gir`
Async entries: `5`

#### `Gtk`

- `Gtk.print_run_page_setup_dialog_async` (function; finish: none; name: `*_async`; C: `gtk_print_run_page_setup_dialog_async`)

#### `Gtk.IconInfo`

- `Gtk.IconInfo.load_icon_async` (method; finish: `load_icon_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `gtk_icon_info_load_icon_async`)
- `Gtk.IconInfo.load_symbolic_async` (method; finish: `load_symbolic_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `gtk_icon_info_load_symbolic_async`)
- `Gtk.IconInfo.load_symbolic_for_context_async` (method; finish: `load_symbolic_for_context_finish`; name: `*_async`; callback: `Gio.AsyncReadyCallback`; C: `gtk_icon_info_load_symbolic_for_context_async`)

#### `Gtk.PrintOperation`

- `Gtk.PrintOperation.set_allow_async` (method; finish: none; name: `*_async`; C: `gtk_print_operation_set_allow_async`)

### Gtk-4.0

Source: `/usr/share/gir-1.0/Gtk-4.0.gir`
Async entries: `22`

#### `Gtk`

- `Gtk.print_run_page_setup_dialog_async` (function; finish: none; name: `*_async`; C: `gtk_print_run_page_setup_dialog_async`)

#### `Gtk.AlertDialog`

- `Gtk.AlertDialog.choose` (method; finish: `choose_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_alert_dialog_choose`)

#### `Gtk.ColorDialog`

- `Gtk.ColorDialog.choose_rgba` (method; finish: `choose_rgba_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_color_dialog_choose_rgba`)

#### `Gtk.FileDialog`

- `Gtk.FileDialog.open` (method; finish: `open_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_dialog_open`)
- `Gtk.FileDialog.open_multiple` (method; finish: `open_multiple_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_dialog_open_multiple`)
- `Gtk.FileDialog.open_multiple_text_files` (method; finish: `open_multiple_text_files_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_dialog_open_multiple_text_files`)
- `Gtk.FileDialog.open_text_file` (method; finish: `open_text_file_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_dialog_open_text_file`)
- `Gtk.FileDialog.save` (method; finish: `save_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_dialog_save`)
- `Gtk.FileDialog.save_text_file` (method; finish: `save_text_file_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_dialog_save_text_file`)
- `Gtk.FileDialog.select_folder` (method; finish: `select_folder_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_dialog_select_folder`)
- `Gtk.FileDialog.select_multiple_folders` (method; finish: `select_multiple_folders_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_dialog_select_multiple_folders`)

#### `Gtk.FileLauncher`

- `Gtk.FileLauncher.launch` (method; finish: `launch_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_launcher_launch`)
- `Gtk.FileLauncher.open_containing_folder` (method; finish: `open_containing_folder_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_file_launcher_open_containing_folder`)

#### `Gtk.FontDialog`

- `Gtk.FontDialog.choose_face` (method; finish: `choose_face_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_font_dialog_choose_face`)
- `Gtk.FontDialog.choose_family` (method; finish: `choose_family_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_font_dialog_choose_family`)
- `Gtk.FontDialog.choose_font` (method; finish: `choose_font_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_font_dialog_choose_font`)
- `Gtk.FontDialog.choose_font_and_features` (method; finish: `choose_font_and_features_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_font_dialog_choose_font_and_features`)

#### `Gtk.PrintDialog`

- `Gtk.PrintDialog.print` (method; finish: `print_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_print_dialog_print`)
- `Gtk.PrintDialog.print_file` (method; finish: `print_file_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_print_dialog_print_file`)
- `Gtk.PrintDialog.setup` (method; finish: `setup_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_print_dialog_setup`)

#### `Gtk.PrintOperation`

- `Gtk.PrintOperation.set_allow_async` (method; finish: none; name: `*_async`; C: `gtk_print_operation_set_allow_async`)

#### `Gtk.UriLauncher`

- `Gtk.UriLauncher.launch` (method; finish: `launch_finish`; callback: `Gio.AsyncReadyCallback`; C: `gtk_uri_launcher_launch`)

## Missing Namespaces

- `Gst`: no installed `Gst-*.gir` file was found in the scanned GIR search directories.
