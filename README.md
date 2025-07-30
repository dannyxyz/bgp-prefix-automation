# BGP Prefix List Automation

[![Python Version](https://img.shields.io/badge/python-3.6%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Automate the generation and deployment of Juniper BGP prefix lists using `bgpq4` based on YAML-defined router and policy configurations. This tool streamlines network automation by providing a simple, yet powerful way to manage prefix lists across multiple Juniper devices.

## ✨ Features

- **YAML-based Configuration**: Define router and policy configurations in a simple, readable format
- **Multi-RIR Support**: Works with AFRINIC, RIPE, and other RIRs
- **Safe Deployment**: Utilizes Juniper's commit confirmed for risk-free deployments
- **Flexible Policy Management**: Support for multiple policies per router
- **Comprehensive Logging**: Detailed logs for auditing and troubleshooting
- **Environment Variable Support**: Secure credential management
- **Dry Run Capability**: Preview changes before applying

## 📋 Prerequisites

- Python 3.6 or higher
- `bgpq4` installed and in system PATH
- Network connectivity to target Juniper devices

## 🚀 Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/bgp-prefix-automation.git
   cd bgp-prefix-automation
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your environment**:
   ```bash
   # Linux/Mac
   export USERNAME=your_juniper_username
   export PASSWORD=your_juniper_password
   
   # Windows
   set USERNAME=your_juniper_username
   set PASSWORD=your_juniper_password
   ```

4. **Edit the configuration**:
   Update `configs/prefix_policies.yaml` with your router and policy details.

5. **Generate and apply configurations**:
   ```bash
   python scripts/bgpq4_netmiko.py --apply
   ```

## 🛠️ Configuration

### Example `prefix_policies.yaml`

```yaml
routers:
  - hostname: edge-router-01
    ip: 192.168.1.1
    policies:
      - name: "CUSTOMER-A"
        as_set: "AS12345"
        description: "Customer A Routes"
        max_prefix_length: 24
        rir: "RIPE"
      
      - name: "PEERING-PARTNERS"
        as_set: "AS-EXAMPLE"
        description: "Peering Partner Routes"
        max_prefix_length: 24
        rir: "RADB"

global:
  default_rir: "RIPE"
  default_max_prefix_length: 24
  log_level: "INFO"
```

## 📚 Usage

### Generate Configurations (Dry Run)
```bash
python scripts/bgpq4_netmiko.py
```

### Apply Configurations with 3-minute Rollback
```bash
python scripts/bgpq4_netmiko.py --apply
```

### Commit Pending Changes
```bash
# Commit changes on a specific router
python scripts/bgpq4_netmiko.py --commit 192.168.1.1

# Commit changes on all routers
python scripts/bgpq4_netmiko.py --commit all
```

### Full Options
```
usage: bgpq4_netmiko.py [-h] [-c CONFIG] [--apply] [--commit [ROUTER_IP]] 
                       [--rollback-minutes MINUTES] [--username USERNAME] 
                       [--password PASSWORD] [--port PORT]

Generate and apply BGP prefix list configurations to Juniper devices.

optional arguments:
  -h, --help            show this help message and exit
  -c, --config CONFIG   Path to YAML config (default: configs/prefix_policies.yaml)
  --apply               Apply configurations with commit confirmed
  --commit [ROUTER_IP]  Commit pending changes (use 'all' for all routers)
  --rollback-minutes N  Minutes before auto-rollback (default: 3)
  --username USERNAME   Username for authentication
  --password PASSWORD   Password for authentication
  --port PORT           SSH port (default: 22)
```

## 🏗️ Project Structure

```
bgp-prefix-automation/
├── configs/
│   ├── generated/          # Generated configs
│   └── prefix_policies.yaml  # Main configuration
├── logs/                   # Log files
├── scripts/
│   ├── bgpq4_netmiko.py    # Main script
│   └── juniper_configurator.py  # Juniper device handling
├── tests/                  # Test files
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

## 🔒 Security Best Practices

1. **Never commit sensitive data** to version control
2. Use **environment variables** for credentials
3. Restrict **file permissions** on configuration files
4. Regularly **rotate credentials**
5. Use **SSH keys** instead of passwords when possible

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [bgpq4](https://github.com/bgp/bgpq4) - BGP prefix list generation
- [Netmiko](https://github.com/ktbyers/netmiko) - Network device automation
- [PyYAML](https://pyyaml.org/) - YAML configuration handling

## 📧 Contact

For questions or support, please open an issue on GitHub.

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

