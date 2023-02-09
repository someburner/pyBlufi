# pyBlufi

**NOTE**: This is a WIP. Feel free to clone and try it out, but not installable
with pip yet.

Python utility to interface with esp32 Blufi component. Mimics
[EspBlufiForAndroid](https://github.com/EspressifApp/EspBlufiForAndroid)
and [EspBlufiForiOS](https://github.com/EspressifApp/EspBlufiForiOS).

## Why

Useful for testing/debugging Blufi commands without having to use a
phone. Thus making it easier to implement new features, build on top of
Blufi and not having to design apps and protocols from scratch.

## MTU

On some platforms, negotiated MTU is not accessible via API. On Linux, bluez
does not provide a way (yet?) to get negotiated MTU via dbus. For this reason,
payloads must be artificially capped using the `setPostPackageLengthLimit`
method. Using `setPostPackageLengthLimit(256)` should work in most cases. If
the client PC has a requirement for lower MTU, then this must be set lower. Or
if/when `bleak` can correctly obtain MTU for a given platform, it can be removed.

## Requirements

```sh
# bleak - develop branch
pip install https://github.com/hbldh/bleak/archive/refs/heads/develop.zip
# cryptography
pip install cryptography
```
