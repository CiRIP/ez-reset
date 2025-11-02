# This file incorporates code from the following BSD-licensed project(s):
#
# * pywinusb - https://github.com/rene-aguirre/pywinusb
#
# The BSD license text can be found below:
#
# Copyright (c) 2008-2012, RENE F. AGUIRRE
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the pywinusb nor the names of its contributors may be
#    used to endorse or promote products derived from this software without
#    specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# ruff: noqa: D205, D400, D415, N801

import ctypes
import platform
from ctypes.wintypes import (
    BOOL,
    BYTE,
    DWORD,
    HANDLE,
    HWND,
    LPCWSTR,
    PWCHAR,
    ULONG,
    WCHAR,
    WORD,
)

if platform.system() != "Windows":
    msg = "This module is for Win32 systems only!"
    raise RuntimeError(msg)

HDEVINFO = ctypes.c_void_p
PCWSTR = PWCHAR
NULL = 0
ANYSIZE_ARRAY = 1
UCHAR = ctypes.c_ubyte
ENUM = ctypes.c_uint
TCHAR = WCHAR

WIN_PACK = 8 if platform.architecture()[0].startswith("64") else 1


class GUID(ctypes.Structure):
    """GUID Windows OS structure."""

    _pack_ = 1
    _fields_ = (("data1", DWORD), ("data2", WORD), ("data3", WORD), ("data4", BYTE * 8))

    def __str__(self) -> str:
        return "{{{:08x}-{:04x}-{:04x}-{}-{}}}".format(
            self.data1,
            self.data2,
            self.data3,
            "".join([f"{d:02x}" for d in self.Data4[:2]]),
            "".join([f"{d:02x}" for d in self.Data4[2:]]),
        )


class SP_DEVINFO_DATA(ctypes.Structure):
    """typedef struct _SP_DEVINFO_DATA {
      DWORD     cbSize;
      GUID      ClassGuid;
      DWORD     DevInst;
      ULONG_PTR Reserved;
    } SP_DEVINFO_DATA, *PSP_DEVINFO_DATA;
    """

    _pack_ = WIN_PACK
    _fields_ = (
        ("cb_size", DWORD),
        ("class_guid", GUID),
        ("dev_inst", DWORD),
        ("reserved", ctypes.POINTER(ULONG)),
    )

    def __str__(self) -> str:
        return f"<SP_DEVINFO_DATA ClassGuid:{self.ClassGuid} DevInst:{self.DevInst}>"


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    """typedef struct _SP_DEVICE_INTERFACE_DATA {
      DWORD     cbSize;
      GUID      InterfaceClassGuid;
      DWORD     Flags;
      ULONG_PTR Reserved;
    } SP_DEVICE_INTERFACE_DATA, *PSP_DEVICE_INTERFACE_DATA;
    """

    _pack_ = WIN_PACK
    _fields_ = (
        ("cb_size", DWORD),
        ("interface_class_guid", GUID),
        ("flags", DWORD),
        ("reserved", ctypes.POINTER(ULONG)),
    )

    def __str__(self) -> str:
        return f"<SP_DEVICE_INTERFACE_DATA InterfaceClassGuid:{self.interface_class_guid} Flags:{self.flags}>"


class SP_DEVICE_INTERFACE_DETAIL_DATA(ctypes.Structure):
    """typedef struct _SP_DEVICE_INTERFACE_DETAIL_DATA {
      DWORD cbSize;
      TCHAR DevicePath[ANYSIZE_ARRAY];
    } SP_DEVICE_INTERFACE_DETAIL_DATA, *PSP_DEVICE_INTERFACE_DETAIL_DATA;
    """

    _pack_ = WIN_PACK
    _fields_ = (
        ("cb_size", DWORD),
        ("device_path", TCHAR * ANYSIZE_ARRAY),  # device_path[1]
    )

    def get_string(self) -> str:
        """Retreive stored string."""
        return ctypes.wstring_at(ctypes.byref(self, ctypes.sizeof(DWORD)))


setup_api = ctypes.windll.setupapi

