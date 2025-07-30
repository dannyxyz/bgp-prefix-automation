# BGP Prefix List Automation

This tool automates the generation and deployment of Juniper prefix lists using bgpq4 based on router and policy configurations defined in YAML. It can generate configuration files and optionally apply them to Juniper devices using Netmiko with commit confirmed for safe deployment.

## Features

- Read router and policy configurations from YAML
- Generate prefix lists using bgpq4
- Convert output to Juniper set commands
- Support for multiple RIRs (AFRINIC, RIPE, etc.)
- Logging for auditing and debugging
- Direct deployment to Juniper devices using Netmiko
- Safe deployment with commit confirmed (10-minute rollback window)
- Manual commit process for production safety

## Prerequisites

- Python 3.6+
- bgpq4 installed and in PATH
- Required Python packages (install with `pip install -r requirements.txt`)
- Network connectivity to target Juniper devices (if using direct deployment)

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Install bgpq4 on your system

## Configuration

Edit `configs/prefix_policies.yaml` to define your routers and prefix policies.

## Usage

### Basic Usage (Generate Configs Only)

To generate configuration files without applying them:
```
python scripts/bgpq4_netmiko.py --config path/to/config.yaml
```

### Apply Configurations with Commit Confirmed

To generate and apply configurations with a 10-minute rollback window:
```
python scripts/bgpq4_netmiko.py --apply
```

### Commit Pending Changes

After applying configurations with `--apply`, you have 10 minutes to verify the changes before they are automatically rolled back. To make the changes permanent, run:

For a specific router:
```
python scripts/bgpq4_netmiko.py --commit 192.168.1.1
```

For all routers in the config:
```
python scripts/bgpq4_netmiko.py --commit all
```

### Command Line Options

```
usage: bgpq4_netmiko.py [-h] [-c CONFIG] [--apply] [--commit [ROUTER_IP]] [--rollback-minutes MINUTES]
                       [--username USERNAME] [--password PASSWORD] [--port PORT]

Generate and optionally apply BGP prefix list configurations to Juniper devices.

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Path to the YAML configuration file (default: configs/prefix_policies.yaml)
  --apply               Apply configurations to devices with commit confirmed
  --commit [ROUTER_IP]  Commit pending changes on the specified router (use "all" for all routers)
  --rollback-minutes MINUTES
                        Minutes before automatic rollback (default: 10)
  --username USERNAME   Username for authentication (will prompt if not provided)
  --password PASSWORD   Password for authentication (will prompt if not provided)
  --port PORT           SSH port (default: 22)
```

## Output

Generated configurations will be saved to `configs/generated/` with filenames in the format:
`{hostname}_{policy_name}_{timestamp}.conf`

Logs are written to `logs/bgpq4_automation.log`

## Example YAML Structure

```yaml
# Global defaults (can be overridden per policy)
global:
  default_rir: "AFRINIC"        # Default RIR (AFRINIC, RIPE, etc.)
  default_max_prefix_length: 24  # Default maximum prefix length
  log_level: "INFO"             # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

# List of routers to configure
routers:
  - hostname: router1.wiocc.net  # Router hostname (for reference and logging)
    ip: 192.168.1.1             # Router management IP
    username: admin             # (Optional) SSH username (will prompt if not provided)
    password: yourpassword      # (Optional) SSH password (not recommended, will prompt if not provided)
    port: 22                    # (Optional) SSH port (default: 22)
    
    # List of prefix policies to apply
    policies:
      - name: "WIOCC-ROUTES"    # Policy name (must be unique per router)
        as_set: "AS37439"       # AS number or AS-SET to generate prefix list from
        description: "WIOCC Core Routes"  # Optional description
        max_prefix_length: 24    # Maximum prefix length to accept
        rir: "AFRINIC"          # RIR to use (overrides global default)
```

## Important Notes

1. **Commit Confirmed Process**:
   - When using `--apply`, the tool will apply configurations with `commit confirmed 10`
   - You have 10 minutes to verify the changes on the router
   - To make changes permanent, run with `--commit` before the timeout
   - If no commit is received within 10 minutes, the router will automatically roll back

2. **Security**:
   - Avoid storing passwords in the YAML file
   - The tool will prompt for any missing credentials
   - Use SSH keys when possible for authentication

3. **Testing**:
   - Always test configurations in a non-production environment first
   - Review generated configurations before applying
   - The tool creates backups of previous configurations in the `configs/generated` directory

## License

This project is licensed under the MIT License - see the LICENSE file for details.

