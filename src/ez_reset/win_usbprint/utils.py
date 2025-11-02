import ctypes
from collections.abc import Generator
from ctypes.wintypes import DWORD

from .winapi import (
    DIGCF_DEVICEINTERFACE,
    DIGCF_PRESENT,
    ERROR_INSUFFICIENT_BUFFER,
    ERROR_NO_MORE_ITEMS,
    GUID_DEVINTERFACE_USBPRINT,
    NULL,
    SP_DEVICE_INTERFACE_DATA,
    SP_DEVICE_INTERFACE_DETAIL_DATA,
    SP_DEVINFO_DATA,
    SetupDiDestroyDeviceInfoList,
    SetupDiEnumDeviceInterfaces,
    SetupDiGetClassDevs,
    SetupDiGetDeviceInterfaceDetail,
)


def enumerate_printers() -> Generator[str, None, None]:
    devices_handle = SetupDiGetClassDevs(
        ctypes.byref(GUID_DEVINTERFACE_USBPRINT),
        None,
        NULL,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE,
    )

    idx = 0
    while True:
        device_interface = SP_DEVICE_INTERFACE_DATA()
        device_interface.cb_size = ctypes.sizeof(device_interface)

        if not SetupDiEnumDeviceInterfaces(
            devices_handle,
            None,
            ctypes.byref(GUID_DEVINTERFACE_USBPRINT),
            idx,
            ctypes.byref(device_interface),
        ):
            if ctypes.GetLastError() != ERROR_NO_MORE_ITEMS:
                raise ctypes.WinError()

            break

        size = DWORD(0)
        # get the size
        if not SetupDiGetDeviceInterfaceDetail(
            devices_handle,
            ctypes.byref(device_interface),
            None,
            0,
            ctypes.byref(size),
            None,
        ):
            # Ignore ERROR_INSUFFICIENT_BUFFER
            if ctypes.GetLastError() != ERROR_INSUFFICIENT_BUFFER:
                raise ctypes.WinError()

        dev_info = SP_DEVINFO_DATA()
        dev_info.cb_size = ctypes.sizeof(dev_info)

        device_interface_detail = SP_DEVICE_INTERFACE_DETAIL_DATA()
        device_interface_detail.cb_size = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA)
        ctypes.resize(device_interface_detail, size.value)

        if not SetupDiGetDeviceInterfaceDetail(
            devices_handle,
            ctypes.byref(device_interface),
            ctypes.byref(device_interface_detail),
            size,
            None,
            ctypes.byref(dev_info),
        ):
            raise ctypes.WinError()

        path = str(device_interface_detail.get_string())

        yield path

        idx += 1

    SetupDiDestroyDeviceInfoList(devices_handle)
