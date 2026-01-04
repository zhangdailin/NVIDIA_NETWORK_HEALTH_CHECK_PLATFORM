import sys
import os
import math
import hashlib
import pandas as pd
import plotext as plttext
from tabulate import tabulate
from termcolor import colored

from ib_analysis.const import MAX_WIDTH, REPLACEMENT_DICT
from ib_analysis.node import Node
from ib_analysis.const import MULTI_PLAIN_DEVICES

import re
import math
import pandas as pd
from tabulate import tabulate
# The following imports were removed because these modules do not exist in this codebase
# and are not required here. Keeping them causes ModuleNotFoundError on Windows.
# from src.ib_analysis.constants import *
# from src.ib_analysis.anomaly import *
# from src.ib_analysis.progress import *

# Add timeout mechanism
import signal
import platform
import time

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

def apply_with_timeout(df, func, axis=1, timeout_seconds=300):
    """
    Apply a function to DataFrame with timeout protection.
    
    Args:
        df: DataFrame to apply function to
        func: Function to apply
        axis: Axis to apply along (default 1 for rows)
        timeout_seconds: Maximum time to allow for operation (default 5 minutes)
    
    Returns:
        Result of the apply operation
    """
    # On Windows, SIGALRM is not available; fall back to direct apply
    if not hasattr(signal, 'SIGALRM') or platform.system().lower().startswith('win'):
        return df.apply(func, axis=axis)

    # POSIX: set up timeout handler
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)

    try:
        result = df.apply(func, axis=axis)
        signal.alarm(0)  # Cancel the alarm
        return result
    except TimeoutError:
        signal.alarm(0)  # Cancel the alarm
        raise TimeoutError(f"DataFrame apply operation timed out after {timeout_seconds} seconds")
    except Exception as e:
        signal.alarm(0)  # Cancel the alarm
        raise e

def apply_with_progress(df, func, axis=1, chunk_size=1000):
    """
    Apply a function to DataFrame with progress indication.
    
    Args:
        df: DataFrame to apply function to
        func: Function to apply
        axis: Axis to apply along (default 1 for rows)
        chunk_size: Size of chunks to process (default 1000)
    
    Returns:
        Result of the apply operation
    """
    total_rows = len(df)
    results = []
    
    print(f"Processing {total_rows} rows in chunks of {chunk_size}...")
    
    for i in range(0, total_rows, chunk_size):
        chunk = df.iloc[i:i+chunk_size]
        chunk_result = chunk.apply(func, axis=axis)
        results.append(chunk_result)
        
        # Show progress
        progress = min(100, (i + chunk_size) / total_rows * 100)
        print(f"Progress: {progress:.1f}% ({i + len(chunk)}/{total_rows})")
    
    return pd.concat(results, ignore_index=True)

NUMERICS = ["int16", "int32", "int64", "float16", "float32", "float64"]

def print_aggregate(df, col, title, sorting_col=None):
    # Compute the counts per category and keep it in a DataFrame
    counts = df[col].value_counts().reset_index()
    counts.columns = [col, 'count']

    if sorting_col:
        # Get unique values of col along with their corresponding sorting_col
        sorting_values = df[[col, sorting_col]].drop_duplicates()
        # Merge counts with sorting_values on col
        counts = counts.merge(sorting_values, on=col, how='left')
        # Sort counts based on sorting_col
        counts = counts.sort_values(by=sorting_col)
    counts['count'] = counts['count'].astype(int)

    _types = counts[col].tolist()
    _counts = counts['count'].tolist()
    plttext.simple_bar(_types, _counts, width=MAX_WIDTH, title=title)
    return plttext.build()


def print_aggregate_two(df, primary_col, secondary_col, title):
    primary_values = df[primary_col].value_counts().index.tolist()
    secondary_values = df[secondary_col].value_counts().index.tolist()

    counts_matrix = [[] for a in secondary_values]

    for primary_value in primary_values:
        counts = df[df[primary_col] == primary_value][secondary_col].value_counts().reindex(secondary_values, fill_value=0)
        for index, e in enumerate(counts.tolist()):
            counts_matrix[index].append(e)

    plttext.simple_stacked_bar(primary_values, counts_matrix, width=MAX_WIDTH, labels=secondary_values, title=title)
    return plttext.build()


def print_sum_two(df, primary_col, title, secondary_cols):
    primary_values = df[primary_col].value_counts().index.tolist()
    sum_matrix = [[] for _ in secondary_cols]

    for primary_value in primary_values:
        sum_array = [
            pd.to_numeric(
                df[df[primary_col] == primary_value][col], errors='coerce'
            ).sum() for col in secondary_cols
        ]
        for index, summ in enumerate(sum_array):
            sum_matrix[index].append(summ)

    plttext.simple_stacked_bar(
        primary_values, sum_matrix, width=MAX_WIDTH, labels=secondary_cols, title=title
    )
    return plttext.build()


