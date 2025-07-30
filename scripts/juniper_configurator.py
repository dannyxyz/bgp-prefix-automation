"""
Juniper Device Configuration Module

This module provides a class for configuring Juniper devices using Netmiko
with support for commit confirmed (rollback) functionality.
"""

import logging
import os
from netmiko import ConnectHandler, NetMikoTimeoutException, NetMikoAuthenticationException

class JuniperConfigurator:
    """Class to handle Juniper device configuration using Netmiko."""
    
    def __init__(self, host, username=None, password=None, port=22, device_type='juniper_junos'):
        """Initialize the Juniper device connection parameters.
        
        Args:
            host (str): Device hostname or IP address
            username (str, optional): Username for authentication. If not provided, will use USERNAME env var.
            password (str, optional): Password for authentication. If not provided, will use PASSWORD env var.
            port (int, optional): SSH port. Defaults to 22.
            device_type (str, optional): Netmiko device type. Defaults to 'juniper_junos'.
        """
        self.host = host
        self.username = username or os.environ.get('USERNAME')
        self.password = password or os.environ.get('PASSWORD')
        self.port = port
        self.device_type = device_type
        self.connection = None
        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """Establish connection to the Juniper device.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        device = {
            'device_type': self.device_type,
            'host': self.host,
            'username': self.username,
            'password': self.password or getpass(f"Enter password for {self.username}@{self.host}: "),
            'port': self.port,
            'timeout': 30,
        }
        
        try:
            self.logger.info(f"Connecting to {self.host}...")
            self.connection = ConnectHandler(**device)
            self.connection.enable()
            self.logger.info(f"Successfully connected to {self.host}")
            return True
        except NetMikoAuthenticationException:
            self.logger.error(f"Authentication failed for {self.username}@{self.host}")
            return False
        except NetMikoTimeoutException:
            self.logger.error(f"Connection timeout to {self.host}")
            return False
        except Exception as e:
            self.logger.error(f"Error connecting to {self.host}: {str(e)}")
            return False
    
    def send_config_commands(self, commands, commit_confirmed_minutes=3):
        """Send configuration commands with commit confirmed.
        
        Args:
            commands (list): List of configuration commands to send
            commit_confirmed_minutes (int): Minutes to wait before auto-rollback (default: 3)
            
        Returns:
            tuple: (success, output, manual_commit_required)
        """
        if not self.connection:
            self.logger.error("Not connected to any device")
            return False, "Not connected to any device", False
        
        output = ""
        try:
            # 1. Enter configuration mode explicitly
            self.logger.info("Entering configuration mode...")
            self.connection.config_mode()
            
            # 2. Send each command individually with proper error handling
            self.logger.info("Sending configuration commands...")
            for cmd in commands:
                if cmd.strip().startswith('#'):
                    # Skip comments
                    continue
                self.logger.debug(f"Sending command: {cmd}")
                result = self.connection.send_command_timing(cmd, delay_factor=2)
                output += f"{cmd}\n{result}\n"
                
                # Check for errors in the output
                if 'error' in result.lower() or 'unknown command' in result.lower():
                    error_msg = f"Error executing command: {cmd}\n{result}"
                    self.logger.error(error_msg)
                    return False, error_msg, False
            
            # 3. Execute commit confirmed in configuration mode
            self.logger.info("Running commit confirmed...")
            commit_cmd = f'commit confirmed {commit_confirmed_minutes}'
            
            # Use send_command instead of send_command_timing to wait for the command to complete
            commit_output = self.connection.send_command(
                commit_cmd,
                expect_string=r'[>#]',  # Wait for prompt
                delay_factor=2,
                max_loops=1000
            )
            output += f"\n{commit_cmd}\n{commit_output}"
            
            # 4. Exit configuration mode but keep the session alive
            self.connection.exit_config_mode()
            
            # 5. Important: We need to keep the connection alive for the rollback to work
            # The router will automatically roll back after the specified minutes
            # if no commit is received
            
            self.logger.info("\n" + "="*70)
            self.logger.info(f"CONFIGURATION APPLIED WITH COMMIT CONFIRMED {commit_confirmed_minutes}")
            self.logger.info("="*70)
            self.logger.info(f"\nIMPORTANT: The configuration has been applied with a {commit_confirmed_minutes}-minute rollback window.")
            self.logger.info(f"To make these changes permanent, you must run 'commit' within the next {commit_confirmed_minutes} minutes.")
            self.logger.info("\nIf you do not commit within this window, the configuration")
            self.logger.info("will be automatically rolled back to its previous state.")
            self.logger.info("-"*70 + "\n")
            
            # Return True with manual_commit_required=True
            # The caller should NOT disconnect after this, as it would prevent the rollback
            return True, output, True
                
        except Exception as e:
            error_msg = f"Error during configuration: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, False
    
    def disconnect(self):
        """Close the connection to the device."""
        if self.connection:
            self.connection.disconnect()
            self.logger.info(f"Disconnected from {self.host}")
    
    def commit_changes(self):
        """Commit the configuration changes permanently.
        
        Returns:
            tuple: (success, output)
        """
        if not self.connection:
            self.logger.error("Not connected to any device")
            return False, "Not connected to any device"
        
        try:
            # Ensure we're in configuration mode
            if not self.connection.check_config_mode():
                self.logger.info("Entering configuration mode...")
                self.connection.config_mode()
            
            self.logger.info("Committing configuration changes permanently...")
            # Use send_command_timing to send the commit command directly
            output = self.connection.send_command_timing('commit', delay_factor=2)
            
            if 'complete' in output.lower():
                self.logger.info("Configuration committed successfully")
                return True, output
            else:
                error_msg = f"Commit failed: {output}"
                self.logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error committing changes: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def rollback_changes(self):
        """Rollback to the previous configuration.
        
        Returns:
            tuple: (success, output)
        """
        if not self.connection:
            self.logger.error("Not connected to any device")
            return False, "Not connected to any device"
        
        try:
            # Ensure we're in configuration mode
            if not self.connection.check_config_mode():
                self.logger.info("Entering configuration mode...")
                self.connection.config_mode()
                
            self.logger.info("Rolling back to previous configuration...")
            # Use rollback command directly
            output = self.connection.send_command_timing('rollback 1', delay_factor=2)
            
            # Commit the rollback
            commit_output = self.connection.send_command_timing('commit', delay_factor=2)
            output += "\n" + commit_output
            
            if 'complete' in commit_output.lower():
                self.logger.info("Successfully rolled back to previous configuration")
                return True, output
            else:
                error_msg = f"Rollback failed: {commit_output}"
                self.logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error during rollback: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
            self.logger.info("Rolling back configuration...")
            output = self.connection.send_command("rollback 1")
            output += self.connection.commit()
            
            if 'complete' in output.lower():
                self.logger.info("Configuration rolled back successfully")
                return True, output
            else:
                self.logger.error(f"Rollback failed: {output}")
                return False, output
        except Exception as e:
            self.logger.error(f"Error during rollback: {str(e)}")
            return False, str(e)

