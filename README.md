# Playlite

A native Linux game library for organising games, downloading metadata and artwork, and launching games through configurable play actions.

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
2. Choose **Manual** or an installed integration on the **Installation** tab.
3. Review the installation details, metadata, and images, then **Save**.

Select a game and press **Play**. Right-click a game and choose **Edit…** to change its details. Play actions on the Installation tab define how the game launches; multiple actions open a chooser when you press Play. Compatible integrations can also detect running games and record playtime.

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
Steam and VPN stay active for the Playlite session; game launches pause the VM
when downloads are idle, and game detection resumes it after exit. Closing
Playlite shuts down the VM normally. The installer and bridge are maintained in the
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