def reformat_list_group_lines(names, max_length=MAX_WIDTH):
    """Group names based on the maximum length of the concatenated string."""
    grouped_names = []  # List to hold groups of names
    current_group = []  # Current group of names being processed

    for name in names:
        # Check if adding the next name exceeds the max length (considering commas and spaces)
        if sum(len(n) for n in current_group) + len(name) < max_length or len(current_group) == 0:
            current_group.append(name)
        else:
            # If the group is full, join it and start a new one
            grouped_names.append(', '.join(current_group))
            current_group = [name]  # Start new group with the current name

    # Add the last group if it's not empty
    if current_group:
        grouped_names.append(', '.join(current_group))

    return '\n'.join(grouped_names)


def add_section_with_title(title):
    print(get_section_with_title(title))


def get_section_with_title(title):
    if len(title) >= MAX_WIDTH:
        print("Title too long!", file=sys.stderr)
        return
    solid_line = int((MAX_WIDTH - len(title) - 2) / 2)
    return f"{solid_line * '─'} {title} {solid_line * '─'}"


def remove_redundant_zero(row):
    try:
        return hex(int(row['NodeGUID'], 16))
    except KeyError:
        try:
            return hex(int(row['NodeGuid'], 16))
        except KeyError:
            return "NA"


INFERRED_HEADERS = [
    'Node Name',
    'Simple Type',
    'Node Inferred Type',
    'Attached To',
    'Source',
    'Target',
    'Target Port',
    'Target GUID',
    'Target Type',
    'LID',
    'Plain',
    'Rack',
    'Target Rack'
]


def infere_node(g, row, guid_col='NodeGUID', port_col='PortNumber'):
    """
    Infers node and peer information based on GUID and port.

    Returns: A tuple containing: (node_name, node_simple_type, node_infere_type,
    peer_name, node_id, peer_id,
     target_port, peer_guid, peer_infere_type, node_lid)
    """
    guid = str(row.get(guid_col, 'NA'))
    port = str(row.get(port_col, 'NA'))

    # Initialize default values
    node_name = node_simple_type = node_infere_type = node_id = node_lid = rack = "NA"
    plain = peer_name = peer_id = target_port = peer_guid = peer_infere_type = peer_rack = "NA"

    node = g.get_node(guid)
    if node:
        node_name = node.name()
        node_simple_type = node.simple_type()
        node_infere_type = node.infere_type()
        node_id = node.id
        node_lid = node.lid
        rack = node.rack

        peer = g.get_connection(guid, port)
        if peer:
            # Safely attempt to get target_port
            try:
                port_index = int(port)
                target_port = node.children[port_index].dstport
                plain = node.children[port_index].plain
            except (ValueError, IndexError, AttributeError):
                target_port = "NA"

            peer_name = peer.name()
            peer_id = peer.id
            peer_guid = peer.guid
            peer_infere_type = peer.infere_type()
            peer_rack = peer.rack

    return (node_name, node_simple_type, node_infere_type, peer_name, node_id, peer_id,
            target_port, peer_guid, peer_infere_type, node_lid, plain, rack, peer_rack)


def _t(title, color="yellow"):
    color_code = "\033[33m"
    after_code = "\033[0m"

    if color == "yellow":
        color_code = "\033[33m"
    if color == "red":
        color_code = "\033[31m"
    if color == "green":
        color_code = "\033[32m"
    if color == "magenta":
        color_code = "\033[35m"

    return f"{color_code}{title}{after_code}"


def xmit_wait2bw_gbps(xmit_wait, duration: float, col_type="string"):
    bw = xmit_wait * 64 / duration / 10 ** 9

    if col_type.lower() == "string":
        return f"{bw:.1f}"
    return bw


def xmit_wait2bw(xmit_wait, duration: float):
    bw_wait = xmit_wait * 64 / duration / 1000
    return bit2bw(bw_wait)


def xmit_data2bw(xmit_data, duration: float):
    bw_data = xmit_data * 32 / duration / 1000
    return bit2bw(bw_data)


def hex2decimal(hex_value):
    try:
        return int(hex_value, 16)
    except TypeError:
        return hex_value


def bit2bw(bw: int):
    if bw < 10 ** 3:
        return f"{bw:.1f} Kbps"

    bw /= 10 ** 3  # Convert to Mbps
    if bw < 10 ** 3:
        return f"{bw:.1f} Mbps"

    bw /= 10 ** 3  # Convert to Gbps
    return f"{bw:.1f} Gbps"


def xmit_data2bw_gbps(xmit_data, duration: float, col_type="string"):
    bw = xmit_data * 32 / duration / 10 ** 9
    if col_type.lower() == "string":
        return f"{bw:.1f}"
    else:
        return bw


