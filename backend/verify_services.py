#!/usr/bin/env python3
"""
Data Verification Script for NVIDIA Network Health Check Platform
Verifies all analysis services against actual upload data
"""

import sys
import os
from pathlib import Path
import json
from typing import Dict, Any, List

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.cable_service import CableService
from services.xmit_service import XmitService
from services.ber_service import BerService
from services.per_lane_performance_service import PerLanePerformanceService
from services.extended_port_info_service import ExtendedPortInfoService
from services.extended_switch_info_service import ExtendedSwitchInfoService
from services.extended_node_info_service import ExtendedNodeInfoService
from services.neighbors_service import NeighborsService
from services.pm_delta_service import PmDeltaService
from services.mlnx_counters_service import MlnxCountersService
from services.buffer_histogram_service import BufferHistogramService
from services.pci_performance_service import PciPerformanceService
from services.phy_diagnostics_service import PhyDiagnosticsService
from services.power_sensors_service import PowerSensorsService
from services.temp_alerts_service import TempAlertsService
from services.fec_mode_service import FecModeService
from services.ar_info_service import ArInfoService
from services.n2n_security_service import N2NSecurityService
from services.pkey_service import PkeyService
from services.qos_service import QosService
from services.routing_config_service import RoutingConfigService
from services.sharp_service import SharpService
from services.system_info_service import SystemInfoService
from services.vports_service import VPortsService
from services.port_hierarchy_service import PortHierarchyService


