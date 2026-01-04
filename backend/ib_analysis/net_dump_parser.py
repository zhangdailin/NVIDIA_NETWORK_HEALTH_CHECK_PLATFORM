import os
import re
import pandas as pd
from typing import Dict, List, Optional, Tuple
from .pbar import pbar_r, close_pbar
from .utils import s2n


class NetDumpExtParser:
    """
    Parser for ibdiagnet2.net_dump_ext files to extract BER data
    """
    
    def __init__(self, ib_dir: str):
        self.ib_dir = ib_dir
        self.net_dump_file = self._find_net_dump_file()
        
    def _find_net_dump_file(self) -> Optional[str]:
        """Find the net_dump_ext file in the given directory"""
        possible_names = [
            "ibdiagnet2.net_dump_ext",
            "net_dump_ext",
            "ibdiagnet.net_dump_ext"
        ]
        
        for filename in possible_names:
            file_path = os.path.join(self.ib_dir, filename)
            if os.path.exists(file_path):
                return file_path
                
        # If not found, list all files to help debug
        try:
            files = os.listdir(self.ib_dir)
            net_dump_files = [f for f in files if 'net_dump' in f.lower() or 'dump' in f.lower()]
            if net_dump_files:
                print(f"Found potential net_dump files: {net_dump_files}")
                return os.path.join(self.ib_dir, net_dump_files[0])
        except Exception as e:
            print(f"Error listing directory {self.ib_dir}: {e}")
            
        return None
    
    def parse_ber_data(self) -> pd.DataFrame:
        """
        Parse BER data from net_dump_ext file
        Returns DataFrame with columns: NodeGUID, PortNumber, Raw BER, Effective BER, Symbol BER
        """
        if not self.net_dump_file:
            raise FileNotFoundError(f"No net_dump_ext file found in {self.ib_dir}")
            
        # First try the structured format parser (for real ibdiagnet2 files)
        try:
            return self._parse_structured_format()
        except Exception as e:
            print(f"Structured parsing failed: {e}")
            
        # Fallback to alternative parsing methods
        return self._parse_alternative_format()
    
    def _parse_structured_format(self) -> pd.DataFrame:
        """
        Parse structured ibdiagnet2.net_dump_ext format
        This handles the real format with columns like:
        Ty : # : #IB : GUID : LID : Sta : PhysSta : LWA : LSA : Conn LID (#) : FEC mode : RTR : Raw BER : Effective BER : Symbol BER : Symbol Err : Effective Err : Node Desc
        """
        print("Trying structured format parsing...")
        
        ber_data = []
        
        try:
            with open(self.net_dump_file, 'r', encoding='latin-1') as file:
                lines = file.readlines()
                
            # Initialize progress bar
            pbar = pbar_r(key="net_dump_ber", desc="Parsing structured BER data...", total=len(lines))
            
            header_found = False
            
            for line in lines:
                pbar.update()
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Look for the header line to understand column positions
                if 'Raw BER' in line and 'Effective BER' in line and 'Symbol BER' in line:
                    header_found = True
                    continue
                
                # Skip lines without header context
                if not header_found:
                    continue
                
                # Parse data lines - they start with device type (CA, SW, etc.)
                if line.startswith(('CA ', 'SW ', 'RT ')):
                    try:
                        # Split the line by colons and clean up
                        parts = [part.strip() for part in line.split(':')]
                        
                        if len(parts) < 15:  # Need at least 15 parts for BER data
                            continue
                            
                        # Extract GUID (typically in position 3)
                        guid_part = parts[3].strip()
                        guid_match = re.search(r'0x([0-9a-fA-F]+)', guid_part)
                        if not guid_match:
                            continue
                        node_guid = self._normalize_guid(guid_match.group(1))
                        
                        # Extract port number (typically in position 2)
                        port_part = parts[2].strip()
                        port_match = re.search(r'(\d+)', port_part)
                        if not port_match:
                            continue
                        port_number = int(port_match.group(1))
                        
                        # Extract BER values - they're typically in the last few columns
                        # Look for the pattern: RTR : Raw BER : Effective BER : Symbol BER [: Symbol Err : Effective Err]
                        raw_ber_str = None
                        eff_ber_str = None
                        sym_ber_str = None
                        sym_err_val = None
                        eff_err_val = None
                        
                        # Find BER data by looking for scientific notation patterns in the parts
                        ber_candidates = []
                        for part in parts:
                            # Look for scientific notation numbers
                            ber_matches = re.findall(r'([0-9]+\.?[0-9]*e[+-]?\d+)', part, re.IGNORECASE)
                            ber_candidates.extend(ber_matches)
                        
                        # We expect at least 3 BER values (Raw, Effective, Symbol)
                        if len(ber_candidates) >= 3:
                            # The BER values are typically the last 3 scientific notation numbers
                            # before the error counters
                            raw_ber_str = ber_candidates[-6] if len(ber_candidates) >= 6 else ber_candidates[0]
                            eff_ber_str = ber_candidates[-5] if len(ber_candidates) >= 5 else ber_candidates[1] if len(ber_candidates) >= 2 else None
                            sym_ber_str = ber_candidates[-4] if len(ber_candidates) >= 4 else ber_candidates[2] if len(ber_candidates) >= 3 else None
                            
                            # Alternative: look for specific positions based on typical format
                            # RTR is around position 11, BER values follow
                            if len(parts) >= 15:
                                for i in range(11, min(len(parts)-3, 15)):
                                    part = parts[i].strip()
                                    if 'NO-RTR' in part or 'RTR' in part:
                                        # BER values should be in the next 3 positions
                                        if i+3 < len(parts):
                                            raw_ber_str = parts[i+1].strip()
                                            eff_ber_str = parts[i+2].strip()  
                                            sym_ber_str = parts[i+3].strip()
                                            # Try to parse optional Symbol Err and Effective Err numbers if present
                                            def _to_int_safe(s):
                                                try:
                                                    return int(float(s))
                                                except Exception:
                                                    return None
                                            if i+4 < len(parts):
                                                sym_err_val = _to_int_safe(parts[i+4].strip())
                                            if i+5 < len(parts):
                                                eff_err_val = _to_int_safe(parts[i+5].strip())
                                        break
                        
                        # Convert BER strings to floats
                        raw_ber = self._safe_float_convert(raw_ber_str) if raw_ber_str else None
                        eff_ber = self._safe_float_convert(eff_ber_str) if eff_ber_str else None
                        sym_ber = self._safe_float_convert(sym_ber_str) if sym_ber_str else None
                        
                        # Only add if we have valid BER data
                        if raw_ber is not None and eff_ber is not None and sym_ber is not None:
                            rec = {
                                'NodeGUID': node_guid,
                                'PortNumber': port_number,
                                'Raw BER': self._format_ber(raw_ber),
                                'Effective BER': self._format_ber(eff_ber),
                                'Symbol BER': self._format_ber(sym_ber)
                            }
                            if sym_err_val is not None:
                                rec['Symbol Err'] = sym_err_val
                            if eff_err_val is not None:
                                rec['Effective Err'] = eff_err_val
                            ber_data.append(rec)
                            
                    except Exception as e:
                        # Skip problematic lines but continue processing
                        continue
            
            close_pbar("net_dump_ber")
            
        except Exception as e:
            close_pbar("net_dump_ber")
            raise Exception(f"Error parsing structured format: {e}")
            
        return pd.DataFrame(ber_data)
    
    def _parse_alternative_format(self) -> pd.DataFrame:
        """
        Alternative parsing method for different net_dump_ext formats
        """
        print("Trying alternative parsing method...")
        
        try:
            with open(self.net_dump_file, 'r', encoding='latin-1') as file:
                lines = file.readlines()
                
            ber_data = []
            current_node = None
            current_port = None
            
            # Try line-by-line parsing with more flexible patterns
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Look for GUID patterns (various formats)
                guid_patterns = [
                    r'guid[=:\s]+([0-9a-fA-Fx]{12,})',  # Standard GUID
                    r'([0-9a-fA-F]{16,})',              # Raw hex GUID
                    r'0x([0-9a-fA-F]{12,})',           # Hex with 0x prefix
                ]
                
                for pattern in guid_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        current_node = self._normalize_guid(match.group(1))
                        break
                
                # Look for port patterns
                port_patterns = [
                    r'port[=:\s]+(\d+)',
                    r'port(\d+)',
                    r'p(\d+)',
                ]
                
                for pattern in port_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        current_port = int(match.group(1))
                        break
                
                # Look for BER data in the line - try multiple approaches
                if current_node and current_port is not None:
                    # Approach 1: Look for explicit BER labels
                    ber_matches = {}
                    
                    # Raw BER
                    raw_patterns = [
                        r'raw.*?ber[=:\s]+([0-9.eE\-+]+)',
                        r'raw[=:\s]+([0-9.eE\-+]+)',
                        r'ber.*?raw[=:\s]+([0-9.eE\-+]+)',
                    ]
                    
                    for pattern in raw_patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            raw_val = self._safe_float_convert(match.group(1))
                            if raw_val is not None:
                                ber_matches['Raw BER'] = self._format_ber(raw_val)
                                break
                    
                    # Effective BER
                    eff_patterns = [
                        r'effective.*?ber[=:\s]+([0-9.eE\-+]+)',
                        r'eff.*?ber[=:\s]+([0-9.eE\-+]+)',
                        r'ber.*?eff[=:\s]+([0-9.eE\-+]+)',
                    ]
                    
                    for pattern in eff_patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            eff_val = self._safe_float_convert(match.group(1))
                            if eff_val is not None:
                                ber_matches['Effective BER'] = self._format_ber(eff_val)
                                break
                    
                    # Symbol BER
                    sym_patterns = [
                        r'symbol.*?ber[=:\s]+([0-9.eE\-+]+)',
                        r'sym.*?ber[=:\s]+([0-9.eE\-+]+)',
                        r'ber.*?sym[=:\s]+([0-9.eE\-+]+)',
                    ]
                    
                    for pattern in sym_patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            sym_val = self._safe_float_convert(match.group(1))
                            if sym_val is not None:
                                ber_matches['Symbol BER'] = self._format_ber(sym_val)
                                break
                    
                    # Approach 2: Look for numeric sequences that might be BER values
                    if not ber_matches:
                        # Find all scientific notation numbers in the line
                        sci_numbers = re.findall(r'([0-9]+\.?[0-9]*[eE][+-]?\d+)', line)
                        if len(sci_numbers) >= 3:
                            # Assume first 3 are Raw, Effective, Symbol BER
                            raw_val = self._safe_float_convert(sci_numbers[0])
                            eff_val = self._safe_float_convert(sci_numbers[1])
                            sym_val = self._safe_float_convert(sci_numbers[2])
                            
                            if all(v is not None for v in [raw_val, eff_val, sym_val]):
                                ber_matches = {
                                    'Raw BER': self._format_ber(raw_val),
                                    'Effective BER': self._format_ber(eff_val),
                                    'Symbol BER': self._format_ber(sym_val)
                                }
                    
                    # If we found BER data, add it
                    if len(ber_matches) == 3:
                        ber_data.append({
                            'NodeGUID': current_node,
                            'PortNumber': current_port,
                            **ber_matches
                        })
                        # Reset for next entry
                        current_node = None
                        current_port = None
            
            # Approach 3: If still no data, try a more aggressive pattern matching
            if not ber_data:
                ber_data = self._parse_aggressive_format()
                            
            return pd.DataFrame(ber_data)
            
        except Exception as e:
            print(f"Alternative parsing also failed: {e}")
            return pd.DataFrame()
    
    def _parse_aggressive_format(self) -> List[Dict]:
        """
        Most aggressive parsing - extract any numbers that look like BER values
        """
        print("Trying aggressive parsing...")
        
        try:
            with open(self.net_dump_file, 'r', encoding='latin-1') as file:
                content = file.read()
            
            # Look for any GUID-like patterns
            guid_pattern = r'([0-9a-fA-F]{12,})'
            guids = re.findall(guid_pattern, content)
            
            # Look for any scientific notation numbers
            sci_pattern = r'([0-9]+\.?[0-9]*[eE][+-]?\d+)'
            sci_numbers = re.findall(sci_pattern, content)
            
            # Look for port numbers
            port_pattern = r'port[=:\s]*(\d+)|p(\d+)'
            port_matches = re.findall(port_pattern, content, re.IGNORECASE)
            ports = [int(p[0] or p[1]) for p in port_matches if p[0] or p[1]]
            
            ber_data = []
            
            # Try to match GUIDs with BER values
            if guids and sci_numbers and len(sci_numbers) >= 3:
                # Group scientific numbers in sets of 3
                for i in range(0, min(len(guids), len(sci_numbers) // 3)):
                    guid = self._normalize_guid(guids[i])
                    port = ports[i] if i < len(ports) else 1
                    
                    base_idx = i * 3
                    if base_idx + 2 < len(sci_numbers):
                        raw_val = self._safe_float_convert(sci_numbers[base_idx])
                        eff_val = self._safe_float_convert(sci_numbers[base_idx + 1])
                        sym_val = self._safe_float_convert(sci_numbers[base_idx + 2])
                        
                        if all(v is not None for v in [raw_val, eff_val, sym_val]):
                            ber_data.append({
                                'NodeGUID': guid,
                                'PortNumber': port,
                                'Raw BER': self._format_ber(raw_val),
                                'Effective BER': self._format_ber(eff_val),
                                'Symbol BER': self._format_ber(sym_val)
                            })
            
            return ber_data
            
        except Exception as e:
            print(f"Aggressive parsing failed: {e}")
            return []
    
    def _safe_float_convert(self, value_str: str) -> Optional[float]:
        """Safely convert string to float with robust error handling"""
        if not value_str or value_str.strip() == '':
            return None
            
        # Clean the string
        clean_str = value_str.strip().upper()
        
        # Handle special cases
        if clean_str in ['NA', 'N/A', 'NULL', 'NONE', '-', '']:
            return None
            
        # Handle scientific notation variations
        # Convert different E notation formats
        if 'E' in clean_str:
            # Handle cases like "1.5E-254" or "1E-10"
            try:
                return float(clean_str)
            except ValueError:
                # Try to fix malformed scientific notation
                # Handle cases like "1.5E" (missing exponent)
                if clean_str.endswith('E'):
                    try:
                        return float(clean_str[:-1])  # Remove trailing E
                    except ValueError:
                        pass
                        
                # Handle cases like "E-10" (missing mantissa)
                if clean_str.startswith('E'):
                    try:
                        return float('1' + clean_str)  # Add mantissa of 1
                    except ValueError:
                        pass
        
        # Try direct conversion
        try:
            return float(clean_str)
        except ValueError:
            pass
            
        # Try using the existing s2n function
        try:
            result = s2n(clean_str)
            if isinstance(result, (int, float)):
                return float(result)
        except Exception:
            pass
            
        # Try hex conversion if it looks like hex
        if clean_str.startswith('0X') or clean_str.startswith('0x'):
            try:
                return float(int(clean_str, 16))
            except ValueError:
                pass
        
        return None
    
    def _normalize_guid(self, guid_str: str) -> str:
        """Normalize GUID format to 0x prefixed hex string"""
        # Remove any existing 0x prefix and clean the string
        clean_guid = guid_str.replace('0x', '').replace('0X', '').strip()
        # Ensure it's a valid hex string and add 0x prefix
        try:
            int(clean_guid, 16)
            return f"0x{clean_guid.lower()}"
        except ValueError:
            return guid_str
    
    def _format_ber(self, value: float) -> str:
        """Format BER value in scientific notation"""
        if value == 0:
            return "0e+00"
        
        # Convert to scientific notation with 1 decimal place
        import math
        if value > 0:
            exponent = int(math.floor(math.log10(value)))
            mantissa = value / (10 ** exponent)
            return f"{mantissa:.1f}e{exponent:+03d}"
        else:
            return "NA"
    
    def get_file_info(self) -> Dict:
        """Get information about the net_dump_ext file"""
        if not self.net_dump_file:
            return {"error": "No net_dump_ext file found"}
            
        try:
            file_size = os.path.getsize(self.net_dump_file)
            with open(self.net_dump_file, 'r', encoding='latin-1') as file:
                first_lines = [file.readline().strip() for _ in range(10)]
                
            return {
                "file_path": self.net_dump_file,
                "file_size": file_size,
                "first_10_lines": first_lines
            }
        except Exception as e:
            return {"error": f"Error reading file: {e}"}


def test_parser(ib_dir: str):
    """Test function to analyze net_dump_ext file structure"""
    parser = NetDumpExtParser(ib_dir)
    
    # Get file info first
    info = parser.get_file_info()
    print("File Info:", info)
    
    # Try to parse BER data
    try:
        df = parser.parse_ber_data()
        print(f"\nParsed {len(df)} BER records")
        if len(df) > 0:
            print("\nFirst 5 records:")
            print(df.head())
        return df
    except Exception as e:
        print(f"Parsing failed: {e}")
        return None


if __name__ == "__main__":
    # Test with a directory path
    test_dir = input("Enter path to ibdiagnet directory: ")
    test_parser(test_dir)
