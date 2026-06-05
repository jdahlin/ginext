# ABI2 GIR Name Conflicts

Generated from installed system `.gir` XML files. A conflict is a normalized Python attribute name visible on a class or interface as more than one ABI2 member kind: method, property, or signal.

Inherited class members, interface prerequisites, and implemented interface members are included. Names are normalized by replacing `-` with `_`, matching `docs/internals/abi2/abi2.md`.

## Summary

- Generated: `2026-05-16`
- GIR files scanned: `57`
- Classes/interfaces parsed: `1157`
- Unique conflict sets: `205`
- Conflicted type attributes: `6782`
- Search directories: `/usr/share/gir-1.0`, `/usr/lib/x86_64-linux-gnu/gir-1.0`, `/usr/share/sushi/gir-1.0`

Conflict kinds:
- `method+signal`: `5926` type attributes
- `property+method`: `844` type attributes
- `property+method+signal`: `1` type attributes
- `property+signal`: `11` type attributes

## Table Of Contents

- [[#Adw|Adw]]: `59` conflict sets, `1413` type attributes
- [[#AppStream|AppStream]]: `1` conflict sets, `32` type attributes
- [[#Atk|Atk]]: `1` conflict sets, `16` type attributes
- [[#Atspi|Atspi]]: `1` conflict sets, `13` type attributes
- [[#CloudProviders|CloudProviders]]: `1` conflict sets, `12` type attributes
- [[#DBusGLib|DBusGLib]]: `1` conflict sets, `1` type attributes
- [[#GObject|GObject]]: `1` conflict sets, `6` type attributes
- [[#GUdev|GUdev]]: `1` conflict sets, `3` type attributes
- [[#Gdk|Gdk]]: `5` conflict sets, `52` type attributes
- [[#GdkPixbuf|GdkPixbuf]]: `1` conflict sets, `7` type attributes
- [[#GdkWayland|GdkWayland]]: `1` conflict sets, `8` type attributes
- [[#GdkX11|GdkX11]]: `2` conflict sets, `18` type attributes
- [[#Gio|Gio]]: `16` conflict sets, `145` type attributes
- [[#GioUnix|GioUnix]]: `1` conflict sets, `5` type attributes
- [[#Gly|Gly]]: `1` conflict sets, `7` type attributes
- [[#Grl|Grl]]: `1` conflict sets, `9` type attributes
- [[#GrlNet|GrlNet]]: `1` conflict sets, `1` type attributes
- [[#Gsk|Gsk]]: `1` conflict sets, `7` type attributes
- [[#Gtk|Gtk]]: `154` conflict sets, `4502` type attributes
- [[#GtkSource|GtkSource]]: `62` conflict sets, `265` type attributes
- [[#JavaScriptCore|JavaScriptCore]]: `1` conflict sets, `6` type attributes
- [[#Json|Json]]: `1` conflict sets, `5` type attributes
- [[#MediaArt|MediaArt]]: `1` conflict sets, `1` type attributes
- [[#Pango|Pango]]: `4` conflict sets, `14` type attributes
- [[#PangoCairo|PangoCairo]]: `2` conflict sets, `3` type attributes
- [[#PangoFT2|PangoFT2]]: `2` conflict sets, `2` type attributes
- [[#PangoFc|PangoFc]]: `2` conflict sets, `4` type attributes
- [[#PangoOT|PangoOT]]: `1` conflict sets, `2` type attributes
- [[#PangoXft|PangoXft]]: `2` conflict sets, `4` type attributes
- [[#Soup|Soup]]: `4` conflict sets, `42` type attributes
- [[#Sushi|Sushi]]: `25` conflict sets, `44` type attributes
- [[#Tracker|Tracker]]: `1` conflict sets, `10` type attributes
- [[#Tsparql|Tsparql]]: `1` conflict sets, `10` type attributes
- [[#WebKit|WebKit]]: `31` conflict sets, `100` type attributes
- [[#WebKitWebProcessExtension|WebKitWebProcessExtension]]: `1` conflict sets, `13` type attributes

## Libraries

### Adw

Conflict sets: `59`. Conflicted type attributes: `1413`.

#### `action_added` `method+signal`

Members:
- `Gio.ActionGroup.action_added`
- `Gio.ActionGroup::action-added`
Affected types: `2`
Examples: `Application`, `ApplicationWindow`

#### `action_enabled_changed` `method+signal`

Members:
- `Gio.ActionGroup.action_enabled_changed`
- `Gio.ActionGroup::action-enabled-changed`
Affected types: `2`
Examples: `Application`, `ApplicationWindow`

#### `action_removed` `method+signal`

Members:
- `Gio.ActionGroup.action_removed`
- `Gio.ActionGroup::action-removed`
Affected types: `2`
Examples: `Application`, `ApplicationWindow`

#### `action_state_changed` `method+signal`

Members:
- `Gio.ActionGroup.action_state_changed`
- `Gio.ActionGroup::action-state-changed`
Affected types: `2`
Examples: `Application`, `ApplicationWindow`

#### `activate` `method+signal`

Members:
- `Gio.Application.activate`
- `Gio.Application::activate`
Affected types: `1`
Examples: `Application`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Adw.SplitButton::activate`
Affected types: `1`
Examples: `SplitButton`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Adw.TabButton::activate`
Affected types: `1`
Examples: `TabButton`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.ListBoxRow::activate`
Affected types: `5`
Examples: `ButtonRow`, `EntryRow`, `ExpanderRow`, `PasswordEntryRow`, `PreferencesRow`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.ListBoxRow::activate`
- `Adw.ActionRow.activate`
Affected types: `4`
Examples: `ActionRow`, `ComboRow`, `SpinRow`, `SwitchRow`

#### `activate_default` `method+signal`

Members:
- `Gtk.Window.activate_default`
- `Gtk.Window::activate-default`
Affected types: `5`
Examples: `AboutWindow`, `ApplicationWindow`, `MessageDialog`, `PreferencesWindow`, `Window`

#### `activate_focus` `method+signal`

Members:
- `Gtk.Window.activate_focus`
- `Gtk.Window::activate-focus`
Affected types: `5`
Examples: `AboutWindow`, `ApplicationWindow`, `MessageDialog`, `PreferencesWindow`, `Window`

#### `add` `method+signal`

Members:
- `Gtk.Container.add`
- `Gtk.Container::add`
Affected types: `13`
Examples: `AboutWindow`, `ActionRow`, `ApplicationWindow`, `ButtonRow`, `ComboRow`, `EntryRow`, `ExpanderRow`, `MessageDialog`, ... `5` more

#### `add` `method+signal`

Members:
- `Gtk.Container.add`
- `Gtk.Container::add`
- `Adw.PreferencesWindow.add`
Affected types: `1`
Examples: `PreferencesWindow`

#### `can_activate_accel` `method+signal`

Members:
- `Gtk.Widget.can_activate_accel`
- `Gtk.Widget::can-activate-accel`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `changed` `method+signal`

Members:
- `Gtk.ListBoxRow.changed`
- `Gtk.Editable::changed`
Affected types: `3`
Examples: `EntryRow`, `PasswordEntryRow`, `SpinRow`

#### `check_resize` `method+signal`

Members:
- `Gtk.Container.check_resize`
- `Gtk.Container::check-resize`
Affected types: `14`
Examples: `AboutWindow`, `ActionRow`, `ApplicationWindow`, `ButtonRow`, `ComboRow`, `EntryRow`, `ExpanderRow`, `MessageDialog`, ... `6` more

#### `child_notify` `method+signal`

Members:
- `Gtk.Widget.child_notify`
- `Gtk.Widget::child-notify`
Affected types: `49`
Examples: `AboutDialog`, `AlertDialog`, `Avatar`, `Banner`, `Bin`, `BottomSheet`, `BreakpointBin`, `ButtonContent`, ... `41` more

#### `child_notify` `method+signal`

Members:
- `Gtk.Widget.child_notify`
- `Gtk.Widget::child-notify`
- `Gtk.Container.child_notify`
Affected types: `14`
Examples: `AboutWindow`, `ActionRow`, `ApplicationWindow`, `ButtonRow`, `ComboRow`, `EntryRow`, `ExpanderRow`, `MessageDialog`, ... `6` more

#### `close_page` `method+signal`

Members:
- `Adw.TabView.close_page`
- `Adw.TabView::close-page`
Affected types: `1`
Examples: `TabView`

#### `delete_text` `method+signal`

Members:
- `Gtk.Editable.delete_text`
- `Gtk.Editable::delete-text`
Affected types: `3`
Examples: `EntryRow`, `PasswordEntryRow`, `SpinRow`

#### `destroy` `method+signal`

Members:
- `Gtk.Widget.destroy`
- `Gtk.Widget::destroy`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `drag_begin` `method+signal`

Members:
- `Gtk.Widget.drag_begin`
- `Gtk.Widget::drag-begin`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `draw` `method+signal`

Members:
- `Gtk.Widget.draw`
- `Gtk.Widget::draw`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `event` `method+signal`

Members:
- `Gtk.Widget.event`
- `Gtk.Widget::event`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `grab_focus` `method+signal`

Members:
- `Gtk.Widget.grab_focus`
- `Gtk.Widget::grab-focus`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `hide` `method+signal`

Members:
- `Gtk.Widget.hide`
- `Gtk.Widget::hide`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `insert_text` `method+signal`

Members:
- `Gtk.Editable.insert_text`
- `Gtk.Editable::insert-text`
Affected types: `3`
Examples: `EntryRow`, `PasswordEntryRow`, `SpinRow`

#### `invalidate_contents` `method+signal`

Members:
- `Gdk.Paintable.invalidate_contents`
- `Gdk.Paintable::invalidate-contents`
Affected types: `1`
Examples: `SpinnerPaintable`

#### `invalidate_size` `method+signal`

Members:
- `Gdk.Paintable.invalidate_size`
- `Gdk.Paintable::invalidate-size`
Affected types: `1`
Examples: `SpinnerPaintable`

#### `items_changed` `method+signal`

Members:
- `Gio.ListModel.items_changed`
- `Gio.ListModel::items-changed`
Affected types: `3`
Examples: `EnumListModel`, `ShortcutsSection`, `ViewStackPages`

#### `keynav_failed` `method+signal`

Members:
- `Gtk.Widget.keynav_failed`
- `Gtk.Widget::keynav-failed`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `map` `method+signal`

Members:
- `Gtk.Widget.map`
- `Gtk.Widget::map`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `mnemonic_activate` `method+signal`

Members:
- `Gtk.Widget.mnemonic_activate`
- `Gtk.Widget::mnemonic-activate`
Affected types: `58`
Examples: `AboutDialog`, `ActionRow`, `AlertDialog`, `Avatar`, `Banner`, `Bin`, `BottomSheet`, `BreakpointBin`, ... `50` more

#### `mnemonic_activate` `method+signal`

Members:
- `Gtk.Widget.mnemonic_activate`
- `Gtk.Widget::mnemonic-activate`
- `Gtk.Window.mnemonic_activate`
Affected types: `5`
Examples: `AboutWindow`, `ApplicationWindow`, `MessageDialog`, `PreferencesWindow`, `Window`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `91`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `Animation`, `AnimationTarget`, `Application`, `ApplicationWindow`, ... `83` more

#### `open` `method+signal`

Members:
- `Gio.Application.open`
- `Gio.Application::open`
Affected types: `1`
Examples: `Application`

#### `realize` `method+signal`

Members:
- `Gtk.Widget.realize`
- `Gtk.Widget::realize`
Affected types: `58`
Examples: `AboutDialog`, `ActionRow`, `AlertDialog`, `Avatar`, `Banner`, `Bin`, `BottomSheet`, `BreakpointBin`, ... `50` more

#### `realize` `method+signal`

Members:
- `Gtk.Widget.realize`
- `Gtk.Widget::realize`
- `Gtk.Native.realize`
Affected types: `5`
Examples: `AboutWindow`, `ApplicationWindow`, `MessageDialog`, `PreferencesWindow`, `Window`

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
Affected types: `6`
Examples: `AboutWindow`, `ApplicationWindow`, `ButtonRow`, `MessageDialog`, `PreferencesRow`, `Window`

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
- `Adw.ActionRow.remove`
Affected types: `4`
Examples: `ActionRow`, `ComboRow`, `SpinRow`, `SwitchRow`

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
- `Adw.EntryRow.remove`
Affected types: `2`
Examples: `EntryRow`, `PasswordEntryRow`

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
- `Adw.ExpanderRow.remove`
Affected types: `1`
Examples: `ExpanderRow`

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
- `Adw.PreferencesWindow.remove`
Affected types: `1`
Examples: `PreferencesWindow`

#### `response` `method+signal`

Members:
- `Adw.MessageDialog.response`
- `Adw.MessageDialog::response`
Affected types: `1`
Examples: `MessageDialog`

#### `sections_changed` `method+signal`

Members:
- `Gtk.SectionModel.sections_changed`
- `Gtk.SectionModel::sections-changed`
Affected types: `1`
Examples: `ViewStackPages`

#### `selection_changed` `method+signal`

Members:
- `Gtk.SelectionModel.selection_changed`
- `Gtk.SelectionModel::selection-changed`
Affected types: `1`
Examples: `ViewStackPages`

#### `set_focus` `method+signal`

Members:
- `Gtk.Window.set_focus`
- `Gtk.Window::set-focus`
- `Gtk.Root.set_focus`
Affected types: `5`
Examples: `AboutWindow`, `ApplicationWindow`, `MessageDialog`, `PreferencesWindow`, `Window`

#### `set_focus_child` `method+signal`

Members:
- `Gtk.Container.set_focus_child`
- `Gtk.Container::set-focus-child`
Affected types: `14`
Examples: `AboutWindow`, `ActionRow`, `ApplicationWindow`, `ButtonRow`, `ComboRow`, `EntryRow`, `ExpanderRow`, `MessageDialog`, ... `6` more

#### `show` `method+signal`

Members:
- `Gtk.Widget.show`
- `Gtk.Widget::show`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `size_allocate` `method+signal`

Members:
- `Gtk.Widget.size_allocate`
- `Gtk.Widget::size-allocate`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `unmap` `method+signal`

Members:
- `Gtk.Widget.unmap`
- `Gtk.Widget::unmap`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `unrealize` `method+signal`

Members:
- `Gtk.Widget.unrealize`
- `Gtk.Widget::unrealize`
Affected types: `58`
Examples: `AboutDialog`, `ActionRow`, `AlertDialog`, `Avatar`, `Banner`, `Bin`, `BottomSheet`, `BreakpointBin`, ... `50` more

#### `unrealize` `method+signal`

Members:
- `Gtk.Widget.unrealize`
- `Gtk.Widget::unrealize`
- `Gtk.Native.unrealize`
Affected types: `5`
Examples: `AboutWindow`, `ApplicationWindow`, `MessageDialog`, `PreferencesWindow`, `Window`

#### `has_default` `property+method`

Members:
- `Gtk.Widget.has_default`
- `Gtk.Widget:has-default`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `has_focus` `property+method`

Members:
- `Gtk.Widget.has_focus`
- `Gtk.Widget:has-focus`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `has_toplevel_focus` `property+method`

Members:
- `Gtk.Window.has_toplevel_focus`
- `Gtk.Window:has-toplevel-focus`
Affected types: `5`
Examples: `AboutWindow`, `ApplicationWindow`, `MessageDialog`, `PreferencesWindow`, `Window`

#### `is_active` `property+method`

Members:
- `Gtk.Window.is_active`
- `Gtk.Window:is-active`
Affected types: `5`
Examples: `AboutWindow`, `ApplicationWindow`, `MessageDialog`, `PreferencesWindow`, `Window`

#### `is_focus` `property+method`

Members:
- `Gtk.Widget.is_focus`
- `Gtk.Widget:is-focus`
Affected types: `63`
Examples: `AboutDialog`, `AboutWindow`, `ActionRow`, `AlertDialog`, `ApplicationWindow`, `Avatar`, `Banner`, `Bin`, ... `55` more

#### `is_maximized` `property+method`

Members:
- `Gtk.Window.is_maximized`
- `Gtk.Window:is-maximized`
Affected types: `5`
Examples: `AboutWindow`, `ApplicationWindow`, `MessageDialog`, `PreferencesWindow`, `Window`

### AppStream

Conflict sets: `1`. Conflicted type attributes: `32`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `32`
Examples: `Agreement`, `AgreementSection`, `Artifact`, `Branding`, `Bundle`, `Category`, `Checksum`, `Component`, ... `24` more

### Atk

Conflict sets: `1`. Conflicted type attributes: `16`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `16`
Examples: `GObjectAccessible`, `Hyperlink`, `Misc`, `NoOpObject`, `NoOpObjectFactory`, `Object`, `ObjectFactory`, `Plug`, ... `8` more

### Atspi

Conflict sets: `1`. Conflicted type attributes: `13`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `13`
Examples: `Accessible`, `Application`, `Device`, `DeviceA11yManager`, `DeviceLegacy`, `DeviceListener`, `DeviceX11`, `EventListener`, ... `5` more

### CloudProviders

Conflict sets: `1`. Conflicted type attributes: `12`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `12`
Examples: `Account`, `AccountExporter`, `Collector`, `DbusAccountProxy`, `DbusAccountSkeleton`, `DbusObjectManagerClient`, `DbusObjectProxy`, `DbusObjectSkeleton`, ... `4` more

### DBusGLib

Conflict sets: `1`. Conflicted type attributes: `1`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `1`
Examples: `Proxy`

### GObject

Conflict sets: `1`. Conflicted type attributes: `6`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `6`
Examples: `Binding`, `BindingGroup`, `InitiallyUnowned`, `Object`, `SignalGroup`, `TypeModule`

### GUdev

Conflict sets: `1`. Conflicted type attributes: `3`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `3`
Examples: `Client`, `Device`, `Enumerator`

### Gdk

Conflict sets: `5`. Conflicted type attributes: `52`.

#### `content_changed` `method+signal`

Members:
- `Gdk.ContentProvider.content_changed`
- `Gdk.ContentProvider::content-changed`
Affected types: `1`
Examples: `ContentProvider`

#### `invalidate_contents` `method+signal`

Members:
- `Gdk.Paintable.invalidate_contents`
- `Gdk.Paintable::invalidate-contents`
Affected types: `5`
Examples: `DmabufTexture`, `GLTexture`, `MemoryTexture`, `Paintable`, `Texture`

#### `invalidate_size` `method+signal`

Members:
- `Gdk.Paintable.invalidate_size`
- `Gdk.Paintable::invalidate-size`
Affected types: `5`
Examples: `DmabufTexture`, `GLTexture`, `MemoryTexture`, `Paintable`, `Texture`

#### `launch_failed` `method+signal`

Members:
- `Gio.AppLaunchContext.launch_failed`
- `Gio.AppLaunchContext::launch-failed`
Affected types: `1`
Examples: `AppLaunchContext`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `40`
Examples: `AppLaunchContext`, `CairoContext`, `CicpParams`, `Clipboard`, `ContentDeserializer`, `ContentProvider`, `ContentSerializer`, `Cursor`, ... `32` more

### GdkPixbuf

Conflict sets: `1`. Conflicted type attributes: `7`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `7`
Examples: `Pixbuf`, `PixbufAnimation`, `PixbufAnimationIter`, `PixbufLoader`, `PixbufNonAnim`, `PixbufSimpleAnim`, `PixbufSimpleAnimIter`

### GdkWayland

Conflict sets: `1`. Conflicted type attributes: `8`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `8`
Examples: `WaylandDevice`, `WaylandDisplay`, `WaylandGLContext`, `WaylandMonitor`, `WaylandPopup`, `WaylandSeat`, `WaylandSurface`, `WaylandToplevel`

### GdkX11

Conflict sets: `2`. Conflicted type attributes: `18`.

#### `launch_failed` `method+signal`

Members:
- `Gio.AppLaunchContext.launch_failed`
- `Gio.AppLaunchContext::launch-failed`
Affected types: `1`
Examples: `X11AppLaunchContext`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `17`
Examples: `X11AppLaunchContext`, `X11Cursor`, `X11DeviceCore`, `X11DeviceManagerCore`, `X11DeviceManagerXI2`, `X11DeviceXI2`, `X11Display`, `X11DisplayManager`, ... `9` more

### Gio

Conflict sets: `16`. Conflicted type attributes: `145`.

#### `action_added` `method+signal`

Members:
- `Gio.ActionGroup.action_added`
- `Gio.ActionGroup::action-added`
Affected types: `5`
Examples: `ActionGroup`, `Application`, `DBusActionGroup`, `RemoteActionGroup`, `SimpleActionGroup`

#### `action_enabled_changed` `method+signal`

Members:
- `Gio.ActionGroup.action_enabled_changed`
- `Gio.ActionGroup::action-enabled-changed`
Affected types: `5`
Examples: `ActionGroup`, `Application`, `DBusActionGroup`, `RemoteActionGroup`, `SimpleActionGroup`

#### `action_removed` `method+signal`

Members:
- `Gio.ActionGroup.action_removed`
- `Gio.ActionGroup::action-removed`
Affected types: `5`
Examples: `ActionGroup`, `Application`, `DBusActionGroup`, `RemoteActionGroup`, `SimpleActionGroup`

#### `action_state_changed` `method+signal`

Members:
- `Gio.ActionGroup.action_state_changed`
- `Gio.ActionGroup::action-state-changed`
Affected types: `5`
Examples: `ActionGroup`, `Application`, `DBusActionGroup`, `RemoteActionGroup`, `SimpleActionGroup`

#### `activate` `method+signal`

Members:
- `Gio.Action.activate`
- `Gio.SimpleAction::activate`
Affected types: `1`
Examples: `SimpleAction`

#### `activate` `method+signal`

Members:
- `Gio.Application.activate`
- `Gio.Application::activate`
Affected types: `1`
Examples: `Application`

#### `allow_mechanism` `method+signal`

Members:
- `Gio.DBusAuthObserver.allow_mechanism`
- `Gio.DBusAuthObserver::allow-mechanism`
Affected types: `1`
Examples: `DBusAuthObserver`

#### `authorize_authenticated_peer` `method+signal`

Members:
- `Gio.DBusAuthObserver.authorize_authenticated_peer`
- `Gio.DBusAuthObserver::authorize-authenticated-peer`
Affected types: `1`
Examples: `DBusAuthObserver`

#### `change_state` `method+signal`

Members:
- `Gio.Action.change_state`
- `Gio.SimpleAction::change-state`
Affected types: `1`
Examples: `SimpleAction`

#### `items_changed` `method+signal`

Members:
- `Gio.ListModel.items_changed`
- `Gio.ListModel::items-changed`
Affected types: `2`
Examples: `ListModel`, `ListStore`

#### `items_changed` `method+signal`

Members:
- `Gio.MenuModel.items_changed`
- `Gio.MenuModel::items-changed`
Affected types: `3`
Examples: `DBusMenuModel`, `Menu`, `MenuModel`

#### `launch_failed` `method+signal`

Members:
- `Gio.AppLaunchContext.launch_failed`
- `Gio.AppLaunchContext::launch-failed`
Affected types: `1`
Examples: `AppLaunchContext`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `111`
Examples: `AppInfoMonitor`, `AppLaunchContext`, `Application`, `ApplicationCommandLine`, `BufferedInputStream`, `BufferedOutputStream`, `BytesIcon`, `Cancellable`, ... `103` more

#### `open` `method+signal`

Members:
- `Gio.Application.open`
- `Gio.Application::open`
Affected types: `1`
Examples: `Application`

#### `reply` `method+signal`

Members:
- `Gio.MountOperation.reply`
- `Gio.MountOperation::reply`
Affected types: `1`
Examples: `MountOperation`

#### `closed` `property+signal`

Members:
- `Gio.DBusConnection:closed`
- `Gio.DBusConnection::closed`
Affected types: `1`
Examples: `DBusConnection`

### GioUnix

Conflict sets: `1`. Conflicted type attributes: `5`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `5`
Examples: `DesktopAppInfo`, `FDMessage`, `InputStream`, `MountMonitor`, `OutputStream`

### Gly

Conflict sets: `1`. Conflicted type attributes: `7`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `7`
Examples: `Creator`, `EncodedImage`, `Frame`, `FrameRequest`, `Image`, `Loader`, `NewFrame`

### Grl

Conflict sets: `1`. Conflicted type attributes: `9`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `9`
Examples: `Caps`, `Config`, `Data`, `Media`, `OperationOptions`, `Plugin`, `Registry`, `RelatedKeys`, ... `1` more

### GrlNet

Conflict sets: `1`. Conflicted type attributes: `1`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `1`
Examples: `Wc`

### Gsk

Conflict sets: `1`. Conflicted type attributes: `7`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `7`
Examples: `BroadwayRenderer`, `CairoRenderer`, `GLRenderer`, `GLShader`, `NglRenderer`, `Renderer`, `VulkanRenderer`

### Gtk

Conflict sets: `154`. Conflicted type attributes: `4502`.

#### `action_added` `method+signal`

Members:
- `Gio.ActionGroup.action_added`
- `Gio.ActionGroup::action-added`
Affected types: `2`
Examples: `Application`, `ApplicationWindow`

#### `action_enabled_changed` `method+signal`

Members:
- `Gio.ActionGroup.action_enabled_changed`
- `Gio.ActionGroup::action-enabled-changed`
Affected types: `2`
Examples: `Application`, `ApplicationWindow`

#### `action_removed` `method+signal`

Members:
- `Gio.ActionGroup.action_removed`
- `Gio.ActionGroup::action-removed`
Affected types: `2`
Examples: `Application`, `ApplicationWindow`

#### `action_state_changed` `method+signal`

Members:
- `Gio.ActionGroup.action_state_changed`
- `Gio.ActionGroup::action-state-changed`
Affected types: `2`
Examples: `Application`, `ApplicationWindow`

#### `activate` `method+signal`

Members:
- `Gio.Application.activate`
- `Gio.Application::activate`
Affected types: `1`
Examples: `Application`

#### `activate` `method+signal`

Members:
- `Gtk.Action.activate`
- `Gtk.Action::activate`
Affected types: `4`
Examples: `Action`, `RadioAction`, `RecentAction`, `ToggleAction`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.Button::activate`
Affected types: `12`
Examples: `Button`, `CheckButton`, `ColorButton`, `FontButton`, `LinkButton`, `LockButton`, `MenuButton`, `ModelButton`, ... `4` more

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.ColorDialogButton::activate`
Affected types: `1`
Examples: `ColorDialogButton`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.ColumnView::activate`
Affected types: `1`
Examples: `ColumnView`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.DropDown::activate`
Affected types: `1`
Examples: `DropDown`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.Entry::activate`
Affected types: `3`
Examples: `Entry`, `SearchEntry`, `SpinButton`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.Expander::activate`
Affected types: `1`
Examples: `Expander`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.FlowBoxChild::activate`
Affected types: `1`
Examples: `FlowBoxChild`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.FontDialogButton::activate`
Affected types: `1`
Examples: `FontDialogButton`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.GridView::activate`
Affected types: `1`
Examples: `GridView`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.ListBoxRow::activate`
Affected types: `1`
Examples: `ListBoxRow`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.ListView::activate`
Affected types: `1`
Examples: `ListView`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.MenuItem.activate`
- `Gtk.MenuItem::activate`
Affected types: `6`
Examples: `CheckMenuItem`, `ImageMenuItem`, `MenuItem`, `RadioMenuItem`, `SeparatorMenuItem`, `TearoffMenuItem`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.PasswordEntry::activate`
Affected types: `1`
Examples: `PasswordEntry`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.Switch::activate`
Affected types: `1`
Examples: `Switch`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.Text::activate`
Affected types: `1`
Examples: `Text`

#### `activate_default` `method+signal`

Members:
- `Gtk.Window.activate_default`
- `Gtk.Window::activate-default`
Affected types: `18`
Examples: `AboutDialog`, `AppChooserDialog`, `ApplicationWindow`, `Assistant`, `ColorChooserDialog`, `ColorSelectionDialog`, `Dialog`, `FileChooserDialog`, ... `10` more

#### `activate_focus` `method+signal`

Members:
- `Gtk.Window.activate_focus`
- `Gtk.Window::activate-focus`
Affected types: `18`
Examples: `AboutDialog`, `AppChooserDialog`, `ApplicationWindow`, `Assistant`, `ColorChooserDialog`, `ColorSelectionDialog`, `Dialog`, `FileChooserDialog`, ... `10` more

#### `add` `method+signal`

Members:
- `Gtk.Container.add`
- `Gtk.Container::add`
Affected types: `110`
Examples: `AboutDialog`, `ActionBar`, `Alignment`, `AppChooserButton`, `AppChooserDialog`, `AppChooserWidget`, `ApplicationWindow`, `AspectFrame`, ... `102` more

#### `apply_attributes` `method+signal`

Members:
- `Gtk.CellArea.apply_attributes`
- `Gtk.CellArea::apply-attributes`
Affected types: `2`
Examples: `CellArea`, `CellAreaBox`

#### `apply_tag` `method+signal`

Members:
- `Gtk.TextBuffer.apply_tag`
- `Gtk.TextBuffer::apply-tag`
Affected types: `1`
Examples: `TextBuffer`

#### `begin_user_action` `method+signal`

Members:
- `Gtk.TextBuffer.begin_user_action`
- `Gtk.TextBuffer::begin-user-action`
Affected types: `1`
Examples: `TextBuffer`

#### `can_activate_accel` `method+signal`

Members:
- `Gtk.Widget.can_activate_accel`
- `Gtk.Widget::can-activate-accel`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `cancel` `method+signal`

Members:
- `Gtk.MenuShell.cancel`
- `Gtk.MenuShell::cancel`
Affected types: `4`
Examples: `Menu`, `MenuBar`, `MenuShell`, `RecentChooserMenu`

#### `changed` `method+signal`

Members:
- `Gtk.Adjustment.changed`
- `Gtk.Adjustment::changed`
Affected types: `1`
Examples: `Adjustment`

#### `changed` `method+signal`

Members:
- `Gtk.Filter.changed`
- `Gtk.Filter::changed`
Affected types: `7`
Examples: `AnyFilter`, `BoolFilter`, `CustomFilter`, `EveryFilter`, `Filter`, `MultiFilter`, `StringFilter`

#### `changed` `method+signal`

Members:
- `Gtk.Sorter.changed`
- `Gtk.Sorter::changed`
Affected types: `7`
Examples: `ColumnViewSorter`, `CustomSorter`, `MultiSorter`, `NumericSorter`, `Sorter`, `StringSorter`, `TreeListRowSorter`

#### `check_resize` `method+signal`

Members:
- `Gtk.Container.check_resize`
- `Gtk.Container::check-resize`
Affected types: `110`
Examples: `AboutDialog`, `ActionBar`, `Alignment`, `AppChooserButton`, `AppChooserDialog`, `AppChooserWidget`, `ApplicationWindow`, `AspectFrame`, ... `102` more

#### `child_notify` `method+signal`

Members:
- `Gtk.Widget.child_notify`
- `Gtk.Widget::child-notify`
Affected types: `57`
Examples: `AccelLabel`, `Actionable`, `AppChooser`, `Arrow`, `Calendar`, `CellEditable`, `CellView`, `CenterBox`, ... `49` more

#### `child_notify` `method+signal`

Members:
- `Gtk.Widget.child_notify`
- `Gtk.Widget::child-notify`
- `Gtk.Container.child_notify`
Affected types: `110`
Examples: `AboutDialog`, `ActionBar`, `Alignment`, `AppChooserButton`, `AppChooserDialog`, `AppChooserWidget`, `ApplicationWindow`, `AspectFrame`, ... `102` more

#### `clicked` `method+signal`

Members:
- `Gtk.Button.clicked`
- `Gtk.Button::clicked`
Affected types: `12`
Examples: `Button`, `CheckButton`, `ColorButton`, `FontButton`, `LinkButton`, `LockButton`, `MenuButton`, `ModelButton`, ... `4` more

#### `clicked` `method+signal`

Members:
- `Gtk.TreeViewColumn.clicked`
- `Gtk.TreeViewColumn::clicked`
Affected types: `1`
Examples: `TreeViewColumn`

#### `close` `method+signal`

Members:
- `Gtk.Window.close`
- `Gtk.Assistant::close`
Affected types: `1`
Examples: `Assistant`

#### `close` `method+signal`

Members:
- `Gtk.Window.close`
- `Gtk.Dialog::close`
Affected types: `12`
Examples: `AboutDialog`, `AppChooserDialog`, `ColorChooserDialog`, `ColorSelectionDialog`, `Dialog`, `FileChooserDialog`, `FontChooserDialog`, `FontSelectionDialog`, ... `4` more

#### `close` `method+signal`

Members:
- `Gtk.Window.close`
- `Gtk.ShortcutsWindow::close`
Affected types: `1`
Examples: `ShortcutsWindow`

#### `copy_clipboard` `method+signal`

Members:
- `Gtk.Editable.copy_clipboard`
- `Gtk.Entry::copy-clipboard`
Affected types: `3`
Examples: `Entry`, `SearchEntry`, `SpinButton`

#### `copy_clipboard` `method+signal`

Members:
- `Gtk.Editable.copy_clipboard`
- `Gtk.Text::copy-clipboard`
Affected types: `1`
Examples: `Text`

#### `cut_clipboard` `method+signal`

Members:
- `Gtk.Editable.cut_clipboard`
- `Gtk.Entry::cut-clipboard`
Affected types: `3`
Examples: `Entry`, `SearchEntry`, `SpinButton`

#### `cut_clipboard` `method+signal`

Members:
- `Gtk.Editable.cut_clipboard`
- `Gtk.Text::cut-clipboard`
Affected types: `1`
Examples: `Text`

#### `deactivate` `method+signal`

Members:
- `Gtk.MenuShell.deactivate`
- `Gtk.MenuShell::deactivate`
Affected types: `4`
Examples: `Menu`, `MenuBar`, `MenuShell`, `RecentChooserMenu`

#### `delete_surrounding` `method+signal`

Members:
- `Gtk.IMContext.delete_surrounding`
- `Gtk.IMContext::delete-surrounding`
Affected types: `3`
Examples: `IMContext`, `IMContextSimple`, `IMMulticontext`

#### `delete_text` `method+signal`

Members:
- `Gtk.Editable.delete_text`
- `Gtk.Editable::delete-text`
Affected types: `7`
Examples: `Editable`, `EditableLabel`, `Entry`, `PasswordEntry`, `SearchEntry`, `SpinButton`, `Text`

#### `deselect` `method+signal`

Members:
- `Gtk.MenuItem.deselect`
- `Gtk.MenuItem::deselect`
Affected types: `6`
Examples: `CheckMenuItem`, `ImageMenuItem`, `MenuItem`, `RadioMenuItem`, `SeparatorMenuItem`, `TearoffMenuItem`

#### `destroy` `method+signal`

Members:
- `Gtk.Widget.destroy`
- `Gtk.Widget::destroy`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `drag_begin` `method+signal`

Members:
- `Gtk.Widget.drag_begin`
- `Gtk.Widget::drag-begin`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `drag_cancel` `method+signal`

Members:
- `Gtk.DragSource.drag_cancel`
- `Gtk.DragSource::drag-cancel`
Affected types: `1`
Examples: `DragSource`

#### `draw` `method+signal`

Members:
- `Gtk.Widget.draw`
- `Gtk.Widget::draw`
Affected types: `166`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `158` more

#### `editing_done` `method+signal`

Members:
- `Gtk.CellEditable.editing_done`
- `Gtk.CellEditable::editing-done`
Affected types: `7`
Examples: `AppChooserButton`, `CellEditable`, `ComboBox`, `ComboBoxText`, `Entry`, `SearchEntry`, `SpinButton`

#### `end_user_action` `method+signal`

Members:
- `Gtk.TextBuffer.end_user_action`
- `Gtk.TextBuffer::end-user-action`
Affected types: `1`
Examples: `TextBuffer`

#### `enter` `method+signal`

Members:
- `Gtk.Button.enter`
- `Gtk.Button::enter`
Affected types: `12`
Examples: `Button`, `CheckButton`, `ColorButton`, `FontButton`, `LinkButton`, `LockButton`, `MenuButton`, `ModelButton`, ... `4` more

#### `event` `method+signal`

Members:
- `Gtk.TextTag.event`
- `Gtk.TextTag::event`
Affected types: `1`
Examples: `TextTag`

#### `event` `method+signal`

Members:
- `Gtk.Widget.event`
- `Gtk.Widget::event`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `grab_focus` `method+signal`

Members:
- `Gtk.Widget.grab_focus`
- `Gtk.Widget::grab-focus`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `hide` `method+signal`

Members:
- `Gtk.Widget.hide`
- `Gtk.Widget::hide`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `insert` `method+signal`

Members:
- `Gtk.MenuShell.insert`
- `Gtk.MenuShell::insert`
Affected types: `4`
Examples: `Menu`, `MenuBar`, `MenuShell`, `RecentChooserMenu`

#### `insert_child_anchor` `method+signal`

Members:
- `Gtk.TextBuffer.insert_child_anchor`
- `Gtk.TextBuffer::insert-child-anchor`
Affected types: `1`
Examples: `TextBuffer`

#### `insert_pixbuf` `method+signal`

Members:
- `Gtk.TextBuffer.insert_pixbuf`
- `Gtk.TextBuffer::insert-pixbuf`
Affected types: `1`
Examples: `TextBuffer`

#### `insert_prefix` `method+signal`

Members:
- `Gtk.EntryCompletion.insert_prefix`
- `Gtk.EntryCompletion::insert-prefix`
Affected types: `1`
Examples: `EntryCompletion`

#### `insert_text` `method+signal`

Members:
- `Gtk.Editable.insert_text`
- `Gtk.Editable::insert-text`
Affected types: `7`
Examples: `Editable`, `EditableLabel`, `Entry`, `PasswordEntry`, `SearchEntry`, `SpinButton`, `Text`

#### `invalidate_contents` `method+signal`

Members:
- `Gdk.Paintable.invalidate_contents`
- `Gdk.Paintable::invalidate-contents`
Affected types: `6`
Examples: `IconPaintable`, `MediaFile`, `MediaStream`, `Svg`, `SymbolicPaintable`, `WidgetPaintable`

#### `invalidate_size` `method+signal`

Members:
- `Gdk.Paintable.invalidate_size`
- `Gdk.Paintable::invalidate-size`
Affected types: `6`
Examples: `IconPaintable`, `MediaFile`, `MediaStream`, `Svg`, `SymbolicPaintable`, `WidgetPaintable`

#### `item_activated` `method+signal`

Members:
- `Gtk.IconView.item_activated`
- `Gtk.IconView::item-activated`
Affected types: `1`
Examples: `IconView`

#### `items_changed` `method+signal`

Members:
- `Gio.ListModel.items_changed`
- `Gio.ListModel::items-changed`
Affected types: `20`
Examples: `AnyFilter`, `BookmarkList`, `DirectoryList`, `EveryFilter`, `FilterListModel`, `FlattenListModel`, `MapListModel`, `MultiFilter`, ... `12` more

#### `keynav_failed` `method+signal`

Members:
- `Gtk.Widget.keynav_failed`
- `Gtk.Widget::keynav-failed`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `leave` `method+signal`

Members:
- `Gtk.Button.leave`
- `Gtk.Button::leave`
Affected types: `12`
Examples: `Button`, `CheckButton`, `ColorButton`, `FontButton`, `LinkButton`, `LockButton`, `MenuButton`, `ModelButton`, ... `4` more

#### `map` `method+signal`

Members:
- `Gtk.Widget.map`
- `Gtk.Widget::map`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `mnemonic_activate` `method+signal`

Members:
- `Gtk.Widget.mnemonic_activate`
- `Gtk.Widget::mnemonic-activate`
Affected types: `149`
Examples: `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserWidget`, `Arrow`, ... `141` more

#### `mnemonic_activate` `method+signal`

Members:
- `Gtk.Widget.mnemonic_activate`
- `Gtk.Widget::mnemonic-activate`
- `Gtk.Window.mnemonic_activate`
Affected types: `18`
Examples: `AboutDialog`, `AppChooserDialog`, `ApplicationWindow`, `Assistant`, `ColorChooserDialog`, `ColorSelectionDialog`, `Dialog`, `FileChooserDialog`, ... `10` more

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `402`
Examples: `ATContext`, `AboutDialog`, `AccelGroup`, `AccelLabel`, `AccelMap`, `Accessible`, `AccessibleHyperlink`, `AccessibleHypertext`, ... `394` more

#### `open` `method+signal`

Members:
- `Gio.Application.open`
- `Gio.Application::open`
Affected types: `1`
Examples: `Application`

#### `paste_clipboard` `method+signal`

Members:
- `Gtk.Editable.paste_clipboard`
- `Gtk.Entry::paste-clipboard`
Affected types: `3`
Examples: `Entry`, `SearchEntry`, `SpinButton`

#### `paste_clipboard` `method+signal`

Members:
- `Gtk.Editable.paste_clipboard`
- `Gtk.Text::paste-clipboard`
Affected types: `1`
Examples: `Text`

#### `popdown` `method+signal`

Members:
- `Gtk.ComboBox.popdown`
- `Gtk.ComboBox::popdown`
Affected types: `3`
Examples: `AppChooserButton`, `ComboBox`, `ComboBoxText`

#### `popup` `method+signal`

Members:
- `Gtk.ComboBox.popup`
- `Gtk.ComboBox::popup`
Affected types: `3`
Examples: `AppChooserButton`, `ComboBox`, `ComboBoxText`

#### `pressed` `method+signal`

Members:
- `Gtk.Button.pressed`
- `Gtk.Button::pressed`
Affected types: `12`
Examples: `Button`, `CheckButton`, `ColorButton`, `FontButton`, `LinkButton`, `LockButton`, `MenuButton`, `ModelButton`, ... `4` more

#### `realize` `method+signal`

Members:
- `Gtk.Widget.realize`
- `Gtk.Widget::realize`
Affected types: `161`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `153` more

#### `realize` `method+signal`

Members:
- `Gtk.Widget.realize`
- `Gtk.Widget::realize`
- `Gtk.Native.realize`
Affected types: `6`
Examples: `DragIcon`, `EmojiChooser`, `Native`, `PageSetupUnixDialog`, `PrintUnixDialog`, `Root`

#### `released` `method+signal`

Members:
- `Gtk.Button.released`
- `Gtk.Button::released`
Affected types: `12`
Examples: `Button`, `CheckButton`, `ColorButton`, `FontButton`, `LinkButton`, `LockButton`, `MenuButton`, `ModelButton`, ... `4` more

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
Affected types: `108`
Examples: `AboutDialog`, `ActionBar`, `Alignment`, `AppChooserButton`, `AppChooserDialog`, `AppChooserWidget`, `ApplicationWindow`, `AspectFrame`, ... `100` more

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
- `Gtk.ComboBoxText.remove`
Affected types: `1`
Examples: `ComboBoxText`

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
- `Gtk.Statusbar.remove`
Affected types: `1`
Examples: `Statusbar`

#### `remove_tag` `method+signal`

Members:
- `Gtk.TextBuffer.remove_tag`
- `Gtk.TextBuffer::remove-tag`
Affected types: `1`
Examples: `TextBuffer`

#### `remove_widget` `method+signal`

Members:
- `Gtk.CellEditable.remove_widget`
- `Gtk.CellEditable::remove-widget`
Affected types: `7`
Examples: `AppChooserButton`, `CellEditable`, `ComboBox`, `ComboBoxText`, `Entry`, `SearchEntry`, `SpinButton`

#### `reply` `method+signal`

Members:
- `Gio.MountOperation.reply`
- `Gio.MountOperation::reply`
Affected types: `1`
Examples: `MountOperation`

#### `response` `method+signal`

Members:
- `Gtk.Dialog.response`
- `Gtk.Dialog::response`
Affected types: `12`
Examples: `AboutDialog`, `AppChooserDialog`, `ColorChooserDialog`, `ColorSelectionDialog`, `Dialog`, `FileChooserDialog`, `FontChooserDialog`, `FontSelectionDialog`, ... `4` more

#### `response` `method+signal`

Members:
- `Gtk.InfoBar.response`
- `Gtk.InfoBar::response`
Affected types: `1`
Examples: `InfoBar`

#### `row_activated` `method+signal`

Members:
- `Gtk.TreeView.row_activated`
- `Gtk.TreeView::row-activated`
Affected types: `1`
Examples: `TreeView`

#### `row_changed` `method+signal`

Members:
- `Gtk.TreeModel.row_changed`
- `Gtk.TreeModel::row-changed`
Affected types: `6`
Examples: `ListStore`, `TreeModel`, `TreeModelFilter`, `TreeModelSort`, `TreeSortable`, `TreeStore`

#### `row_deleted` `method+signal`

Members:
- `Gtk.TreeModel.row_deleted`
- `Gtk.TreeModel::row-deleted`
Affected types: `6`
Examples: `ListStore`, `TreeModel`, `TreeModelFilter`, `TreeModelSort`, `TreeSortable`, `TreeStore`

#### `row_expanded` `method+signal`

Members:
- `Gtk.TreeView.row_expanded`
- `Gtk.TreeView::row-expanded`
Affected types: `1`
Examples: `TreeView`

#### `row_has_child_toggled` `method+signal`

Members:
- `Gtk.TreeModel.row_has_child_toggled`
- `Gtk.TreeModel::row-has-child-toggled`
Affected types: `6`
Examples: `ListStore`, `TreeModel`, `TreeModelFilter`, `TreeModelSort`, `TreeSortable`, `TreeStore`

#### `row_inserted` `method+signal`

Members:
- `Gtk.TreeModel.row_inserted`
- `Gtk.TreeModel::row-inserted`
Affected types: `6`
Examples: `ListStore`, `TreeModel`, `TreeModelFilter`, `TreeModelSort`, `TreeSortable`, `TreeStore`

#### `rows_reordered` `method+signal`

Members:
- `Gtk.TreeModel.rows_reordered`
- `Gtk.TreeModel::rows-reordered`
Affected types: `6`
Examples: `ListStore`, `TreeModel`, `TreeModelFilter`, `TreeModelSort`, `TreeSortable`, `TreeStore`

#### `sections_changed` `method+signal`

Members:
- `Gtk.SectionModel.sections_changed`
- `Gtk.SectionModel::sections-changed`
Affected types: `9`
Examples: `FilterListModel`, `FlattenListModel`, `MapListModel`, `MultiSelection`, `NoSelection`, `SectionModel`, `SingleSelection`, `SliceListModel`, ... `1` more

#### `select` `method+signal`

Members:
- `Gtk.MenuItem.select`
- `Gtk.MenuItem::select`
Affected types: `6`
Examples: `CheckMenuItem`, `ImageMenuItem`, `MenuItem`, `RadioMenuItem`, `SeparatorMenuItem`, `TearoffMenuItem`

#### `select_all` `method+signal`

Members:
- `Gtk.FlowBox.select_all`
- `Gtk.FlowBox::select-all`
Affected types: `1`
Examples: `FlowBox`

#### `select_all` `method+signal`

Members:
- `Gtk.IconView.select_all`
- `Gtk.IconView::select-all`
Affected types: `1`
Examples: `IconView`

#### `select_all` `method+signal`

Members:
- `Gtk.ListBox.select_all`
- `Gtk.ListBox::select-all`
Affected types: `1`
Examples: `ListBox`

#### `selection_changed` `method+signal`

Members:
- `Gtk.SelectionModel.selection_changed`
- `Gtk.SelectionModel::selection-changed`
Affected types: `4`
Examples: `MultiSelection`, `NoSelection`, `SelectionModel`, `SingleSelection`

#### `set_focus` `method+signal`

Members:
- `Gtk.Window.set_focus`
- `Gtk.Window::set-focus`
Affected types: `16`
Examples: `AboutDialog`, `AppChooserDialog`, `ApplicationWindow`, `Assistant`, `ColorChooserDialog`, `ColorSelectionDialog`, `Dialog`, `FileChooserDialog`, ... `8` more

#### `set_focus` `method+signal`

Members:
- `Gtk.Window.set_focus`
- `Gtk.Window::set-focus`
- `Gtk.Root.set_focus`
Affected types: `2`
Examples: `PageSetupUnixDialog`, `PrintUnixDialog`

#### `set_focus_child` `method+signal`

Members:
- `Gtk.Container.set_focus_child`
- `Gtk.Container::set-focus-child`
Affected types: `110`
Examples: `AboutDialog`, `ActionBar`, `Alignment`, `AppChooserButton`, `AppChooserDialog`, `AppChooserWidget`, `ApplicationWindow`, `AspectFrame`, ... `102` more

#### `show` `method+signal`

Members:
- `Gtk.Widget.show`
- `Gtk.Widget::show`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `size_allocate` `method+signal`

Members:
- `Gtk.Widget.size_allocate`
- `Gtk.Widget::size-allocate`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `sort_column_changed` `method+signal`

Members:
- `Gtk.TreeSortable.sort_column_changed`
- `Gtk.TreeSortable::sort-column-changed`
Affected types: `4`
Examples: `ListStore`, `TreeModelSort`, `TreeSortable`, `TreeStore`

#### `toggle_size_allocate` `method+signal`

Members:
- `Gtk.MenuItem.toggle_size_allocate`
- `Gtk.MenuItem::toggle-size-allocate`
Affected types: `6`
Examples: `CheckMenuItem`, `ImageMenuItem`, `MenuItem`, `RadioMenuItem`, `SeparatorMenuItem`, `TearoffMenuItem`

#### `toggle_size_request` `method+signal`

Members:
- `Gtk.MenuItem.toggle_size_request`
- `Gtk.MenuItem::toggle-size-request`
Affected types: `6`
Examples: `CheckMenuItem`, `ImageMenuItem`, `MenuItem`, `RadioMenuItem`, `SeparatorMenuItem`, `TearoffMenuItem`

#### `toggled` `method+signal`

Members:
- `Gtk.CheckMenuItem.toggled`
- `Gtk.CheckMenuItem::toggled`
Affected types: `2`
Examples: `CheckMenuItem`, `RadioMenuItem`

#### `toggled` `method+signal`

Members:
- `Gtk.ToggleAction.toggled`
- `Gtk.ToggleAction::toggled`
Affected types: `2`
Examples: `RadioAction`, `ToggleAction`

#### `toggled` `method+signal`

Members:
- `Gtk.ToggleButton.toggled`
- `Gtk.ToggleButton::toggled`
Affected types: `4`
Examples: `CheckButton`, `MenuButton`, `RadioButton`, `ToggleButton`

#### `toolbar_reconfigured` `method+signal`

Members:
- `Gtk.ToolItem.toolbar_reconfigured`
- `Gtk.ToolItem::toolbar-reconfigured`
Affected types: `6`
Examples: `MenuToolButton`, `RadioToolButton`, `SeparatorToolItem`, `ToggleToolButton`, `ToolButton`, `ToolItem`

#### `unmap` `method+signal`

Members:
- `Gtk.Widget.unmap`
- `Gtk.Widget::unmap`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `unrealize` `method+signal`

Members:
- `Gtk.Widget.unrealize`
- `Gtk.Widget::unrealize`
Affected types: `161`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `153` more

#### `unrealize` `method+signal`

Members:
- `Gtk.Widget.unrealize`
- `Gtk.Widget::unrealize`
- `Gtk.Native.unrealize`
Affected types: `6`
Examples: `DragIcon`, `EmojiChooser`, `Native`, `PageSetupUnixDialog`, `PrintUnixDialog`, `Root`

#### `unselect_all` `method+signal`

Members:
- `Gtk.FlowBox.unselect_all`
- `Gtk.FlowBox::unselect-all`
Affected types: `1`
Examples: `FlowBox`

#### `unselect_all` `method+signal`

Members:
- `Gtk.IconView.unselect_all`
- `Gtk.IconView::unselect-all`
Affected types: `1`
Examples: `IconView`

#### `unselect_all` `method+signal`

Members:
- `Gtk.ListBox.unselect_all`
- `Gtk.ListBox::unselect-all`
Affected types: `1`
Examples: `ListBox`

#### `value_changed` `method+signal`

Members:
- `Gtk.Adjustment.value_changed`
- `Gtk.Adjustment::value-changed`
Affected types: `1`
Examples: `Adjustment`

#### `accepts_pdf` `property+method`

Members:
- `Gtk.Printer.accepts_pdf`
- `Gtk.Printer:accepts-pdf`
Affected types: `1`
Examples: `Printer`

#### `accepts_ps` `property+method`

Members:
- `Gtk.Printer.accepts_ps`
- `Gtk.Printer:accepts-ps`
Affected types: `1`
Examples: `Printer`

#### `contains_focus` `property+method`

Members:
- `Gtk.EventControllerFocus.contains_focus`
- `Gtk.EventControllerFocus:contains-focus`
Affected types: `1`
Examples: `EventControllerFocus`

#### `contains_pointer` `property+method`

Members:
- `Gtk.DropControllerMotion.contains_pointer`
- `Gtk.DropControllerMotion:contains-pointer`
Affected types: `1`
Examples: `DropControllerMotion`

#### `ended` `property+method`

Members:
- `Gtk.MediaStream.ended`
- `Gtk.MediaStream:ended`
Affected types: `2`
Examples: `MediaFile`, `MediaStream`

#### `error` `property+method`

Members:
- `Gtk.MediaStream.error`
- `Gtk.MediaStream:error`
Affected types: `2`
Examples: `MediaFile`, `MediaStream`

#### `has_audio` `property+method`

Members:
- `Gtk.MediaStream.has_audio`
- `Gtk.MediaStream:has-audio`
Affected types: `2`
Examples: `MediaFile`, `MediaStream`

#### `has_default` `property+method`

Members:
- `Gtk.Widget.has_default`
- `Gtk.Widget:has-default`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `has_focus` `property+method`

Members:
- `Gtk.Widget.has_focus`
- `Gtk.Widget:has-focus`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `has_map` `property+method`

Members:
- `Gtk.MapListModel.has_map`
- `Gtk.MapListModel:has-map`
Affected types: `1`
Examples: `MapListModel`

#### `has_toplevel_focus` `property+method`

Members:
- `Gtk.Window.has_toplevel_focus`
- `Gtk.Window:has-toplevel-focus`
Affected types: `18`
Examples: `AboutDialog`, `AppChooserDialog`, `ApplicationWindow`, `Assistant`, `ColorChooserDialog`, `ColorSelectionDialog`, `Dialog`, `FileChooserDialog`, ... `10` more

#### `has_video` `property+method`

Members:
- `Gtk.MediaStream.has_video`
- `Gtk.MediaStream:has-video`
Affected types: `2`
Examples: `MediaFile`, `MediaStream`

#### `is_active` `property+method`

Members:
- `Gtk.Window.is_active`
- `Gtk.Window:is-active`
Affected types: `18`
Examples: `AboutDialog`, `AppChooserDialog`, `ApplicationWindow`, `Assistant`, `ColorChooserDialog`, `ColorSelectionDialog`, `Dialog`, `FileChooserDialog`, ... `10` more

#### `is_focus` `property+method`

Members:
- `Gtk.EventControllerFocus.is_focus`
- `Gtk.EventControllerFocus:is-focus`
Affected types: `1`
Examples: `EventControllerFocus`

#### `is_focus` `property+method`

Members:
- `Gtk.Widget.is_focus`
- `Gtk.Widget:is-focus`
Affected types: `167`
Examples: `AboutDialog`, `AccelLabel`, `ActionBar`, `Actionable`, `Alignment`, `AppChooser`, `AppChooserButton`, `AppChooserDialog`, ... `159` more

#### `is_maximized` `property+method`

Members:
- `Gtk.Window.is_maximized`
- `Gtk.Window:is-maximized`
Affected types: `18`
Examples: `AboutDialog`, `AppChooserDialog`, `ApplicationWindow`, `Assistant`, `ColorChooserDialog`, `ColorSelectionDialog`, `Dialog`, `FileChooserDialog`, ... `10` more

#### `is_pointer` `property+method`

Members:
- `Gtk.DropControllerMotion.is_pointer`
- `Gtk.DropControllerMotion:is-pointer`
Affected types: `1`
Examples: `DropControllerMotion`

#### `is_showing` `property+method`

Members:
- `Gtk.MountOperation.is_showing`
- `Gtk.MountOperation:is-showing`
Affected types: `1`
Examples: `MountOperation`

#### `is_symbolic` `property+method`

Members:
- `Gtk.IconPaintable.is_symbolic`
- `Gtk.IconPaintable:is-symbolic`
Affected types: `1`
Examples: `IconPaintable`

#### `is_virtual` `property+method`

Members:
- `Gtk.Printer.is_virtual`
- `Gtk.Printer:is-virtual`
Affected types: `1`
Examples: `Printer`

#### `prepared` `property+method`

Members:
- `Gtk.MediaStream.prepared`
- `Gtk.MediaStream:prepared`
Affected types: `2`
Examples: `MediaFile`, `MediaStream`

#### `show_all` `property+method`

Members:
- `Gtk.Widget.show_all`
- `Gtk.AppChooserWidget:show-all`
Affected types: `1`
Examples: `AppChooserWidget`

#### `draw` `property+method+signal`

Members:
- `Gtk.Widget.draw`
- `Gtk.Widget::draw`
- `Gtk.SeparatorToolItem:draw`
Affected types: `1`
Examples: `SeparatorToolItem`

#### `child_detached` `property+signal`

Members:
- `Gtk.HandleBox:child-detached`
- `Gtk.HandleBox::child-detached`
Affected types: `1`
Examples: `HandleBox`

#### `drop` `property+signal`

Members:
- `Gtk.DropTarget:drop`
- `Gtk.DropTarget::drop`
Affected types: `1`
Examples: `DropTarget`

#### `embedded` `property+signal`

Members:
- `Gtk.Plug:embedded`
- `Gtk.Plug::embedded`
Affected types: `1`
Examples: `Plug`

#### `show_connect_to_server` `property+signal`

Members:
- `Gtk.PlacesSidebar:show-connect-to-server`
- `Gtk.PlacesSidebar::show-connect-to-server`
Affected types: `1`
Examples: `PlacesSidebar`

#### `show_enter_location` `property+signal`

Members:
- `Gtk.PlacesSidebar:show-enter-location`
- `Gtk.PlacesSidebar::show-enter-location`
Affected types: `1`
Examples: `PlacesSidebar`

#### `show_hidden` `property+signal`

Members:
- `Gtk.FileChooser:show-hidden`
- `Gtk.FileChooserWidget::show-hidden`
Affected types: `1`
Examples: `FileChooserWidget`

#### `show_other_locations` `property+signal`

Members:
- `Gtk.PlacesSidebar:show-other-locations`
- `Gtk.PlacesSidebar::show-other-locations`
Affected types: `1`
Examples: `PlacesSidebar`

#### `show_starred_location` `property+signal`

Members:
- `Gtk.PlacesSidebar:show-starred-location`
- `Gtk.PlacesSidebar::show-starred-location`
Affected types: `1`
Examples: `PlacesSidebar`

### GtkSource

Conflict sets: `62`. Conflicted type attributes: `265`.

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `Gtk.Button::activate`
Affected types: `1`
Examples: `StyleSchemeChooserButton`

#### `activate` `method+signal`

Members:
- `Gtk.Widget.activate`
- `GtkSource.StyleSchemePreview::activate`
Affected types: `1`
Examples: `StyleSchemePreview`

#### `activate` `method+signal`

Members:
- `GtkSource.GutterRenderer.activate`
- `GtkSource.GutterRenderer::activate`
Affected types: `3`
Examples: `GutterRenderer`, `GutterRendererPixbuf`, `GutterRendererText`

#### `activate_default` `method+signal`

Members:
- `Gtk.Window.activate_default`
- `Gtk.Window::activate-default`
Affected types: `1`
Examples: `CompletionInfo`

#### `activate_focus` `method+signal`

Members:
- `Gtk.Window.activate_focus`
- `Gtk.Window::activate-focus`
Affected types: `1`
Examples: `CompletionInfo`

#### `add` `method+signal`

Members:
- `Gtk.Container.add`
- `Gtk.Container::add`
Affected types: `5`
Examples: `CompletionInfo`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `View`

#### `apply_tag` `method+signal`

Members:
- `Gtk.TextBuffer.apply_tag`
- `Gtk.TextBuffer::apply-tag`
Affected types: `1`
Examples: `Buffer`

#### `begin_user_action` `method+signal`

Members:
- `Gtk.TextBuffer.begin_user_action`
- `Gtk.TextBuffer::begin-user-action`
Affected types: `1`
Examples: `Buffer`

#### `can_activate_accel` `method+signal`

Members:
- `Gtk.Widget.can_activate_accel`
- `Gtk.Widget::can-activate-accel`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `can_redo_changed` `method+signal`

Members:
- `GtkSource.UndoManager.can_redo_changed`
- `GtkSource.UndoManager::can-redo-changed`
Affected types: `1`
Examples: `UndoManager`

#### `can_undo_changed` `method+signal`

Members:
- `GtkSource.UndoManager.can_undo_changed`
- `GtkSource.UndoManager::can-undo-changed`
Affected types: `1`
Examples: `UndoManager`

#### `changed` `method+signal`

Members:
- `GtkSource.CompletionProposal.changed`
- `GtkSource.CompletionProposal::changed`
Affected types: `2`
Examples: `CompletionItem`, `CompletionProposal`

#### `check_resize` `method+signal`

Members:
- `Gtk.Container.check_resize`
- `Gtk.Container::check-resize`
Affected types: `5`
Examples: `CompletionInfo`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `View`

#### `child_notify` `method+signal`

Members:
- `Gtk.Widget.child_notify`
- `Gtk.Widget::child-notify`
Affected types: `3`
Examples: `CompletionCell`, `HoverDisplay`, `StyleSchemePreview`

#### `child_notify` `method+signal`

Members:
- `Gtk.Widget.child_notify`
- `Gtk.Widget::child-notify`
- `Gtk.Container.child_notify`
Affected types: `5`
Examples: `CompletionInfo`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `View`

#### `clicked` `method+signal`

Members:
- `Gtk.Button.clicked`
- `Gtk.Button::clicked`
Affected types: `1`
Examples: `StyleSchemeChooserButton`

#### `delete_surrounding` `method+signal`

Members:
- `Gtk.IMContext.delete_surrounding`
- `Gtk.IMContext::delete-surrounding`
Affected types: `1`
Examples: `VimIMContext`

#### `destroy` `method+signal`

Members:
- `Gtk.Widget.destroy`
- `Gtk.Widget::destroy`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `drag_begin` `method+signal`

Members:
- `Gtk.Widget.drag_begin`
- `Gtk.Widget::drag-begin`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `draw` `method+signal`

Members:
- `Gtk.Widget.draw`
- `Gtk.Widget::draw`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `end_user_action` `method+signal`

Members:
- `Gtk.TextBuffer.end_user_action`
- `Gtk.TextBuffer::end-user-action`
Affected types: `1`
Examples: `Buffer`

#### `enter` `method+signal`

Members:
- `Gtk.Button.enter`
- `Gtk.Button::enter`
Affected types: `1`
Examples: `StyleSchemeChooserButton`

#### `event` `method+signal`

Members:
- `Gtk.TextTag.event`
- `Gtk.TextTag::event`
Affected types: `1`
Examples: `Tag`

#### `event` `method+signal`

Members:
- `Gtk.Widget.event`
- `Gtk.Widget::event`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `execute_command` `method+signal`

Members:
- `GtkSource.VimIMContext.execute_command`
- `GtkSource.VimIMContext::execute-command`
Affected types: `1`
Examples: `VimIMContext`

#### `grab_focus` `method+signal`

Members:
- `Gtk.Widget.grab_focus`
- `Gtk.Widget::grab-focus`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `hide` `method+signal`

Members:
- `Gtk.Widget.hide`
- `Gtk.Widget::hide`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `hide` `method+signal`

Members:
- `GtkSource.Completion.hide`
- `GtkSource.Completion::hide`
Affected types: `1`
Examples: `Completion`

#### `insert_child_anchor` `method+signal`

Members:
- `Gtk.TextBuffer.insert_child_anchor`
- `Gtk.TextBuffer::insert-child-anchor`
Affected types: `1`
Examples: `Buffer`

#### `insert_pixbuf` `method+signal`

Members:
- `Gtk.TextBuffer.insert_pixbuf`
- `Gtk.TextBuffer::insert-pixbuf`
Affected types: `1`
Examples: `Buffer`

#### `keynav_failed` `method+signal`

Members:
- `Gtk.Widget.keynav_failed`
- `Gtk.Widget::keynav-failed`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `leave` `method+signal`

Members:
- `Gtk.Button.leave`
- `Gtk.Button::leave`
Affected types: `1`
Examples: `StyleSchemeChooserButton`

#### `map` `method+signal`

Members:
- `Gtk.Widget.map`
- `Gtk.Widget::map`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `mnemonic_activate` `method+signal`

Members:
- `Gtk.Widget.mnemonic_activate`
- `Gtk.Widget::mnemonic-activate`
Affected types: `7`
Examples: `CompletionCell`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `mnemonic_activate` `method+signal`

Members:
- `Gtk.Widget.mnemonic_activate`
- `Gtk.Widget::mnemonic-activate`
- `Gtk.Window.mnemonic_activate`
Affected types: `1`
Examples: `CompletionInfo`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `45`
Examples: `Annotation`, `AnnotationProvider`, `Annotations`, `Buffer`, `Completion`, `CompletionCell`, `CompletionContext`, `CompletionInfo`, ... `37` more

#### `pressed` `method+signal`

Members:
- `Gtk.Button.pressed`
- `Gtk.Button::pressed`
Affected types: `1`
Examples: `StyleSchemeChooserButton`

#### `query_activatable` `method+signal`

Members:
- `GtkSource.GutterRenderer.query_activatable`
- `GtkSource.GutterRenderer::query-activatable`
Affected types: `3`
Examples: `GutterRenderer`, `GutterRendererPixbuf`, `GutterRendererText`

#### `query_data` `method+signal`

Members:
- `GtkSource.GutterRenderer.query_data`
- `GtkSource.GutterRenderer::query-data`
Affected types: `3`
Examples: `GutterRenderer`, `GutterRendererPixbuf`, `GutterRendererText`

#### `query_tooltip` `method+signal`

Members:
- `GtkSource.GutterRenderer.query_tooltip`
- `GtkSource.GutterRenderer::query-tooltip`
Affected types: `3`
Examples: `GutterRenderer`, `GutterRendererPixbuf`, `GutterRendererText`

#### `queue_draw` `method+signal`

Members:
- `GtkSource.GutterRenderer.queue_draw`
- `GtkSource.GutterRenderer::queue-draw`
Affected types: `3`
Examples: `GutterRenderer`, `GutterRendererPixbuf`, `GutterRendererText`

#### `realize` `method+signal`

Members:
- `Gtk.Widget.realize`
- `Gtk.Widget::realize`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `redo` `method+signal`

Members:
- `GtkSource.Buffer.redo`
- `GtkSource.Buffer::redo`
Affected types: `1`
Examples: `Buffer`

#### `released` `method+signal`

Members:
- `Gtk.Button.released`
- `Gtk.Button::released`
Affected types: `1`
Examples: `StyleSchemeChooserButton`

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
Affected types: `5`
Examples: `CompletionInfo`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `View`

#### `remove_tag` `method+signal`

Members:
- `Gtk.TextBuffer.remove_tag`
- `Gtk.TextBuffer::remove-tag`
Affected types: `1`
Examples: `Buffer`

#### `set_focus` `method+signal`

Members:
- `Gtk.Window.set_focus`
- `Gtk.Window::set-focus`
Affected types: `1`
Examples: `CompletionInfo`

#### `set_focus_child` `method+signal`

Members:
- `Gtk.Container.set_focus_child`
- `Gtk.Container::set-focus-child`
Affected types: `5`
Examples: `CompletionInfo`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `View`

#### `show` `method+signal`

Members:
- `Gtk.Widget.show`
- `Gtk.Widget::show`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `size_allocate` `method+signal`

Members:
- `Gtk.Widget.size_allocate`
- `Gtk.Widget::size-allocate`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `undo` `method+signal`

Members:
- `GtkSource.Buffer.undo`
- `GtkSource.Buffer::undo`
Affected types: `1`
Examples: `Buffer`

#### `unmap` `method+signal`

Members:
- `Gtk.Widget.unmap`
- `Gtk.Widget::unmap`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `unrealize` `method+signal`

Members:
- `Gtk.Widget.unrealize`
- `Gtk.Widget::unrealize`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `can_redo` `property+method`

Members:
- `GtkSource.Buffer.can_redo`
- `GtkSource.Buffer:can-redo`
Affected types: `1`
Examples: `Buffer`

#### `can_undo` `property+method`

Members:
- `GtkSource.Buffer.can_undo`
- `GtkSource.Buffer:can-undo`
Affected types: `1`
Examples: `Buffer`

#### `has_default` `property+method`

Members:
- `Gtk.Widget.has_default`
- `Gtk.Widget:has-default`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `has_focus` `property+method`

Members:
- `Gtk.Widget.has_focus`
- `Gtk.Widget:has-focus`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `has_toplevel_focus` `property+method`

Members:
- `Gtk.Window.has_toplevel_focus`
- `Gtk.Window:has-toplevel-focus`
Affected types: `1`
Examples: `CompletionInfo`

#### `is_active` `property+method`

Members:
- `Gtk.Window.is_active`
- `Gtk.Window:is-active`
Affected types: `1`
Examples: `CompletionInfo`

#### `is_focus` `property+method`

Members:
- `Gtk.Widget.is_focus`
- `Gtk.Widget:is-focus`
Affected types: `8`
Examples: `CompletionCell`, `CompletionInfo`, `HoverDisplay`, `Map`, `StyleSchemeChooserButton`, `StyleSchemeChooserWidget`, `StyleSchemePreview`, `View`

#### `is_maximized` `property+method`

Members:
- `Gtk.Window.is_maximized`
- `Gtk.Window:is-maximized`
Affected types: `1`
Examples: `CompletionInfo`

#### `smart_home_end` `property+signal`

Members:
- `GtkSource.View:smart-home-end`
- `GtkSource.View::smart-home-end`
Affected types: `2`
Examples: `Map`, `View`

### JavaScriptCore

Conflict sets: `1`. Conflicted type attributes: `6`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `6`
Examples: `Class`, `Context`, `Exception`, `Value`, `VirtualMachine`, `WeakValue`

### Json

Conflict sets: `1`. Conflicted type attributes: `5`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `5`
Examples: `Builder`, `Generator`, `Parser`, `Path`, `Reader`

### MediaArt

Conflict sets: `1`. Conflicted type attributes: `1`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `1`
Examples: `Process`

### Pango

Conflict sets: `4`. Conflicted type attributes: `14`.

#### `items_changed` `method+signal`

Members:
- `Gio.ListModel.items_changed`
- `Gio.ListModel::items-changed`
Affected types: `2`
Examples: `FontFamily`, `FontMap`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `10`
Examples: `Context`, `Coverage`, `Font`, `FontFace`, `FontFamily`, `FontMap`, `Fontset`, `FontsetSimple`, ... `2` more

#### `is_monospace` `property+method`

Members:
- `Pango.FontFamily.is_monospace`
- `Pango.FontFamily:is-monospace`
Affected types: `1`
Examples: `FontFamily`

#### `is_variable` `property+method`

Members:
- `Pango.FontFamily.is_variable`
- `Pango.FontFamily:is-variable`
Affected types: `1`
Examples: `FontFamily`

### PangoCairo

Conflict sets: `2`. Conflicted type attributes: `3`.

#### `items_changed` `method+signal`

Members:
- `Gio.ListModel.items_changed`
- `Gio.ListModel::items-changed`
Affected types: `1`
Examples: `FontMap`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `2`
Examples: `Font`, `FontMap`

### PangoFT2

Conflict sets: `2`. Conflicted type attributes: `2`.

#### `items_changed` `method+signal`

Members:
- `Gio.ListModel.items_changed`
- `Gio.ListModel::items-changed`
Affected types: `1`
Examples: `FontMap`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `1`
Examples: `FontMap`

### PangoFc

Conflict sets: `2`. Conflicted type attributes: `4`.

#### `items_changed` `method+signal`

Members:
- `Gio.ListModel.items_changed`
- `Gio.ListModel::items-changed`
Affected types: `1`
Examples: `FontMap`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `3`
Examples: `Decoder`, `Font`, `FontMap`

### PangoOT

Conflict sets: `1`. Conflicted type attributes: `2`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `2`
Examples: `Info`, `Ruleset`

### PangoXft

Conflict sets: `2`. Conflicted type attributes: `4`.

#### `items_changed` `method+signal`

Members:
- `Gio.ListModel.items_changed`
- `Gio.ListModel::items-changed`
Affected types: `1`
Examples: `FontMap`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `3`
Examples: `Font`, `FontMap`, `Renderer`

### Soup

Conflict sets: `4`. Conflicted type attributes: `42`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `27`
Examples: `Auth`, `AuthBasic`, `AuthDigest`, `AuthDomain`, `AuthDomainBasic`, `AuthDomainDigest`, `AuthManager`, `AuthNTLM`, ... `19` more

#### `is_authenticated` `property+method`

Members:
- `Soup.Auth.is_authenticated`
- `Soup.Auth:is-authenticated`
Affected types: `5`
Examples: `Auth`, `AuthBasic`, `AuthDigest`, `AuthNTLM`, `AuthNegotiate`

#### `is_cancelled` `property+method`

Members:
- `Soup.Auth.is_cancelled`
- `Soup.Auth:is-cancelled`
Affected types: `5`
Examples: `Auth`, `AuthBasic`, `AuthDigest`, `AuthNTLM`, `AuthNegotiate`

#### `is_for_proxy` `property+method`

Members:
- `Soup.Auth.is_for_proxy`
- `Soup.Auth:is-for-proxy`
Affected types: `5`
Examples: `Auth`, `AuthBasic`, `AuthDigest`, `AuthNTLM`, `AuthNegotiate`

### Sushi

Conflict sets: `25`. Conflicted type attributes: `44`.

#### `add` `method+signal`

Members:
- `Gtk.Container.add`
- `Gtk.Container::add`
Affected types: `1`
Examples: `MediaBin`

#### `can_activate_accel` `method+signal`

Members:
- `Gtk.Widget.can_activate_accel`
- `Gtk.Widget::can-activate-accel`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `check_resize` `method+signal`

Members:
- `Gtk.Container.check_resize`
- `Gtk.Container::check-resize`
Affected types: `1`
Examples: `MediaBin`

#### `child_notify` `method+signal`

Members:
- `Gtk.Widget.child_notify`
- `Gtk.Widget::child-notify`
Affected types: `1`
Examples: `FontWidget`

#### `child_notify` `method+signal`

Members:
- `Gtk.Widget.child_notify`
- `Gtk.Widget::child-notify`
- `Gtk.Container.child_notify`
Affected types: `1`
Examples: `MediaBin`

#### `destroy` `method+signal`

Members:
- `Gtk.Widget.destroy`
- `Gtk.Widget::destroy`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `drag_begin` `method+signal`

Members:
- `Gtk.Widget.drag_begin`
- `Gtk.Widget::drag-begin`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `draw` `method+signal`

Members:
- `Gtk.Widget.draw`
- `Gtk.Widget::draw`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `event` `method+signal`

Members:
- `Gtk.Widget.event`
- `Gtk.Widget::event`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `grab_focus` `method+signal`

Members:
- `Gtk.Widget.grab_focus`
- `Gtk.Widget::grab-focus`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `hide` `method+signal`

Members:
- `Gtk.Widget.hide`
- `Gtk.Widget::hide`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `keynav_failed` `method+signal`

Members:
- `Gtk.Widget.keynav_failed`
- `Gtk.Widget::keynav-failed`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `map` `method+signal`

Members:
- `Gtk.Widget.map`
- `Gtk.Widget::map`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `mnemonic_activate` `method+signal`

Members:
- `Gtk.Widget.mnemonic_activate`
- `Gtk.Widget::mnemonic-activate`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `realize` `method+signal`

Members:
- `Gtk.Widget.realize`
- `Gtk.Widget::realize`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `remove` `method+signal`

Members:
- `Gtk.Container.remove`
- `Gtk.Container::remove`
Affected types: `1`
Examples: `MediaBin`

#### `set_focus_child` `method+signal`

Members:
- `Gtk.Container.set_focus_child`
- `Gtk.Container::set-focus-child`
Affected types: `1`
Examples: `MediaBin`

#### `show` `method+signal`

Members:
- `Gtk.Widget.show`
- `Gtk.Widget::show`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `size_allocate` `method+signal`

Members:
- `Gtk.Widget.size_allocate`
- `Gtk.Widget::size-allocate`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `unmap` `method+signal`

Members:
- `Gtk.Widget.unmap`
- `Gtk.Widget::unmap`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `unrealize` `method+signal`

Members:
- `Gtk.Widget.unrealize`
- `Gtk.Widget::unrealize`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `has_default` `property+method`

Members:
- `Gtk.Widget.has_default`
- `Gtk.Widget:has-default`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `has_focus` `property+method`

Members:
- `Gtk.Widget.has_focus`
- `Gtk.Widget:has-focus`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

#### `is_focus` `property+method`

Members:
- `Gtk.Widget.is_focus`
- `Gtk.Widget:is-focus`
Affected types: `2`
Examples: `FontWidget`, `MediaBin`

### Tracker

Conflict sets: `1`. Conflicted type attributes: `10`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `10`
Examples: `Batch`, `Endpoint`, `EndpointDBus`, `EndpointHttp`, `NamespaceManager`, `Notifier`, `Resource`, `SparqlConnection`, ... `2` more

### Tsparql

Conflict sets: `1`. Conflicted type attributes: `10`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `10`
Examples: `Batch`, `Endpoint`, `EndpointDBus`, `EndpointHttp`, `NamespaceManager`, `Notifier`, `Resource`, `SparqlConnection`, ... `2` more

### WebKit

Conflict sets: `31`. Conflicted type attributes: `100`.

#### `attach` `method+signal`

Members:
- `WebKit.WebInspector.attach`
- `WebKit.WebInspector::attach`
Affected types: `1`
Examples: `WebInspector`

#### `can_activate_accel` `method+signal`

Members:
- `Gtk.Widget.can_activate_accel`
- `Gtk.Widget::can-activate-accel`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `child_notify` `method+signal`

Members:
- `Gtk.Widget.child_notify`
- `Gtk.Widget::child-notify`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `clicked` `method+signal`

Members:
- `WebKit.Notification.clicked`
- `WebKit.Notification::clicked`
Affected types: `1`
Examples: `Notification`

#### `close` `method+signal`

Members:
- `WebKit.OptionMenu.close`
- `WebKit.OptionMenu::close`
Affected types: `1`
Examples: `OptionMenu`

#### `destroy` `method+signal`

Members:
- `Gtk.Widget.destroy`
- `Gtk.Widget::destroy`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `detach` `method+signal`

Members:
- `WebKit.WebInspector.detach`
- `WebKit.WebInspector::detach`
Affected types: `1`
Examples: `WebInspector`

#### `drag_begin` `method+signal`

Members:
- `Gtk.Widget.drag_begin`
- `Gtk.Widget::drag-begin`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `draw` `method+signal`

Members:
- `Gtk.Widget.draw`
- `Gtk.Widget::draw`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `event` `method+signal`

Members:
- `Gtk.Widget.event`
- `Gtk.Widget::event`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `grab_focus` `method+signal`

Members:
- `Gtk.Widget.grab_focus`
- `Gtk.Widget::grab-focus`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `hide` `method+signal`

Members:
- `Gtk.Widget.hide`
- `Gtk.Widget::hide`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `initialize_notification_permissions` `method+signal`

Members:
- `WebKit.WebContext.initialize_notification_permissions`
- `WebKit.WebContext::initialize-notification-permissions`
Affected types: `1`
Examples: `WebContext`

#### `keynav_failed` `method+signal`

Members:
- `Gtk.Widget.keynav_failed`
- `Gtk.Widget::keynav-failed`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `map` `method+signal`

Members:
- `Gtk.Widget.map`
- `Gtk.Widget::map`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `mnemonic_activate` `method+signal`

Members:
- `Gtk.Widget.mnemonic_activate`
- `Gtk.Widget::mnemonic-activate`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `51`
Examples: `AuthenticationRequest`, `AutomationSession`, `BackForwardList`, `BackForwardListItem`, `ClipboardPermissionRequest`, `ColorChooserRequest`, `ContextMenu`, `ContextMenuItem`, ... `43` more

#### `realize` `method+signal`

Members:
- `Gtk.Widget.realize`
- `Gtk.Widget::realize`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `show` `method+signal`

Members:
- `Gtk.Widget.show`
- `Gtk.Widget::show`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `size_allocate` `method+signal`

Members:
- `Gtk.Widget.size_allocate`
- `Gtk.Widget::size-allocate`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `unmap` `method+signal`

Members:
- `Gtk.Widget.unmap`
- `Gtk.Widget::unmap`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `unrealize` `method+signal`

Members:
- `Gtk.Widget.unrealize`
- `Gtk.Widget::unrealize`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `has_default` `property+method`

Members:
- `Gtk.Widget.has_default`
- `Gtk.Widget:has-default`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `has_focus` `property+method`

Members:
- `Gtk.Widget.has_focus`
- `Gtk.Widget:has-focus`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `is_controlled_by_automation` `property+method`

Members:
- `WebKit.WebView.is_controlled_by_automation`
- `WebKit.WebView:is-controlled-by-automation`
Affected types: `1`
Examples: `WebView`

#### `is_ephemeral` `property+method`

Members:
- `WebKit.NetworkSession.is_ephemeral`
- `WebKit.NetworkSession:is-ephemeral`
Affected types: `1`
Examples: `NetworkSession`

#### `is_ephemeral` `property+method`

Members:
- `WebKit.WebsiteDataManager.is_ephemeral`
- `WebKit.WebsiteDataManager:is-ephemeral`
Affected types: `1`
Examples: `WebsiteDataManager`

#### `is_focus` `property+method`

Members:
- `Gtk.Widget.is_focus`
- `Gtk.Widget:is-focus`
Affected types: `2`
Examples: `WebView`, `WebViewBase`

#### `is_immersive_mode_enabled` `property+method`

Members:
- `WebKit.WebView.is_immersive_mode_enabled`
- `WebKit.WebView:is-immersive-mode-enabled`
Affected types: `1`
Examples: `WebView`

#### `is_loading` `property+method`

Members:
- `WebKit.WebView.is_loading`
- `WebKit.WebView:is-loading`
Affected types: `1`
Examples: `WebView`

#### `is_playing_audio` `property+method`

Members:
- `WebKit.WebView.is_playing_audio`
- `WebKit.WebView:is-playing-audio`
Affected types: `1`
Examples: `WebView`

### WebKitWebProcessExtension

Conflict sets: `1`. Conflicted type attributes: `13`.

#### `notify` `method+signal`

Members:
- `GObject.Object.notify`
- `GObject.Object::notify`
Affected types: `13`
Examples: `ContextMenu`, `ContextMenuItem`, `Frame`, `HitTestResult`, `ScriptWorld`, `URIRequest`, `URIResponse`, `UserMessage`, ... `5` more
