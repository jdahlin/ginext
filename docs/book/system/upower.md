# UPower (battery & power)

> The system service for battery, AC, and power-profile state. Talk to it via DBus on the system bus.

## What this chapter covers

- What UPower exposes: devices (battery, line power, peripherals with batteries), composite "display device," power profiles (`power-saver`, `balanced`, `performance`).
- Connecting and enumerating devices via `Gio.DBusProxy`.
- Properties that matter: `Percentage`, `State`, `TimeToEmpty`, `TimeToFull`, `IconName`, `WarningLevel`.
- Subscribing to property changes and watching for AC plug/unplug.
- Power profile API: reading the current profile, requesting a hold for performance-sensitive operations (and releasing it).
- Practical patterns:
    - Pause background work when on battery and below threshold.
    - Show battery state in your app's status indicator.
    - Request `performance` only for measurable spikes; release promptly.

## What you'll be able to do

- Read battery state and react to changes.
- Be a good citizen on battery: throttle, defer, or pause work.

## Notes for the writer

- One short worked example: pause a sync task when battery drops below 20% and resume on AC.
- Note that desktop machines won't have a battery device; handle gracefully.
