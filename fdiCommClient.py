import asyncio
import asyncua
import asyncua.ua
import logging
import argparse
import xml.etree.ElementTree as ET

_logger = logging.getLogger()

class FdiCommClient():
    def __init__(self, url):
        self.__url = url

    def start(self):
        # run the async main routine
        asyncio.run(self.amain())

    async def amain(self):
        self.__client = asyncua.Client(url=self.__url)            
        try:
            await self.__client.connect()

            nsSmartLink = await self.__client.get_namespace_index('urn://linkhost/Softing/smartLinkHW-PN')
            nsFDI7  = await self.__client.get_namespace_index('http://fdi-cooperation.com/OPCUA/FDI7/')
            objFDICommunicationServer = asyncua.Node(self.__client.uaclient, f"ns={nsSmartLink};s=FDI:CS|MS")
            objServerCommDevice = asyncua.Node(self.__client.uaclient, f"ns={nsSmartLink};s=FDI:CS|SD|CD|MS")
            objServiceProvider = asyncua.Node(self.__client.uaclient, f"ns={nsSmartLink};s=FDI:CS|SD|CD|SP|MS")

            resInitialize = await objFDICommunicationServer.call_method(f"{nsFDI7}:Initialize")
            _logger.info(f"Initialize result is: {resInitialize}")

            if resInitialize == 0:
                retScan, resScan = await objServerCommDevice.call_method(f"{nsFDI7}:Scan")
                _logger.info(f"Scan result is: {resScan}")

                if resScan == 0:
                    scanNetwork = ET.fromstring(retScan.Value)
                    for scanConnectionPoint in scanNetwork:
                        #print(scanConnectionPoint.tag, scanConnectionPoint.attrib)
                        if scanConnectionPoint.tag != 'ConnectionPoint':
                            continue

                        deviceName = scanConnectionPoint.attrib['DNSName']
                        print(f"Device name = {deviceName}")
                        for deviceIdentification in scanConnectionPoint:
                            #print(deviceIdentification.tag, deviceIdentification.attrib)
                            if deviceIdentification.tag != 'Identification':
                                continue
                            deviceId = int(deviceIdentification.attrib['DeviceID'], 16)
                            vendorId = int(deviceIdentification.attrib['VendorID'], 16)
                            print(f"Device id = 0x{deviceId:04x}")
                            print(f"Vendor id = 0x{vendorId:04x}")
                            break
                        crId = bytes('cr_' + deviceName, 'utf-8')

                        # connect to PN device
                        resConnect = await objServiceProvider.call_method(f"{nsFDI7}:Connect", 
                                                                          asyncua.ua.Variant(crId, asyncua.ua.VariantType.ByteString),
                                                                          asyncua.ua.Variant(deviceName, asyncua.ua.VariantType.String),
                                                                          asyncua.ua.Variant(deviceId, asyncua.ua.VariantType.UInt16),
                                                                          asyncua.ua.Variant(vendorId, asyncua.ua.VariantType.UInt16))
                        _logger.info(f"Connect result is: {resConnect}")
                        
                        # read I&M0 from the PN device
                        readData, readResCodes, resRead = await objServiceProvider.call_method(f"{nsFDI7}:Transfer", 
                                                                          asyncua.ua.Variant(crId, asyncua.ua.VariantType.ByteString),
                                                                          asyncua.ua.Variant('READ', asyncua.ua.VariantType.String),    # operation
                                                                          asyncua.ua.Variant(0, asyncua.ua.VariantType.UInt16),         # slot
                                                                          asyncua.ua.Variant(1, asyncua.ua.VariantType.UInt16),         # subslot
                                                                          asyncua.ua.Variant(0xAFF0, asyncua.ua.VariantType.UInt16),    # index - 0xAFF1 = I&M0
                                                                          asyncua.ua.Variant(0, asyncua.ua.VariantType.UInt32),         # api
                                                                          asyncua.ua.Variant(b'', asyncua.ua.VariantType.ByteString))   # write data
                        _logger.info(f"Read result is: {resRead}")
                        _logger.info(f"Read return codes: {readResCodes}")
                        print(f"Read data length: {len(readData)}")
                        i = 0
                        for b in readData:
                            print(f"[{i:03}] {b:02x} {chr(b)}")
                            i+=1

                        # disconnect from PN device
                        resDisconnect = await objServiceProvider.call_method(f"{nsFDI7}:Disconnect",
                                                                             asyncua.ua.Variant(crId, asyncua.ua.VariantType.ByteString))
                        _logger.info(f"Disconnect result is: {resDisconnect}")

        except (TimeoutError, asyncua.ua.UaError) as tE:
            _logger.error(f"Can't connect to FDI communication server {tE}")
        except Exception as e:
            _logger.error(f"Exception: {e}")

        if self.__client is not None:
            await self.__client.disconnect()


logging.basicConfig()
_logger = logging.getLogger()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url', required=True, help='Command to execute')
    parser.add_argument('-v', '--verbose', required=False, help='Log level (ERROR, WARING, INFO, DEBUG)')
    args = parser.parse_args()
    if args.verbose != None:
        if args.verbose == 'INFO':
            _logger.setLevel(logging.INFO)
        elif args.verbose == 'WARNING':
            _logger.setLevel(logging.WARNING)
        elif args.verbose == 'DEBUG':
            _logger.setLevel(logging.DEBUG)
        else:
            _logger.setLevel(logging.ERROR)

    client = FdiCommClient(args.url)
    client.start()