#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 UFM CSV 增强功能
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
from services.ufm_csv_service import UFMCSVService

def create_test_csv():
    """创建测试 CSV 数据"""
    data = {
        'Node_GUID': ['0x001', '0x002', '0x003', '0x004', '0x005'],
        'Port_Number': [1, 2, 3, 4, 5],
        'node_description': ['Node1', 'Node2', 'Node3', 'Node4', 'Node5'],
        'host_name': ['host1', 'host2', 'host3', 'host4', 'host5'],
        'Symbol_BER': [0, 1e-7, 1e-10, 0, 1e-8],
        'Symbol_Errors': [0, 100, 10, 0, 50],
        'Total_Raw_BER': [0, 1e-6, 1e-9, 0, 1e-7],
        'Effective_BER': [0, 1e-7, 1e-10, 0, 1e-8],
        'Link_Down': [0, 0, 0, 0, 0],
        'LinkErrorRecoveryCounter': [0, 5, 0, 0, 2],
        'Temperature': [45.5, 62.3, 50.1, 48.7, 55.2],
        'Module_Temperature': [44.0, 61.0, 49.0, 47.5, 54.0],
        'Cable_PN': ['CAB001', 'CAB002', 'CAB003', 'CAB004', 'CAB005'],
        'Cable_Type': ['AOC', 'DAC', 'AOC', 'DAC', 'AOC'],
        'Cable_Length': ['10m', '3m', '10m', '5m', '10m'],
        'PortRcvErrors': [0, 10, 0, 0, 5],
        'PortXmitDiscards': [0, 20, 0, 0, 10],
        'PortRcvRemotePhysicalErrors': [0, 5, 0, 0, 2],
        'LinkIntegrityErrors': [0, 3, 0, 0, 1],
        'PortXmitData': [1000000, 2000000, 1500000, 1200000, 1800000],
        'PortRcvData': [900000, 1900000, 1400000, 1100000, 1700000],
        'PortXmitPkts': [10000, 20000, 15000, 12000, 18000],
        'PortRcvPkts': [9000, 19000, 14000, 11000, 17000],
        'PortXmitWait': [0, 1500, 500, 0, 800],
        'Status_Message': ['OK', 'OK', 'OK', 'OK', 'OK'],
    }

    return pd.DataFrame(data)

def test_health_score(service):
    """测试健康评分功能"""
    print("\n" + "="*60)
    print("测试健康评分功能")
    print("="*60)

    try:
        result = service.calculate_health_score()
        print(f"✅ 健康评分: {result['overall_score']}")
        print(f"   等级: {result['grade']}")
        print(f"   状态: {result['status']}")
        print(f"   详细评分: {result['scores']}")
        return True
    except Exception as e:
        print(f"❌ 健康评分测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_performance(service):
    """测试性能分析功能"""
    print("\n" + "="*60)
    print("测试性能分析功能")
    print("="*60)

    try:
        result = service.analyze_performance()
        print(f"✅ 性能分析完成")
        print(f"   流量统计: {len(result['traffic_stats'])} 项")
        print(f"   高带宽端口: {len(result['top_bandwidth_ports'])} 个")
        print(f"   拥塞端口: {len(result['congestion_ports'])} 个")
        if result['summary']:
            print(f"   摘要: {result['summary']}")
        return True
    except Exception as e:
        print(f"❌ 性能分析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_port_distribution(service):
    """测试端口分布功能"""
    print("\n" + "="*60)
    print("测试端口分布功能")
    print("="*60)

    try:
        result = service.analyze_port_distribution()
        print(f"✅ 端口分布分析完成")
        print(f"   速度分布: {len(result['speed_distribution'])} 项")
        print(f"   宽度分布: {len(result['width_distribution'])} 项")
        print(f"   状态分布: {len(result['state_distribution'])} 项")
        return True
    except Exception as e:
        print(f"❌ 端口分布测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_full_analysis(service):
    """测试完整分析"""
    print("\n" + "="*60)
    print("测试完整分析功能")
    print("="*60)

    try:
        result = service.get_full_analysis()
        print(f"✅ 完整分析完成")
        print(f"   包含的分析项:")
        for key in result.keys():
            print(f"     - {key}")
        return True
    except Exception as e:
        print(f"❌ 完整分析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*60)
    print("UFM CSV 增强功能测试")
    print("="*60)

    # 创建测试数据
    print("\n创建测试数据...")
    df = create_test_csv()
    print(f"✅ 测试数据创建完成: {len(df)} 行, {len(df.columns)} 列")

    # 初始化服务
    print("\n初始化 UFM CSV 服务...")
    service = UFMCSVService()
    service.df = df
    print("✅ 服务初始化完成")

    # 运行测试
    results = []
    results.append(("健康评分", test_health_score(service)))
    results.append(("性能分析", test_performance(service)))
    results.append(("端口分布", test_port_distribution(service)))
    results.append(("完整分析", test_full_analysis(service)))

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！新功能工作正常。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，需要修复。")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
