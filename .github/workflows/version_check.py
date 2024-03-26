import sys

def compare_versions(old_version, new_version):
    if old_version == new_version:
        return "Version must be incremented."

    old_parts = [int(part) for part in old_version.split('!')[1].split('.')]
    new_parts = [int(part) for part in new_version.split('!')[1].split('.')]

    if len(old_parts) != 3 or len(new_parts) != 3:
        return "Versions must have three parts: major, minor, patch."

    for i in range(3):
        if new_parts[i] < old_parts[i]:
            return "New version cannot be lower than old version."
        elif new_parts[i] > old_parts[i]:
            if any(new_parts[j] != 0 for j in range(i+1, 3)):
                return "Digits following the increased digit must be set to 0."
            if any(new_parts[k] > old_parts[k] for k in range(i+1, 3)):
                return "Only one digit can be incremented at a time."
            break

    return "Version bump is sane."

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python version_check.py <old_version> <new_version>")
        sys.exit(1)
    
    result = compare_versions(sys.argv[1], sys.argv[2])
    print(result)
    if result != "Version bump is sane.":
        sys.exit(1)  # Exit with code 1 to indicate failure
