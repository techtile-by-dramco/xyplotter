import argparse
import numpy as np
import serial
import time
import zmq


context = zmq.Context()

iq_socket = context.socket(zmq.PUB)

iq_socket.bind(f"tcp://*:{50001}")


class ACRO:
    def __init__(self, COMport):
        # Establish serial connection
        self.ser = serial.Serial(
            COMport, baudrate=115200, timeout=1
        )  # Replace with the appropriate serial port

        # Wake up grbl
        self.ser.write(b"\r\n\r\n")
        time.sleep(2)  # Wait for grbl to initialize
        self.ser.flushInput()  # Flush startup text in serial input

    def wait_till_idle(self):
        response = ""
        while True:
            time.sleep(0.1)

            self.ser.flushInput()
            self.ser.write(b"?\n")
            response = self.ser.readline().decode().strip()
            print(response)

            if "Idle" in response:
                break

    def home_ACRO(self):
        # Send the query command
        self.ser.write(b"G54\n")
        self.ser.write(b"?\n")

        self.wait_till_idle()

        # Read and decode the response
        response = self.ser.readline().decode().strip()
        print("Controller response:", response)

        # Send homing command
        command = f"$H\n"  # Command to start homing
        self.ser.write(command.encode())
        self.wait_till_idle()  # Wait until controller reports idle state

        self.ser.write("G10 P0 L20 X0 Y0 Z0\n".encode())
        self.wait_till_idle()

        self.ser.write(b"G54\n")
        self.ser.write(b"?\n")

        self.wait_till_idle()

        print("Machine is homed")

    def move_ACRO(self, x, y, wait_idle=True):
        command = f"G0 X{x} Y{y} F50\n"  # Command to move to specific location
        self.ser.write(command.encode())  # Send command to move to a specific position
        if wait_idle:
            self.wait_till_idle()  # Wait until controller reports idle state

    def move_ACRO_to_origin(self):
        command = f"G0 X0 Y0\n"  # Command to move to specific location
        self.ser.write(command.encode())
        self.wait_till_idle()  # Wait until controller reports idle state

    def close_ACRO(self):
        self.ser.close()


def wait_till_pressed():
    input("Press any key and then Enter to continue...")


def wait_till_go_from_server():

    SERVER_IP = "192.108.0.1"

    global meas_id, file_open, data_file, file_name
    # Connect to the publisher's address
    print("Connecting to server %s.", SERVER_IP)
    sync_socket = context.socket(zmq.SUB)

    alive_socket = context.socket(zmq.REQ)

    sync_socket.connect(f"tcp://{SERVER_IP}:{5557}")
    alive_socket.connect(f"tcp://{SERVER_IP}:{5558}")
    # Subscribe to topics
    sync_socket.subscribe("")

    print("Sending ALIVE")
    alive_socket.send_string("ROVER")
    # Receives a string format message
    print("Waiting on SYNC from server %s.", SERVER_IP)

    meas_id, unique_id = sync_socket.recv_string().split(" ")

    print(meas_id)

    alive_socket.close()
    sync_socket.close()



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple XY sweep with increasing density.")
    parser.add_argument("--x-min", type=float, default=10.0, help="Minimum X coordinate.")
    parser.add_argument("--x-max", type=float, default=1240.0, help="Maximum X coordinate.")
    parser.add_argument("--y-min", type=float, default=10.0, help="Minimum Y coordinate.")
    parser.add_argument("--y-max", type=float, default=1240.0, help="Maximum Y coordinate.")
    parser.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial port for ACRO.")
    args = parser.parse_args()

    if args.x_max <= args.x_min or args.y_max <= args.y_min:
        raise ValueError("x-max must be greater than x-min and y-max greater than y-min.")

    ACRO = ACRO(COMport=args.port)
    ACRO.home_ACRO()

    # x = [10,1250] # np.arange(0, 1250, 300/5) + 10  # np.arange(25, 1200, 300/100) + 25
    # y = np.arange(0, 1250, 300/10) + 10

    # xx, yy = np.meshgrid(x, y)
    # xx[1::2] = xx[
    #     1::2, ::-1
    # ]  # flip the coordinates of x every other y to create a zig zag
    # xx, yy = xx.ravel(), yy.ravel()

    center_x = (args.x_min + args.x_max) / 2
    center_y = (args.y_min + args.y_max) / 2

    ACRO.move_ACRO(center_x, center_y, wait_idle=True)
    # wait_till_go_from_server()
    # time.sleep(80) # be sure that calibration is done
    wait_till_pressed()

    # Simple sweep that increases density every other pass and alternates row/column snakes.
    spacing = 120.0  # start coarse
    min_spacing = 20.0
    decay = 0.75  # smaller every 2nd sweep
    sweep = 0

    while True:
        sweep += 1
        # Adjust spacing after every 2nd sweep
        if sweep > 1 and sweep % 2 == 1:
            spacing = max(min_spacing, spacing * decay)

        # Offset to avoid retracing the same paths
        x_offset = (spacing / 2) if sweep % 2 == 0 else 0
        y_offset = (spacing / 2) if sweep % 3 == 0 else 0

        x = np.arange(args.x_min + x_offset, args.x_max, spacing)
        y = np.arange(args.y_min + y_offset, args.y_max, spacing)

        if len(x) == 0 or len(y) == 0:
            x = np.arange(args.x_min, args.x_max, spacing)
            y = np.arange(args.y_min, args.y_max, spacing)

        xx, yy = np.meshgrid(x, y)
        # Serpentine; flip direction each sweep
        xx[1::2] = xx[1::2, ::-1]
        if sweep % 2 == 0:
            # Swap x and y to traverse columns instead of rows
            xx, yy = yy, xx

        xx, yy = xx.ravel(), yy.ravel()
        ACRO.move_ACRO(650, 650, wait_idle=True)
        for x, y in zip(xx, yy):
            ACRO.move_ACRO(x, y, wait_idle=True)
            time.sleep(0.1)
    # Return to origin
    ACRO.move_ACRO_to_origin()

    print("Done")
