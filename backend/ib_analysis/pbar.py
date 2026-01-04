from tqdm import tqdm

IBH_BAR_DISABLED = False
IBH_PBAR = {}

def pbar_r(key="key", desc="graph components...", total=4):
    if key not in IBH_PBAR:
        IBH_PBAR[key] = tqdm(desc=desc, disable=IBH_BAR_DISABLED, total=total, leave=False)
    else:
        # Update the disable state and description if they have changed
        ppbar = IBH_PBAR[key]
        if ppbar.disable != IBH_BAR_DISABLED:
            ppbar.disable = IBH_BAR_DISABLED
    return IBH_PBAR[key]

def disable_pbar():
    global IBH_BAR_DISABLED
    IBH_BAR_DISABLED = True
    for ppbar in IBH_PBAR.values():
        ppbar.disable = True

def enable_pbar():
    global IBH_BAR_DISABLED
    IBH_BAR_DISABLED = False
    for ppbar in IBH_PBAR.values():
        ppbar.disable = False

def close_pbar(key):
    pbar = IBH_PBAR[key]
    pbar.clear()
    pbar.close()