SetupDiDestroyDeviceInfoList = setup_api.SetupDiDestroyDeviceInfoList
SetupDiDestroyDeviceInfoList.restype = BOOL
SetupDiDestroyDeviceInfoList.argtypes = [
    HDEVINFO,  # __in       HDEVINFO DeviceInfoSet,
]

SetupDiGetClassDevs = setup_api.SetupDiGetClassDevsW
SetupDiGetClassDevs.restype = HANDLE
SetupDiGetClassDevs.argtypes = [
    ctypes.POINTER(GUID),  # __in_opt  const GUID *ClassGuid,
    LPCWSTR,  # __in_opt  PCTSTR Enumerator,
    HWND,  # __in_opt  HWND hwndParent,
    DWORD,  # __in      DWORD Flags
]

SetupDiEnumDeviceInterfaces = setup_api.SetupDiEnumDeviceInterfaces
SetupDiEnumDeviceInterfaces.restype = BOOL
SetupDiEnumDeviceInterfaces.argtypes = [
    HDEVINFO,  # _In_ HDEVINFO DeviceInfoSet,
    ctypes.POINTER(SP_DEVINFO_DATA),  # _In_opt_ PSP_DEVINFO_DATA DeviceInfoData,
    ctypes.POINTER(GUID),  # _In_ const GUIDi *InterfaceClassGuid,
    DWORD,  # _In_ DWORD MemberIndex,
    ctypes.POINTER(
        SP_DEVICE_INTERFACE_DATA,
    ),  # _Out_ PSP_DEVICE_INTERFACE_DATA DeviceInterfaceData
]

SetupDiGetDeviceInterfaceDetail = setup_api.SetupDiGetDeviceInterfaceDetailW
SetupDiGetDeviceInterfaceDetail.restype = BOOL
SetupDiGetDeviceInterfaceDetail.argtypes = [
    HDEVINFO,  # __in       HDEVINFO DeviceInfoSet,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),  # __in PSP_DEVICE_INTERFACE_DATA DeviceIn
    # __out_opt  PSP_DEVICE_INTERFACE_DETAIL_DATA DeviceInterfaceDetailData,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DETAIL_DATA),
    DWORD,  # __in       DWORD DeviceInterfaceDetailDataSize,
    ctypes.POINTER(DWORD),  # __out_opt  PDWORD RequiredSize,
    ctypes.POINTER(SP_DEVINFO_DATA),  # __out_opt  PSP_DEVINFO_DATA DeviceInfoData
]

SetupDiGetDeviceRegistryProperty = setup_api.SetupDiGetDeviceRegistryPropertyW
SetupDiGetDeviceRegistryProperty.restype = BOOL
SetupDiGetDeviceRegistryProperty.argtypes = [
    HDEVINFO,  # __in       HDEVINFO DeviceInfoSet,
    ctypes.POINTER(SP_DEVINFO_DATA),  # __in PSP_DEVINFO_DATA DeviceInfoData,
    DWORD,  # __in       DWORD Property,
    ctypes.POINTER(DWORD),  # __out_opt  PDWORD PropertyRegDataType,
    ctypes.POINTER(BYTE),  # __out_opt  PBYTE PropertyBuffer,
    DWORD,  # __in       DWORD PropertyBufferSize,
    ctypes.POINTER(DWORD),  # __out_opt  PDWORD RequiredSize
]

GUID_DEVINTERFACE_USBPRINT = GUID(
    0x28D78FAD,
    0x5A12,
    0x11D1,
    (BYTE * 8)(0xAE, 0x5B, 0x00, 0x00, 0xF8, 0x03, 0xA8, 0xC2),
)

DIGCF_PRESENT = 2
DIGCF_DEVICEINTERFACE = 16
INVALID_HANDLE_VALUE = 0
ERROR_INSUFFICIENT_BUFFER = 122
SPDRP_DEVICEDESC = 0
SPDRP_HARDWAREID = 1
SPDRP_FRIENDLYNAME = 12
SPDRP_LOCATION_INFORMATION = 13
ERROR_NO_MORE_ITEMS = 259

IOCTL_USBPRINT_GET_1284_ID = 2228276
IOCTL_USBPRINT_SOFT_RESET = 2228288
