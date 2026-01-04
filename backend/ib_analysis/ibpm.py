import os
import re
from tabulate import tabulate
import pandas as pd

from .utils import s2n
from .pbar import pbar_r, close_pbar


class IbPm:
    """
    This class is responsible for loading the ibdiagnet.pm file. The dataframe generated here
    will be merged into the Xmit and PMInfo. It's not associated with any operation. 
    """
    COLUMNS_TO_PRINT = [
        'port_local_physical_errors',
        'port_malformed_packet_errors',
        'port_buffer_overrun_errors',
        'port_dlid_mapping_errors',
        'port_vl_mapping_errors',
        'port_looping_errors',
        'port_inactive_discards',
        'port_neighbor_mtu_discards',
        'port_sw_lifetime_limit_discards',
        'port_sw_hoq_lifetime_limit_discards'
    ]

    def __init__(self, ib_dir):
        files = [f for f in os.listdir(ib_dir) if str(f).endswith(".pm")]
        try:
            file_path = os.path.join(ib_dir, files[0])
            self.df = parse_file(file_path)
        except IndexError:
            # Could not find the .pm file
            self.df = pd.DataFrame(columns=['NodeGUID', 'PortNumber'])
            return

    def table(self, num_lines=50, sort=0, extended_columns=None):
        df = self.df.copy()
        if not extended_columns:
            extended_columns = []
        columns = IbPm.COLUMNS_TO_PRINT + extended_columns

        if abs(sort) > 0:
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))

        df['Index'] = range(1, len(df) + 1)  # should be after sort
        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)
        return tabulate(df, headers='keys', tablefmt='pretty', showindex=False)

    def to_csv(self, ibpm_filename="ibpm.csv"):
        self.df.to_csv(ibpm_filename, index=False)


def parse_file(file_path):
    pattern = r'Port=(\d+).*GUID=([0-9a-fx]+)'
    pm_data = []
    current_section = {}

    with open(file_path, 'r', encoding="latin-1") as file:
        pbar = pbar_r(key="ibpm", desc="IbPm...", total=len(file.readlines()))

    with open(file_path, 'r', encoding="latin-1") as file:
        for line in file:
            pbar.update()
            line = line.strip()
            match = re.search(pattern, line)
            if match:
                port, guid = match.groups()
                if len(current_section.keys()) > 0:
                    pm_data.append(current_section)
                    current_section = {}
                current_section['NodeGUID'] = hex(int(guid, 16))
                current_section['PortNumber'] = int(port)
            else:
                if '=' in line:
                    key, value = line.split('=')
                    if value.startswith("0x"):
                        value = int(value, 16)
                    else:
                        value = s2n(value)
                    current_section[key] = value

    if len(current_section.keys()) > 0:
        pm_data.append(current_section)

    close_pbar("ibpm")    
    return pd.DataFrame(pm_data)
