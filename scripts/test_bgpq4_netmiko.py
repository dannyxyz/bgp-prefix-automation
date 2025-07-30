#!/usr/bin/env python3
"""
Test script for BGPQ4 Automation

This script provides test cases for the BGPQ4Generator class.
"""

import unittest
import os
import tempfile
import shutil
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path to allow importing bgpq4_netmiko
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.bgpq4_netmiko import BGPQ4Generator

class TestBGPQ4Generator(unittest.TestCase):
    """Test cases for BGPQ4Generator class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_path = self.test_dir / 'test_config.yaml'
        self.output_dir = self.test_dir / 'generated'
        
        # Create test config
        self.test_config = {
            'routers': [
                {
                    'hostname': 'test-router',
                    'ip': '10.0.0.1',
                    'policies': [
                        {
                            'name': 'TEST-ROUTES',
                            'as_set': 'AS65530',
                            'description': 'Test Routes',
                            'max_prefix_length': 24,
                            'rir': 'RIPE'
                        }
                    ]
                }
            ],
            'global': {
                'default_rir': 'RIPE',
                'default_max_prefix_length': 24,
                'log_level': 'INFO'
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    @patch('subprocess.run')
    def test_bgpq4_generation(self, mock_run):
        """Test bgpq4 command generation and output processing."""
        # Mock the subprocess.run return value
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
        prefix-set "TEST-ROUTES" {
            192.0.2.0/24,
            198.51.100.0/24
        }
        """
        mock_run.return_value = mock_result
        
        # Initialize generator
        generator = BGPQ4Generator(self.config_path)
        
        # Test with a mock command
        output = generator.run_bgpq4(
            as_set="AS65530",
            policy_name="TEST-ROUTES",
            rir="RIPE",
            max_length=24
        )
        
        # Verify command was called correctly
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        self.assertIn('bgpq4', cmd_args)
        self.assertIn('AS65530', cmd_args)
        self.assertIn('TEST-ROUTES', cmd_args)
        
        # Test Juniper config conversion
        juniper_config = generator.convert_to_juniper_set(
            "route-filter 192.0.2.0/24 exact; route-filter 198.51.100.0/24 exact;",
            "TEST-ROUTES"
        )
        
        self.assertIn('set policy-options policy-statement TEST-ROUTES', juniper_config)
        self.assertIn('192.0.2.0/24 exact', juniper_config)
        self.assertIn('198.51.100.0/24 exact', juniper_config)
    
    def test_config_generation(self):
        """Test full config generation with mock bgpq4."""
        with patch('subprocess.run') as mock_run:
            # Mock the subprocess.run return value
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "route-filter 192.0.2.0/24 exact;"
            mock_run.return_value = mock_result
            
            # Initialize and run generator
            generator = BGPQ4Generator(self.config_path)
            generator.generate_configs()
            
            # Verify output file was created
            output_files = list(self.output_dir.glob('*.conf'))
            self.assertEqual(len(output_files), 1)
            
            # Verify file content
            with open(output_files[0], 'r') as f:
                content = f.read()
                self.assertIn('test-router', content)
                self.assertIn('TEST-ROUTES', content)
                self.assertIn('192.0.2.0/24 exact', content)

    @patch('scripts.bgpq4_netmiko.subprocess.run')
    @patch('scripts.bgpq4_netmiko.JuniperConfigurator')
    @patch.dict('os.environ', {'USERNAME': 'testuser', 'PASSWORD': 'testpass'})
    def test_generate_configs_apply(self, mock_juniper, mock_run):
        """Test generating and applying configurations."""
        # Setup mock for subprocess.run
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = 'route-filter 192.0.2.0/24 exact;\nroute-filter 203.0.113.0/24 orlonger;'
        mock_run.return_value = mock_proc
        
        # Setup mock for JuniperConfigurator
        mock_device = MagicMock()
        mock_device.connect.return_value = True
        mock_device.send_config_commands.return_value = (True, 'success', True)
        mock_juniper.return_value = mock_device
        
        # Run with apply
        generator = BGPQ4Generator(self.config_path)
        results = generator.generate_configs(apply_config=True)
        
        # Verify results
        self.assertTrue(all(r['success'] for r in results))
        
        # Verify device connection was attempted with env vars
        mock_juniper.assert_called_once_with(
            host='10.0.0.1',
            username='testuser',
            password='testpass',
            port=22
        )
        mock_device.connect.assert_called_once()
        mock_device.send_config_commands.assert_called_once()
        
        # Verify the correct commands were sent with commit confirmed 3
        commands = mock_device.send_config_commands.call_args[0][0]
        self.assertIn('set policy-options policy-statement TEST-ROUTES term route-set1 from route-filter 192.0.2.0/24 exact', commands[1])
        
        # Verify commit confirmed 3 was used
        self.assertEqual(mock_device.send_config_commands.call_args[1]['commit_confirmed_minutes'], 3)

if __name__ == '__main__':
    unittest.main()

