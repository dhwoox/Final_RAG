import grpc
import logging
import connect_pb2
import time

from example.client.client import GatewayClient
from example.master.master import MasterClient
from example.login.login import LoginSvc
from example.connectMaster.connectMaster import ConnectMasterSvc
from example.connect.connect import ConnectSvc
from example.device.device import DeviceSvc

GATEWAY_CA_FILE = 'c:/cert/gateway/ca.crt'
GATEWAY_ADDR = '192.168.43.108'
GATEWAY_PORT = 4000

MASTER_CA_FILE = 'c:/cert/master/master_ca.crt'
MASTER_ADDR = '192.168.43.108'
MASTER_PORT = 4010

TENANT_CERT_FILE = 'c:/cert/master/tenant_tenant1.crt'
TENANT_KEY_FILE = 'c:/cert/master/tenant_tenant1_key.pem'
MASTER_MODE = False

GATEWAY_ID = 'gateway1'

DEVICE_ADDR = '192.168.40.195'
DEVICE_PORT = 51211
DEVICE_USE_SSL = False

CODE_MAP_FILE = '../../event/event_code.json'

FW_FILE1 = 'c:/bs3-all_v1.1.0_20230414_sign.bin'
FW_FILE2 = 'c:/bs3-all_v1.2.1_20231113_sign.bin'

def UpgradeMain():
  client_ = None
  channel_ = None
  connectSvc_ = None
  deviceSvc_ = None
  deviceID = 0

  try:
    if MASTER_MODE:
      client_ = MasterClient(MASTER_ADDR, MASTER_PORT, MASTER_CA_FILE, TENANT_CERT_FILE, TENANT_KEY_FILE)
      channel_ = client_.getChannel()

      loginSvc = LoginSvc(channel_)
      jwtToken = loginSvc.login(TENANT_CERT_FILE)

      client_.setToken(jwtToken)
      connectSvc_ = ConnectMasterSvc(channel_)
    else:
      client_ = GatewayClient(GATEWAY_ADDR, GATEWAY_PORT, GATEWAY_CA_FILE)
      channel_ = client_.getChannel()

      connectSvc_ = ConnectSvc(channel_)
  except grpc.RpcError as e:
    print(f'Cannot connect to the gateway: {e}', flush=True)
    raise

  connInfo = connect_pb2.ConnectInfo(IPAddr=DEVICE_ADDR, port=DEVICE_PORT, useSSL=DEVICE_USE_SSL)

  try:
    if MASTER_MODE:
      deviceID = connectSvc_.connect(GATEWAY_ID, connInfo)
    else:
      deviceID = connectSvc_.connect(connInfo)
  except grpc.RpcError as e:
    print(f'Cannot connect to the device: {e}', flush=True)
    raise

  deviceSvc_ = DeviceSvc(channel_)

  try:
    t = time.localtime()
    current_time = time.strftime("%H:%M:%S", t)
    print(current_time, "Upgrading Device: ", deviceID)

    #device.firmwareUpdate(deviceID, open('bs3-all_v1.1.0_20230414_sign.bin','rb').read())
    deviceSvc_.upgradeFirmware(deviceID, open(FW_FILE1, 'rb').read())

    t = time.localtime()
    current_time = time.strftime("%H:%M:%S", t)
    print(current_time, "Upgrade Device Complete: ", deviceID)
  except grpc.RpcError as e:
    print(f'Cannot complete upgrade test for device: {e}', flush=True)
  finally:
    if MASTER_MODE:
      connectSvc_.disconnectAll(GATEWAY_ID)
    else:
      connectSvc_.disconnectAll()

    channel_.close()

if __name__ == '__main__':
    logging.basicConfig()
    UpgradeMain()
