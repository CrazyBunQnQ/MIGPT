import json
from miaccount import MiAccount, get_random
from miioservice import MiIOService
import miiocommand

import logging

_LOGGER = logging.getLogger(__package__)


class MiNAService:
    def __init__(self, account: MiAccount):
        self.account = account

    async def mina_request(self, uri, data=None):
        requestId = "app_ios_" + get_random(30)
        if data is not None:
            data["requestId"] = requestId
        else:
            uri += "&requestId=" + requestId
        headers = {
            "User-Agent": "MiHome/6.0.103 (com.xiaomi.mihome; build:6.0.103.1; iOS 14.4.0) Alamofire/6.0.103 MICO/iOSApp/appStore/6.0.103"
        }
        return await self.account.mi_request(
            "micoapi", "https://api2.mina.mi.com" + uri, data, headers
        )

    async def device_list(self, master=0):
        result = await self.mina_request("/admin/v2/device_list?master=" + str(master))
        return result.get("data") if result else None

    async def ubus_request(self, deviceId, method, path, message):
        message = json.dumps(message)
        result = await self.mina_request(
            "/remote/ubus",
            {"deviceId": deviceId, "message": message, "method": method, "path": path},
        )
        return result

    async def text_to_speech(self, deviceId, text):
        return await self.ubus_request(
            deviceId, "text_to_speech", "mibrain", {"text": text}
        )

    async def text_to_speech2(self, deviceDid, soundType, text):
        service = MiIOService(self.account)
        return await self.miio_command(service, deviceDid, soundType + " " + text)

    async def player_set_volume(self, deviceId, volume):
        return await self.ubus_request(
            deviceId,
            "player_set_volume",
            "mediaplayer",
            {"volume": volume, "media": "app_ios"},
        )

    async def player_pause(self, deviceId):
        return await self.ubus_request(
            deviceId,
            "player_play_operation",
            "mediaplayer",
            {"action": "pause", "media": "app_ios"},
        )

    async def player_play(self, deviceId):
        return await self.ubus_request(
            deviceId,
            "player_play_operation",
            "mediaplayer",
            {"action": "play", "media": "app_ios"},
        )

    async def player_get_status(self, deviceId):
        return await self.ubus_request(
            deviceId,
            "player_get_play_status",
            "mediaplayer",
            {"media": "app_ios"},
        )

    async def play_by_url(self, deviceId, url):
        return await self.ubus_request(
            deviceId,
            "player_play_url",
            "mediaplayer",
            {"url": url, "type": 1, "media": "app_ios"},
        )

    async def send_message(self, devices, devno, message, volume=None):  # -1/0/1...
        result = False
        for i in range(0, len(devices)):
            if (
                devno == -1
                or devno != i + 1
                or devices[i]["capabilities"].get("yunduantts")
            ):
                _LOGGER.debug(
                    "Send to devno=%d index=%d: %s", devno, i, message or volume
                )
                deviceId = devices[i]["deviceID"]
                result = (
                    True
                    if volume is None
                    else await self.player_set_volume(deviceId, volume)
                )
                if result and message:
                    result = await self.text_to_speech(deviceId, message)
                if not result:
                    _LOGGER.error("Send failed: %s", message or volume)
                if devno != -1 or not result:
                    break
        return result
    async def miio_command(self, service: MiIOService, did, text):
        cmd, arg = miiocommand.twins_split(text, ' ')
        argv = arg.split(' ') if arg else []
        argc = len(argv)
        props = []
        setp = True
        miot = True
        for item in cmd.split(','):
            key, value = miiocommand.twins_split(item, '=')
            siid, iid = miiocommand.twins_split(key, '-', '1')
            if siid.isdigit() and iid.isdigit():
                prop = [int(siid), int(iid)]
            else:
                prop = [key]
                miot = False
            if value is None:
                setp = False
            elif setp:
                prop.append(miiocommand.string_or_value(value))
            props.append(prop)

        if miot and argc > 0:
            args = [miiocommand.string_or_value(a) for a in argv] if arg != '#NA' else []
            return await service.miot_action(did, props[0], args)
        do_props = ((service.home_get_props, service.miot_get_props), (service.home_set_props, service.miot_set_props))[setp][miot]
        return await do_props(did, props)
