#!/usr/bin/env python3
"""
Integration tests for BGPQ4 automation with Netmiko.

This script tests the end-to-end functionality of the BGPQ4 automation
with a mock Juniper device using the netmiko-mock library.
"""

import os
import sys
import unittest
import yaml
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add parent directory to path to allow importing from scripts
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the modules to test
from scripts.bgpq4_netmiko import BGPQ4Generator

# Mock the JuniperConfigurator class
class MockJuniperConfigurator:
    def __init__(self, host, username, password=None, port=22, device_type='juniper_junos'):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.device_type = device_type
        self.connection = None
        self.logger = logging.getLogger(__name__)
        self.connected = False
    
    def connect(self):
        self.connected = True
        return True
    
    def disconnect(self):
        self.connected = False
    
    def send_config_commands(self, commands, commit_confirmed_minutes=10):
        if not self.connected:
            return False, "Not connected to device", False
        
        # Simulate the behavior of the real method
        if commit_confirmed_minutes > 0:
            # For tests, we'll just return success with manual_commit_required=True
            return True, "Configuration applied with commit confirmed 10", True
        return True, "Configuration applied successfully", False
    
    def commit_changes(self):
        if not self.connected:
            return False, "Not connected to device"
        return True, "Commit complete"

class TestBGPQ4NetmikoIntegration(unittest.TestCase):
    """Integration tests for BGPQ4 automation with Netmiko."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before any tests are run."""
        # Create a test config directory if it doesn't exist
        cls.test_config_dir = Path(__file__).parent.parent / 'test_configs'
        cls.test_config_dir.mkdir(exist_ok=True)
        
        # Create a test output directory
        cls.test_output_dir = Path(__file__).parent.parent / 'test_output'
        cls.test_output_dir.mkdir(exist_ok=True)
        
        # Create a test YAML config file
        cls.test_config = {
            'global': {
                'default_rir': 'AFRINIC',
                'default_max_prefix_length': 24
            },
            'routers': [
                {
                    'hostname': 'test-router1',
                    'ip': '192.0.2.1',
                    'username': 'testuser',
                    'policies': [
                        {
                            'name': 'TEST-POLICY-1',
                            'as_set': 'AS-TEST1',
                            'rir': 'AFRINIC',
                            'max_prefix_length': 24
                        }
                    ]
                }
            ]
        }
        
        cls.test_config_path = cls.test_config_dir / 'test_prefix_policies.yaml'
        with open(cls.test_config_path, 'w') as f:
            yaml.dump(cls.test_config, f)
    
    def setUp(self):
        """Set up test fixtures for each test method."""
        self.generator = BGPQ4Generator(self.test_config_path)
        
        # Mock the subprocess.run function to return test data
        self.mock_run = patch('subprocess.run').start()
        self.mock_process = MagicMock()
        self.mock_process.stdout = 'route-filter 192.0.2.0/24 upto /24;\nroute-filter 203.0.113.0/24 upto /24;'
        self.mock_process.returncode = 0
        self.mock_run.return_value = self.mock_process
    
    def tearDown(self):
        """Clean up after each test method."""
        patch.stopall()
    
    @patch('scripts.bgpq4_netmiko.JuniperConfigurator', new=MockJuniperConfigurator)
    def test_generate_and_apply_config(self):
        """Test generating and applying a configuration."""
        # Generate and apply the configuration
        results = self.generator.generate_configs(
            apply_config=True,
            commit_confirmed_minutes=5
        )
        
        # Verify the results
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]['success'])
        self.assertIn('test-router1', results[0]['router'])
        self.assertIn('TEST-POLICY-1', results[0]['policy'])
    
    @patch('scripts.bgpq4_netmiko.JuniperConfigurator', new=MockJuniperConfigurator)
    def test_commit_changes(self):
        """Test committing changes on a router."""
        # Test committing changes
        success, output = self.generator.commit_changes(
            router_ip='192.0.2.1',
            username='testuser',
            password='testpass',
            port=22
        )
        
        # Verify the results
        self.assertTrue(success)
        self.assertIn("Commit complete", output)
    
    @patch('scripts.bgpq4_netmiko.JuniperConfigurator', new=MockJuniperConfigurator)
    def test_manual_commit_required(self):
        """Test that manual commit is required after applying config with commit confirmed."""
        # Generate and apply the configuration with commit confirmed
        results = self.generator.generate_configs(
            apply_config=True,
            commit_confirmed_minutes=10
        )
        
        # Verify the results
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]['success'])
        self.assertTrue(results[0]['manual_commit_required'])
        self.assertIn('test-router1', results[0]['router'])
        self.assertIn('TEST-POLICY-1', results[0]['policy'])
    
    def test_convert_to_juniper_set(self):
        """Test converting bgpq4 output to Juniper set commands."""
        # Test input
        bgpq4_output = """
        route-filter 192.0.2.0/24 upto /24;
        route-filter 203.0.113.0/24 upto /24;
        """
        
        # Expected output
        expected_commands = [
            'set policy-options policy-statement TEST-POLICY-1 term route-set1 from protocol bgp',
            'set policy-options policy-statement TEST-POLICY-1 term route-set1 from route-filter 192.0.2.0/24 upto /24',
            'set policy-options policy-statement TEST-POLICY-1 term route-set1 from route-filter 203.0.113.0/24 upto /24',
            'set policy-options policy-statement TEST-POLICY-1 term route-set1 then next policy',
            'set policy-options policy-statement TEST-POLICY-1 term reject then reject'
        ]
        
        # Convert the output
        result = self.generator.convert_to_juniper_set(bgpq4_output, 'TEST-POLICY-1')
        
        # Verify the result
        self.assertIsNotNone(result)
        
        # Split the result into lines and check each expected command is present
        result_lines = result.split('\n')
        for cmd in expected_commands:
            self.assertIn(cmd, result_lines)

if __name__ == "__main__":
    unittest.main()