def s2n(s):
    try:
        # First, try to convert it to an integer
        return int(s)
    except ValueError:
        # If it fails, try to convert it to a float
        try:
            return float(s)
        except ValueError:
            # If it still fails, return the original string or raise an error
            return s


def extend_df(row, info, headers):
    key = (row['NodeGUID'], str(row['PortNumber']))

    if key in info and len(info[key]) > 0:
        cc_info = info[key]
        # Ensure we always return a tuple with the exact number of headers,
        # filling missing values with None
        result_tuple = tuple(cc_info.get(h) if h in cc_info else None for h in headers)
    else:
        # Return a fixed-length tuple of Nones to avoid shape mismatch on assignment
        result_tuple = tuple(None for _ in headers)

    return result_tuple


def partition_df(row, headers):
    output = []
    for header in headers:
        bin_size = header[1]
        val = s2n(row[header[0]])
        val = int(val / bin_size) * bin_size
        if val > 10**6:
            output.append(f"[{int(val/1000)}m - {int((val + bin_size) / 1000)}m]")
        elif val > 10**3:
            output.append(f"[{int(val/1000)}k - {int((val + bin_size) / 1000)}k]")
        else:
            output.append(f"[{val} - {val + bin_size}]")
        output.append(int(val)) # for sortint purposes

    result_tuple = tuple(key for key in output)
    return result_tuple


def polish_cc_header(cc_header):
    if cc_header.startswith("ZTR_CC_"):
        cc_header = cc_header[7:]
    if cc_header.endswith("_COUNTER"):
        cc_header = cc_header[:-7]
    return cc_header.replace("_", " ").strip()


def process_extended_column(columns_to_print, extend_column, df):
    """
    This method asssumes `extend_column` is either None or has an element
    """
    if not extend_column:
        extend_column = []
    elif '?' in extend_column[0]:
        query = extend_column[0][:-1]
        if '?' in query:
            return (False, "Invalid search format. Correct example: 'port?'")
        found_columns = []
        for col in df.columns.tolist():
            if col.lower().startswith(query.lower()):
                found_columns.append(col)
        if len(found_columns) == 0:
            return (False, f"Couldn't find any counter starting with '{query}'")

        #divide them into 3 columns list
        found_columns = [found_columns[i:i + 3] for i in range(0, len(found_columns), 3)]
        return (False, tabulate(found_columns, tablefmt="grid"))

    extend_column = correct_user_input(extend_column)
    return (True, columns_to_print + extend_column)


def csv_node_filename(filename, prefix="nodes_"):
    # Extract the directory part and the base file name
    dir_name = os.path.dirname(filename)
    base_name = os.path.basename(filename)

    # Prepend 'nodes_' to the base file name
    new_base_name = prefix + base_name

    # Combine the directory part and the new base file name
    new_filename = os.path.join(dir_name, new_base_name)

    return new_filename


def csv_edge_filename(filename):
    return csv_node_filename(filename=filename, prefix="edges_")


def drop_overlapping(df_a, df_b, exceptions=None):
    if not exceptions:
        exceptions = ["NodeGUID", "PortNumber"]
    # Work on a copy to avoid chained-assignment warnings, then return the copy
    df_out = df_a.copy()
    cols_to_drop = [h for h in df_out.columns.tolist() if h in df_b.columns.tolist() and h not in exceptions]
    if cols_to_drop:
        df_out.drop(cols_to_drop, axis=1, inplace=True)
    return df_out


def convert_any_to_decimal(num):
    if f'{num}'.startswith("0x"):
        return int(num, 16)
    return s2n(num)


def normalize(x):
    return math.atan(x)


def is_intera_plain_link(n1: Node, n2: Node):
    """
    In a multi-plain architecutred fabric, We observe connections/links between
    the plains in the switches. Although this connection is important and can be
    observed in xmit relation operations, it creates a mess in the topology
    visualisation. Therefore, we'd like to avoid it. Be aware, I don't have
    strong reasoning behind it, so I may change it in future as well. 
    """
    if (
        n1.type == "SW" and n2.type == "SW" and
        n1.system_guid == n2.system_guid and n1.guid != n2.guid
    ):
        # TODO: Remove the condition below. It's limiting this rule for
        # Quantom-3 switchs only. For now, I want to avoid any changes in other
        # type of networks. But ideally, this condition should be removed.
        if n1.device_id in MULTI_PLAIN_DEVICES and n2.device_id in MULTI_PLAIN_DEVICES:
            return True
    return False


def color_row(row):
    plain = row.get('Plain')
    try:
        plain = int(plain)
        colors = ['green', 'yellow', 'red', 'blue']
        color = colors[plain % 4]
        return row.apply(lambda x: colored(str(x), color))
    except (TypeError, ValueError):
        return row.apply(str)


