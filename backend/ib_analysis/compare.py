"""
NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
property and proprietary rights in and to this material, related
documentation and any modifications thereto. Any use, reproduction,
disclosure or distribution of this material and related documentation
without an express license agreement from NVIDIA CORPORATION or
its affiliates is strictly prohibited.
"""

import pandas as pd

def compare(df_a, df_b, keys, common_columns, compare_columns):
    """
        Compares `df_a` against `df_b`
        @arg df_a, df_b: first and second dataframe

    """
    columns = keys.copy()
    adf, bdf = df_a.copy(), df_b.copy()
    df = pd.merge(adf, bdf, on=keys, how='inner', suffixes=("_A", "_B"))

    if df.shape[0] == 0:
        raise ValueError("The two ibdiganet directory have nothing in common!")

    # common columns: we consider only the df_a
    for col in common_columns:
        old_name, new_name = f"{col}", f"{col}_A"
        columns.append(old_name)

        df.rename(columns={new_name: old_name}, inplace=True)

    # Add extended columns
    for col in compare_columns:
        columns.append(f"{col}_A")
        columns.append(f"{col}_B")

    return (df, columns)
