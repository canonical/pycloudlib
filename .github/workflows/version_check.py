import sys

def compare_versions(old_version, new_version):
    if old_version >= new_version:
        return f"Version {old_version} must be incremented."
    if not re.match(r"\d!\d+.\d+.\d+", new_version.public):
        return f"Version requires <epoch>!<major>.<minor>.<patch>. Found: {new_version}"
    major_release = new_version.major > old_version.major
    minor_release = new_version.minor > old_version.minor
    micro_release = new_version.micro > old_version.micro
    if sum([major_release, minor_release, micro_release]) > 1:
        return "Only one digit can be incremented at a time.
    if major_release:
         if new_version.minor != 0 or new_version.micro != 0:
             return f"Major version increased. Expected minor and micro versions to be 0. Found: {new_version}"
    elif minor_release and new_version.micro != 0:
             return f"Minor version increased. Expected micro version to be 0. Found {new_version}"

    return f"Valid version: {new_version}"

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python version_check.py <old_version> <new_version>")
        sys.exit(1)
    
    result = compare_versions(version.parse(sys.argv[1]), version.parse(sys.argv[2]))
    print(result)
    if result != "Version bump is sane.":
        sys.exit(1)  # Exit with code 1 to indicate failure