def aggregate(df, keys,
                    exclude_numerical=None,
                    exclude_categorical=None):
    """
    Aggregate multiple entries of a dataframe into one based on the given key.
    Used for the multi-plain architecture
    
    Parameters:
    - df (pd.DataFrame): The DataFrame to process.
    - keys (list): The column name to group by.
    - exclude_numerical (list, optional): List of columns to exclude from numerical.
    - exclude_categorical (list, optional): List of columns to exclude from categorical.
    
    Returns:
    - pd.DataFrame: The aggregated DataFrame.
    """
    # Step 1: Identify numerical and categorical columns
    # Numerical columns
    numerical_cols = df.select_dtypes(include=['number']).columns.tolist()
    if exclude_numerical is not None:
        numerical_cols = [col for col in numerical_cols if col not in exclude_numerical]

    # Categorical columns
    object_cols = df.select_dtypes(include=['object']).columns.tolist()
    if exclude_categorical is not None:
        object_cols = [col for col in object_cols if col not in exclude_categorical]

    # Exclude the key column from being aggregated
    aggregation_cols = [col for col in df.columns if col not in keys]

    # Step 2: Create an aggregation dictionary
    agg_dict = {}
    for col in aggregation_cols:
        if col in numerical_cols:
            agg_dict[col] = 'sum'
        elif col in object_cols:
            agg_dict[col] = 'first'
        else:
            # Default aggregation for other columns (you can customize this)
            agg_dict[col] = 'first'

    # Step 3: Group by 'keys' and aggregate
    df_grouped = df.groupby(keys).agg(agg_dict).reset_index()

    return df_grouped


def get_md5sum(ibdir):
    """
    Calculate and return the MD5 checksum of a file.

    :param filename: Path to the file.
    :return: MD5 checksum as a hexadecimal string.
    """
    file = [f for f in os.listdir(ibdir) if str(f).endswith(".db_csv")][0]
    filename = os.path.join(ibdir, file)
    try:
        hash_md5 = hashlib.md5()
        with open(filename, "rb") as file:
            # Read the file in chunks to handle large files
            for chunk in iter(lambda: file.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except FileNotFoundError:
        return "File not found."
    except Exception as e:
        return f"An error occurred: {e}"


def values_with_not_max_length(d):
    if not d:  # handle the empty-dict case
        return []
    # Find the maximum length among all values
    max_len = max(len(v) for v in d.values())

    has_less_than_max = any(len(v) < max_len for v in d.values())

    # when all are equal, then just return all of them.
    if not has_less_than_max:
        return set(el for v in d.values() for el in v)

    # Collect keys whose value lengths are less than that maximum
    return set(el for v in d.values() if len(v) < max_len for el in v)


def rename_topo_df(edge_df):
    """
    Currenlty the nodes,edges created by the Graph class, don't follow the same 
    naming standard by other classes. Ideally, this should be fixed (TODO)
    For now, this function is used to rename those variables. 
    """
    edge_df.rename(columns={
        'Source GUID': 'NodeGUID', 
        'Source Port': 'PortNumber',
        'Source Inferred Type': 'Node Inferred Type',
        'Target Name': 'Attached To',
        'Source Name': 'Node Name'
    }, inplace=True)


def xy_scatter_plot(df, extended_columns=None):
    if not extended_columns:
        extended_columns = []

    print_table, columns = process_extended_column([], extended_columns, df)
    if not print_table:
        return[columns]

    assert len(extended_columns) > 1, "You should specify at least two columns using `-e`"

    extended_columns = correct_user_input(extended_columns)
    base_col = extended_columns[0]
    comp_cols = extended_columns[1:]

    width, height = plttext.terminal_width(), plttext.terminal_height()

    plots = []
    for col in comp_cols:
        y = df[base_col]
        x = df[col]

        plttext.plot_size(width, height - 3)
        plttext.scatter(x, y)
        plttext.title(f"{base_col} vs {col}")
        plttext.ylabel(f"{base_col}")
        plttext.xlabel(f"{col}")
        plots.append(plttext.build())
    return plots


def all_counter_replacement_keys():
    replacement_names = set()
    for _, v in REPLACEMENT_DICT.items():
        replacement_names.update(v)
    return list(replacement_names)


def correct_user_input(arr, replacements_dict=None):
    """
    Make it easy for specifying counters by using abbreviation or short versions. 
    """
    if not replacements_dict:
        replacements_dict = REPLACEMENT_DICT.copy()

    inverted_map = {}
    for key, value_set in replacements_dict.items():
        for val in value_set:
            inverted_map[val] = key

    # 2) Replace items in arr based on the inverted map
    new_arr = [inverted_map[item.lower()] if item.lower() in inverted_map else item for item in arr]
    return new_arr
