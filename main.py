from subprocess import run
from enum import Enum
from sys import version_info
import yaml
import logging
import requests
import urllib3

urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

if version_info < (3, 11):
    log.warning(
        "This script was developed on Python 3.11. Functionality can't be guaranteed on earlier versions."
    )

"""Read config file"""
try:
    config = yaml.safe_load(open("config.yml"))
except FileExistsError:
    log.error("'config.yml' not found. Please create and run script again.")
    quit()


class State(Enum):
    UNKNOWN = 0
    HEALTHY = 1
    WARNING = 2
    CRITICAL = 3


class Threshold(Enum):
    OK = 0
    WARNING = config["threshold"]["warning"]
    CRITICAL = config["threshold"]["critical"]


def main() -> None:
    """The main script doing things in this order:
    1. Fetch previous state data for comparison later.
    2. Fetch new data via "pvesh" command and compare.
    3. If state changed to warning or critical, send a notification.
    4. Save current state to file and end script."""

    """Read previous state data"""
    try:
        with open(config["state_file"], "r") as file:
            virtual_machines = yaml.safe_load(file)
    except FileNotFoundError:
        virtual_machines = {}

    """Get new state data"""
    output = run(["/usr/bin/pvesh", "get", "/cluster/resources"], capture_output=True)
    output.stdout = output.stdout.decode("utf-8")

    for line in output.stdout.splitlines():
        if not line.startswith("│ "):
            continue

        """Parse column names, generate headers"""
        if line.startswith("│ id "):
            headers = [header.strip() for header in line.split("│")[1:]]

            CPU_USAGE_PERCENT = headers.index("cpu")
            DISK_MAX = headers.index("maxdisk")
            DISK_USAGE = headers.index("disk")
            NAME = headers.index("name")
            ID = headers.index("id")
            RAM_MAX = headers.index("maxmem")
            RAM_USAGE = headers.index("mem")
            continue

        if not headers:
            continue

        if not " running " in line:
            """Only process running VMs"""
            continue

        """Parse column data"""
        columns = [column.strip() for column in line.split("│")[1:]]

        id = columns[ID]
        name = columns[NAME]
        cpu_usage = int(columns[CPU_USAGE_PERCENT].split(".")[0])
        ram_usage = get_usage_percent(columns[RAM_MAX], columns[RAM_USAGE])
        disk_usage = get_usage_percent(columns[DISK_MAX], columns[DISK_USAGE])

        if not id in virtual_machines:
            virtual_machines[id] = {}

        if "cpu_usage" in virtual_machines[id]:
            """Check for CPU usage state changes"""
            previous_cpu_usage = virtual_machines[id]["cpu_usage"]
            previous_cpu_state = get_resource_state(previous_cpu_usage)
            current_cpu_state = get_resource_state(cpu_usage)

            if current_cpu_state == previous_cpu_state:
                """No action necessary if state is the same as before"""
                pass
            elif current_cpu_state.value >= State.WARNING.value:
                message = f"CPU usage ({cpu_usage}%) changed from {previous_cpu_state.name} to {current_cpu_state.name}"
                send_notification(name, message)

        if "disk_usage" in virtual_machines[id]:
            """Check for Disk usage state changes"""
            previous_disk_usage = virtual_machines[id]["disk_usage"]
            previous_disk_state = get_resource_state(previous_disk_usage)
            current_disk_state = get_resource_state(disk_usage)

            if current_disk_state == previous_disk_state:
                """No action necessary if state is the same as before"""
                pass
            elif current_disk_state.value >= State.WARNING.value:
                message = f"RAM usage ({disk_usage}%) changed from {previous_disk_state.name} to {current_disk_state.name}"
                send_notification(name, message)

        if "ram_usage" in virtual_machines[id]:
            """Check for RAM usage state changes"""
            previous_ram_usage = virtual_machines[id]["ram_usage"]
            previous_ram_state = get_resource_state(previous_ram_usage)
            current_ram_state = get_resource_state(ram_usage)

            if current_ram_state == previous_ram_state:
                """No action necessary if state is the same as before"""
                pass
            elif current_ram_state.value >= State.WARNING.value:
                message = f"RAM usage ({ram_usage}%) changed from {previous_ram_state.name} to {current_ram_state.name}"
                send_notification(name, message)

        """Update existing VM"""
        virtual_machines[id]["name"] = name
        virtual_machines[id]["cpu_usage"] = cpu_usage
        virtual_machines[id]["disk_usage"] = disk_usage
        virtual_machines[id]["ram_usage"] = ram_usage

    """Write state data to file"""
    with open(config["state_file"], "w") as file:
        file.write(yaml.dump(virtual_machines))
        log.debug(f"State written to state.yaml")


def send_notification(title: str, message: str) -> None:
    """Helper function, sending notification to NTFY"""
    headers = {"title": title}
    data = message
    response = requests.post(
        f"{config['notification_url']}",
        headers=headers,
        data=data,
    )
    if response.status_code == 200:
        log.info(f"Notification sent: '{title}: {message}'")
    else:
        log.error(f"Failed to send notification: '{title}: {message}'")


def get_resource_state(usage_value: int) -> State:
    """Input value is a percentage value based on the current resource usage, be it CPU/RAM/Disk.
    Based on this value we return the corresponding state to then be acted on."""

    if not isinstance(usage_value, int):
        try:
            usage_value = int(usage_value)
        except ValueError:
            log.debug(f"Failed to convert '{usage_value}' to integer.")
            return State.UNKNOWN

    if usage_value >= Threshold.CRITICAL.value:
        return State.CRITICAL
    if usage_value >= Threshold.WARNING.value:
        return State.WARNING
    if usage_value >= Threshold.OK.value:
        return State.HEALTHY
    else:
        return State.UNKNOWN


def get_usage_percent(max: str, used: str) -> int:
    """Return resource usage in percentages, be it RAM usage or Disk usage"""

    if used == "0.00 B":
        """VMs can't report current disk usage"""
        return "?"

    try:
        max = convert_to_mib(max)
        used = convert_to_mib(used)
    except ValueError as e:
        print(e)
        return "?"

    return int(used / max * 100)


def convert_to_mib(value: str) -> int:
    """We convert string to float and then round to nearest integer."""
    if "GiB" in value:
        value = round(float(value.split()[0]) * 1024)
    elif "MiB" in value:
        value = round(float(value.split()[0]))
    else:
        raise ValueError(f"unable to convert: {value}")
    return value


if __name__ == "__main__":
    main()
