# BER Precision Fix Notes

日期：2026-01-09  
目录：`backend/uploads/4d523c55-aa1e-4c3d-ab57-4708e8d485f2/extracted/var/tmp/ibdiagnet2` 等最新上传

## 问题

1. 新数据集中，`PHY_DB16` 里部分端口的 mantissa 正常但 exponent 变成 10^9 量级（例：`0xfc6a1c0300c487c0`，`field15 = 1933785040`）。这些占位值会覆盖 `ibdiagnet2.net_dump_ext` 的真实 BER，导致 `Effective BER` 被错误显示为 `0.00E+00`。
2. “有效值 → 占位值”冲突在两个样本上传中共出现 65 处，全部来自 `PHY_DB16`。
3. 前端 `BERAnalysis` 已能优先显示后端字符串，因此只要后端修复即可同步生效。

## 处理

1. `backend/services/ber_service.py`：
   - `_mantissa_exponent_to_value()` 中新增 **exponent > 1000 即视为缺失**，避免将巨大的占位值转成 0。
   - 只有在 mantissa/exponent 算出真实值时才生成科学计数法字符串，否则保留 `None`，让 `combine_first()` 回落到 `net_dump_ext`。
   - 针对 `0xfc6a1c0300c487c0:21`、`0xfc6a1c0300c418c0:1` 等端口重新验证，得到与 `iba analyze ber … --format csv` 完全一致的 `9.00E-05 / 4.00E-12 / 1.50E-254`。
2. 扫描 `backend/uploads/*/PHY_DB16`，确认所有 exponent 异常的行都被过滤，`analysis.data` 与 `ber.csv` 数字一致，共 30,463 条记录。

## 验证步骤

```powershell
python - <<'PY'
from pathlib import Path
from backend.services.ber_service import BerService
root = Path(r"backend/uploads/4d523c55-aa1e-4c3d-ab57-4708e8d485f2/extracted/var/tmp/ibdiagnet2")
service = BerService(root)
analysis = service.run()
rows = [row for row in analysis.data if row["NodeGUID"]=="0xfc6a1c0300c487c0" and row["PortNumber"]==21]
print(rows[0]["Raw BER"], rows[0]["Effective BER"], rows[0]["Symbol BER"])
PY
```

输出应为：`9.000000e-05 4.000000e-12 1.500000e-254`。

## 注意事项

- 如果后续数据集中 exponent 占位值阈值需要调整，可修改 `_mantissa_exponent_to_value()` 中的 `1000`，或在读取 PHY 表前过滤异常值。
- 目前 `ber_data` 与 `ber_advanced_data` 都会显示这些端口，前端默认“只看异常”模式即可看到所有 `warning/critical`。
