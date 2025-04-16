import asyncio
import logging
import struct
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.pdu import ModbusPDU, ExceptionResponse
from secure_utils import verify_mac

SESSION_KEY = b'supersecretkey1234'
PDU_COUNTER = 0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CustomModbusResponse(ModbusPDU):
    function_code = 55

    def __init__(self, address=0, values=None, slave=1, transaction=0, action=None):
        super().__init__(dev_id=slave, transaction_id=transaction)
        self.count = 2
        self.address = address
        self.values = values
        self.action = action

    def encode(self):
        if self.action == 'read':
            res = struct.pack(">B", len(self.values) * 2)
            for value in self.values:
                res += struct.pack(">H", value)
            return res

        elif self.action == 'write':
            # Echo back address and value
            res = struct.pack(">BHH", 0x77, self.address, self.values[0])
            return res



class CustomRequest(ModbusPDU):
    function_code = 55  # Custom function code

    def __init__(self, address=0, slave=1, transaction=0, action='read', value=None):
        super().__init__(dev_id=slave, transaction_id=transaction)
        self.address = address
        self.count = 2  # Number of registers to read/write
        self.mac = b''
        self.action = action
        self.value = value
        self.mode = 0

    def decode(self, data):
        
        self.mode, self.address, self.count, self.value = struct.unpack(">BHHH", data[:7])
        self.mac = data[7:]  # MAC

    async def update_datastore(self, context: ModbusSlaveContext):
        global PDU_COUNTER
        PDU_COUNTER += 1
       
        print(self.mode)

        if self.mode == 0x71:
            raw = struct.pack(">BHH", self.mode, self.address, self.count)

        elif self.mode == 0x77:
            raw = struct.pack(">BHHH", self.mode, self.address, self.count, self.value)

        # Log raw and mac for debugging
        logger.info(f"Server - Raw Data: {raw}")
        logger.info(f"Server - PDU Counter: {PDU_COUNTER}")
        logger.info(f"Server - Received MAC: {self.mac.hex()}")
        logger.info(f"Server - Value: {self.value}") 

        if not verify_mac(SESSION_KEY, raw, PDU_COUNTER, self.mac):
            logger.warning("Invalid MAC detected. Rejecting request.")
            return ExceptionResponse(self.function_code)

        logger.info("MAC verified. Proceeding with request.")
    
        if self.mode == 0x71:
            register_value = context.getValues(3, self.address, self.count)
            logger.info(f"Reading values from address {self.address}: {register_value}")
            return CustomModbusResponse(values=register_value, slave=self.dev_id, action='read')

        elif self.mode == 0x77 and self.value is not None:
            logger.info(f"Writing value {self.value} to register address {self.address}")
            context.setValues(3, self.address, [self.value]) 
            return CustomModbusResponse(values=[self.value], slave=self.dev_id, action='write')

        return ExceptionResponse(self.function_code)

async def print_register_value_periodically(store, address=3, interval=3):
        
     while True:
        value = store[2].getValues(3, address, count=1)[0]
        logger.info(f"[Monitor] Register value at address {address}: {value}")
        await asyncio.sleep(interval)

async def run():

    # Initialize the server context with holding registers
    store = ModbusServerContext(
        slaves=ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [17] * 100),  # Discrete Inputs
            co=ModbusSequentialDataBlock(0, [17] * 100),  # Coils
            hr=ModbusSequentialDataBlock(0, [17] * 100),  # Holding Registers (HR)
            ir=ModbusSequentialDataBlock(0, [17] * 100)   # Input Registers
    ),
    single=True
)


    identity = ModbusDeviceIdentification(
    )

    asyncio.create_task(print_register_value_periodically(store))


    await StartAsyncTcpServer(
        context=store,
        identity=identity,
        address=("localhost", 1337),
        custom_functions=[CustomRequest]
    )

if __name__ == "__main__":
    asyncio.run(run())
