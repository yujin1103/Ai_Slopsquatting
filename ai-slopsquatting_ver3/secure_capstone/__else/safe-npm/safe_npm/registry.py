import requests
from safe_npm.models import PackageInfo


REGISTRY_BASE = "https://registry.npmjs.org"


def fetch_package_info(package_name: str) -> PackageInfo:
    url = f"{REGISTRY_BASE}/{package_name}"
    response = requests.get(url, timeout=10)

    if response.status_code == 404:
        return PackageInfo(name=package_name, exists=False)

    response.raise_for_status()
    data = response.json()

    dist_tags = data.get("dist-tags", {})
    latest_version = dist_tags.get("latest")
    version_data = data.get("versions", {}).get(latest_version, {}) if latest_version else {}

    time_info = data.get("time", {})
    published_at = time_info.get(latest_version) if latest_version else None

    repository = version_data.get("repository")
    if isinstance(repository, dict):
        repository_url = repository.get("url")
    else:
        repository_url = repository

    scripts = version_data.get("scripts", {}) or {}

    return PackageInfo(
        name=package_name,
        exists=True,
        latest_version=latest_version,
        published_at=published_at,
        repository_url=repository_url,
        homepage=version_data.get("homepage"),
        scripts=scripts,
        raw=data,
    )