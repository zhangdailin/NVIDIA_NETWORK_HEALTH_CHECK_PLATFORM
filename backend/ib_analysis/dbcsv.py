import re
import shlex
import subprocess
import os

import pandas as pd

index_table_cache = {}
def read_index_table(file_name):
    """
    reads the index table, Windows-compatible implementation using Python's re module
    """
    if file_name in index_table_cache:
        return index_table_cache[file_name]

    # Windows-compatible implementation using Python's re module
    try:
        with open(file_name, 'r', encoding='latin-1') as file:
            lines = file.readlines()
        
        output = ""
        for line_num, line in enumerate(lines, 1):
            if re.match(r'^START_|^END_', line):
                output += f"{line_num}:{line}"
        
        if not output:
            print(f"Error occurred with {file_name}: No START_ or END_ patterns found")
            return None
            
    except Exception as e:
        print(f"Error occurred with {file_name}: {str(e)}")
        return None

    parsed = re.findall(
        r"(\d*):(START|END)_([^\n]*)", output
    )
    index_table = (
        pd.DataFrame(parsed, columns=["line", "edge", "name"])
        .drop_duplicates(subset=["name", "edge"], keep="last")
        .set_index(["name", "edge"])
        .unstack(-1)["line"]
    )
    index_table.columns.name = None
    index_table = index_table[["START", "END"]].astype(float)
    index_table["LINES"] = index_table["END"] - index_table["START"] - 2
    index_table_cache[file_name] = index_table
    return index_table

def read_table(file_name, table_name, index_table):
    start, end = index_table.loc[table_name][["START", "END"]]
    # na_values = pd._libs.parsers.STR_NA_VALUES.copy()
    # na_values = na_values.remove('') #keep empty as non nan
    table = pd.read_csv(
        file_name,
        skiprows=int(start) - 1,  # header
        nrows=int(end - start) - 2,  # remove START and END
        encoding="latin-1",
        header=1,
        skipinitialspace=True,
        low_memory=False,
        quotechar="\x07",
        na_values=["N/A", "ERR"],
    )
    return table
