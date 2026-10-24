# Playlite

A native Linux game library for organising games, downloading metadata and artwork, and launching games through Lutris. Lutris is required, and every game must be associated with a Lutris entry. Manual launching is no longer supported.

## Install

Playlite runs on Linux and requires Python 3.10 or later.

Download **install.sh** from the [latest release](https://github.com/swolfgang-dev/Playlite/releases/latest), then run it from your download folder:

```sh
bash install.sh
```

The installer sets up dependencies automatically. Launch **Playlite** from your applications menu, or run `~/.local/bin/playlite`.

On first launch, **Get started** lets you choose library and tray preferences and install optional plugins. Plugins can open their own setup after installation. These preferences remain available in **Settings → General**, and plugins can be managed in **Settings → Plugins**. Newly installed plugins become available after restarting Playlite. Each profile keeps its own setup status.

To update, use **Settings → General → Updates → Check for updates**, then **Install update and restart**. The installed app closes, runs the verified release installer, and reopens on success. If installation fails, inspect `~/.local/share/playlite/update.log` (or the equivalent custom XDG data path). Repo builds only check releases and must be updated through Git. You can also close Playlite and run the latest installer again. Your library and settings are retained. GitHub CLI and a GitHub login are not required for public releases.

## Uninstall

Close the installed Playlite, then preview removal:

```sh
bash ~/.local/share/playlite/uninstall.sh --dry-run
```

Remove the application and its tracked plugins:

```sh
bash ~/.local/share/playlite/uninstall.sh
```

The script asks separately whether to keep user settings and installed plugins, defaulting to **Yes** for both. For unattended removal, use `--keep-settings` or `--remove-settings`, and `--keep-plugins` or `--remove-plugins` (plugins are removed by default in unattended runs). Removing settings clears known Playlite and plugin preferences while keeping your library, external games, private Steam data, and wallet credentials. Individual plugin removal offers the same checked-by-default option; settings for unknown third-party plugins are retained. To also remove known application data, owned private Steam data/image, and the downloader’s saved credentials, use:

```sh
bash ~/.local/share/playlite/uninstall.sh --purge-data --purge-secrets --remove-steam-image
```

Exported game folders, manually added untracked files/plugins, the repo version, Docker, and shared system packages are retained. Resources without ownership records are preserved. Custom `XDG_DATA_HOME` installs store the uninstaller under `$XDG_DATA_HOME/playlite/`; run it with the same environment used to install.

## Add and play games

1. Open the menu from the Playlite logo and choose **Add Game…**.
2. Import a Lutris entry, add a Windows executable, or select an installed Steam game.
3. Review the installation details, metadata, and images, then **Save**.

Use **Add Game** to import an existing Lutris entry or choose **Add from executable…** to create a Wine entry in Lutris. The executable picker starts in the default installation folder from Settings. The Wine prefix defaults to the configured prefix parent folder plus a slug generated from the game folder, including camel-case word boundaries. You can review and change the prefix before saving. **Edit → Installation → Add action → Add from executable…** adds another Lutris entry when you save the game; cancelling leaves Lutris unchanged.

The executable dialog also offers an optional **Steam association**: enter an app ID or use **Choose Steam game…**. The picker lists installed games and can search the Steam catalogue directly; Steam Metadata is optional. Existing game metadata prefills the ID; you can change or clear it. Associated executable entries keep the Wine runner and prefix while using the Steam-based Lutris ID scheme.

Use **Add Game → Add Steam game…** or **Add action → Add Steam game…** to select an installed Steam game. Only games with Steam’s installed flag and an existing installation folder are listed, including games in additional libraries. New entries without a Steam association receive a random seven-digit Lutris ID ending in `0`. Adding a Steam entry or saving a Steam metadata ID migrates matching random entries to Steam-based IDs and updates Playlite action links and Lutris references. Matching uses the game’s associated entries and installation folder, preserving the executable and Wine prefix.

New Steam-linked Lutris IDs use the app ID followed by the first free two-digit entry number (`01`–`99`), matching the former plugin. Executable actions inherit the game’s Steam metadata ID for this allocation when available. This creates a Lutris Steam-runner entry containing the app ID; launches still go through Lutris. Steam files are read-only, and existing Lutris entries are not overwritten.

To import an existing entry, Choose your Lutris library, search its entries, and select **Import selected**. Already imported entries are hidden; importing does not change Lutris.

Select a game and press **Play** to launch its selected Lutris entry. In **Edit → Installation**, add or change play actions by choosing existing Lutris entries. Launch settings are managed in Lutris. Right-click a game and choose **Edit…** to change its details. Play actions on the Installation tab define how the game launches; multiple actions open a chooser when you press Play. Compatible integrations can also detect running games and record playtime.

Use the toolbar to search, sort, filter, and switch between list and grid views. Filter dropdowns use checkboxes: select multiple values to match any of them, choose **None** for missing metadata, or **All** to clear that filter. Different filters combine. **Sources** lists the integrations attached to each game’s play actions, such as Steam or Lutris; a game can match multiple sources. The list also supports a compact view.

## Plugins

Manual installation is built in. Other features are installed separately through **Settings → Plugins → Available**.

- Select plugins and click **Install selected**. Use Ctrl or Shift to select several.
- The available list loads at startup. Click **Update list** to refresh it.
- Reinstall a plugin to get its latest published version.
- Remove plugins through **Installed → Delete selected**; game entries are retained.
- Restart Playlite after installing, updating, or deleting plugins.

Plugins extend Playlite with features such as game integrations, metadata providers, and themes. Configure installed plugins in their sections under Settings → Plugins. Consult each plugin’s documentation for its requirements and setup.

With Steam Downloader installed, open **Playlite menu → Steam Downloader…**.
Fresh plugin installation opens its setup wizard. Reopen it through
**Settings → Plugins → Steam Downloader → VM setup…**; opening the downloader
does not start setup. The wizard chooses the shared game folder, creates the VM, guides NordVPN
sign-in, and installs Steam and LuaTools/LuaMoon. Sign into Steam and a provider
inside the VM, then verify setup to continue to downloads. **Workshop…** and
**Advanced… → Setup and sign-in…** are inside the downloader. Settings also
provides **Delete VM…**, which removes private VM data and logins while
preserving shared games.

Steam downloads directly into the mounted game folder without copying. The VM,
Steam and VPN stay active while downloads or setup need them. The downloader
shuts down an idle VM after a minute without activity and starts it again when
needed. Closing Playlite shuts down the VM normally. The installer and bridge are maintained in the
[Steam Downloader plugin repository](https://github.com/swolfgang-dev/playlite-plugin-steam-depot-downloader).

## Metadata and artwork

With a compatible metadata or artwork provider installed, edit a game:

- **Metadata → Download metadata…** searches for game details and lets you review changes.
- **Images → Download images…** searches for icons, covers, headers, and backgrounds. Adjust the artwork, shape, and resolution filters as needed.

**Apply** fills the editor; **Save** keeps the changes. Available sources and any required credentials depend on the providers you have installed.

## Settings and data

Open **Settings** from the Playlite menu. General controls startup and window behaviour; Appearance controls themes, colours, blur, and panel transparency.

By default, Playlite stores its library, artwork, installed plugins, and interface settings under `~/.local/share/playlite`. The library is `library.json`, and interface preferences are in `ui.ini`. Back up this folder to preserve your library and artwork.

## Further information

The previous README is preserved in [README_REFERENCE.md](README_REFERENCE.md), including development notes, import instructions, plugin details, and implementation history.

Plugin manifests can declare dependencies on other plugins using `plugin_dependencies`:

```json
"plugin_dependencies": [
  {
    "id": "LutrisIntegration",
    "repository": "swolfgang-dev/playlite-plugin-lutris-integration",
    "minimum_version": "1.1.17"
  }
]
```

GitHub installation installs or updates required plugins first and reports dependencies in its progress output. Local archives require dependencies to be installed already. Disabled dependencies must be enabled explicitly. Circular dependencies and conflicting repository identities are rejected; plugins with unsatisfied dependencies are not loaded.

Use **Playlite menu → Background tasks…** to inspect downloads and supported plugin jobs, copy logs, cancel downloads, or retry available tasks. History survives restarts; unfinished work is marked interrupted. **Check library installations…** and the game Installation menu check explicit launch paths and readable Lutris Wine configurations. These checks do not verify Steam file hashes. Missing configured paths prevent launching until corrected.

Per-game commands are available in **Edit → Automation**. Enable automation and enter Bash commands before launch, after launch or after exit. Before-launch commands must succeed before the selected play action starts. Exit commands use the settings captured at launch, wait for after-launch work, and finish before plugin exit hooks such as save backup. External game sessions do not run these commands. Playlite must remain running and the integration must support game-exit detection for after-exit commands. Set a timeout; view output or cancel running commands through **Background tasks…**. Commands run on the host, including when the selected action uses a VM. Saving or cancelling the editor never executes a command.

Commands run in the selected action's installation folder when available and receive `PLAYLITE_GAME_NAME`, `PLAYLITE_GAME_ID`, `PLAYLITE_INSTALL_DIR`, `PLAYLITE_PREFIX` and `PLAYLITE_ACTION_NAME`. Use quoted variables for paths. To start a companion app without waiting for its window to close, append `&`; its cleanup can be handled by an after-exit command. Playlite does not automatically stop successfully started companion apps.

Dialog layouts share a 24-pixel outer margin, 16-pixel card padding, 12-pixel
form-row spacing, and 8-pixel action spacing. Plugin dialogs receive the same
layout conventions through the application style. Tall forms keep their action
footer outside the scrolling body. Settings → Plugins uses searchable navigation.

Background artwork is prepared at display resolution in a worker, preserving the
complete image. Resizing uses the same frame; game changes crossfade without a blank
intermediate background. Appearance → Keep text panels readable over artwork limits
partial game-panel transparency to 20%; switch it off to use the exact slider value.

## Isolated source review

Use a Python environment containing the project and plugin dependencies. In this
workspace the existing interpreter is `.dev/venv/bin/python`. From the core repo:

```sh
.dev/venv/bin/python tools/check_workspace.py
.dev/venv/bin/python tools/check_workspace.py playlite --pattern test_ui_layout.py --scale 2
.dev/venv/bin/python tools/run_isolated.py
```

The tools create disposable profiles under `/tmp`, including independent home,
configuration, library, cache, state, runtime and plugin directories. Fixtures come
from Git-tracked source files in sibling plugin repositories; live settings,
credentials and libraries are never copied. Profiles are removed on exit. No
dependencies are installed and the legacy development launcher is not invoked.
External operations in tests use mocks and temporary fixtures. The graphical
preview starts with an empty library; use fixture directories for manual review.
Profile separation does not sandbox arbitrary plugin code or external commands.

For an offscreen preview, run
`.dev/venv/bin/python tools/run_isolated.py --screenshot /tmp/playlite-preview.png`.
The screenshot remains at the requested path. For a core-only check or preview,
add `--core-only`. Unix socket tests require an environment that permits local
socket binding.
