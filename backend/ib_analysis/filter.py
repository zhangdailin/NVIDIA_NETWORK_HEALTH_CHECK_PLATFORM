import sys
import operator
from functools import reduce
import numpy as np
import pandas as pd

from ib_analysis.utils import s2n, _t, correct_user_input, all_counter_replacement_keys

FILTER_MODES = [
    'column',
    'guid',
    'smart'
]

ops = {
    '>': operator.gt,
    '>=': operator.ge,
    '=>': operator.ge,
    '<': operator.lt,
    '<=': operator.le,
    '=<': operator.le,
    '==': operator.eq,
    '=': operator.eq,
    '!=': operator.ne,
    'in': lambda x, val: x.str.contains(val, case=False, na=False, regex=False),
    '!in': lambda x, val: ~x.str.contains(val, case=False, na=False, regex=False),
}


def translate_params(index, params, duration, df):
    col, op, val = params[index:index + 3]
    col = correct_user_input([col])[0]

    if col in ["Xmit Data Gbps"]:
        val = float(val) * 10 ** 9 * duration / 32
        col = 'PortXmitDataTotal'
    elif col in ["Xmit Wait Gbps"]:
        val = float(val) * 10 ** 9 * duration / 64
        col = 'PortXmitWaitTotal'

    op_func = ops.get(op)
    if op_func is None:
        raise ValueError(f"Invalid operation: {op}")

    # Skip numeric conversion for string operations
    if op in ['in', 'notin']:
        df[col] = df[col].astype(str)
    else:
        val = s2n(val)
    return op_func(df[col], val)


def parse_and_apply_filter(counter_tbl, mode, params):
    """
    filter the data for the xmit (PM_DELTA) and pminfo tables.
    """
    df = counter_tbl.original_df.copy()

    if len(params) == 0:
        print(f"{_t('Warn', color='red')}: Removing filter.", file=sys.stderr)
        counter_tbl.df = df
        return False

    if mode == FILTER_MODES[0]:  # columns
        if len(params) % 3 != 0:
            raise ValueError(f"Invalid filtering parameters: {params}")

        conditions = []
        for i in range(0, len(params), 3):
            conditions.append(translate_params(i, params, counter_tbl.duration, df))

        # Combine all conditions
        final_condition = reduce(np.logical_and, conditions)
        counter_tbl.df = df[final_condition]

    elif mode == FILTER_MODES[1]:  # guid
        params = [p.strip() for p in params if len(p) > 3]
        mask = df['NodeGUID'].isin(params)
        counter_tbl.df = df[mask]
    elif mode == FILTER_MODES[2]:  # smart
        columns = counter_tbl.df.columns.tolist() + all_counter_replacement_keys()
        conditions = []
        skip = -1 # to jump over params when we detected mode=column
        for index, p in enumerate(params):
            if index < skip:
                continue
            if p.startswith('0x') and len(p) > 10 and len(p) < 20:
                # GUID
                op_func = ops.get('=')
                conditions.append(op_func(df['NodeGUID'], p))
            elif p in columns and len(params) > index + 2 and ops.get(params[index+1]):
                # COLUMN
                conditions.append(translate_params(index, params, counter_tbl.duration, df))
                skip = index + 3
            else:
                op_func = ops.get('in')
                conditions.append(op_func(df['Name'], p))
        final_condition = reduce(np.logical_and, conditions)
        counter_tbl.df = df[final_condition]
    else:
        raise ValueError(f"Invalid mode: {mode}")

    if len(counter_tbl.df) == 0:
        counter_tbl.df = counter_tbl.original_df.copy()
        return False
    return True


def accommodate_filter_in_graph(nodes, edges, filtering_df,
    dst_guid='Target GUID', dst_port='Target Port', src_guid='Source GUID', src_port='Source Port'
):
    """
    In case the data has been filtered by user, this function also prunes
    irrelevant nodes and edges from the graph.
    """
    if len(edges) == len(filtering_df):
        return (nodes, edges)

    xmit_active_tuple = set(
        (str(g), int(p))
        for g, p in zip(filtering_df['NodeGUID'], filtering_df['PortNumber'])
        if str(p).isdigit()
    )
    xmit_active_tuple.update(
        (str(g), int(p))
        for g, p in zip(filtering_df['Target GUID'], filtering_df['Target Port'])
        if str(p).isdigit()
    )

    mask = edges.apply(lambda row:
        ((row[dst_guid], row[dst_port]) in xmit_active_tuple) or
            ((row[src_guid], row[src_port]) in xmit_active_tuple),
        axis=1
    )
    edges = edges[mask]

    if nodes is not None:
        active_guids = set(pd.concat([edges[src_guid], edges[dst_guid]]))
        mask = nodes.apply(lambda row: (row['GUID']) in active_guids, axis=1)
        nodes = nodes[mask]

    return (nodes, edges)


def accommodate_filter_in_cable(cable_m, filtering_df):
    accommodate_filter_in_table(tbl=cable_m, filtering_df=filtering_df)


def accommodate_filter_in_ber(ber, filtering_df):
    accommodate_filter_in_table(tbl=ber, filtering_df=filtering_df)


def accommodate_filter_in_port(port, filtering_df):
    accommodate_filter_in_table(tbl=port, filtering_df=filtering_df)


def accommodate_filter_in_brief(brief, filtering_df):
    accommodate_filter_in_table(tbl=brief, filtering_df=filtering_df)


def accommodate_filter_in_histogram(histogram, filtering_df):
    accommodate_filter_in_table(tbl=histogram, filtering_df=filtering_df)


def accommodate_filter_in_hca(hca, filtering_df):
    df = hca.original_df.copy()

    xmit_active_tuple = set(filtering_df['NodeGUID'].unique())
    mask = df.apply(lambda row: row['NodeGUID'] in xmit_active_tuple, axis=1)

    hca.df = df[mask]


def accommodate_filter_in_cc(cc, filtering_df):
    df = cc.original_df.copy()

    xmit_active_tuple = set(zip(filtering_df['NodeGUID'], filtering_df['PortNumber']))

    mask = df.apply(lambda row:
                    ((row['NodeGUID'], row['PortNumber']) in xmit_active_tuple),
                    axis=1)
    cc.df = df[mask]


def accommodate_filter_in_table(tbl, filtering_df):
    df = tbl.original_df.copy()

    xmit_active_tuple = set(zip(filtering_df['NodeGUID'], filtering_df['PortNumber']))
    mask = df.apply(lambda row: (row['NodeGUID'], row['PortNumber']) in xmit_active_tuple, axis=1)
    tbl.df = df[mask]
