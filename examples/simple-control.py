import argparse
import math
import sys
import numpy as np
import time
import zmq


context = zmq.Context()

iq_socket = context.socket(zmq.PUB)

iq_socket.bind(f"tcp://*:{50001}")

# Simple ANSI coloring for logs
USE_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


class ACRO:
    def __init__(self, COMport):
        try:
            import serial  # local import so plotting mode works without pyserial
        except ImportError as exc:
            raise ImportError("pyserial is required when not using --plot") from exc
        # Establish serial connection
        self.ser = serial.Serial(
            COMport, baudrate=115200, timeout=1
        )  # Replace with the appropriate serial port

        # Hard stop any prior motion and clear buffer
        self.reset_controller()

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
            # print(response)

            if "Idle" in response:
                break

    def home_ACRO(self):
        # Send the query command
        self.ser.write(b"G54\n")
        self.ser.write(b"?\n")

        self.wait_till_idle()

        # Read and decode the response
        response = self.ser.readline().decode().strip()
        # print("Controller response:", response)

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

    def move_ACRO(self, x, y, wait_idle=True, speed=50):
        command = f"G0 X{x:.3f} Y{y:.3f} F{int(speed)}\n"  # Command to move to specific location (F = mm/min)
        self.ser.write(command.encode())  # Send command to move to a specific position
        if wait_idle:
            self.wait_till_idle()  # Wait until controller reports idle state

    def move_ACRO_to_origin(self):
        command = f"G0 X0 Y0\n"  # Command to move to specific location
        self.ser.write(command.encode())
        self.wait_till_idle()  # Wait until controller reports idle state

    def close_ACRO(self):
        self.ser.close()

    def reset_controller(self):
        """Send GRBL soft reset to halt any prior buffered motion."""
        try:
            self.ser.write(b"\x18")  # Ctrl+X
            time.sleep(0.5)
            self.ser.flushInput()
        except Exception:
            pass


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


def compute_spacing_for_sweep(start_spacing: float, min_spacing: float, decay: float, target_sweep: int) -> float:
    """Compute the spacing that would be in effect at a given sweep number."""
    spacing = start_spacing
    for s in range(1, target_sweep):
        if s > 1 and s % 2 == 1:
            spacing = max(min_spacing, spacing * decay)
    return spacing


def generate_sweep_points(
    sweeps: int,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    start_sweep: int = 1,
    start_spacing: float = 120.0,
    decay: float = 0.75,
    min_spacing: float = 20.0,
) -> list[tuple[int, list[tuple[float, float]]]]:
    """Replicate the sweep path without driving hardware."""
    all_sweeps: list[tuple[int, list[tuple[float, float]]]] = []
    spacing = compute_spacing_for_sweep(start_spacing, min_spacing, decay, start_sweep)
    center = ((x_min + x_max) / 2, (y_min + y_max) / 2)
    sweep_number = start_sweep
    for _ in range(sweeps):
        if sweep_number > 1 and sweep_number % 2 == 1 and sweep_number != start_sweep:
            spacing = max(min_spacing, spacing * decay)

        x_offset = (spacing / 2) if sweep_number % 2 == 0 else 0
        y_offset = (spacing / 2) if sweep_number % 3 == 0 else 0

        x_lines = np.arange(x_min + x_offset, x_max, spacing)
        y_lines = np.arange(y_min + y_offset, y_max, spacing)

        if len(x_lines) == 0 or len(y_lines) == 0:
            x_lines = np.arange(x_min, x_max, spacing)
            y_lines = np.arange(y_min, y_max, spacing)

        pts: list[tuple[float, float]] = [center]
        if sweep_number % 2 == 0:
            for idx, x_val in enumerate(x_lines):
                if idx % 2 == 0:
                    pts.append((x_val, y_min))
                    pts.append((x_val, y_max))
                else:
                    pts.append((x_val, y_max))
                    pts.append((x_val, y_min))
        else:
            for idx, y_val in enumerate(y_lines):
                if idx % 2 == 0:
                    pts.append((x_min, y_val))
                    pts.append((x_max, y_val))
                else:
                    pts.append((x_max, y_val))
                    pts.append((x_min, y_val))

        all_sweeps.append((sweep_number, pts))
        sweep_number += 1
    return all_sweeps


