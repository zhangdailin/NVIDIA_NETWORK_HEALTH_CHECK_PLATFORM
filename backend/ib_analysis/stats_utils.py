import sys
import pandas as pd

from ib_analysis.utils import (
    NUMERICS
)

def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    @return: clean df without columns with illegal values or 
            if it has only a single value
    """
    null_valued_cols = list(df.isna().all()[lambda x: x])  # columns that have only null value
    if len(null_valued_cols) > 0:
        df.dropna(axis=1, inplace=True)

    # drop columns that all elements have similar values
    df = df.loc[:, df.nunique() != 1]

    # df is updated to only include rows that do not contain any NaN values.
    # This operation effectively reduces the DataFrame to only those rows that
    # are complete, with all data points present.
    df = df.dropna()

    return df

# Define a function to determine if a column should be considered categorical.
# Only if the number of unique values, are less than 10% of total 
# elements in the table.
def is_categorical(df, column, threshold=0.1):
    if f'{df[column].dtype}' in NUMERICS:
        return False
    return df[column].nunique() / len(df) < threshold


def similar_columns(original_df, column, threshold=0.8, k=3):
    df = original_df.copy()
    df = clean_columns(df)

    # Apply this to each column in the DataFrame
    categorical_columns = [col for col in df.columns if is_categorical(df, col)]

    # Proceed with one-hot encoding for identified categorical columns
    if categorical_columns:
        # Adds a new columns per unique value!
        dummies = pd.get_dummies(df[categorical_columns], prefix_sep='##')
        dummies = dummies.astype(int)
        df = pd.concat([df, dummies], axis=1)
        df.drop(categorical_columns, axis=1, inplace=True)

    # keep only the numerical columns. That includes categorical columns added above
    numeric_df = df.select_dtypes(include=NUMERICS)

    # gracefully check if the column actuall exists
    if not (column in categorical_columns or column in numeric_df.columns.tolist()):
        print(
            f"Err: couldn't find similar columns for `{column}`! " +
            "Perhaps it's not a numerical/categorical counter with multiple different values.",
            file=sys.stderr
        )
        return []

    # Compute the correlation matrix, not with the default algo
    correlation_matrix = numeric_df.corr(method='spearman')

    if column in categorical_columns:
        target_columns = [col for col in df.columns if col.startswith(f'{column}##')]
    else:
        target_columns = [column]

    found_columns = {}
    for col in target_columns:
        # Get correlations with column column
        correlations_df = correlation_matrix[col].drop(col, errors='ignore')

        # Check if all correlations are zero
        if correlations_df.abs().max() == 0:
            continue

        # Filter columns based on the threshold
        filtered_correlations = correlations_df[abs(correlations_df) > threshold]

        # Check if there are enough columns meeting the threshold
        if filtered_correlations.empty:
            # No columns meet the threshold, return empty
            continue

        # Some columns meet the threshold, return the top K
        top_correlations = filtered_correlations.abs().sort_values(ascending=False).to_dict()
        for col, cor in top_correlations.items():
            if (index:= col.find('##')) != -1: # categorical column
                col = col[:index]
            found_columns[col] = found_columns.get(col, 0) + cor

    top_items = sorted(found_columns.items(), key=lambda item: item[1], reverse=True)[:k]
    return [item for item, cof in top_items]