class ServiceVerifier:
    """Verifies all analysis services against actual data"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.results = {}

    def verify_service(self, name: str, service_class, dataset_root: Path, supports_return_only_issues: bool = True) -> Dict[str, Any]:
        """Verify a single service"""
        print(f"\n{'='*60}")
        print(f"验证服务: {name}")
        print(f"{'='*60}")

        try:
            # Create service instance and run
            service = service_class(dataset_root=dataset_root)

            # Some services support return_only_issues parameter, others don't
            if supports_return_only_issues:
                result = service.run(return_only_issues=False)
            else:
                result = service.run()

            # Extract data
            if hasattr(result, 'data'):
                data = result.data
            elif isinstance(result, dict) and 'data' in result:
                data = result['data']
            else:
                data = []

            # Count severity levels
            severity_counts = {'critical': 0, 'warning': 0, 'healthy': 0, 'info': 0}
            if data:
                for row in data:
                    severity = row.get('severity', 'info').lower()
                    if severity in severity_counts:
                        severity_counts[severity] += 1

            total_rows = len(data) if data else 0

            verification = {
                'status': 'success',
                'total_rows': total_rows,
                'severity_counts': severity_counts,
                'has_data': total_rows > 0,
                'has_issues': severity_counts['critical'] > 0 or severity_counts['warning'] > 0,
                'sample_data': data[:3] if data else []
            }

            # Print summary (avoid Unicode characters for Windows console)
            print(f"[OK] 状态: 成功")
            print(f"  总行数: {total_rows}")
            print(f"  严重: {severity_counts['critical']}")
            print(f"  警告: {severity_counts['warning']}")
            print(f"  健康: {severity_counts['healthy']}")
            print(f"  信息: {severity_counts['info']}")

            if total_rows == 0:
                print(f"  [WARNING] 警告: 没有返回数据")

            return verification

        except Exception as e:
            print(f"[ERROR] 错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'error',
                'error': str(e),
                'has_data': False
            }

    def run_all_verifications(self):
        """Run all service verifications"""
        print(f"\n{'#'*60}")
        print(f"# 数据验证开始")
        print(f"# 数据目录: {self.data_dir}")
        print(f"{'#'*60}")

        # Services that support return_only_issues parameter
        # 1. Cable Analysis
        self.results['cable'] = self.verify_service(
            'Cable 跳线分析',
            CableService,
            self.data_dir,
            supports_return_only_issues=True
        )

        # 2. Xmit Congestion
        self.results['xmit'] = self.verify_service(
            'Xmit 拥塞分析',
            XmitService,
            self.data_dir,
            supports_return_only_issues=True
        )

        # 3. BER Analysis
        self.results['ber'] = self.verify_service(
            'BER 分析',
            BerService,
            self.data_dir,
            supports_return_only_issues=True
        )

        # Services that don't support return_only_issues parameter
        # 4. Per-Lane Performance
        self.results['per_lane'] = self.verify_service(
            'Per-Lane Performance',
            PerLanePerformanceService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 5. Extended Port Info
        self.results['extended_port'] = self.verify_service(
            'Extended Port Info',
            ExtendedPortInfoService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 6. Extended Switch Info
        self.results['extended_switch'] = self.verify_service(
            'Extended Switch Info',
            ExtendedSwitchInfoService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 7. Extended Node Info
        self.results['extended_node'] = self.verify_service(
            'Extended Node Info',
            ExtendedNodeInfoService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 8. Neighbors
        self.results['neighbors'] = self.verify_service(
            'Neighbors',
            NeighborsService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 9. PM Delta
        self.results['pm_delta'] = self.verify_service(
            'PM Delta',
            PmDeltaService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 10. MLNX Counters
        self.results['mlnx_counters'] = self.verify_service(
            'MLNX Counters',
            MlnxCountersService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 11. Buffer Histogram
        self.results['buffer_histogram'] = self.verify_service(
            'Buffer Histogram',
            BufferHistogramService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 12. PCI Performance
        self.results['pci_performance'] = self.verify_service(
            'PCI Performance',
            PciPerformanceService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 14. PHY Diagnostics
        self.results['phy_diagnostics'] = self.verify_service(
            'PHY Diagnostics',
            PhyDiagnosticsService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 15. Power Sensors
        self.results['power_sensors'] = self.verify_service(
            'Power Sensors',
            PowerSensorsService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 16. Temperature Alerts
        self.results['temp_alerts'] = self.verify_service(
            'Temperature Alerts',
            TempAlertsService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 17. FEC Mode
        self.results['fec_mode'] = self.verify_service(
            'FEC Mode',
            FecModeService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 18. AR Info
        self.results['ar_info'] = self.verify_service(
            'AR Info',
            ArInfoService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 19. N2N Security
        self.results['n2n_security'] = self.verify_service(
            'N2N Security',
            N2NSecurityService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 20. PKey
        self.results['pkey'] = self.verify_service(
            'PKey',
            PkeyService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 21. QoS
        self.results['qos'] = self.verify_service(
            'QoS',
            QosService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 22. Routing Config
        self.results['routing_config'] = self.verify_service(
            'Routing Config',
            RoutingConfigService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 23. SHARP
        self.results['sharp'] = self.verify_service(
            'SHARP',
            SharpService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 24. System Info
        self.results['system_info'] = self.verify_service(
            'System Info',
            SystemInfoService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 25. VPorts
        self.results['vports'] = self.verify_service(
            'VPorts',
            VPortsService,
            self.data_dir,
            supports_return_only_issues=False
        )

        # 26. Port Hierarchy
        self.results['port_hierarchy'] = self.verify_service(
            'Port Hierarchy',
            PortHierarchyService,
            self.data_dir,
            supports_return_only_issues=False
        )

        self.print_summary()
        self.save_report()

    def print_summary(self):
        """Print verification summary"""
        print(f"\n{'#'*60}")
        print(f"# 验证总结")
        print(f"{'#'*60}\n")

        services_with_data = []
        services_without_data = []
        services_with_errors = []
        services_with_issues = []

        for name, result in self.results.items():
            if result['status'] == 'error':
                services_with_errors.append(name)
            elif result.get('has_data'):
                services_with_data.append(name)
                if result.get('has_issues'):
                    services_with_issues.append(name)
            else:
                services_without_data.append(name)

        print(f"[OK] 有数据的服务 ({len(services_with_data)}):")
        for name in services_with_data:
            result = self.results[name]
            issue_marker = " [有问题]" if name in services_with_issues else ""
            print(f"  - {name}: {result['total_rows']} 行{issue_marker}")

        if services_without_data:
            print(f"\n[WARNING] 无数据的服务 ({len(services_without_data)}):")
            for name in services_without_data:
                print(f"  - {name}")

        if services_with_errors:
            print(f"\n[ERROR] 错误的服务 ({len(services_with_errors)}):")
            for name in services_with_errors:
                print(f"  - {name}: {self.results[name].get('error', 'Unknown error')}")

        print(f"\n[ISSUES] 发现问题的服务 ({len(services_with_issues)}):")
        for name in services_with_issues:
            result = self.results[name]
            counts = result['severity_counts']
            print(f"  - {name}: 严重={counts['critical']}, 警告={counts['warning']}")

    def save_report(self):
        """Save verification report to file"""
        report_path = Path(__file__).parent / 'verification_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n详细报告已保存到: {report_path}")


def main():
    # Use the latest upload directory - need to find the ibdiagnet2 subdirectory
    upload_dir = Path(__file__).parent / 'uploads' / '468dd275-5a83-4ce7-a3b1-3e46d6c90fef' / 'extracted'

    if not upload_dir.exists():
        print(f"错误: 数据目录不存在: {upload_dir}")
        sys.exit(1)

    # Find the actual data directory (contains .db_csv file)
    data_dir = upload_dir / 'var' / 'tmp' / 'ibdiagnet2'
    if not data_dir.exists():
        print(f"错误: ibdiagnet2 数据目录不存在: {data_dir}")
        sys.exit(1)

    verifier = ServiceVerifier(str(data_dir))
    verifier.run_all_verifications()


if __name__ == '__main__':
    main()
