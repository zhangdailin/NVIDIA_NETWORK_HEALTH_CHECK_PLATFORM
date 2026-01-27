#!/usr/bin/env python3
"""
诊断脚本：检查 ibdiagnet 数据中的关键表
用于排查为什么 Latency、Switches 等分析结果为空
"""

import sys
from pathlib import Path
from services.ibdiagnet import read_index_table, read_table

# 定义需要检查的关键表
KEY_TABLES = {
    "PERFORMANCE_HISTOGRAM_PORTS_DATA": "Latency 分析",
    "SWITCHES": "交换机信息",
    "SYSTEM_GENERAL_INFORMATION": "系统信息",
    "AR_INFO": "自适应路由信息",
    "HBF_CONFIG": "HBF 配置",
    "PFRN_CONFIG": "PFRN 配置",
}

def check_ibdiagnet_data(db_csv_path: str):
    """检查 db_csv 文件中的各种关键表"""

    db_csv = Path(db_csv_path)

    if not db_csv.exists():
        print(f"❌ 错误: 文件不存在: {db_csv_path}")
        return

    print(f"📁 检查文件: {db_csv}")
    print("=" * 80)

    try:
        # 读取索引表
        print("\n1️⃣ 读取索引表...")
        index_table = read_index_table(db_csv)
        print(f"✅ 成功读取索引表，共 {len(index_table)} 个表")

        # 查找 Latency 相关的表
        print("\n2️⃣ 查找 Latency/Histogram 相关的表...")
        latency_tables = []
        histogram_tables = []
        performance_tables = []

        for table_name in index_table.index:
            table_name_lower = table_name.lower()
            if 'latency' in table_name_lower:
                latency_tables.append(table_name)
            if 'histogram' in table_name_lower:
                histogram_tables.append(table_name)
            if 'performance' in table_name_lower:
                performance_tables.append(table_name)

        print(f"\n📊 包含 'latency' 的表 ({len(latency_tables)} 个):")
        for table in latency_tables:
            rows = int(index_table.loc[table]['LINES'])
            print(f"  - {table} ({rows} 行)")

        print(f"\n📊 包含 'histogram' 的表 ({len(histogram_tables)} 个):")
        for table in histogram_tables:
            rows = int(index_table.loc[table]['LINES'])
            print(f"  - {table} ({rows} 行)")

        print(f"\n📊 包含 'performance' 的表 ({len(performance_tables)} 个):")
        for table in performance_tables:
            rows = int(index_table.loc[table]['LINES'])
            print(f"  - {table} ({rows} 行)")

        # 检查目标表
        target_table = "PERFORMANCE_HISTOGRAM_PORTS_DATA"
        print(f"\n3️⃣ 检查目标表: {target_table}")

        if target_table in index_table.index:
            rows = int(index_table.loc[target_table]['LINES'])
            print(f"✅ 表存在，共 {rows} 行数据")

            if rows > 0:
                print(f"\n4️⃣ 读取表数据预览...")
                df = read_table(db_csv, target_table, index_table)
                print(f"✅ 成功读取，DataFrame shape: {df.shape}")
                print(f"\n列名 ({len(df.columns)} 列):")
                for i, col in enumerate(df.columns, 1):
                    print(f"  {i}. {col}")

                if len(df) > 0:
                    print(f"\n前 3 行数据预览:")
                    print(df.head(3).to_string())
                else:
                    print("\n⚠️ 表存在但没有数据行")
            else:
                print("⚠️ 表存在但标记为 0 行")
        else:
            print(f"❌ 表不存在: {target_table}")
            print("\n💡 可能的原因:")
            print("  1. ibdiagnet 运行时未启用性能直方图采集")
            print("  2. 网络设备不支持 RTT 延迟测量")
            print("  3. ibdiagnet 版本过旧，不包含此功能")
            print("\n💡 解决方案:")
            print("  1. 运行 ibdiagnet 时添加性能采集参数")
            print("  2. 检查 ibdiagnet 版本和配置")
            print("  3. 确认网络设备支持 RTT 测量")

        # 列出所有表
        print(f"\n5️⃣ 所有可用的表 ({len(index_table)} 个):")
        for i, (table_name, row) in enumerate(index_table.iterrows(), 1):
            rows = int(row['LINES'])
            print(f"  {i:3d}. {table_name:50s} ({rows:6d} 行)")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_latency_data.py <path_to_db_csv_file>")
        print("\n示例:")
        print("  python check_latency_data.py uploads/extracted_xxx/ibdiagnet2.db_csv")
        print("\n或者自动查找最新的 db_csv 文件:")

        # 尝试自动查找
        uploads_dir = Path("uploads")
        if uploads_dir.exists():
            db_csv_files = list(uploads_dir.rglob("*.db_csv"))
            if db_csv_files:
                # 按修改时间排序，取最新的
                latest = max(db_csv_files, key=lambda p: p.stat().st_mtime)
                print(f"\n🔍 找到最新的 db_csv 文件: {latest}")
                print(f"运行: python check_latency_data.py {latest}")
                print("\n是否使用此文件? (y/n)")
                response = input().strip().lower()
                if response == 'y':
                    check_latency_data(str(latest))
            else:
                print("\n❌ 未找到任何 .db_csv 文件")
        sys.exit(1)
    else:
        check_latency_data(sys.argv[1])
