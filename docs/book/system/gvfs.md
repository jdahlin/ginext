# GVfs (mounts and trash)

> The GIO virtual filesystem layer: SMB shares, SFTP, MTP devices, the Trash, the recent-files list. Mostly transparent through `Gio.File`; sometimes you need to drive it explicitly.

## What this chapter covers

- The model: `Gio.File` is the abstraction; GVfs is one set of implementations of it.
- Listing mounts and volumes (`Gio.VolumeMonitor`).
- Mounting a remote share programmatically (SFTP, SMB).
- Authentication during mount: `Gio.MountOperation` and the prompt UI.
- The Trash: moving files to trash via `Gio.File.trash`, listing trashed files via `trash://`.
- Recent files: `Gtk.RecentManager`, adding entries.
- URI schemes Gio handles vs ones it doesn't.
- Limits: streaming reads, seek behavior, when to copy locally for performance.

## What you'll be able to do

- Open remote files the same way you open local ones.
- Trash files correctly (not delete) when that's the user's expectation.
- Mount a remote location from your app with proper credential prompts.

## Notes for the writer

- Keep this short; readers mostly want to know "is it transparent?" and "where do I look when it isn't?"
- One example for trash, one for SFTP mount.
