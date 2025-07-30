#!/usr/bin/env python3
"""
BGPQ4 Automation Script for Juniper Prefix List Generation

This script reads router and policy configurations from a YAML file,
generates prefix lists using bgpq4, and configures Juniper devices
using Netmiko with commit confirmed for safe deployment.
"""


import os
import sys
import re
import yaml
import json
import time
import subprocess
import logging
import argparse
from pathlib import Path
from datetime import datetime
from getpass import getpass

# Import the JuniperConfigurator class from the separate module
from juniper_configurator import JuniperConfigurator

# Configure logging
def setup_logging():
    """Configure logging to file and console."""
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / 'bgpq4_automation.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()


class BGPQ4Generator:
    """Class to handle BGPQ4 prefix list generation and device configuration."""
    
    def __init__(self, config_path):
        """Initialize with path to YAML config."""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.output_dir = Path(__file__).parent.parent / 'configs' / 'generated'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def _load_config(self):
        """Load and validate the YAML configuration."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Validate required fields
            if 'routers' not in config:
                raise ValueError("Missing 'routers' section in config")
                
            return config
            
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)
    
    def run_bgpq4(self, as_set, policy_name, rir, max_length):
        """Run bgpq4 command and return the output."""
        # Format the policy name with route-set if it doesn't already include it
        if not any(prefix in policy_name.lower() for prefix in ['route-set', 'as-set']):
            policy_name = f"{policy_name}/route-set1"
            
        cmd = [
            'bgpq4',
            '-S', rir,
            '-A',  # Aggregate prefix
            '-J',  # Junos format
            '-E',  # Extended format (capital E)
            '-l', policy_name,  # Policy name with route-set
            as_set,
            '-R', str(max_length),
            '-M', 'protocol bgp'  # Single quoted argument
        ]
        
        try:
            logger.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=True
            )
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            logger.error(f"bgpq4 command failed: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("bgpq4 command not found. Please install bgpq4.")
            sys.exit(1)
    
    def convert_to_juniper_set(self, bgpq4_output, policy_name):
        """Convert bgpq4 output to Juniper set commands."""
        if not bgpq4_output:
            return None
            
        commands = []
        
        # Add the initial command for protocol
        commands.append(f'set policy-options policy-statement {policy_name} term route-set1 from protocol bgp')
        
        # Find all route-filter entries
        route_filters = re.findall(r'route-filter (\S+) (exact|upto /\d+);', bgpq4_output)
        for route, filter_type in route_filters:
            if filter_type == 'exact':
                commands.append(f'set policy-options policy-statement {policy_name} term route-set1 from route-filter {route} exact')
            else:
                commands.append(f'set policy-options policy-statement {policy_name} term route-set1 from route-filter {route} {filter_type}')
        
        # Add the next policy and reject terms
        commands.append(f'set policy-options policy-statement {policy_name} term route-set1 then next policy')
        commands.append(f'set policy-options policy-statement {policy_name} term reject then reject')
        
        return '\n'.join(commands)
    
    def _get_router_credentials(self, router_config):
        """Get router credentials from config or environment variables."""
        import os
        return {
            'username': router_config.get('username') or os.environ.get('USERNAME'),
            'password': router_config.get('password') or os.environ.get('PASSWORD'),
            'port': router_config.get('port', 22)
        }

    def generate_configs(self, apply_config=False, commit_confirmed_minutes=10):
        """Generate configurations for all routers and policies.
        
        Args:
            apply_config (bool): If True, apply the configuration to devices
            commit_confirmed_minutes (int): Minutes to wait before auto-rollback
            
        Returns:
            list: List of results for each configuration
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results = []
        
        for router in self.config.get('routers', []):
            hostname = router.get('hostname')
            router_ip = router.get('ip')
            
            if not hostname or not router_ip:
                self.logger.warning(f"Skipping router with missing hostname or IP: {router}")
                continue
                
            self.logger.info(f"Processing router: {hostname} ({router_ip})")
            
            # Initialize device connection if applying config
            device = None
            if apply_config:
                credentials = self._get_router_credentials(router)
                device = JuniperConfigurator(
                    host=router_ip,
                    username=credentials['username'],
                    password=credentials['password'],
                    port=credentials['port']
                )
                if not device.connect():
                    self.logger.error(f"Failed to connect to {hostname}, skipping...")
                    continue
            
            policies = []
            for policy in router.get('policies', []):
                policy_name = policy.get('name')
                as_set = policy.get('as_set')
                rir = policy.get('rir', self.config.get('global', {}).get('default_rir', 'AFRINIC'))
                max_length = policy.get('max_prefix_length', 
                                     self.config.get('global', {}).get('default_max_prefix_length', 24))
                
                if not all([policy_name, as_set]):
                    self.logger.warning(f"Skipping policy with missing name or AS set: {policy}")
                    continue
                
                self.logger.info(f"  Generating policy: {policy_name} for {as_set}")
                
                # Run bgpq4
                bgpq4_output = self.run_bgpq4(as_set, policy_name, rir, max_length)
                
                if not bgpq4_output:
                    self.logger.error(f"Failed to generate prefix list for {policy_name}")
                    continue
                
                # Convert to Juniper set commands
                juniper_config = self.convert_to_juniper_set(bgpq4_output, policy_name)
                
                if not juniper_config:
                    self.logger.error(f"Failed to convert bgpq4 output to Juniper config for {policy_name}")
                    continue
                
                # Split into individual commands for Netmiko
                config_commands = juniper_config.split('\n')
                
                # Add a comment at the beginning
                config_commands.insert(0, f'# BGP Prefix List for {policy_name} ({as_set})')
                
                policies.append({
                    'policy_name': policy_name,
                    'config_commands': config_commands
                })
            
            if policies:
                # Write to file
                output_file = self.output_dir / f"{hostname}_{timestamp}.conf"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"# Generated: {datetime.now()}\n")
                    f.write(f"# Router: {hostname} ({router_ip})\n\n")
                    for policy in policies:
                        f.write('\n'.join(policy['config_commands']))
                        f.write('\n\n')
                
                self.logger.info(f"    Configuration written to: {output_file}")
                
                # Apply configuration to device if requested
                if apply_config and device:
                    self.logger.info(f"\nApplying configuration to {hostname}...")
                    success, output, manual_commit_required = device.send_config_commands(
                        [command for policy in policies for command in policy['config_commands']],
                        commit_confirmed_minutes=commit_confirmed_minutes
                    )
                    
                    result = {
                        'router': hostname,
                        'success': success,
                        'output': output,
                        'config_file': str(output_file),
                        'manual_commit_required': manual_commit_required
                    }
                    
                    if success and manual_commit_required:
                        # IMPORTANT: Do not disconnect the device here to allow the rollback to occur
                        # The device will automatically roll back after the specified minutes
                        self.logger.warning(
                            f"\n{'*'*80}\n"
                            f"WARNING: Configuration applied with commit confirmed {commit_confirmed_minutes} minutes.\n"
                            f"The device {hostname} will automatically roll back in {commit_confirmed_minutes} minutes\n"
                            f"if no commit is received. To make the changes permanent, run:\n"
                            f"  python {__file__} --commit {router_ip}\n"
                            f"{'*'*80}\n"
                        )
                        # Set device to None to prevent disconnection
                        device = None
                    results.append(result)
                    
                    if success and manual_commit_required:
                        # The success message is already logged by send_config_commands
                        pass
                    elif success:
                        self.logger.info("Configuration applied successfully")
                    else:
                        self.logger.error(f"Failed to apply configuration: {output}")
            
            # Disconnect from device
            if device:
                device.disconnect()
        
        return results
    
    def commit_changes(self, router_ip, username=None, password=None, port=22):
        """Commit pending configuration changes on a router.
        
        Args:
            router_ip (str): IP address of the router
            username (str, optional): Username for authentication
            password (str, optional): Password for authentication
            port (int, optional): SSH port. Defaults to 22.
            
        Returns:
            tuple: (success, output)
        """
        device = JuniperConfigurator(
            host=router_ip,
            username=username or input(f"Enter username for {router_ip}: "),
            password=password,
            port=port
        )
        
        if not device.connect():
            self.logger.error(f"Failed to connect to {router_ip}")
            return False, "Connection failed"
        
        try:
            success, output = device.commit_changes()
            return success, output
        finally:
            device.disconnect()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate and optionally apply BGP prefix list configurations to Juniper devices.'
    )
    
    parser.add_argument(
        '-c', '--config',
        default=Path(__file__).parent.parent / 'configs' / 'prefix_policies.yaml',
        help='Path to the YAML configuration file (default: configs/prefix_policies.yaml)'
    )
    
    # Action group (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        '--apply',
        action='store_true',
        help='Apply configurations to devices with commit confirmed'
    )
    action_group.add_argument(
        '--commit',
        metavar='ROUTER_IP',
        nargs='?',
        const='all',
        help='Commit pending changes on the specified router (use "all" for all routers)'
    )
    
    # Optional arguments for apply action
    parser.add_argument(
        '--rollback-minutes',
        type=int,
        default=3,
        help='Minutes before automatic rollback (default: 3)'
    )
    
    # Optional arguments for commit action
    parser.add_argument(
        '--username',
        help='Username for authentication (will prompt if not provided)'
    )
    parser.add_argument(
        '--password',
        help='Password for authentication (will prompt if not provided)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=22,
        help='SSH port (default: 22)'
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_arguments()
    
    # Check if config file exists
    if not os.path.exists(args.config):
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)
    
    # Initialize the generator
    generator = BGPQ4Generator(args.config)
    
    # Handle commit action
    if args.commit:
        if args.commit.lower() == 'all':
            # Commit all routers in the config
            for router in generator.config.get('routers', []):
                router_ip = router.get('ip')
                if router_ip:
                    logger.info(f"Committing changes on {router.get('hostname', router_ip)}...")
                    success, output = generator.commit_changes(
                        router_ip=router_ip,
                        username=args.username,
                        password=args.password,
                        port=args.port
                    )
                    if success:
                        logger.info(f"Successfully committed changes on {router_ip}")
                    else:
                        logger.error(f"Failed to commit changes on {router_ip}: {output}")
        else:
            # Commit specific router
            logger.info(f"Committing changes on {args.commit}...")
            success, output = generator.commit_changes(
                router_ip=args.commit,
                username=args.username,
                password=args.password,
                port=args.port
            )
            if success:
                logger.info(f"Successfully committed changes on {args.commit}")
            else:
                logger.error(f"Failed to commit changes on {args.commit}: {output}")
    else:
        # Generate and optionally apply configurations
        logger.info(f"Using configuration file: {args.config}")
        results = generator.generate_configs(
            apply_config=args.apply,
            commit_confirmed_minutes=args.rollback_minutes
        )
        
        if args.apply and results:
            # Print summary of applied configurations
            success_count = sum(1 for r in results if r['success'])
            logger.info(f"\nConfiguration application summary:")
            logger.info(f"  - Total policies: {len(results)}")
            logger.info(f"  - Successfully applied: {success_count}")
            logger.info(f"  - Failed: {len(results) - success_count}")
            
            if success_count < len(results):
                logger.warning("Some configurations failed to apply. Check the logs for details.")
            
            logger.info("\nIMPORTANT: Remember to commit the changes within the rollback window")
            logger.info(f"to make them permanent. Use '--commit <router_ip>' to commit.")
        else:
            logger.info("Configuration generation complete!")
            if not args.apply:
                logger.info("To apply these configurations, run with the '--apply' flag.")

if __name__ == "__main__":
    main()

