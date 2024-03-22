# pyBlufi

**NOTE**: This is a WIP. Feel free to clone and try it out but APIs may change.

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

## Install

```sh
pip install git+https://github.com/someburner/pyBlufi.git
```

## Usages

See `test.py` for example. To try connecting to Wifi, copy `creds.example.py` to `creds.py` and run `./test.py`.