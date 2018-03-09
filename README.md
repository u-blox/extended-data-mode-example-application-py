# extended-data-mode-example-application-py
Extended data mode example appliction for use with short range radio stand-alone modules.
The extended data mode is a protocol to enable control of each individual connection. Thus, it is possible to transmit data to one specific remote device and to know from what remote device the data is received.

[Extended data mode protocol specification](https://www.u-blox.com/sites/default/files/ExtendedDataMode_ProtocolSpec_%28UBX-14044126%29.pdf)
***
Start script:
```
> python edm.py <com> <central|peripheral>

Example:
> python edm.py 134 central
```
Script functionality:
- Reset the device to factory settings
- Set central or peripheral ble role
- Enter EDM mode.
- Start listening for incoming edm packets
- A menu can be opened by pressing any key (Note! While the menu is open incoming packets are buffered)
```
1) Data Command
2) AT Request
3) Resend Connect Events
4) Connect to SPS remote peer
>
```