def plot_sweeps(
    sweeps: list[tuple[int, list[tuple[float, float]]]],
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> None:
    """Scatter and connect each sweep; include a combined view."""
    import matplotlib.pyplot as plt

    total_plots = len(sweeps) + 1
    cols = 5
    rows = math.ceil(total_plots / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
    axes = axes.flatten()

    def draw_envelope(ax):
        ax.plot(
            [x_min, x_max, x_max, x_min, x_min],
            [y_min, y_min, y_max, y_max, y_min],
            color="gray",
            linestyle="--",
            linewidth=1,
        )

    for idx, (ax, sweep_entry) in enumerate(zip(axes, sweeps), start=1):
        sweep_number, pts = sweep_entry
        ax.set_title(f"Sweep {sweep_number}")
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        draw_envelope(ax)
        if len(pts) > 1:
            xs, ys = zip(*pts)
            color = plt.cm.plasma((sweep_number - sweeps[0][0]) / max(len(sweeps), 1))
            ax.plot(xs, ys, linewidth=1.2, color=color, alpha=0.8)
            ax.scatter(xs, ys, c=[color], s=10, alpha=0.8, zorder=3)
            ax.scatter(xs[0], ys[0], c="lime", edgecolor="black", s=36, zorder=4, label="start")
            ax.scatter(xs[-1], ys[-1], c="orange", edgecolor="black", s=32, zorder=4, label="end")
        ax.legend(loc="upper right", fontsize="x-small", framealpha=0.7)

    combined_ax_index = len(sweeps)
    if combined_ax_index < len(axes):
        ax = axes[combined_ax_index]
        ax.set_title("All sweeps")
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        draw_envelope(ax)
        for idx, sweep_entry in enumerate(sweeps):
            sweep_number, pts = sweep_entry
            if len(pts) < 2:
                continue
            xs, ys = zip(*pts)
            color = plt.cm.plasma(idx / max(len(sweeps) - 1, 1))
            ax.plot(xs, ys, linewidth=1.1, color=color, alpha=0.85, label=f"Sweep {sweep_number}")
            ax.scatter(xs, ys, c=[color], s=10, alpha=0.75, edgecolor="none")
        if len(sweeps) > 0 and len(sweeps[0][1]) > 0:
            ax.scatter(
                sweeps[0][1][0][0],
                sweeps[0][1][0][1],
                c="lime",
                edgecolor="black",
                s=28,
                zorder=3,
                label="start (sweep 1)",
            )
        ax.legend(loc="upper right", fontsize="x-small", framealpha=0.7)

    for ax in axes[total_plots:]:
        ax.axis("off")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple XY sweep with increasing density.")
    parser.add_argument("--min", dest="min_xy", type=float, default=None, help="Set both x-min and y-min.")
    parser.add_argument("--max", dest="max_xy", type=float, default=None, help="Set both x-max and y-max.")
    parser.add_argument("--x-min", type=float, default=None, help="Minimum X coordinate (overrides --min).")
    parser.add_argument("--x-max", type=float, default=None, help="Maximum X coordinate (overrides --max).")
    parser.add_argument("--y-min", type=float, default=None, help="Minimum Y coordinate (overrides --min).")
    parser.add_argument("--y-max", type=float, default=None, help="Maximum Y coordinate (overrides --max).")
    parser.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial port for ACRO.")
    parser.add_argument("--speed", type=int, default=50, help="Motion speed (mm/min, sets G-code F).")
    parser.add_argument("--plot", action="store_true", help="Plot the path instead of driving hardware.")
    parser.add_argument("--sweeps", type=int, default=10, help="Number of sweeps to plot (if --plot).")
    parser.add_argument("--start-sweep", type=int, default=1, help="Sweep number to start from (skip earlier sweeps).")
    parser.add_argument("--skip-waiting", action="store_true", help="Do not move to center before sweeping.")
    args = parser.parse_args()

    default_min, default_max = 10.0, 1240.0
    base_min = args.min_xy if args.min_xy is not None else default_min
    base_max = args.max_xy if args.max_xy is not None else default_max

    x_min = args.x_min if args.x_min is not None else base_min
    x_max = args.x_max if args.x_max is not None else base_max
    y_min = args.y_min if args.y_min is not None else base_min
    y_max = args.y_max if args.y_max is not None else base_max

    if x_max <= x_min or y_max <= y_min:
        raise ValueError("x-max must be greater than x-min and y-max greater than y-min.")
    if args.start_sweep < 1:
        raise ValueError("start-sweep must be >= 1.")

    print(_c("Run config:", "96"))
    for key, val in [
        ("x_min", x_min),
        ("x_max", x_max),
        ("y_min", y_min),
        ("y_max", y_max),
        ("port", args.port),
        ("speed", f"{args.speed} mm/min"),
        ("plot", args.plot),
        ("sweeps", args.sweeps),
        ("start_sweep", args.start_sweep),
        ("skip_waiting", args.skip_waiting),
    ]:
        print(f"  {_c(key, '93')}: {val}")

    if args.plot:
        sweeps = generate_sweep_points(
            sweeps=args.sweeps,
            x_min=x_min,
            x_max=x_max,
            y_min=y_min,
            y_max=y_max,
            start_sweep=args.start_sweep,
        )
        plot_sweeps(sweeps, x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)
        raise SystemExit(0)

    ACRO = ACRO(COMport=args.port)
    ACRO.home_ACRO()

    # x = [10,1250] # np.arange(0, 1250, 300/5) + 10  # np.arange(25, 1200, 300/100) + 25
    # y = np.arange(0, 1250, 300/10) + 10

    # xx, yy = np.meshgrid(x, y)
    # xx[1::2] = xx[
    #     1::2, ::-1
    # ]  # flip the coordinates of x every other y to create a zig zag
    # xx, yy = xx.ravel(), yy.ravel()

    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2

    if not args.skip_waiting:
        ACRO.move_ACRO(center_x, center_y, wait_idle=True, speed=args.speed)
        # wait_till_go_from_server()
        # time.sleep(80) # be sure that calibration is done
        wait_till_pressed()

    # Simple sweep that increases density every other pass and alternates row/column snakes.
    spacing = compute_spacing_for_sweep(120.0, 20.0, 0.75, args.start_sweep)
    min_spacing = 20.0
    decay = 0.75
    sweep = args.start_sweep

    try:
        while True:
            sweep += 1
            # Adjust spacing after every 2nd sweep
            if sweep > 1 and sweep % 2 == 1 and sweep != args.start_sweep:
                spacing = max(min_spacing, spacing * decay)

            # Offset to avoid retracing the same paths
            x_offset = (spacing / 2) if sweep % 2 == 0 else 0
            y_offset = (spacing / 2) if sweep % 3 == 0 else 0

            # Generate line positions; we only travel between min and max per line.
            x_lines = np.arange(x_min + x_offset, x_max, spacing)
            y_lines = np.arange(y_min + y_offset, y_max, spacing)

            if len(x_lines) == 0 or len(y_lines) == 0:
                x_lines = np.arange(x_min, x_max, spacing)
                y_lines = np.arange(y_min, y_max, spacing)

            mode = "column" if sweep % 2 == 0 else "row"
            print(
                f"{_c('[sweep]', '95')} {sweep} "
                f"{_c('mode', '94')}={mode} "
                f"{_c('x', '92')}[{x_min + x_offset:.1f}->{x_max:.1f}] "
                f"{_c('y', '92')}[{y_min + y_offset:.1f}->{y_max:.1f}] "
                f"{_c('spacing', '93')}={spacing:.2f} "
                f"{_c('speed', '96')}={args.speed} mm/min"
            )

            if not args.skip_waiting:
                ACRO.move_ACRO(center_x, center_y, wait_idle=True, speed=args.speed)

            if sweep % 2 == 0:
                # Column sweep: move along Y for each X
                for idx, x_val in enumerate(x_lines):
                    if idx % 2 == 0:
                        # bottom -> top
                        ACRO.move_ACRO(x_val, y_min, wait_idle=False, speed=args.speed)
                        ACRO.move_ACRO(x_val, y_max, wait_idle=False, speed=args.speed)
                    else:
                        # top -> bottom
                        ACRO.move_ACRO(x_val, y_max, wait_idle=False, speed=args.speed)
                        ACRO.move_ACRO(x_val, y_min, wait_idle=False, speed=args.speed)
            else:
                # Row sweep: move along X for each Y
                for idx, y_val in enumerate(y_lines):
                    if idx % 2 == 0:
                        # left -> right
                        ACRO.move_ACRO(x_min, y_val, wait_idle=False, speed=args.speed)
                        ACRO.move_ACRO(x_max, y_val, wait_idle=False, speed=args.speed)
                    else:
                        # right -> left
                        ACRO.move_ACRO(x_max, y_val, wait_idle=False, speed=args.speed)
                        ACRO.move_ACRO(x_min, y_val, wait_idle=False, speed=args.speed)

            # Ensure the controller finishes the sweep before the next one
            ACRO.wait_till_idle()
    except KeyboardInterrupt:
        print(_c("Interrupted; sending controller reset.", "91"))
        ACRO.reset_controller()
        ACRO.wait_till_idle()
    finally:
        try:
            if not args.skip_waiting:
                ACRO.move_ACRO_to_origin()
        except Exception:
            pass
        try:
            ACRO.close_ACRO()
        except Exception:
            pass

    print("Done")
