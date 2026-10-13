# Publishing this repository on GitHub

This checkout is prepared for a public **source repository**. It includes source,
tests, scientific model documentation, five example projects, two screenshots,
an MIT license, contributor guidance, issue/PR templates, and GitHub Actions checks.
It does not include a virtual environment or prebuilt desktop installers.
The public repository is [aalto-ema/surfaces](https://github.com/aalto-ema/surfaces).

## Before the first upload

1. Inspect `git status --short` and the staged diff. The allowlisted source files,
   examples, and screenshots should be present. Environments, caches, build outputs,
   logs, credentials, and personal project files belong outside the upload.
2. Review the two README PNGs. They were captured from app windows and public examples,
   without unrelated desktop content. Keep their relative paths and filenames intact.
3. The MIT notice currently credits **Surfaces contributors**. Adjust that attribution
   if the project owner wants a different public copyright notice.
4. Create an **empty** public repository on GitHub, without auto-generating a second
   README/license. Set its name as desired; the app's display name is Surfaces.
5. Commit the prepared files using your own Git author identity. Add the remote URL
   shown by GitHub and push `main`.

If starting from an uninitialized copy, the commands are:

```sh
git init -b main
git add .
git diff --cached --stat
git commit -m "Initial public release of Surfaces"
```

For this repository, configure the remote and push with:

```sh
git remote add origin https://github.com/aalto-ema/surfaces.git
git push -u origin main
```

Skip adding the remote if `origin` is already configured correctly.

## After the first push

- Check that README images display and example/download links work.
- Let the **Checks** workflow run. It configures scientific/export/Qt tests on
  Linux, macOS, and Windows, plus a wheel/source build. Local validation does not
  replace seeing the first hosted CI result.
- Keep the repository and issue URLs in `pyproject.toml` current if the repository moves.
- Add a GitHub release/tag when appropriate. A source release is separate from
  uploading to PyPI or building signed desktop installers; neither is automated here.

## Distribution checks

With build tooling installed:

```sh
python -m pip install build
python -m build
```

The wheel contains the Python application and license/metadata. The source archive
also contains the root launcher, README images, docs, examples, tests, and contributor
files. Both exclude local environments, caches, and personal output directories.
Run packaging checks after changing the manifest or metadata.

## Ongoing maintenance

Update `CHANGELOG.md` with notable user-visible changes. Regenerate screenshots after
relevant UI changes using `python tools/capture_screenshots.py`. Keep the runtime
compound catalog and guide consistent. Use scientific references for new models and
state their assumptions. The CI workflow does not publish, deploy, or need repository
write permissions.
