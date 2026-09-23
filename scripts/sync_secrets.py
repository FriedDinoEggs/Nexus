#!/usr/bin/env python3
"""GCP Secret Manager Synchronization Script for Nexus (Production Environment)

Supported subcommands:
  - pull:   Fetch GCP secrets, merge with base env configs, and package into .env.prod
  - verify: Check status and accessibility of all required secrets on GCP
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional

try:
    from google.api_core.exceptions import NotFound, PermissionDenied
    from google.cloud import secretmanager
except ImportError:
    print(
        "Error: 'google-cloud-secret-manager' is required. Run 'uv sync' or install it.",
        file=sys.stderr,
    )
    sys.exit(1)

# Default GCP Project ID (can be overridden via GCP_PROJECT_ID env var or --project-id flag)
DEFAULT_PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'nexus-484609')

# Mapping of Local Environment Variable Name -> GCP Secret ID (Case-sensitive)
SECRET_MAPPINGS: Dict[str, str] = {
    'NEXUS_SECRET_KEY': 'NEXUS_SECRET_KEY',
    'NEXUS_DB_PWD': 'NEXUS_DB_PWD',
    'REDIS_PASSWORD': 'REDIS_PASSWORD',
    'R2_ACCESS_KEY': 'R2_ACCESS_KEY',
    'R2_SECRET_KEY': 'R2_SECRET_KEY',
    'MAILTRAP_KEY': 'MAILTRAP_KEY',
    'GOOGLE_CLIENT_SECRET_JSON': 'GOOGLE_CLIENT_SECRET_JSON',
    'POSTGRES_EXPORTER_PASSWORD': 'POSTGRES_EXPORTER_PASSWORD',
    'GRAFANA_ADMIN_PASSWORD': 'GRAFANA_ADMIN_PASSWORD',
}

# Required non-secret production configuration keys that MUST be supplied by base env
REQUIRED_NON_SECRET_KEYS = [
    'NEXUS_DB_NAME',
    'NEXUS_DB_USER',
    'NEXUS_DB_HOST',
    'NEXUS_DB_PORT',
    'PROD_ALLOW_HOST',
    'REDIS_HOST',
    'REDIS_PORT',
    'REDIS_DB',
    'R2_API',
    'R2_BUCKET_NAME',
    'MAILTRAP_DOMAIN',
    'MAILTRAP_INBOX_ID',
    'GOOGLE_OAUTH_CLIENT_ID',
    'GRAFANA_ADMIN_USER',
]


def parse_env_file(filepath: Path) -> Dict[str, str]:
    """Parse a simple KEY=VALUE .env file."""
    env: Dict[str, str] = {}
    if not filepath.exists():
        return env

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                env[key] = val
    return env


def get_client() -> secretmanager.SecretManagerServiceClient:
    """Initialize GCP Secret Manager Client with auto-detection of credentials."""
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        candidate_keys = [
            Path('nexus-secret-reader.json'),
            Path('secret-reader.json'),
        ]
        for key_path in candidate_keys:
            if key_path.exists():
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(key_path.resolve())
                break

    try:
        return secretmanager.SecretManagerServiceClient()
    except Exception as e:
        print(f'[ERROR] Failed to initialize SecretManagerServiceClient: {e}', file=sys.stderr)
        print(
            "\nTip: For local machines, run: 'gcloud auth application-default login'\n"
            '     Or set GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json\n',
            file=sys.stderr,
        )
        sys.exit(1)


def fetch_secret(
    client: secretmanager.SecretManagerServiceClient,
    project_id: str,
    secret_id: str,
    env_var: str,
) -> str:
    """Fetch a single secret version payload from GCP."""
    name = f'projects/{project_id}/secrets/{secret_id}/versions/latest'
    response = client.access_secret_version(name=name)
    payload = response.payload.data.decode('utf-8').strip()
    if not payload:
        raise ValueError(f'Secret value for {env_var} is empty')
    print(f'  ✓ Fetched: {secret_id} -> {env_var}')
    return payload


def fetch_all_gcp_secrets(
    client: secretmanager.SecretManagerServiceClient,
    project_id: str,
) -> Dict[str, str]:
    """Fetch and strictly validate all secrets from GCP."""
    fetched: Dict[str, str] = {}
    failed: list = []

    for env_var, secret_id in SECRET_MAPPINGS.items():
        try:
            fetched[env_var] = fetch_secret(client, project_id, secret_id, env_var)
        except NotFound:
            print(f'  ✗ Not Found: {secret_id} (Expected for {env_var})', file=sys.stderr)
            failed.append((secret_id, 'Secret not found on GCP'))
        except PermissionDenied:
            print(f'  ✗ Permission Denied: {secret_id}', file=sys.stderr)
            failed.append((secret_id, 'Permission denied'))
        except Exception as e:
            print(f'  ✗ Error accessing {secret_id}: {e}', file=sys.stderr)
            failed.append((secret_id, str(e)))

    if failed:
        print(
            f'\n[CRITICAL ERROR] Failed to retrieve {len(failed)} required secret(s) from GCP:',
            file=sys.stderr,
        )
        for sid, reason in failed:
            print(f'  - {sid}: {reason}', file=sys.stderr)
        print('\nProduction deployment ABORTED! All secrets must exist on GCP.', file=sys.stderr)
        sys.exit(1)

    return fetched


def load_and_validate_base_env(base_env_path: Optional[Path]) -> Dict[str, str]:
    """Validate all required non-secret configurations from base env."""
    if not base_env_path or not base_env_path.exists():
        print(
            f"\n[CRITICAL ERROR] Base configuration file '{base_env_path}' not found!",
            file=sys.stderr,
        )
        print('Production deployment ABORTED!', file=sys.stderr)
        sys.exit(1)

    base_env = parse_env_file(base_env_path)
    missing = [k for k in REQUIRED_NON_SECRET_KEYS if not base_env.get(k)]
    if missing:
        print(
            f'\n[CRITICAL ERROR] Missing {len(missing)} required configuration(s) in '
            f'{base_env_path}:',
            file=sys.stderr,
        )
        for k in missing:
            print(f'  - {k} is missing or empty', file=sys.stderr)
        print(
            '\nProduction deployment ABORTED! No fake defaults allowed in production.',
            file=sys.stderr,
        )
        sys.exit(1)

    return base_env


def assemble_final_env(base_env: Dict[str, str], fetched_secrets: Dict[str, str]) -> Dict[str, str]:
    """Assemble final production environment dictionary."""
    final_env = {k: v for k, v in base_env.items() if k not in SECRET_MAPPINGS}
    final_env.update(fetched_secrets)
    final_env['DEBUG'] = 'False'
    final_env['ALLOW_HOST'] = final_env['PROD_ALLOW_HOST']
    return final_env


def write_env_file(output_path: Path, project_id: str, env_vars: Dict[str, str]) -> None:
    """Write out .env.prod with restricted permissions."""
    lines = []

    for env_var in sorted(SECRET_MAPPINGS.keys()):
        val = env_vars.get(env_var, '').replace('\n', '\\n')
        lines.append(f"{env_var}='{val}'")

    lines.append('')
    lines.append('# --- Production Environment Configurations (from .env) ---')
    for k in sorted(env_vars.keys()):
        if k not in SECRET_MAPPINGS:
            lines.append(f'{k}={env_vars[k]}')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    try:
        os.chmod(output_path, 0o644)
    except OSError:
        pass

    print(f'\n[SUCCESS] Production package written to: {output_path}')
    print('          File permissions set to 644 (rw-------).')


def pull_secrets(project_id: str, output_path: Path, base_env_path: Optional[Path]) -> None:
    """Pull secrets from GCP and package with base configs into .env.prod."""
    print(f'[INFO] Connecting to GCP Secret Manager (Project: {project_id})...')
    client = get_client()
    fetched_secrets = fetch_all_gcp_secrets(client, project_id)
    base_env = load_and_validate_base_env(base_env_path)
    final_env = assemble_final_env(base_env, fetched_secrets)
    write_env_file(output_path, project_id, final_env)


def verify_secrets(project_id: str) -> None:
    """Verify existence and access to all mapped secrets on GCP."""
    print(f'[INFO] Verifying secrets in project: {project_id}\n')
    client = get_client()

    print(f'{"Secret ID":<40} {"Status":<12} {"Description"}')
    print('-' * 75)

    all_ok = True
    for env_var, secret_id in SECRET_MAPPINGS.items():
        name = f'projects/{project_id}/secrets/{secret_id}/versions/latest'
        try:
            resp = client.access_secret_version(name=name)
            val_len = len(resp.payload.data)
            print(f'{secret_id:<40} {"[OK]":<12} ({env_var}, {val_len} bytes)')
        except NotFound:
            print(f'{secret_id:<40} {"[MISSING]":<12} ({env_var})')
            all_ok = False
        except PermissionDenied:
            print(f'{secret_id:<40} {"[NO ACCESS]":<12} (Permission Denied)')
            all_ok = False
        except Exception as e:
            print(f'{secret_id:<40} {"[ERROR]":<12} ({e})')
            all_ok = False

    print('-' * 75)
    if all_ok:
        print('\nAll required secrets are accessible in GCP Secret Manager!')
    else:
        print(
            '\nSome secrets are missing or inaccessible. Please check GCP Secret Manager console.',
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Nexus GCP Secret Manager Synchronization Tool',
    )
    parser.add_argument(
        '--project-id',
        default=DEFAULT_PROJECT_ID,
        help=f'GCP Project ID (default: {DEFAULT_PROJECT_ID})',
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    # pull
    pull_p = subparsers.add_parser('pull', help='Pull secrets from GCP and package into .env.prod')
    pull_p.add_argument(
        '--output',
        default='.env.prod',
        type=Path,
        help='Target output file (default: .env.prod)',
    )
    pull_p.add_argument(
        '--base-env',
        default='.env',
        type=Path,
        help='Base .env to supply non-secret configs (default: .env)',
    )

    # verify
    subparsers.add_parser('verify', help='Verify secret accessibility on GCP')

    args = parser.parse_args()

    if args.command == 'pull':
        pull_secrets(args.project_id, args.output, args.base_env)
    elif args.command == 'verify':
        verify_secrets(args.project_id)


if __name__ == '__main__':
    main()
