# Playlite

A native Linux game library for organising games, downloading metadata and artwork, and launching games through configurable play actions.

## Install

Playlite runs on Linux and requires Python 3.10 or later.

Download **install.sh** from the [latest release](https://github.com/swolfgang-dev/Playlite/releases/latest), then run it from your download folder:

```sh
bash install.sh
```

The installer sets up dependencies automatically. Launch **Playlite** from your applications menu, or run `~/.local/bin/playlite`.

To update, close Playlite and run the latest installer again. Your library and settings are retained. GitHub CLI and a GitHub login are not required for public releases.

## Add and play games

1. Open the menu from the Playlite logo and choose **Add Game…**.
2. Choose **Manual** or an installed integration on the **Installation** tab.
3. Review the installation details, metadata, and images, then **Save**.

Select a game and press **Play**. Right-click a game and choose **Edit…** to change its details. Play actions on the Installation tab define how the game launches; multiple actions open a chooser when you press Play. Compatible integrations can also detect running games and record playtime.

Use the toolbar to search, sort, filter, and switch between list and grid views. The list also supports a compact view.

## Plugins

Manual installation is built in. Other features are installed separately through **Settings → Plugins → Available**.

- Select plugins and click **Install selected**. Use Ctrl or Shift to select several.
- The available list loads at startup. Click **Update list** to refresh it.
- Reinstall a plugin to get its latest published version.
- Remove plugins through **Installed → Delete selected**; game entries are retained.
- Restart Playlite after installing, updating, or deleting plugins.

Plugins extend Playlite with features such as game integrations, metadata providers, and themes. Configure installed plugins in their sections under Settings → Plugins. Consult each plugin’s documentation for its requirements and setup.

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
