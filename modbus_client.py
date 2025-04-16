import asyncio
import struct
import logging
from pymodbus.client import AsyncModbusTcpClient as ModbusClient
from pymodbus.pdu import ModbusPDU
from pymodbus.exceptions import ModbusIOException
from secure_utils import generate_mac

SESSION_KEY = b'supersecretkey1234'
PDU_COUNTER = 0
# Set up logger for debugging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure the logging level is set to DEBUG or INFO
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)  # Ensure the console handler captures debug messages
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class CustomRequest(ModbusPDU):
    function_code = 55

    def __init__(self, address=0, slave=1, transaction=0, action='read', value=None):
        super().__init__(dev_id=slave, transaction_id=transaction)
        self.address = address
        self.count = 2
        self.mac = b''
        self.action = action
        self.value = value

    def encode(self):
        global PDU_COUNTER
        PDU_COUNTER += 1

        if self.action == 'read':
            raw = struct.pack(">BHH", 0x72, self.address, self.count)
            mac = generate_mac(SESSION_KEY, raw, PDU_COUNTER)

        elif self.action == 'write':
            raw = struct.pack(">BHHH", 0x77, self.address, self.count, self.value)
            mac = generate_mac(SESSION_KEY, raw, PDU_COUNTER)
    
        # Log raw and mac for debugging
        logger.info(f"Client - Raw Data: {raw}")
        logger.info(f"Client - PDU Counter: {PDU_COUNTER}")
        logger.info(f"Client - Generated MAC: {mac.hex()}")
        logger.info(f"Client - Action: {self.action}")

        if self.action == 'read':
            return raw + mac
        elif self.action == 'write' and self.value is not None:
            return raw + mac
        else:
            raise ValueError("Invalid action or missing value for write.")

    def decode(self, data):
        print("Hello")
        self.address, self.count = struct.unpack(">HH", data[:4])
        self.mac = data[4:]
        if self.action == 'write':
            self.value = struct.unpack(">H", data[4:6])[0]

async def run_client():
    async with ModbusClient("localhost", port=5020) as client:
        await client.connect()
        client.register(CustomRequest)

        try:
            while True:
                # Create a write request to write the value 1337 to register address 3
                write_request = CustomRequest(address=3, action='write', value=50, slave=1)
                try:
                    result = await client.execute(False, write_request)
                    print(f"Write Request Result: {result}")
                except ModbusIOException:
                    print("Server does not support CustomRequest.")
                except Exception as e:
                    print(f"Unexpected error: {e}")
                await asyncio.sleep(5)  # Repeat the write operation every 5 seconds
        except asyncio.CancelledError:
            print("Client loop cancelled.")

if __name__ == "__main__":
    asyncio.run(run_client())

