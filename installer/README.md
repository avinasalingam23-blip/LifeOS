# LifeOS Windows installer

The installer wraps the **existing verified `dist/LifeOS` folder**. It does not run PyInstaller, change application source or copy a live profile.

## Install

1. Run `dist\installer\LifeOS-Setup.exe` from a normal Windows desktop session.
2. Approve the Windows UAC request for this local unsigned installer. Administrative permission is required for the default all-users installation.
3. Keep the default `Program Files\LifeOS` destination, or choose a dedicated application folder. Close LifeOS before upgrading an existing installation; setup does not force applications to close.
4. Choose whether to create a desktop shortcut; it is unchecked by default. A Start Menu group is created unless you choose not to create one.
5. Install, then launch from **Start > LifeOS**, the optional desktop shortcut, or the optional launch checkbox on the final page.

No separate Python installation is needed. Keep the original portable package if you want to continue using it separately. There is no installer download/release URL; this task creates only local output. The installer is unsigned; verify its SHA-256 against the adjacent `BUILD_INFO.json`. Another-machine/clean-VM testing is still outstanding.

## Data and uninstall

Normal SQLite storage is `%LOCALAPPDATA%\LifeOS\lifeos.sqlite3`. Logs and backups stay alongside the profile, **outside Program Files**. Setup does not initialize, copy, migrate or open the database. Each Windows user retains their own profile. If you deliberately use `LIFEOS_DATA_DIR` or `--data-dir`, choose another writable data directory outside the application installation.

Use **Windows Settings > Apps > Installed apps > LifeOS > Uninstall**. Inno Setup removes its managed program files, shortcuts and uninstall registration. There is no custom profile-deletion action and no recursive cleanup rule. Personal SQLite data, logs and backups remain. Files a user creates inside the application folder are not removed by a wildcard cleanup. Reinstallation should use the existing external profile when LifeOS is next launched.

## Build again without rebuilding the application

Obtain Inno Setup from its [official downloads page](https://jrsoftware.org/isdl.php), verify the publisher signature using the [official instructions](https://jrsoftware.org/isdl-verify.php), and use its compiler:

```powershell
powershell -ExecutionPolicy Bypass -File .\Build-Installer.ps1 -IsccPath "C:\Program Files\Inno Setup 7\ISCC.exe"
```

The current local compiler was obtained in official portable mode under ignored test output, with a valid Pyrsys B.V. signature. [Build-Installer.ps1](../Build-Installer.ps1) also discovers standard compiler locations; it does not download or install tools automatically. [The build helper](../tools/build_installer.py) audits the package, stages supplemental dependency notices, compiles [LifeOS.iss](LifeOS.iss), verifies the original package is unchanged and preserves previous installer output before promoting a new build to `dist/installer`.

The stable application ID supports future upgrades and the standard uninstall entry. The version comes from the existing project metadata. The original source now has the owner-authorized [MIT license](../LICENSE), Copyright (c) 2026 Avinash S; the existing binary was not regenerated to update its older review-note wording. Third-party terms and the partially resolved Python branding/marking item remain separate; see [the current review](../PUBLICATION_REVIEW.md).

## Verification scope

[tools/check_installer.py](../tools/check_installer.py) tests the **same installer** using its explicit `/CURRENTUSER` override, with program files confined to a new directory under `.test-artifacts`. It refuses an existing LifeOS installation, uses a unique Start Menu test group, preserves any pre-existing desktop shortcut and never opens the normal profile. It checks installed file hashes, shortcut targets, registration, both-theme/all-page frozen GUI workflows, ordinary launches, two install/uninstall cycles, external-profile persistence and preservation of an unmanaged file inside the test application folder.

This requires permission to launch GUI programs and briefly create/remove the test registration/shortcuts. The production default remains administrative installation in Program Files; the override does not establish that Windows UAC or all-users destinations were tested. Review the actual completed results in [PROJECT_STATUS.md](../PROJECT_STATUS.md). Do not run the checker against a real installation or reuse a previous result directory.

Manual checks still include the interactive UAC/Program Files installation, all-users shortcuts/uninstall on another Windows account, clean Windows VM/another-machine behavior and the remaining branding/marking review. The earlier standalone-Tcl warning is resolved: the existing delivered `ThirdParty-Notices/Python-LICENSE.txt` contains both version-matched Tcl/Tk notices verbatim. Its standalone filename is not required. No application/installer rebuild or repeated lifecycle test was needed for this content finding.
