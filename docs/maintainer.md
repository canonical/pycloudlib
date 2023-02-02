# Maintainer Notes

## Release Checklist

### Run tox

```shell
tox
```

### Update `VERSION` file with new release number

Use [Semantic Versioning](https://semver.org/):

- major release is for breaking changes
- minor release for new features/functionality
- patch release for bug fixes

Some example scenarios are below

```text
1.1.1 -> 1.1.2 for a bug fix
1.1.1 -> 1.2.0 for a new feature
1.1.1 -> 2.1.0 for a breaking change
```

### Push to Github

```shell
git commit -am "Commit message"
git push
```

### Submit Pull Request on Github

Use the web UI or one of the supported CLI tools
