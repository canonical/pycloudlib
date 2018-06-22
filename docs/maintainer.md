# Maintainer Notes

## Merge Checklist

TODO

## Release Checklist

1. Run all example tests

    Verify no regressions and all examples continue to work to ensure correct API calls.

    ```shell
    git checkout master
    make venv
    . venv/bin/activate
    make install
    ./example/*.py
    ```

    If there are any failures, stop and resolve.

2. Update `setup.py` with new release number

    Use modified version of [Semantic Versioning](https://semver.org/):

    - major release is for each new year (2019 --> 19.x, 2020 --> 20.x)
    - minor release for new features/functionality
    - patch release for bug fixes

    Some example scenarios are below

    ```text
    18.2.1 -> 18.2.2 for a bug fix
    18.2.1 -> 18.3 for a new feature
    18.2.1 -> 19.1 for a new year

    19.1 -> 19.1.1 for a bug fix
    19.1 -> 19.2 for a new feature
    19.1 -> 20.1 for a new year
    ```

3. Update docs/history.md with commits since last release

    Add the lines since last release to `docs/history.md` under a new heading for the new release

    ```shell
    git log --pretty=oneline --abbrev-commit
    ```

4. Build Docs

    Verify the docs and API pages still build. As well as any new pages.

    ```shell
    pushd docs
    make deps
    make build
    popd
    ```

5. Run tox

    ```shell
    tox
    ```

6. Push to PyPI

    ```shell
    make publish
    ```

7. Push to Git

    ```shell
    git commit -am "Release X.Y.Z"
    git push
    ```

8. Update Read The Docs

    ```shell
    curl -X POST -d "token=$API_TOKEN" https://readthedocs.org/api/v2/webhook/pycloudlib/40086/
    ```
